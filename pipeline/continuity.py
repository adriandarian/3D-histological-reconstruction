"""Compare a face-connected reconstruction with an independent annotated graph.

The two raster volumes must already occupy the same registered ZYX grid.
Positive integers in the reference identify distinct regions within one section.
Reference links are supplied explicitly and never inferred from raster overlap.
"""

from collections import Counter

import numpy as np
from scipy.ndimage import label
from scipy.optimize import linear_sum_assignment


def _match_regions(predicted, reference, minimum):
    ref_ids, inverse = np.unique(reference, return_inverse=True)
    n_pred = int(predicted.max())
    overlaps = np.bincount(
        predicted.ravel() * len(ref_ids) + inverse.ravel(),
        minlength=(n_pred + 1) * len(ref_ids),
    ).reshape(n_pred + 1, len(ref_ids))
    foreground = ref_ids > 0
    ref_ids = ref_ids[foreground]
    intersection = overlaps[1:, foreground]
    union = (overlaps[1:].sum(axis=1, keepdims=True)
             + overlaps[:, foreground].sum(axis=0) - intersection)
    iou = intersection / union
    eligible = iou >= minimum
    # Make one additional eligible match worth more than all IoU tie-breakers.
    weight = eligible * (min(iou.shape) + 1 + iou)
    row, col = linear_sum_assignment(weight, maximize=True)
    matches = {int(r + 1): int(ref_ids[c]) for r, c in zip(row, col) if eligible[r, c]}
    return matches, {
        "matches": [{"predicted": int(r + 1), "reference": int(ref_ids[c]),
                     "iou": float(iou[r, c])} for r, c in zip(row, col) if eligible[r, c]],
        "missed": sorted(set(ref_ids.tolist()) - set(matches.values())),
        "extra": sorted(set(range(1, n_pred + 1)) - matches.keys()),
    }


def _events(edges, axis):
    """IDs of nodes with multiple outgoing (0) or incoming (1) links."""
    counts = Counter(edge[axis] for edge in edges)
    return {region for region, count in counts.items() if count > 1}


def score_continuity(prediction, reference, pairs, *, reviewed_sections=None, min_iou=0.1):
    """Score a binary target ROI using one-to-one planar IoU correspondence.

    pairs[z] describes z -> z+1 with status reviewed/uncertain/unreviewed/missing,
    and optional independent registration verdict pass/fail/unknown. A reviewed
    pair requires an exhaustive list of reference ID pairs in edges. A failed
    registration still contributes its connectivity errors if the reference
    identities were reviewed. Unreviewed sections and links are excluded from
    denominators and retained in the audit rows. All section indices start at 0.
    """
    prediction, reference = np.asarray(prediction), np.asarray(reference)
    if prediction.ndim != 3 or prediction.shape != reference.shape or min(prediction.shape) < 1:
        raise ValueError("Expected equal nonempty ZYX volumes")
    if reference.dtype.kind not in "bui" or np.any(reference < 0):
        raise ValueError("Expected nonnegative integer reference IDs")
    if not np.isin(prediction, [False, True]).all():
        raise ValueError("Expected a binary prediction for one target")
    depth = len(prediction)
    if len(pairs) != depth - 1 or not 0 < min_iou <= 1:
        raise ValueError("Expected one record per adjacent pair and 0 < min_iou <= 1")
    reviewed = np.ones(depth, dtype=bool) if reviewed_sections is None else np.asarray(reviewed_sections)
    if reviewed.shape != (depth,) or reviewed.dtype.kind != "b":
        raise ValueError("Expected one boolean review flag per section")

    components, mappings, sections = [], [], []
    totals = dict.fromkeys(("matchedRegions", "missedRegions", "extraRegions", "supportedLinks",
                            "missedLinks", "falseLinks", "missedSplits", "falseSplits",
                            "missedMerges", "falseMerges", "scoredPairs", "excludedPairs",
                            "registrationFailures", "reviewedSections"), 0)
    for z in range(depth):
        regions, count = label(prediction[z])  # planar 4-connectivity
        components.append(regions)
        section = {"z": z, "reviewed": bool(reviewed[z]), "predictedCount": count}
        mapping = {}
        if reviewed[z]:
            mapping, details = _match_regions(regions, reference[z], min_iou)
            section.update(details)
            totals["reviewedSections"] += 1
            for field, key in [("matchedRegions", "matches"), ("missedRegions", "missed"),
                               ("extraRegions", "extra")]:
                totals[field] += len(details[key])
        mappings.append(mapping)
        sections.append(section)

    records = []
    for z, pair in enumerate(pairs):
        status, registration = pair["status"], pair.get("registration", "unknown")
        if status not in {"reviewed", "uncertain", "unreviewed", "missing"}:
            raise ValueError(f"Unknown review status on pair {z}")
        if registration not in {"unknown", "pass", "fail"}:
            raise ValueError(f"Unknown registration verdict on pair {z}")
        row = {"z": z, "status": status, "registration": registration}
        records.append(row)
        totals["registrationFailures"] += int(registration == "fail")
        if status != "reviewed":
            totals["excludedPairs"] += 1
            continue
        if not reviewed[z:z+2].all():
            raise ValueError(f"Reviewed pair {z} requires two reviewed sections")
        expected = {tuple(edge) for edge in pair["edges"]}
        ref_a, ref_b = set(np.unique(reference[z])), set(np.unique(reference[z+1]))
        if any(len(edge) != 2 or edge[0] <= 0 or edge[1] <= 0 or edge[0] not in ref_a
               or edge[1] not in ref_b for edge in expected):
            raise ValueError(f"Invalid reference edge on pair {z}")
        a, b = components[z:z+2]
        contact = (a > 0) & (b > 0)
        links = np.unique(np.column_stack((a[contact], b[contact])), axis=0).tolist()
        # Negative IDs retain distinct unmatched predictions for false-link accounting.
        observed = {(mappings[z].get(i, -i), mappings[z+1].get(j, -j)) for i, j in links}
        row.update(supportedLinks=sorted(expected & observed), missedLinks=sorted(expected - observed),
                   falseLinks=sorted(observed - expected))
        for axis, event in enumerate(["Splits", "Merges"]):
            obs, ref = _events(observed, axis), _events(expected, axis)
            row["false" + event] = sorted(obs - ref)
            row["missed" + event] = sorted(ref - obs)
        totals["scoredPairs"] += 1
        for field in ("supportedLinks", "missedLinks", "falseLinks", "missedSplits", "falseSplits",
                      "missedMerges", "falseMerges"):
            totals[field] += len(row[field])
    return {"minIoU": min_iou, "totals": totals, "sections": sections, "pairs": records}
