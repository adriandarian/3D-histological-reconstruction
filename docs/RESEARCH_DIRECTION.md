# What can serial H&E tell us about tissue in three dimensions?

Can we computationally reconstruct reliable 3D tissue anatomy from serial 2D histology scans, and does that reconstruction reveal biologically meaningful information that conventional 2D pathology review can miss?

Consider two gland profiles on one H&E slide. They might belong to separate glands or to branches of the same gland. A useful reconstruction would let a pathologist follow each profile to the section where the paths join, inspect the epithelial boundary in the original scan, and record an unresolved connection when a fold or missing section obscures that boundary.

CODA has already demonstrated large-scale reconstruction from serial H&E and found distinct three-dimensional morphologies in pancreatic precursor lesions. Multiscale histology viewers have also linked organ models to full-resolution tissue patches. Our contribution depends on how accurately we can recover these relationships, how readily a reader can audit them, and whether access to the volume changes the reader's answer. [CODA study](https://www.nature.com/articles/s41592-022-01650-9) · [Multiscale histology study](https://doi.org/10.1186/s12885-021-08542-9)

## Where the evidence stands

The viewer links 3D selections to source sections. A synthetic duct tests recovery of known geometry. A real fly neuron tests a stronger claim in electron microscopy: one parent reaches both manually traced daughters, which occupy separate profiles for eight consecutive planes. The human cortical vascular study leaves its exact junction unresolved. These results establish methods for testing connectivity. The ordinary H&E pancreas series still has unknown depth spacing and an unconfirmed cavity. A verified gland, duct or vessel connection in calibrated routine slides remains the next milestone. [Evidence by case](PROJECT_GUIDE.md#cases-and-evidence)

## The next experiment

1. **Start with a bounded H&E question.** The CODA lung window already has 20 retained slides, scanner XY calibration, a nominal 10 µm sampling interval and published bronchiole and vascular outlines on the first slide. Choose an outlined structure before inspecting predictions. Record whether it continues, branches, exits the field, or becomes untraceable. The distributed slides skip alternate section numbers. A junction spanning an unsampled cut can only be localized to an interval. [Acquisition record](CODA_LUNG.md)
2. **Establish an independent reference.** Have two qualified readers mark corresponding profiles in original slide coordinates, blinded to the reconstruction. Record parent and daughter identities, competing nearby profiles, disagreement and abstentions. Freeze their annotations and adjudicate disagreements before scoring. A repeated parent, two structures that pass close together, and an apparent merge next to a tear are informative failure cases.
3. **Test geometry and topology separately.** Measure registration error in micrometres at withheld landmarks near the target and across depth. Score both daughter paths and every proposed join against the reference. Report missed branches, false joins, unresolved intervals and denominators. Inspect whether plausible changes in alignment alter the claimed connection. Report scanner spacing and section sampling separately from unknown tissue shrinkage.
4. **Publish an auditable result.** A reader should be able to select either branch, inspect the corresponding source crops on both sides of each claimed join, and identify which pixels were measured, transformed, interpolated or predicted. Preserve ambiguous findings and failed cases in the report. One verified connection establishes feasibility for that specimen.

## What would establish scientific utility?

Give readers the same calibrated serial slides under two conditions. In one they can scroll through the full 2D series. In the other they also have the linked 3D reconstruction. Ask the same question in both conditions, such as whether two profiles belong to one branching structure. Use adjudicated cases from held-out tissue blocks, counterbalance the viewing conditions across readers and cases, and keep the reference hidden. Predefine connectivity accuracy and false joins as primary outcomes. Record time, confidence and abstentions. Report paired differences with uncertainty accounting for repeated readers and blocks. This separates the value of 3D access from the advantage of simply seeing more sections.

## Scaling and AI

For the 300-section target, retain full-resolution source pyramids for OpenSeadragon and stream the visible volume regions and mesh levels into Three.js. Benchmark initial load, peak memory and time from a 3D selection to its full-resolution source region on a named device. Repeat the landmark and connectivity checks across the full block to detect cumulative drift. A responsive preview alone cannot establish geometric accuracy.

Evaluate AI registration, correspondence and gap filling against a classical baseline on held-out blocks. Hide intact sections to test predictions against actual measurements, then measure false joins as well as recovered branches. A genuinely missing cut has no direct image reference. Keep its predicted content selectable as a separate layer and carry that uncertainty into measurements of branch length, proximity to vessels and invasion across a boundary.
