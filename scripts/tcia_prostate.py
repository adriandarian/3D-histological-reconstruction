"""Reconstruct and separately score the prespecified aaa0051 TCIA experiment."""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt

LEVELS = "BCDEFG"
ANCHORS = "BDFG"
HOLDOUT = "CE"
SIZE = 256


def path_for(root, level, suffix):
    matches = list(root.rglob(f"aaa 0051 {level}*.{suffix}"))
    if len(matches) != 1:
        raise ValueError(f"Expected one {suffix} for level {level}, found {len(matches)}")
    return matches[0]


def section(path):
    import tifffile  # Optional only for decoding the large original TIFFs.
    with tifffile.TiffFile(path) as tif:
        pixels = tif.pages[0].asarray(out="memmap")
        h, w = pixels.shape[:2]
        thumb = cv2.resize(pixels, (w//32, h//32), interpolation=cv2.INTER_AREA)
    # Percentiles suppress isolated ink or debris at the slide margin.
    r, g, b = thumb.astype(float).transpose(2,0,1)
    ys, xs = np.where((r-g > 12) & (b-g > 4) & (g < 220))
    lo = np.floor([np.percentile(xs,.1), np.percentile(ys,.1)]).astype(int)
    hi = np.ceil([np.percentile(xs,99.9), np.percentile(ys,99.9)]).astype(int)+1
    xy = lo * [w/thumb.shape[1], h/thumb.shape[0]]
    extent = (hi-lo) * [w/thumb.shape[1], h/thumb.shape[0]]
    crop = thumb[lo[1]:hi[1], lo[0]:hi[0]]
    frame = {"file":path.name, "origin":xy.tolist(), "extent":extent.tolist()}
    return cv2.resize(crop, (SIZE,SIZE), interpolation=cv2.INTER_AREA), frame


def tumor(path, frame):
    layers = [a for a in ElementTree.parse(path).findall(".//Annotation")
              if any(t.get("Name","").strip().upper()=="CAP" for t in a.findall("Attributes/Attribute"))]
    if len(layers) != 1:
        raise ValueError(f"Missing or ambiguous CAP layer in {path}")
    contours = []
    for region in layers[0].findall("Regions/Region"):
        points = np.array([(float(v.get("X")),float(v.get("Y"))) for v in region.findall("Vertices/Vertex")])
        if len(points) < 3:
            raise ValueError(f"Invalid CAP contour in {path}")
        contours.append(np.rint((points-frame["origin"])*SIZE/frame["extent"]-.5).astype(np.int32))
    mask = np.zeros((SIZE,SIZE), np.uint8)
    if contours:
        cv2.fillPoly(mask, contours, 1)  # even-odd interior, including nested contours
    return mask.astype(bool)


def signed(mask):
    return distance_transform_edt(mask)-distance_transform_edt(~mask)


def reconstruct(root, out):
    out.mkdir(parents=True,exist_ok=True)
    frames, rgb, anchors = {}, [], {}
    for level in LEVELS:
        im, frames[level] = section(path_for(root,level,"tif"))
        rgb.append(im)
        Image.fromarray(im).save(out/f"{level}.png")
        if level in ANCHORS:
            anchors[level] = tumor(path_for(root,level,"xml"), frames[level])
    layers = dict(anchors)
    for level in HOLDOUT:
        left = max(k for k in anchors if k<level)
        right = min(k for k in anchors if k>level)
        layers[level] = signed(anchors[left])+signed(anchors[right]) > 0  # both midpoints
    labels = np.stack([np.where(layers[k],2, (im[:,:,1]<225).astype(np.uint8))
                       for k, im in zip(LEVELS,rgb)]).astype(np.uint8)
    labels.tofile(out/"labels.bin")
    np.stack(rgb).tofile(out/"rgb.bin")
    from pipeline.branching import surface
    (out/"mesh.json").write_text(json.dumps(surface(labels==2),separators=(",",":")))
    manifest = dict(name="TCIA prostate aaa0051", anatomyName="Tumor extent", dimensions=[SIZE,SIZE,6],
                    spacing=[1,1,12], unit="display units", rgb="rgb.bin", labels="labels.bin",
                    mesh="mesh.json",sections=[f"{k}.png" for k in LEVELS], prostateFrames=list(frames.values()))
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))


def metrics(pred, ref):
    tp = int((pred & ref).sum())
    fp, fn = int((pred & ~ref).sum()), int((~pred & ref).sum())
    return dict(dice=2*tp/(2*tp+fp+fn) if tp+fp+fn else None,
                overlap_px=tp, excess_px=fp, missed_px=fn)


def evaluate(root, out, report):
    manifest=json.loads((out/"manifest.json").read_text())
    labels=out/"labels.bin"
    volume=np.fromfile(labels,np.uint8).reshape(6,SIZE,SIZE)==2
    report.mkdir(exist_ok=True,parents=True)
    scores={}
    reference_volume=np.zeros_like(volume,dtype=np.uint8)
    fig=Image.new("RGB",(SIZE*3,(SIZE+30)*2),"white")
    for row,level in enumerate(HOLDOUT):
        z=LEVELS.index(level)
        reference=tumor(path_for(root,level,"xml"),manifest["prostateFrames"][z])
        reference_volume[z]=reference
        pred, baseline=volume[z],volume[z-1]
        scores[level]={k:metrics(v,reference) for k,v in [("interpolation",pred),("nearest",baseline)]}
        im=np.array(Image.open(out/f"{level}.png"))
        for i,(name,mask,color) in enumerate([("Pathologist",reference,(0,110,72)),("Reconstruction",pred,(154,41,0)),("Nearest anchor",baseline,(34,74,155))]):
            tile=im.copy()
            c,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(tile,c,-1,color,1)
            y=row*(SIZE+30)
            fig.paste(Image.fromarray(tile),(i*SIZE,y))
            ImageDraw.Draw(fig).text((i*SIZE+4,y+SIZE+4),f"Level {level} | {name}",fill="black")
    fig.save(report/"holdouts.png")
    reference_volume.tofile(out/"held-out.bin")
    result=dict(prediction_sha256=hashlib.sha256(labels.read_bytes()).hexdigest(),levels=scores)
    (report/"scores.json").write_text(json.dumps(result,indent=2)+"\n")
    print(result)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=["reconstruct","evaluate"])
    parser.add_argument("--inputs",type=Path,default=Path("data/tcia/files"))
    parser.add_argument("--output",type=Path,default=Path("public/tcia-prostate"))
    parser.add_argument("--report",type=Path,default=Path("docs/tcia-prostate"))
    args=parser.parse_args()
    if args.stage=="reconstruct":
        reconstruct(args.inputs,args.output)
    else:
        evaluate(args.inputs,args.output,args.report)
