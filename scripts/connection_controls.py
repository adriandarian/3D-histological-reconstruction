"""Export the seed-11 synthetic controls from the frozen connection robustness study."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label

from pipeline.branching import surface
from pipeline.connection_evidence import build_graph
from pipeline.robustness_methods import reconstruct
from pipeline.robustness_phantom import DEPTH, LINEAGE, SPACING_UM, SPLIT_Z, PhantomSettings, generate
from scripts.connection_robustness import SCENARIOS, dice


CONTROLS = {
    "field-gap": ("edge_gap", "Seven sections missing at a field boundary"),
    "fold": ("fold", "Fold joins two neighboring lumens"),
    "dilation": ("dilate1", "One-pixel dilation joins neighboring lumens"),
    "branch-depth": ("stride4", "Daughters recovered across sparsely sampled sections"),
}


def write_json(path, obj):
    path.write_bytes((json.dumps(obj, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8"))


def mixed_profiles(mask, ids):
    """Planar components covering at least 25% of each near-contact profile (IDs 4 and 5)."""
    fused = set()
    for z, plane in enumerate(mask):
        components, count = label(plane)
        hits = []
        for profile in (4, 5):
            overlaps = np.bincount(components[ids[z] == profile], minlength=count + 1)
            hits.append(set(np.flatnonzero(overlaps[1:] >= .25 * overlaps.sum()) + 1))
        fused.update((z, int(component)) for component in hits[0] & hits[1])
    return fused


def annotate_control(name, graph, masks, ids):
    """Select a control edge by its geometry; only label effects demonstrated for that edge."""
    edges = graph["edges"]
    if name in ("fold", "dilation"):
        fused = mixed_profiles(masks, ids)
        affected = [edge for edge in edges if
                    (edge["a"][2], edge["fromComponent"]) in fused or
                    (edge["b"][2], edge["toComponent"]) in fused]
        clean_rgb, clean_ids = generate(11)
        clean_masks, _ = reconstruct(clean_rgb, range(DEPTH), DEPTH, register=False)
        if mixed_profiles(clean_masks["signed_distance"], clean_ids):
            raise ValueError("Unperturbed control unexpectedly contains a near-contact fusion")
        mechanism = "fold" if name == "fold" else "one-pixel dilation"
        for edge in affected:
            if name == "dilation" and "segmentation_sensitive" not in edge["flags"]:
                edge["flags"].append("segmentation_sensitive")
            edge["reasons"].append(
                f"The {mechanism} fused synthetic profiles 4 and 5 on an endpoint plane. "
                "They are separate in the paired unperturbed reconstruction."
            )
        chosen = min(affected, key=lambda e: abs(e["a"][2] - 11))
    elif name == "field-gap":
        # Inside the unsampled interval both matched identities are absent here.
        # The path still joins separate families on the measured flanks.
        chosen = next(e for e in edges if e["a"][2] == 12 and e["a"][0] < 20 and e["a"][1] > 65)
    else:
        # Choose a daughter link at the apparent split between measured planes 8 and 12.
        parent_edges = [e for e in edges if 8 <= e["a"][2] < 12 and e["a"][0] < 48 and e["a"][1] < 48]
        chosen = next(e for e in parent_edges if sum(
            other["a"][2] == e["a"][2] and other["fromComponent"] == e["fromComponent"]
            for other in parent_edges) > 1)
        chosen["reasons"].append(
            f"The synthetic parent on z=8 and daughters on z=12 bracket the split. "
            f"The reconstruction splits at {chosen['a'][2]}–{chosen['b'][2]}; "
            f"the generator places it at {SPLIT_Z-1}–{SPLIT_Z}. The measured flanks cannot locate its exact depth."
        )
    return chosen["id"]


def export_control(name, root):
    scenario, title = CONTROLS[name]
    config = SCENARIOS[scenario]
    rgb, ids = generate(11, PhantomSettings(fold=config.get("fold", False)))
    omitted = range(config["omit"][0], config["omit"][1] + 1) if "omit" in config else ()
    retained = [z for z in range(0, DEPTH, config.get("stride", 1)) if z not in omitted]
    boundary = config.get("boundary", 0)
    volumes, _ = reconstruct(rgb[retained], retained, DEPTH, boundary_px=boundary, register=False)
    mask = volumes["signed_distance"]
    segmentation = "Segment observed RGB with the branching phantom intensity and component-size rules."
    if boundary:
        segmentation += " Dilate each measured mask by one pixel with four-neighbor morphology."
    if len(retained) < DEPTH:
        segmentation += " Interpolate signed distances between the flanking masks at omitted planes."
    registration = "Identity transform on an already aligned synthetic grid (2 µm XY, 5 µm Z)."
    folder = root / name
    (folder / "sections").mkdir(parents=True, exist_ok=True)
    source_paths = [f"sections/{z:03d}.png" if z in retained else None for z in range(DEPTH)]
    for z in retained:
        Image.fromarray(rgb[z]).save(folder / source_paths[z])
    sections = [dict(id=f"z={z}", measured=path is not None, source=path) for z, path in enumerate(source_paths)]
    graph = build_graph(mask, sections, registration=registration, segmentation=segmentation,
                        oracle=ids, families=LINEAGE)
    default_edge = annotate_control(name, graph, mask, ids)

    # The display knows the inferred mask. It receives neither hidden source intensities
    # nor an apparent tissue opacity on omitted planes.
    # White has zero stain density in the intensity renderer.
    displayed_rgb = np.full_like(rgb, 255)
    displayed_rgb[retained] = rgb[retained]
    displayed_rgb.tofile(folder / "rgb.bin")
    np.uint8(2 * mask).tofile(folder / "labels.bin")
    foreground = np.zeros(mask.shape, dtype=np.uint8)
    foreground[retained] = 1
    foreground.tofile(folder / "foreground.bin")
    manifest = dict(name=title, controlDescription=title, defaultEdge=default_edge,
                    dice=dice(mask, ids > 0), dimensions=list(mask.shape[::-1]), spacing=list(SPACING_UM),
                    unit="µm", provenance="Synthetic connection robustness study, seed 11. " + registration,
                    anatomyName="Reconstructed synthetic lumen", rgb="rgb.bin", labels="labels.bin",
                    foreground="foreground.bin", mesh="mesh.json", sections=source_paths, graph="graph.json",
                    study=dict(scenario=scenario, seed=11, registration=0, method="signed_distance"))
    write_json(folder / "mesh.json", surface(mask))
    write_json(folder / "manifest.json", manifest)
    for name, key in [("labels.bin", "labelsSha256"), ("manifest.json", "manifestSha256")]:
        data = (folder / name).read_bytes()
        graph[key] = hashlib.sha256(data.replace(b"\r\n", b"\n") if name.endswith(".json") else data).hexdigest()
    write_json(folder / "graph.json", graph)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("public/evidence-controls"))
    args = parser.parse_args()
    for control in CONTROLS:
        manifest = export_control(control, args.output)
        print(control, manifest["defaultEdge"], manifest["dice"])
