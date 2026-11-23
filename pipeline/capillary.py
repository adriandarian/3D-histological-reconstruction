"""Propagate an identified lumen from the first plane using adjacent EM images.

The remaining author annotations are held out by the function boundary. No
label is injected after initialization and no missing plane is bridged.
"""
import cv2
import numpy as np


def trace_lumen(images, seed):
    if images.dtype != np.uint8 or images.ndim != 3 or seed.shape != images.shape[1:]:
        raise ValueError("Expected a ZYX uint8 EM stack and its first YX section mask")
    if not seed.any() or not images[0].std():
        raise ValueError("The first section needs measured signal and a nonempty seed")
    height, width = seed.shape
    y, x = np.indices((height, width), dtype=np.float32)
    # Transport a signed-distance field. Repeatedly rounding binary masks
    # erases subpixel movement during slow changes between adjacent sections.
    binary = seed.astype(np.uint8)
    field = (cv2.distanceTransform(binary, cv2.DIST_L2, 5)
             - cv2.distanceTransform(1 - binary, cv2.DIST_L2, 5))
    masks = [binary.astype(bool)]
    for previous, current in zip(images, images[1:]):
        if not current.std() or not previous.std():
            field.fill(-1)
        else:
            backward = cv2.calcOpticalFlowFarneback(current, previous, None,
                                                    .5, 3, 17, 4, 5, 1.2, 0)
            field = cv2.remap(field, x + backward[..., 0], y + backward[..., 1],
                              cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=-1)
        masks.append(field > 0)
    return np.stack(masks)
