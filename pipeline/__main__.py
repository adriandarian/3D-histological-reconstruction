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


def warp(image, shift, background, interpolation=cv2.INTER_LINEAR):
    h, w = image.shape[:2]
    return cv2.warpAffine(
        image,
        np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]),
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


def reconstruct(rows, out, name, kind, attribution):
    files, images, offsets = zip(*rows)
    h, w = images[0].shape[:2]
    gray = [cv2.cvtColor(im, cv2.COLOR_RGB2GRAY).astype(np.float32) for im in images]
    mid = len(images) // 2
    shifts = np.zeros((len(images), 2))
    window = cv2.createHanningWindow((w, h), cv2.CV_32F)
    valid_frame = np.ones((h, w), np.uint8)
    qa = [
        dict(beforeScore=None, score=None, status="reference", fixed=None)
        for _ in images
    ]
    for i in [*range(mid - 1, -1, -1), *range(mid + 1, len(images))]:
        fixed = i + 1 if i < mid else i - 1
        delta, response = cv2.phaseCorrelate(gray[i].copy(), gray[fixed].copy(), window)
        before = ncc(gray[i], gray[fixed])
        candidates = []
        if response >= 0.05 and min(gray[i].std(), gray[fixed].std()) > 0:
            candidates.append(delta)
        coarse = coarse_translation(gray[i], gray[fixed], shifts[fixed])
        if coarse is not None:
            candidates.append(coarse)
        size = np.array([w, h])
        accepted = False
        score = before
        best_gain = 0.0
        for translation in candidates:
            magnitude = np.abs(translation)
            total = np.abs(shifts[fixed] + translation)
            if not np.isfinite(total).all() or np.any(magnitude > 0.25 * size):
                continue
            if np.prod(np.maximum(0, 1 - total / size)) < 0.70:
                continue
            valid = warp(valid_frame, translation, 0, cv2.INTER_NEAREST).astype(bool)
            candidate = ncc(warp(gray[i], translation, 255), gray[fixed], valid)
            overlap_before = ncc(gray[i], gray[fixed], valid)
            gain = candidate - overlap_before
            if gain > best_gain and candidate >= 0.20:
                before, score, best_gain = overlap_before, candidate, gain
                accepted = True
                shifts[i] = translation
        shifts[i] += shifts[fixed]
        qa[i] = dict(
            beforeScore=before,
            score=score,
            status="accepted" if accepted else "identity fallback",
            fixed=fixed,
        )
    sections, stack, masks, validity = [], [], [], []
    for i, (im, shift) in enumerate(zip(images, shifts)):
        registered = warp(im, shift, (255, 255, 255))
        valid = warp(valid_frame, shift, 0, cv2.INTER_NEAREST)
        hsv = cv2.cvtColor(registered, cv2.COLOR_RGB2HSV)
        mask = (
            ((hsv[:, :, 1] > 18) & (hsv[:, :, 2] < 250)) | (hsv[:, :, 2] < 170)
        ) & valid.astype(bool)
        stack.append(registered)
        validity.append(valid)
        masks.append(mask)
        entry = dict(
            index=i,
            filename=files[i],
            shift=shift.tolist(),
            z_um=4 * i if kind == "synthetic" else None,
            **qa[i],
        )
        for key, pixels in (
            ("source", im),
            ("registered", registered),
            ("texture", np.dstack((registered, mask.astype(np.uint8) * 255))),
        ):
            entry[key] = f"{key}/{i:03}.png"
            dest = out / entry[key]
            dest.parent.mkdir(exist_ok=True)
            asset = Image.fromarray(pixels)
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
        registration="Adjacent phase correlation and coarse normalized template matching to middle section",
    )
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
        reconstruct(rows, stage, name, kind, attribution)
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
