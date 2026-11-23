"""Build the H01 vascular ROI from frozen upstream class predictions.

No reviewer annotation is used to segment, filter or connect the structures.
"""
import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes, label


def reconstruct(classes):
    # Recover a vessel profile from the H01 soft-tissue mask. Occupancy includes
    # enclosed nuclei and blood cells. A hole touching the outer ROI is retained.
    if classes.shape != (24, 400, 400):
        raise ValueError("Expected the 24 original H01 masking predictions")
    planes = []
    for image in classes:
        filled = binary_fill_holes(image == 4)
        occupancy = cv2.resize(filled.astype(np.float32), (200, 200), interpolation=cv2.INTER_AREA)
        planes.append(occupancy > .5)
    model = np.stack(planes)
    # Choose the 3D face-connected structure containing the largest first-plane
    # profile. Keep its other connected fragments, including splits and merges.
    components, _ = label(model)
    first, count = label(model[0])
    if not count:
        raise ValueError("No predicted parent profile")
    root = np.argmax(np.bincount(first.ravel())[1:]) + 1
    track = components[0][first == root][0]
    # Each 66 nm model slab covers two measured 33 nm planes. This is a
    # piecewise-constant visualization, not two independent model predictions.
    return (components == track).repeat(2, axis=0)
