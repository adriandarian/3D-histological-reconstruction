# Project guide

Section Atlas investigates whether the same biological structure can be followed through depth. A source image, an aligned volume, a segmented surface, and an independently supported connection answer different questions. To inspect a claim, start with its case report and follow the links to its images, labels, and validation results.

## Cases and evidence

The [research direction](RESEARCH_DIRECTION.md) connects these experiments to the proposed H&E continuity study, the 300-section target and the reader comparison.

| Case | Evidence available | What it establishes |
| --- | --- | --- |
| Registration phantom | 36 simulated sections with known offsets and sampling. [Generator](../pipeline/phantom.py) and [registration tests](../tests/test_pipeline.py) | Recovery of acquisition motion and mapping between source and registered coordinates. |
| Branching duct phantom | 32 simulated sections on a 2 × 2 × 5 µm grid. [Report](VOLUME_RECONSTRUCTION.md) and [reference and recovered graphs](../public/branching/validation.json) | Image segmentation recovers the known bifurcation and both tips, with Dice 0.9923. Removing a section breaks the graph. |
| Roy pancreas | 36 H&E sections. [Dataset and registration review](DATA.md), [held-out landmarks](pancreas_frozen_landmarks.csv), and [cavity results](../public/pancreas/validation.json) | A bright connected candidate persists across retained sections 6–15. Its anatomical identity, physical spacing, and intervening tissue remain unknown. Three held-out landmarks have a mean residual of 14.1 preview pixels. |
| H01 cortical capillary V1 | 32 consecutive registered EM planes, 600–631. [Case report](H01_CAPILLARY.md) and [per-plane and per-link results](../public/capillary/validation.json) | Published human-corrected annotations support the main lumen over 31 transitions at matching IoU 0.50. A stationary seed retains those same links. The trace introduces 21 extra links relative to the principal lumen. The window contains no reference bifurcation. |
| FAFB neuronal bifurcation | 25 consecutive EM sections, independent manual centerlines and a published FFN instance. [Case report](REAL_BIFURCATION.md) | Both named daughters have supported paths from the parent and separate profiles on sections 4708 to 4715. Repeating the parent mask fails to split. |
| H01 vascular fork candidate | 48 registered EM planes, a coarse manual atlas and blinded AI visual landmarks. [Evidence and uncertainty](H01_VASCULAR_FORK.md) | Both marked profiles remain distinct on 20 planes. The reader withheld 15 transitional planes. The precise lumen junction remains unresolved. |
| TCIA prostate aaa0051 | Six stitched H&E levels and independent pathologist cancer contours. [Held-out study](tcia-prostate/README.md) | Signed-distance interpolation scored mean Dice 0.0046 across C and E versus 0.0529 for the nearest anchor. Geometric accuracy and continuity are unestablished. |
| CODA lung bronchiole | 20 retained H&E slides with scanner XY calibration and a nominal 10 µm interval. [Acquisition](CODA_LUNG.md) and [bronchiole trace](coda-lung/README.md) | The candidate includes all 20 AI reader points. A transported first mask includes nine. The publisher identifies the seed on 001. Later identity and peripheral connections await expert review. |

BigBrain was investigated as another calibrated source. The original proposal also discusses RAPID, ANHIR, ACROBAT, larger whole-slide series, and multiscale storage. Their appearance in the planning document records a research direction. [Calibrated dataset investigation](VOLUME_RECONSTRUCTION.md#calibrated-serial-section-acquisition) · [Original POC plan](POC_PLAN.md)

The [connection robustness study](robustness/README.md) measures how motion, tissue damage, segmentation errors and missing sections affect false joins. It includes paired synthetic ablations and source-image sensitivity checks on Roy, CODA and TCIA.

## From a section to a selected surface point

Use the [connection evidence inspector](connection-inspector/README.md) to select a component edge in the graph or on the 3D view, compare its measured flanks and inspect alignment, boundary and whole-path warnings.

1. **Load and align a series.** The Python CLI reads equal-sized, single-frame images with consecutive numeric section identifiers. It resizes the images, estimates pairwise rigid transforms, composes them toward the middle section, and records the valid sampled field. Optional local refinement saves a displacement grid for each section. The H01 experiment starts with the registration supplied by its publisher. [Registration CLI](../pipeline/__main__.py) · [Local deformation](../pipeline/deformation.py) · [Tissue-tip refinement](../pipeline/contours.py)
2. **Label and reconstruct a target.** Each case defines its own anatomical target and segmentation method. The phantom uses stain intensity, the pancreas experiment tracks a bright cavity, and V1 propagates one author seed with optical flow. Surface triangles bound predicted voxels. A connection in the graph requires contact between samples in successive planes. [Phantom and mesh generation](../pipeline/branching.py) · [Pancreas selection](../pipeline/pancreas.py) · [V1 propagation](../pipeline/capillary.py)
3. **Inspect the measurements.** The WebGL2 ray marcher interpolates registered intensities for display. Orthogonal reslices show sampled planes. A mesh click selects a labeled voxel and updates the linked views. For locally refined pancreas, the viewer maps the registered point through the pull grid and inverse rigid transform to the original preview. For V1, it opens the registered EM crop, the native H01 location, or the corresponding external label TIFF. [Ray marcher](../src/ray-volume.js) · [Reslicing and source projection](../src/reconstruction.js) · [Plane-stack comparison](../src/volume.js)
4. **Score the evidence.** Registration residuals measure how closely landmarks align. Dice measures voxel overlap. Graph scoring uses reference region identities and explicit expected links between successive sections. Its report records misses, extra edges, splits, merges, excluded pairs, and registration verdicts. Unreviewed edges stay outside the scored denominator. [Landmark tool](../scripts/landmark_error.py) · [Connectivity scorer](../pipeline/continuity.py) · [Graph error tests](../tests/test_continuity.py)

A registered image contains resampled measurements. A prediction or an author annotation assigns an interpretation to a region. Interpolation fills the displayed space between samples. Missing cuts, source registration errors, and downsampling can each change the apparent topology. Consult each case's reference provenance before treating a mesh as anatomical evidence.

## Files, units, and reproduction

Run the [README demo commands](../README.md#run-the-published-demo) for the complete packaged site. Vite serves checked-in case exports during development. The release installer also downloads two checksum-verified plane-stack archives into the production bundle. A clean development checkout needs local registration exports for those comparison views. [Production asset installer](../scripts/install-demo-data.mjs)

| Goal | Inputs and entry point | Output or check |
| --- | --- | --- |
| Build an aligned series | Run `python -m pipeline --help`. Use a new or empty output directory. Omit `--input` for the registration phantom. | The registration manifest contains source names, source and registered preview paths, transformations, pairwise QA, and calibration where available. The NPZ contains RGB, tissue, and validity arrays. [CLI and usage](../README.md#inspect-an-export) |
| Reproduce the pancreas case | Download the TIFFs and run the documented registration command, then run `python -m pipeline.pancreas public/data/real public/pancreas`. | The cavity export records the registration manifest digest. Regenerate the cavity export after changing the registration or its metadata. [Data preparation](DATA.md) · [Validation](VOLUME_RECONSTRUCTION.md) |
| Rebuild the branching phantom | Run `python -m pipeline.branching public/branching`. | Source images, truth, prediction, mesh, and graph comparison. [Phantom regression tests](../tests/test_branching.py) |
| Rebuild H01 V1 | Install TensorStore in addition to the base requirements. Retrieve the EM crop and the 32 original author masks, then run `python -m pipeline.h01`. | The exporter checks the exact input buffers and writes predicted, reference, and unmatched-fragment masks. [Commands and attribution](H01_CAPILLARY.md#reproduction-and-attribution) |
| Reproduce the real fork | Use the commands and fixed source window in the [bifurcation report](REAL_BIFURCATION.md). | Examine each daughter on held-out, consecutive source sections. |
| Acquire the CODA sample | Run `python scripts/download_coda_lung.py`. | Checksum-verified local NDPI files and the first-plane XML. Allow about 1.61 GB for the download. [Acquisition details](CODA_LUNG.md) |
| Verify the app | Run the [Python and Playwright suites](../README.md#verify-and-build) and build the production site. | Python checks volume and graph behavior. Chromium tests exercise actual WebGL picking, source coordinates, and reference links. [Browser tests](../tests/browser) |

The browser manifests list **dimensions and spacing in XYZ order**. Raw volume buffers use Z,Y,X order with X contiguous. RGB samples have three interleaved channels. Mesh coordinates are in voxel-center units. The renderer applies spacing to both the volume and the mesh. For the uncalibrated pancreas, the viewer displays indices. The nominal H01 display spacing describes the published registered grid; distortion and physical cut thickness affect specimen measurements. [Volume format](VOLUME_RECONSTRUCTION.md#reproduce) · [H01 geometry](H01_CAPILLARY.md#geometry-and-reconstruction)

## Availability and review

The integration build includes both synthetic series, Roy pancreas, the three EM cases and TCIA. Only local development serves the CODA scan-derived crops. Selecting CODA in the packaged build shows its pending review status. The source panel links to the sampled section or preview used for display. Native coordinates locate the corresponding field in the original scan where the dataset supplies that mapping.

For independent CODA readings, prepare the [blinded packet](coda-lung/PATHOLOGIST_REVIEW.md), [import the native-slide annotations and withheld landmarks](coda-lung/ANNOTATION_IMPORT.md), then [score the frozen candidate and fixed-seed baseline](coda-lung/INDEPENDENT_SCORING.md). Keep reviewer submissions and source exports under the ignored `data/` directory. The green-and-white [profile figure](coda-lung/profiles.png) contains derived silhouettes and point markers. The measured image montage remains local.

## Development history

| Change | Delivered work |
| --- | --- |
| [Research plan](POC_PLAN.md) | Scientific objective, proposed architecture, candidate datasets, and longer-term scale targets. |
| [PR 1](https://github.com/adriandarian/3D-histological-reconstruction/pull/1) | Runnable Python registration pipeline, real and simulated comparison series, and linked 2D and plane-stack navigation. |
| [PR 2](https://github.com/adriandarian/3D-histological-reconstruction/pull/2) | Build-time installation of versioned, checksum-verified demo archives. |
| [PR 3](https://github.com/adriandarian/3D-histological-reconstruction/pull/3) | GPU ray marching, reslices, arbitrary clipping, labeled meshes, synthetic branch validation, and exploratory pancreas continuity. |
| [PR 4](https://github.com/adriandarian/3D-histological-reconstruction/pull/4) | Seeded tracing of a real capillary against withheld published masks, per-link scoring, a stationary-seed control, and CODA acquisition. |
| [PR 5](https://github.com/adriandarian/3D-histological-reconstruction/pull/5) | Named neuronal bifurcation, companion vascular fork study, point-by-point daughter navigation, and the integrated project guide. |
| [PR 6](https://github.com/adriandarian/3D-histological-reconstruction/pull/6) | First calibrated routine H&E trace, local source-linked bronchiole volume, native-slide landmarks and a transported-mask control. |
