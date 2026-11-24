# Prespecified holdout for TCIA specimen aaa0051

Evaluate one specimen with six successive, unambiguous H&E-to-T2 correspondences in the public inventory. B, C, D, E, F and G correspond to T2 slices 17 through 12. Use B, D, F and G as contour anchors. Withhold all XML on C and E until the candidate volume is written. Selection uses correspondence availability. Neither the MRI-mapped cancer masks nor atypia, PIN or capsule labels enter the prediction.

Map each H&E section to a common 256 by 256 field using the bounding box of stained tissue, preserving slide orientation. Between anchors interpolate the signed distances to the tumor outlines. Compare with the nearest anchor in the same frame, breaking ties toward the earlier letter. Evaluate each withheld slice separately, counting empty predictions as misses when tumor is present. Report overlap and missed and excess area in evaluation-grid pixels. The primary endpoint is mean held-out Dice. No retuning on these slides.

The frame normalizes organ width and height separately on each slide. Tissue displacement, quarter stitching and deformation within the gland can alter correspondence. Native histology spacing is unverified. Report extent in section and normalized coordinates. This experiment estimates tumor extent from sparse expert contours and H&E geometry. It does not detect cancer de novo.
