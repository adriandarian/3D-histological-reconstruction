# Serial-section connection robustness protocol

Base revision: `0237af79f251a31c40537654ae4cd367ace95b97`. This design applies to the synthetic study. It changes no frozen case, production policy or viewer threshold.

## Decision and unit of analysis

Test whether a reconstructed connection can join unrelated known lumens despite visually similar adjacent sections, and whether rejecting low-confidence or unmeasured intervals prevents that error while retaining the true branch. Treat any residual wrong-family contact as evidence against using that policy alone. Compare error counts together with coverage and branch recovery. All runs and zero-coverage policies remain in the tables.

Use seeds 11, 23, 37, 53, 71 and 89. One simulation is a 25-plane block sampled at 2 µm per XY pixel and 5 µm per dense Z step. Compare methods on identical images. Reference identities, family membership and edges come from the phantom design; reconstruction receives only the retained images and their indices. The first section is the registration anchor.

## Perturbation grid

Start with the unperturbed acquisition. Change one factor at a time: translation amplitudes 2 and 6 px, rotation 3 and 9 degrees, local warp amplitudes 2 and 5 px, nominal sampling strides 2 and 4, loss of the central branch section or a three-section interval around it, stain contrast multipliers 0.75 and 0.5, noise SD 12 and 24 intensity levels, a fold, a tissue-loss defect, and boundary offsets of -2, -1, +1 and +2 px. Include one combined stress case (6 px shift, 9 degree rotation, 5 px deformation, 0.75 contrast, noise SD 12, stride 2). Run registration on and off. Keep first and last planes in every acquisition.

Compare segmentation of measured planes with gaps left empty, copying the registered first mask, nearest retained segmentation, and interpolation of signed distances between the same flanking segmentations. Include image-based optical-flow propagation if compatible with the input data. Report dense-grid results including hidden planes and report hidden-plane Dice separately. A deliberately empty gap is an omitted prediction; it does not constitute evidence of anatomical termination.

## Endpoints and reporting

Use the existing planar four-connectivity and adjacent voxel-face contact scorer at one-to-one IoU ≥ 0.50. Record TP, FP, FN, wrong-family links between matched identities, unmatched-endpoint false links, false and missed splits/merges, and recovery of both named edges of the true split. Additionally flag a planar component that covers at least 25% of each of two *unrelated* profiles, since one-to-one identity matching can hide a fused cross-section. Report foreground Dice and empirical seed spread. A one-pixel contact can create a graph edge. These operational definitions do not establish material continuity between samples.

Sweep post-registration image correlation gates of none, 0.60, 0.90 and 0.97, with and without requiring both neighboring planes to be measured. Retain raw errors before abstention, accepted-interval errors, rejected reference links, and branch coverage. Correlation is a similarity statistic, not a probability of correct anatomy.

Display clean, dilation, missing-section and combined stress configurations for the first listed seed regardless of outcome. Report all other seeds in machine-readable tables. Seed ranges describe this simulator only; the study cannot estimate clinical reliability, validate a real H&E connection or measure reader benefit.

### Field-boundary challenge added before execution

Also omit planes 9 through 15 inclusive. This deliberately brackets the disappearance of family 6 and arrival of unrelated family 7. For each reconstruction label its six-connected 3D components. Count distinct family pairs for which one component covers at least 25% of a cross-section of each family anywhere in the volume. Record the specific 6/7 join separately. This captures a long false path even when no single adjacent link matches two different reference identities. Figure panels for this additional case use the same first seed.
