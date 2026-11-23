"""Trace CODA bronchiole region 3 with one XML seed and measured serial H&E.

Run with python -m scripts.trace_coda_lung after scripts/download_coda_lung.py.
Measured tissue imagery stays in the local browser export.
"""
import argparse
import csv
import json
from pathlib import Path
from xml.etree import ElementTree

import cv2
import numpy as np
import openslide
from PIL import Image, ImageDraw
from pipeline.branching import surface

SIZE = 640
STEP = 8  # level 3 in the pinned NDPI series
SLIDES = [f"lungs_{section:03}.ndpi" for section in range(1, 40, 2)]
DEFAULT_POINTS = Path("docs/coda-lung/bronchiole-3.csv")


def seed_polygon(xml):
    region = ElementTree.parse(xml).find(
        ".//Annotation[@Name='bronchioles']/Regions/Region[@Id='3']"
    )
    return np.float64([(float(v.get("X")), float(v.get("Y")))
                       for v in region.findall("Vertices/Vertex")])


def features(slide):
    overview = slide.read_region((0, 0), 4, slide.level_dimensions[4]).convert("L")
    gray = cv2.createCLAHE().apply(np.asarray(overview))
    detector = cv2.SIFT_create(nfeatures=8000, contrastThreshold=.012)
    keys, descriptors = detector.detectAndCompute(gray, None)
    return np.float32([key.pt for key in keys]), descriptors


def registration(previous, current, center):
    old, new = previous[0], current[0]
    pairs = cv2.BFMatcher().knnMatch(previous[1], current[1], k=2)
    matches = [m for m, n in pairs if m.distance < .79 * n.distance]
    matches.sort(key=lambda m: np.linalg.norm(old[m.queryIdx] - center / 16))
    local = matches[:80]
    if len(local) < 8:
        raise ValueError("Insufficient tissue correspondences")
    a = np.float32([old[m.queryIdx] for m in local])
    b = np.float32([new[m.trainIdx] for m in local])
    mat, inliers = cv2.estimateAffinePartial2D(a, b, ransacReprojThreshold=4)
    if mat is None or inliers.sum() < 8:
        raise ValueError("Cannot register this interval")
    # Preserve scanner distances. Fit a rigid transform to the robust inliers.
    keep = inliers.ravel().astype(bool)
    left, right = a[keep], b[keep]
    u, _, vt = np.linalg.svd((left - left.mean(0)).T @ (right - right.mean(0)))
    rotation = vt.T @ u.T
    if np.linalg.det(rotation) <= 0:
        raise ValueError("Reflection in local registration")
    mat[:, :2] = rotation
    mat[:, 2] = (right.mean(0) - rotation @ left.mean(0)) * 16
    return mat, int(inliers.sum())


def warp(mask, transform):
    return cv2.warpAffine(mask.astype(np.uint8), transform, (SIZE, SIZE),
                          flags=cv2.INTER_NEAREST).astype(bool)


def lumen(rgb, prior):
    # Dark nuclei and eosin outline the pale spaces. Close narrow breaks in
    # the wall before matching a single airspace to the preceding section.
    green = rgb[:, :, 1]
    pale = cv2.morphologyEx((green >= 214).astype(np.uint8), cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(pale, connectivity=4)
    intersection = np.bincount(labels[prior], minlength=count)
    sizes = stats[:, cv2.CC_STAT_AREA]
    iou = intersection / np.maximum(prior.sum() + sizes - intersection, 1)
    iou[0] = 0
    index = np.argmax(iou)
    if iou[index] < .12:
        return np.zeros_like(prior), float(iou[index])
    return labels == index, float(iou[index])


def trace(folder):
    polygon = seed_polygon(folder / "lungs_001.xml")
    center = polygon.mean(axis=0)
    previous = None
    rows, images, masks, controls = [], [], [], []
    for z, name in enumerate(SLIDES):
        with openslide.OpenSlide(str(folder / name)) as slide:
            if tuple(slide.level_downsamples[3:5]) != (8, 16):
                raise ValueError(f"Unexpected pyramid calibration in {name}")
            current = features(slide)
            if previous is not None:
                mat, inliers = registration(previous, current, center)
                center = mat[:, :2] @ center + mat[:, 2]
            origin = np.rint(center - SIZE * STEP / 2).astype(int)
            crop = slide.read_region(tuple(origin), 3, (SIZE, SIZE)).convert("RGB")
            rgb = np.asarray(crop)
            if previous is None:
                reference = np.zeros((SIZE, SIZE), np.uint8)
                cv2.fillPoly(reference, [np.rint((polygon-origin)/STEP).astype(np.int32)], 1)
                prior = reference.astype(bool)
                cumulative = np.eye(3)
                inliers = None
            else:
                transform = mat.copy()
                transform[:, 2] = (mat[:, :2] @ last_origin + mat[:, 2] - origin) / STEP
                prior = warp(masks[-1], transform)
                cumulative = np.vstack([transform, [0, 0, 1]]) @ cumulative
            mask, overlap = lumen(rgb, prior)
            if not np.any(mask):
                raise ValueError(f"Lost bronchiole at {name}, best overlap {overlap:.3f}")
            scale = [float(slide.properties[f"openslide.mpp-{axis}"]) for axis in "xy"]
            rows.append(dict(slide=name, nominal_z_um=z * 10, crop_origin_level0=origin.tolist(),
                             crop_step_level0=STEP, mpp=scale, registration_inliers=inliers,
                             first_crop_to_current=cumulative[:2].tolist(),
                             prior_iou=round(overlap, 4), profile_pixels=int(mask.sum()),
                             crop_clipped=bool(mask[[0,-1],:].any() or mask[:,[0,-1]].any())))
            controls.append(warp(masks[0] if masks else mask, cumulative[:2]))
            images.append(rgb)
            masks.append(mask)
            previous, last_origin = current, origin
    return rows, images, masks, controls


def export_volume(rows, images, masks, output):
    width = SIZE // 4
    colors, labels, sections = [], [], []
    for row, rgb, mask in zip(rows, images, masks, strict=True):
        transform = cv2.invertAffineTransform(np.array(row["first_crop_to_current"]))
        registered = cv2.warpAffine(rgb, transform, (SIZE, SIZE), borderValue=(255, 255, 255))
        color = cv2.resize(registered, (width, width), interpolation=cv2.INTER_AREA)
        profile = cv2.resize(warp(mask, transform).astype(np.uint8), (width, width),
                             interpolation=cv2.INTER_AREA).astype(bool)
        classes = (color[:, :, 1] < 212).astype(np.uint8)
        classes[profile] = 2
        colors.append(color)
        labels.append(classes)
        sections.append(dict(source=Path(row["slide"]).stem + ".png", transform=transform.tolist(),
                             slide=row["slide"], origin=row["crop_origin_level0"], step=STEP,
                             point=row["point_level0"]))
    volume = np.stack(labels)
    np.stack(colors).tofile(output / "rgb.bin")
    volume.tofile(output / "labels.bin")
    (output / "mesh.json").write_text(json.dumps(surface(volume == 2), separators=(",", ":")))
    manifest = dict(name="CODA lung bronchiole 3", anatomyName="Candidate bronchiole airspace",
                    dimensions=[width, width, len(rows)], spacing=[v*STEP*4 for v in rows[0]["mpp"]]+[10],
                    rgb="rgb.bin", labels="labels.bin", mesh="mesh.json", sourceSections=sections)
    (output / "manifest.json").write_text(json.dumps(manifest))


def audit(rows, images, masks, controls, points_path, output):
    with points_path.open(newline="") as source:
        points = list(csv.DictReader(source))
    if [p["slide"] for p in points] != SLIDES:
        raise ValueError("Expected one ordered source landmark per slide")
    sheet = Image.new("RGB", (5 * 256, 4 * 280), "white")
    for i, (row, rgb, mask, control, point) in enumerate(zip(rows, images, masks, controls, points, strict=True)):
        xy = np.array([int(point["x_level0"]), int(point["y_level0"])])
        location = (xy - row["crop_origin_level0"]) // STEP
        if np.any(location < 0) or np.any(location >= SIZE):
            raise ValueError(f"Landmark outside source crop on {row['slide']}")
        x, y = location
        row.update(point_level0=xy.tolist(), point_in_mask=bool(mask[y,x]),
                   point_in_transported_first_mask=bool(control[y,x]))
        name = Path(row["slide"]).stem
        Image.fromarray(rgb).save(output / f"{name}.png")
        Image.fromarray(mask).save(output / f"{name}-mask.png")
        marked = rgb.copy()
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(marked, contours, -1, (0,120,100), 2)
        cv2.drawMarker(marked, (int(x), int(y)), (206,35,35), cv2.MARKER_CROSS, 14, 2)
        tile = Image.fromarray(marked).resize((256,256), Image.Resampling.LANCZOS)
        col, top = i%5*256, i//5*280
        sheet.paste(tile, (col,top))
        ImageDraw.Draw(sheet).text((col+6,top+259), name, fill="black")
    sheet.save(output / "source-audit.jpg", quality=94)
    (output / "trace.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    fields = ["slide", "nominal_z_um", "prior_iou", "registration_inliers", "profile_pixels",
              "crop_clipped", "point_in_mask", "point_in_transported_first_mask"]
    with (output / "audit.csv").open("w", newline="") as dest:
        writer = csv.DictWriter(dest, fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    # Share derived profiles without redistributing scans. Use one frame and
    # scale across all tiles so slide rotation cannot masquerade as anatomy.
    profiles = Image.new("RGB", (5*176, 4*198), "white")
    for i, (row, mask) in enumerate(zip(rows, masks, strict=True)):
        transform = cv2.invertAffineTransform(np.array(row["first_crop_to_current"]))
        view = np.full((SIZE, SIZE, 3), 255, np.uint8)
        view[warp(mask, transform)] = [46, 121, 120]
        point = (np.array(row["point_level0"]) - row["crop_origin_level0"]) / STEP - .5
        xy = np.rint(transform[:, :2] @ point + transform[:, 2]).astype(int)
        cv2.circle(view, tuple(xy), 9, (238, 133, 32), -1)
        tile = Image.fromarray(view).resize((176,176), Image.Resampling.LANCZOS)
        x, y = i%5*176, i//5*198
        profiles.paste(tile, (x,y))
        ImageDraw.Draw(profiles).text((x+6,y+177), row["slide"], fill="black")
    profiles.save(output / "profiles.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slides", type=Path, default=Path("data/coda-lung"))
    parser.add_argument("--output", type=Path, default=Path("public/data/coda-lung"))
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    rows, images, masks, controls = trace(args.slides)
    audit(rows, images, masks, controls, DEFAULT_POINTS, args.output)
    export_volume(rows, images, masks, args.output)


if __name__ == "__main__":
    main()
