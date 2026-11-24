"""Build an auditable graph of voxel-face contacts on a registered Z,Y,X grid.

Section metadata and path geometry are separate. An edge through an unobserved
plane is always inferred. Independent evidence applies only to its specified
edge. Synthetic lineage is a third evidence source and cannot verify anatomy.
"""
from collections import defaultdict

import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, label

from scripts.robustness_measured import contact_areas


SHIFTS = ((-2, 0), (2, 0), (0, -2), (0, 2))


def _family_hits(regions, truth, families):
    """Same 25%-of-one-reference-profile criterion as the PR 11 path metric."""
    hits = defaultdict(set)
    for profile in np.unique(truth[truth > 0]):
        counts = np.bincount(regions[truth == profile])
        for region in np.flatnonzero(counts[1:] * 4 >= counts.sum()) + 1:
            hits[int(region)].add(int(families[int(profile)]))
    return hits


def _dilation_fusions(mask, regions):
    expanded, _ = label(binary_dilation(mask))
    originals = defaultdict(set)
    for region, grown in np.unique(np.stack((regions[mask], expanded[mask]), axis=1), axis=0):
        originals[grown].add(int(region))
    return {r for group in originals.values() if len(group) > 1 for r in group}


def _eroded_fragments(eroded):
    remnants, count = label(eroded > 0)
    if not count:
        return set()
    _, first = np.unique(remnants[remnants > 0], return_index=True)
    original = eroded[remnants > 0][first]
    ids, counts = np.unique(original, return_counts=True)
    return set(ids[counts > 1])


def _reachable(start_z, components, target_z, adjacent):
    step = 1 if target_z >= start_z else -1
    for z in range(start_z, target_z, step):
        components = set().union(*(adjacent[z, r] for r in components))
    return components


def _flank(start, target_z, adjacent, labels, contact):
    """Find a measured endpoint by following directed contacts on the same path."""
    if target_z is None:
        return None, set()
    z, region = start
    reached = _reachable(z, {region}, target_z, adjacent)
    if not reached:
        return None, reached
    if z == target_z:
        return [*contact, z], reached
    ys, xs = np.where(np.isin(labels[target_z], list(reached)))
    index = np.argmin((xs - contact[0])**2 + (ys - contact[1])**2)
    return [int(xs[index]), int(ys[index]), target_z], reached


def build_graph(mask, sections, *, registration, segmentation, oracle=None, families=None, references=None):
    """Return JSON-ready graph. Each section has an ID, measured bool and optional missingBefore IDs.

    Coordinates in a/b and flanks use XYZ registered voxel indices. For two
    measured planes separated by known missing physical cuts, list their IDs
    in the later plane's missingBefore. A null flank means no measured witness
    is reachable in that direction. Consumers can expose the bounding image
    for context but cannot claim a corresponding profile on it.

    Optional independent references are keyed by (z, fromComponent, toComponent),
    with status verified/contradicted/unresolved, nonempty source and reason.
    """
    mask = np.asarray(mask)
    if mask.ndim != 3 or min(mask.shape) == 0 or mask.dtype != np.bool_ or len(sections) != len(mask):
        raise ValueError("Expected a nonempty binary boolean ZYX volume and one record per plane")
    if not registration or not segmentation:
        raise ValueError("Registration and segmentation provenance are required")
    if any(not isinstance(s.get("id"), str) or not s["id"] or type(s.get("measured")) is not bool
           for s in sections) or len({s["id"] for s in sections}) != len(sections):
        raise ValueError("Sections require unique source IDs and explicit sampling status")
    for s in sections:
        cuts = s.get("missingBefore", [])
        if not isinstance(cuts, list) or any(not isinstance(c, str) or not c for c in cuts):
            raise ValueError("Missing section IDs must be a list of nonempty strings")
    references = references or {}
    for ref in references.values():
        if (ref.get("status") not in ("verified", "contradicted", "unresolved")
                or not all(isinstance(ref.get(k), str) and ref[k].strip() for k in ("source", "reason"))):
            raise ValueError("Independent evidence requires status, source and reason")
    if oracle is not None:
        oracle = np.asarray(oracle)
        if (oracle.shape != mask.shape or oracle.dtype.kind not in "iu" or oracle.min() < 0
                or not families or not set(np.unique(oracle[oracle > 0])).issubset(families)):
            raise ValueError("Expected a synthetic identity raster with a family for each positive ID")
        if references:
            raise ValueError("A synthetic lineage experiment cannot establish independent anatomical identity")

    planes = [label(p)[0] for p in mask]
    eroded = [np.where(binary_erosion(m), ids, 0) for m, ids in zip(mask, planes)]
    fragments = [_eroded_fragments(p) for p in eroded]
    fusions = [_dilation_fusions(m, ids) for m, ids in zip(mask, planes)]
    paths, _ = label(mask)
    node_families = defaultdict(set)
    path_families = defaultdict(set)
    if oracle is not None:
        for z, truth in enumerate(oracle):
            for region, hits in _family_hits(planes[z], truth, families).items():
                node_families[z, region] = hits
            for path, hits in _family_hits(paths[z], truth, families).items():
                path_families[path].update(hits)

    forward, backward = defaultdict(set), defaultdict(set)
    edges = []
    for z, (earlier, later) in enumerate(zip(planes, planes[1:])):
        ys, xs = np.where((earlier > 0) & (later > 0))
        pairs = np.stack((earlier[ys, xs], later[ys, xs]), axis=1)
        ids, first, counts = np.unique(pairs, axis=0, return_index=True, return_counts=True)
        shifted = [contact_areas(earlier, later, *offset) for offset in SHIFTS]
        shrunk = contact_areas(eroded[z], eroded[z+1], 0, 0)
        for (i, j), index, count in zip(ids.tolist(), first, counts):
            x, y = int(xs[index]), int(ys[index])
            forward[z, i].add(j)
            backward[z+1, j].add(i)
            edge = dict(id=f"{z}:{i}>{j}", a=[x, y, z], b=[x, y, z+1],
                        fromComponent=i, toComponent=j, contactPixels=int(count),
                        alignmentAreas=[int(probe.get((i,j), 0)) for probe in shifted],
                        erodedContactPixels=int(shrunk.get((i,j), 0)),
                        erosionSplit=i in fragments[z] or j in fragments[z+1],
                        dilationFusion=i in fusions[z] or j in fusions[z+1],
                        pathId=int(paths[z, y, x]))
            edges.append(edge)
    keys = {(e["a"][2], e["fromComponent"], e["toComponent"]) for e in edges}
    if set(references) - keys:
        raise ValueError("Independent evidence references a nonexistent graph edge")
    measured = [z for z,s in enumerate(sections) if s["measured"]]
    for edge in edges:
        x, y, z = edge["a"]
        i, j = edge["fromComponent"], edge["toComponent"]
        lo = max((v for v in measured if v <= z), default=None)
        hi = min((v for v in measured if v > z), default=None)
        left, lnodes = _flank((z, i), lo, backward, planes, [x, y])
        right, rnodes = _flank((z+1, j), hi, forward, planes, [x, y])
        edge["flanks"] = [left, right]
        edge["flankSections"] = [lo, hi]
        begin = 0 if lo is None else lo+1
        end = len(sections)-1 if hi is None else hi
        missing = []
        for k in range(begin, end+1):
            missing.extend(sections[k].get("missingBefore", []))
            if not sections[k]["measured"]:
                missing.append(sections[k]["id"])
        edge["missingSections"] = missing
        gap = bool(missing or lo is None or hi is None)
        flags = ["inferred_gap" if gap else "observed_contact"]
        reasons = ["Connection traverses an unsampled interval." if gap
                   else "Segmented components share a voxel face between sampled section grids."]
        if left is None or right is None:
            reasons.append("No corresponding measured component is reachable on at least one flank.")
        if 0 in edge["alignmentAreas"]:
            flags.append("registration_sensitive")
            reasons.append("A two-pixel cardinal displacement removes this component contact.")
        if not edge["erodedContactPixels"] or edge["dilationFusion"] or edge["erosionSplit"]:
            flags.append("segmentation_sensitive")
            if not edge["erodedContactPixels"]:
                reasons.append("One-pixel erosion of both boundaries removes this contact.")
            if edge["dilationFusion"]:
                reasons.append("One-pixel dilation fuses an endpoint with another component on its plane.")
            if edge["erosionSplit"]:
                reasons.append("One-pixel erosion divides an endpoint into separate components.")
        if gap and lo is not None and hi is not None and any(
                len(_reachable(lo, {node}, hi, forward)) > 1 for node in lnodes):
            flags.append("split_depth_uncertain")
            reasons.append("The predicted split lies across a sampling gap. Its exact depth is inferred.")

        known = path_families[edge["pathId"]]
        ref = references.get((z,i,j))
        edge["reference"] = "No independent identity adjudication for this edge."
        if oracle is not None:
            lfamilies = set().union(*(node_families[lo, n] for n in lnodes))
            rfamilies = set().union(*(node_families[hi, n] for n in rnodes))
            if (len(node_families[z,i]) > 1 or len(node_families[z+1,j]) > 1
                    or (lfamilies and rfamilies and lfamilies.isdisjoint(rfamilies))):
                flags.append("contradicted")
                reasons.append("Synthetic reference identifies unrelated structures in this predicted connection.")
            edge["reference"] = "Synthetic lineage oracle; no human anatomical adjudication."
        if ref:
            edge["reviewerEvidence"] = dict(ref)
            edge["reference"] = f'{ref["source"]}: {ref["reason"]}'
            if ref["status"] == "verified" and "contradicted" not in flags:
                flags.append("verified_identity")
            elif ref["status"] == "contradicted" and "contradicted" not in flags:
                flags.append("contradicted")
        if len(known) > 1:
            flags.append("mixed_path")
            edge["pathRisk"] = "This 3D component reaches distinct synthetic families " + ", ".join(map(str, sorted(known))) + "."
            reasons.append("An erroneous path can span unmatched intermediate components.")
        elif oracle is not None:
            edge["pathRisk"] = "No mixed-family path detected by the synthetic 25% footprint test."
        else:
            edge["pathRisk"] = "Whole-path identity unresolved; independent lineage coverage is unavailable."
        if "verified_identity" not in flags and "contradicted" not in flags:
            flags.append("unresolved")
        edge["flags"], edge["reasons"] = flags, reasons
    if oracle is None:
        hazards = defaultdict(set)
        for e in edges:
            hazards[e["pathId"]].update(set(e["flags"]) & {
                "inferred_gap", "registration_sensitive", "segmentation_sensitive", "contradicted"})
        descriptions = {"inferred_gap": "an unsampled interval", "registration_sensitive": "alignment-sensitive contact",
                        "segmentation_sensitive": "boundary-sensitive contact", "contradicted": "a contradicted edge"}
        for e in edges:
            risk = [descriptions[k] for k in sorted(hazards[e["pathId"]])]
            if risk:
                e["pathRisk"] += " Elsewhere or here, the same connected volume includes " + ", ".join(risk) + "."
    return dict(version=1, sections=sections, edges=edges, registration=registration,
                segmentation=segmentation, alignmentShiftsXY=[list(p) for p in SHIFTS])
