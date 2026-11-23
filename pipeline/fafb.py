"""Reconstruct a seeded, face-connected neurite from a published FFN segmentation.

Manual reference points enter the assessment only after the seeded volume has
been selected. Plane component numbers are local to one section.
"""
import numpy as np
from scipy import ndimage

DAUGHTERS = ("daughterA", "daughterB")


def pixel(point):
    """Trace coordinates are relative to display voxel *centers*."""
    return int(np.floor(point["y"] + .5)), int(np.floor(point["x"] + .5))


def reconstruct(instance_ids, seed):
    y, x = pixel(seed)
    segment = int(instance_ids[0, y, x])
    if segment == 0:
        raise ValueError("Parent seed falls in unsegmented background")
    components, count = ndimage.label(instance_ids == segment)
    connected = components == components[0, y, x]
    return connected, {"segmentId": str(segment), "discardedDisconnectedComponents": count - 1,
                       "discardedDisconnectedVoxels": int(np.count_nonzero(instance_ids == segment) - connected.sum())}


def assess(mask, trace):
    """Assess exact point occupancy, projected edges and per-daughter trajectories.

    A predicted inter-plane edge requires a shared voxel face. Each reference
    edge joins a manual node to its actual parent, carrying the daughter's
    identity even where the two centerlines share a planar component.
    """
    if mask.ndim != 3 or len(mask) != len(trace["planes"]):
        raise ValueError("Prediction and trace must share one ZYX crop")
    planes, intervals = [], []
    nodes = {}
    parent_components, reached, prev = {}, set(), None
    arm_scores = {arm: dict(points=0, hits=0, tracedEdges=0, supportedEdges=0,
                            reachablePoints=0) for arm in DAUGHTERS}
    split_planes = []
    resolved_z = []
    for index, (source, predicted) in enumerate(zip(trace["planes"], mask)):
        z = source["z"]
        labels, count = ndimage.label(predicted)
        if index and z != planes[-1]["z"] + 1:
            raise ValueError("Expected consecutive source section indices")
        links = set()
        if prev is not None:
            overlap = (prev > 0) & (labels > 0)
            links = set(map(tuple, np.unique(np.stack((prev[overlap], labels[overlap]), axis=1), axis=0).tolist()))
            reached = {b for a, b in links if a in reached}
        else:
            reached = {int(labels[pixel(source["points"][0])])} - {0}
        current = {}
        evidence = []
        reference_links, missed = set(), []
        for pt in source["points"]:
            y, x = pixel(pt)
            if not (0 <= y < labels.shape[0] and 0 <= x < labels.shape[1]):
                raise ValueError("Reference point lies outside image crop")
            component = int(labels[y, x])
            arm = pt["arm"]
            current[arm] = component
            row = {"node": pt["node"], "arm": arm, "hit": component != 0,
                   "component": component, "reachableFromSeed": component in reached}
            if arm in DAUGHTERS:
                s = arm_scores[arm]
                s["points"] += 1
                s["hits"] += int(row["hit"])
                s["reachablePoints"] += int(row["reachableFromSeed"])
            if index or pt["parent"] in nodes:
                anchor = nodes.get(pt["parent"])
                if anchor is None:
                    raise ValueError("Missing manual parent within section window")
                pz, pc = anchor
                if pz == z:
                    supported = pc != 0 and pc == component
                elif pz == z-1:
                    supported = (pc, component) in links
                    if supported:
                        reference_links.add((pc, component))
                else:
                    raise ValueError("Manual edge skips a source plane")
                row["edgeSupported"] = supported
                if not supported:
                    missed.append(pt["node"])
                if arm in DAUGHTERS:
                    s["tracedEdges"] += 1
                    s["supportedEdges"] += int(supported)
            nodes[pt["node"]] = (z, component)
            evidence.append(row)
        both = all(a in current for a in DAUGHTERS)
        components = [current.get(a, 0) for a in DAUGHTERS]
        distinct = bool(all(components) and components[0] != components[1]) if both else None
        if distinct:
            resolved_z.append(z)
        if index:
            previous = [parent_components.get(a, 0) for a in DAUGHTERS]
            direct_fork = bool(distinct and all(c in reached for c in components)
                               and previous[0] and previous[0] == previous[1]
                               and all((previous[0], c) in links for c in components))
            if direct_fork:
                split_planes.append(z)
            intervals.append(dict(fromZ=z-1, toZ=z, predictedLinks=len(links),
                                  tracedLinks=len(reference_links), unadjudicatedLinks=len(links - reference_links),
                                  missingEdgeTargets=missed, tracedDaughterSplit=direct_fork,
                                  splitWitness=({"parent": previous[0], "daughterA": components[0],
                                                 "daughterB": components[1]} if direct_fork else None)))
        planes.append(dict(z=z, points=evidence, distinctDaughters=distinct, components=count,
                           unadjudicatedComponents=count-len(set(current.values())-{0})))
        prev, parent_components = labels, current
    return {"planes": planes, "intervals": intervals, "arms": arm_scores,
            "directDaughterSplitZ": split_planes, "distinctDaughterPlanes": resolved_z,
            "unadjudicatedLinks": sum(r["unadjudicatedLinks"] for r in intervals)}


def remove_resolved_arm(mask, report, arm):
    """Negative control: erase only one spatially distinct daughter per plane."""
    if arm not in DAUGHTERS:
        raise ValueError("Choose one daughter arm to erase")
    result = mask.copy()
    for z, row in enumerate(report["planes"]):
        if row["distinctDaughters"]:
            regions, _ = ndimage.label(mask[z])
            target = next(p["component"] for p in row["points"] if p["arm"] == arm)
            result[z, regions == target] = False
    return result
