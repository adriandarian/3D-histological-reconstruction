"""Build registered RGB, validity and tissue stacks plus static browser assets."""

import argparse
import json
import re
import tempfile

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .phantom import generate
from .contours import refine_exposed_tips
from .deformation import displacement_grids, pixel_grid, to_source


def load_series(folder, max_side):
    paths = [
        p
        for p in folder.iterdir()
        if p.suffix.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
    ]
    templates = {tuple(re.split(r"\d+", p.stem)) for p in paths}
    if len(templates) != 1:
        raise ValueError("Expected one series with the same filename pattern")
    tokens = [list(map(int, re.findall(r"\d+", p.stem))) for p in paths]
    varying = [j for j, values in enumerate(zip(*tokens)) if len(set(values)) > 1]
    if len(varying) != 1:
        raise ValueError("Expected exactly one varying numeric section index")
    indexed = [(numbers[varying[0]], p) for numbers, p in zip(tokens, paths)]
    indexed.sort()
    if len(indexed) < 2 or any(
        b != a + 1 for (a, _), (b, _) in zip(indexed, indexed[1:])
    ):
        raise ValueError(
            "Expected at least two consecutive, unique section numbers in one series"
        )
    shape = None
    for _, path in indexed:
        with Image.open(path) as image:
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError(f"Expected one image per file: {path}")
            image = ImageOps.exif_transpose(image).convert("RGB")
            if shape and image.size != shape:
                raise ValueError("Inconsistent source dimensions")
            shape = image.size
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            yield path.name, np.asarray(image), None


def ncc(a, b, valid=None):
    if valid is not None:
        a, b = a[valid], b[valid]
    if a.size == 0:
        return 0.0
    a, b = a - a.mean(), b - b.mean()
    denominator = np.sqrt(np.sum(a * a) * np.sum(b * b))
    return float(np.clip(np.sum(a * b) / denominator, -1, 1)) if denominator else 0.0


def warp(image, matrix, background, interpolation=cv2.INTER_LINEAR):
    h, w = image.shape[:2]
    return cv2.warpAffine(
        image,
        matrix[:2],
        (w, h),
        flags=interpolation,
        borderValue=background,
    )


def coarse_translation(moving, fixed, fixed_shift):
    """Match the central tissue field after suppressing cell-scale texture."""
    h, w = moving.shape
    small_size = (max(8, w // 4), max(8, h // 4))
    a, b = (
        cv2.resize(im, small_size, interpolation=cv2.INTER_AREA)
        for im in (moving, fixed)
    )
    sw, sh = small_size
    mx, my = max(1, sw // 5), max(1, sh // 5)
    template = a[my : sh - my, mx : sw - mx]
    if template.std() < 1 or b.std() < 1:
        return None
    scores = cv2.matchTemplate(b, template, cv2.TM_CCOEFF_NORMED)
    # Restrict the search to translations retaining at least 70% of the canvas.
    yy, xx = np.indices(scores.shape)
    dx = (xx - mx) * w / sw + fixed_shift[0]
    dy = (yy - my) * h / sh + fixed_shift[1]
    coverage = (1 - np.abs(dx) / w) * (1 - np.abs(dy) / h)
    scores[coverage < 0.70] = -1
    _, confidence, _, location = cv2.minMaxLoc(scores)
    if confidence < 0.35:
        return None
    return np.array([(location[0] - mx) * w / sw, (location[1] - my) * h / sh])


def overlap_translation(moving, fixed, fixed_shift):
    """Search all bounded coarse displacements using overlap-normalized correlation."""
    height, width = moving.shape
    size = (max(2, width // 4), max(2, height // 4))
    a, b = [
        cv2.resize(im, size, interpolation=cv2.INTER_AREA) for im in (moving, fixed)
    ]
    w, h = size
    mx, my = w // 4, h // 4
    dx, dy = np.meshgrid(np.arange(-mx, mx + 1), np.arange(-my, my + 1))

    # For each displacement, obtain moments on exactly the shared rectangle.
    def moments(image, x, y):
        integral = cv2.integral(image, sdepth=cv2.CV_64F)
        x0, x1 = np.maximum(0, x), np.minimum(w, w + x)
        y0, y1 = np.maximum(0, y), np.minimum(h, h + y)
        return integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]

    sa, sb = moments(a, -dx, -dy), moments(b, dx, dy)
    area = (w - abs(dx)) * (h - abs(dy))
    va = moments(a * a, -dx, -dy) - sa * sa / area
    vb = moments(b * b, dx, dy) - sb * sb / area
    cross = cv2.matchTemplate(np.pad(b, ((my, my), (mx, mx))), a, cv2.TM_CCORR)
    denom = np.sqrt(np.maximum(va, 0) * np.maximum(vb, 0))
    corr = np.divide(
        cross - sa * sb / area, denom, out=np.full_like(denom, -1), where=denom > 1
    )
    tx, ty = dx * width / w, dy * height / h
    coverage = (1 - abs(fixed_shift[0] + tx) / width) * (
        1 - abs(fixed_shift[1] + ty) / height
    )
    corr[coverage < 0.70] = -1
    peak = np.unravel_index(np.argmax(corr), corr.shape)
    if corr[peak] < 0.35:
        return None
    return np.array([tx[peak], ty[peak]])


def rigid_registration(gray, reference):
    """Register grayscale planes into the chosen reference frame and return adjacent-pair QA."""
    h, w = gray[0].shape
    mid = reference
    transforms = np.repeat(np.eye(3)[None], len(gray), axis=0)
    center = np.array([w / 2, h / 2, 1])
    window = cv2.createHanningWindow((w, h), cv2.CV_32F)
    valid_frame = np.ones((h, w), np.uint8)
    qa = [
        dict(beforeScore=None, score=None, status="reference", fixed=None)
        for _ in gray
    ]
    for i in [*range(mid - 1, -1, -1), *range(mid + 1, len(gray))]:
        fixed = i + 1 if i < mid else i - 1
        parent = transforms[fixed]
        offset = (parent @ center - center)[:2]
        delta, response = cv2.phaseCorrelate(gray[i].copy(), gray[fixed].copy(), window)
        before = ncc(gray[i], gray[fixed])
        candidates = []
        if response >= 0.05 and min(gray[i].std(), gray[fixed].std()) > 0:
            candidates.append(delta)
        coarse = coarse_translation(gray[i], gray[fixed], offset)
        if coarse is not None:
            candidates.append(coarse)
        overlap_shift = overlap_translation(gray[i], gray[fixed], offset)
        if overlap_shift is not None:
            candidates.append(overlap_shift)
        matrices = []
        for dx, dy in candidates:
            matrix = np.eye(3)
            matrix[:2, 2] = [dx, dy]
            matrices.append(matrix)
        seeds = dict.fromkeys(tuple(np.round(m[:2, 2])) for m in matrices)
        for dx, dy in seeds:
            # ECC maps template coordinates to input coordinates. Moving is the template.
            seed = np.float32([[1, 0, dx], [0, 1, dy]])
            try:
                _, rigid = cv2.findTransformECC(
                    gray[i],
                    gray[fixed],
                    seed,
                    cv2.MOTION_EUCLIDEAN,
                    (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-6),
                    None,
                    9,
                )
            except cv2.error as error:
                if error.code != cv2.Error.StsNoConv:
                    raise
            else:
                if abs(np.arctan2(rigid[1, 0], rigid[0, 0])) <= np.deg2rad(15):
                    matrices.append(np.vstack([rigid, [0, 0, 1]]))
        accepted = False
        score = before
        best_gain = 0.0
        transforms[i] = parent
        for matrix in matrices:
            travel = np.abs((matrix @ center - center)[:2])
            if not np.isfinite(matrix).all() or np.any(
                travel > 0.25 * np.array([w, h])
            ):
                continue
            total = parent @ matrix
            if warp(valid_frame, total, 0, cv2.INTER_NEAREST).mean() < 0.70:
                continue
            valid = warp(valid_frame, matrix, 0, cv2.INTER_NEAREST).astype(bool)
            candidate = ncc(warp(gray[i], matrix, 255), gray[fixed], valid)
            overlap_before = ncc(gray[i], gray[fixed], valid)
            gain = candidate - overlap_before
            # Prefer translation when a rotation only marginally improves correlation.
            margin = 0.01 if abs(matrix[1, 0]) > 1e-6 and accepted else 0.0
            if gain > best_gain + margin and candidate >= 0.20:
                before, score, best_gain = overlap_before, candidate, gain
                accepted = True
                transforms[i] = total
        qa[i] = dict(
            beforeScore=before,
            score=score,
            status="accepted" if accepted else "identity fallback",
            fixed=fixed,
        )
    return transforms, qa


def reconstruct(rows, out, name, kind, attribution, local=False):
    files, images, offsets = zip(*rows)
    h, w = images[0].shape[:2]
    gray = [cv2.cvtColor(im, cv2.COLOR_RGB2GRAY).astype(np.float32) for im in images]
    mid = len(images) // 2
    transforms, qa = rigid_registration(gray, mid)
    valid_frame = np.ones((h, w), np.uint8)
    sections, stack, masks, validity = [], [], [], []
    grids = None
    if local:
        rigid_images = [
            warp(im, m, 255).astype(np.uint8) for im, m in zip(gray, transforms)
        ]
        valid_images = [warp(valid_frame, m, 0, cv2.INTER_NEAREST) for m in transforms]
        he_channels = None
        if local in ("he", "he-contour"):
            he_channels = [
                [
                    warp(im[:, :, channel].astype(np.float32), m, 255).astype(np.uint8)
                    for im, m in zip(images, transforms)
                ]
                for channel in (0, 1)
            ]
        grids = displacement_grids(
            rigid_images, valid_images, mid, he_channels=he_channels
        )
        pixels = pixel_grid(w, h)
    for i, (im, matrix) in enumerate(zip(images, transforms)):
        registered = warp(im, matrix, (255, 255, 255))
        valid = warp(valid_frame, matrix, 0, cv2.INTER_NEAREST)
        if local:
            grid = grids[i]
            # Back off the local displacement if it would violate the retained-field limit.
            while np.any(grid):
                coords = to_source(pixels, matrix, grid, w, h)
                local_valid = cv2.remap(valid_frame, coords, None, cv2.INTER_NEAREST)
                if local_valid.mean() >= 0.70:
                    valid = local_valid
                    registered = cv2.remap(
                        im, coords, None, cv2.INTER_LINEAR, borderValue=(255, 255, 255)
                    )
                    break
                grid *= 0.5
                if np.max(np.abs(grid)) < 0.01:
                    grid.fill(0)
        stack.append(registered)
        validity.append(valid)
    if local == "he-contour":
        refine_exposed_tips(images, transforms, grids, stack, validity)
    for i, (im, matrix, registered, valid) in enumerate(
        zip(images, transforms, stack, validity)
    ):
        hsv = cv2.cvtColor(registered, cv2.COLOR_RGB2HSV)
        mask = (
            ((hsv[:, :, 1] > 18) & (hsv[:, :, 2] < 250)) | (hsv[:, :, 2] < 170)
        ) & valid.astype(bool)
        masks.append(mask)
        entry = dict(
            index=i,
            filename=files[i],
            shift=matrix[:2, 2].tolist(),
            transform=matrix[:2].tolist(),
            z_um=4 * i if kind == "synthetic" else None,
            **qa[i],
        )
        if local:
            entry["pullGrid"] = grids[i].tolist()
        for key, asset_pixels in (
            ("source", im),
            ("registered", registered),
            ("texture", np.dstack((registered, mask.astype(np.uint8) * 255))),
        ):
            entry[key] = f"{key}/{i:03}.png"
            dest = out / entry[key]
            dest.parent.mkdir(exist_ok=True)
            asset = Image.fromarray(asset_pixels)
            if key == "texture":
                asset.thumbnail((256, 256), Image.Resampling.LANCZOS)
            asset.save(dest)
        if offsets[i] is not None:
            entry["expectedShift"] = (np.array(offsets[mid]) - offsets[i]).tolist()
        sections.append(entry)
    np.savez_compressed(
        out / "volume.npz",
        rgb=np.stack(stack),
        tissue=np.stack(masks),
        valid=np.stack(validity),
    )
    manifest = dict(
        name=name,
        kind=kind,
        width=w,
        height=h,
        sections=sections,
        reference=mid,
        attribution=attribution,
        axes="zyxc",
        volume="volume.npz",
        pixel_size_um=1 if kind == "synthetic" else None,
        section_interval_um=4 if kind == "synthetic" else None,
        registration="Rigid ECC with smooth local flow correction"
        if local
        else "Adjacent translation search and rigid ECC refinement to middle section",
    )
    if local:
        manifest["localRefinement"] = "intensity" if local is True else local
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False), encoding="utf8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="One ordered series, one varying numeric field in filenames",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="New or empty export directory"
    )
    parser.add_argument("--max-side", type=int, default=640)
    parser.add_argument("--name")
    parser.add_argument("--attribution")
    parser.add_argument(
        "--local-refinement",
        nargs="?",
        choices=("intensity", "he", "he-contour"),
        const="intensity",
        help="Apply local refinement using intensity (default), H&E color channels, or H&E plus exposed-tip matching",
    )
    args = parser.parse_args()
    if args.max_side < 16:
        parser.error("--max-side must be at least 16")
    dest = args.output.resolve()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        parser.error(f"Choose a new or empty output directory: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = load_series(args.input, args.max_side) if args.input else generate()
    kind = "measured" if args.input else "synthetic"
    name = args.name or (args.input.name if args.input else "Synthetic gland phantom")
    attribution = args.attribution or (
        "User-supplied serial sections"
        if args.input
        else "Seeded synthetic H&E-like phantom"
    )
    with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
        stage = Path(temp) / "export"
        stage.mkdir()
        reconstruct(rows, stage, name, kind, attribution, args.local_refinement)
        # Publish the manifest last so readers only discover a complete stack.
        dest.mkdir(exist_ok=True)
        for asset in sorted(stage.rglob("*"), key=lambda p: p.name == "manifest.json"):
            target = dest / asset.relative_to(stage)
            if asset.is_dir():
                target.mkdir()
            else:
                target.parent.mkdir(exist_ok=True)
                asset.rename(target)
    print(dest / "manifest.json")


if __name__ == "__main__":
    main()
