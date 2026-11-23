# GOAL — Trustworthy 3D Histological Reconstruction

> **North star:** Can we reconstruct biologically defensible 3D tissue anatomy from routine serial 2D histology, and does that reconstruction reveal useful relationships beyond a careful review of the same 2D sections?
>
> **Mission:** Build an open, reproducible, source-auditable research system that turns ordered physical sections from the same tissue block into calibrated, explorable 3D anatomical structures; validate what actually connects, identify false connections, and test whether 3D improves interpretation.
>
> Updated: November 23, 2026. **Research only; not clinically validated or for diagnosis.**

## 1. The end state

Imagine 300 consecutive H&E-stained sections from a tissue block. A pathologist sees two glandular profiles on one whole-slide scan. Are they different glands, two branches of the same gland, or misleading tangential cuts? How do the glands relate to vessels, stroma, and a possible tumor boundary? A trustworthy 3D reconstruction would let the reader follow each structure through depth, locate a junction, cut the volume along any orientation, and return to the exact original slide pixels supporting — or contradicting — the connection.

Our task is to **answer anatomical questions with auditable evidence**, not just render an attractive 3D mesh.

### Seven project objectives

1. **Reconstruct:** Import ordered serial sections, retain physical X/Y resolution and Z sampling interval when known, register the tissue, and report missing or damaged cuts and deformation uncertainty.
2. **Identify anatomy:** Segment, label and follow vessels, ducts, glands, tumor edges and other preselected structures through the tissue, including branches, joins, terminations and nearby-but-separate profiles.
3. **Validate structure:** Compare 3D identities and inter-section connections to independent annotation. Report false joins, missed branches, boundary error, registration error and unresolved intervals alongside positive results.
4. **Link to measurements:** Selecting a 3D point or edge must open its native scanned 2D section(s), coordinates, transform, provenance and independent reference, if one exists.
5. **Demonstrate scientific benefit:** Ask whether the same reader with the same serial 2D slides plus 3D answers a connectivity question more accurately, with fewer false connections or more justified uncertainty, than with 2D serial-slide review alone.
6. **Scale:** Go from a calibrated 20–50-section experiment toward 300+ WSI sections with multiresolution registration, tiled/chunked volume data and responsive browser access.
7. **Explore AI responsibly:** Test learning-based registration, segmentation, modality translation and missing-section estimation only against withheld measured data and simple baselines. Never depict inferred tissue as though it was directly scanned.

**Priority:** scientific correctness and evidence > measurable reader value > WSI scaling > experimental generative AI > additional visual polish.

## 2. The core scientific question

**Can an anatomically identified structure be followed accurately through consecutive real H&E sections, with independently supported connectivity, and can a linked 3D representation improve the interpretation of that structure beyond 2D serial-slide review?**

The project should test three separate hypotheses:

- **H1 — Spatial and identity fidelity:** a registered, segmented target on held-out slides matches independently annotated identity/boundary evidence, with documented physical scale and registration error.
- **H2 — Topology:** a predicted graph of true joins/splits/terminations is reliable **without inventing connections**. High Dice or a smooth mesh can coexist with unacceptable false graph edges.
- **H3 — Added utility:** access to 3D, when all source sections are equally available, improves correctness, reduces false-join decisions, reduces completion time, or improves appropriate abstentions on a prespecified anatomical task.

A fourth engineering hypothesis is that H1–H3 can eventually be supported with hundreds of gigapixel images without loading the full reconstructed WSI stack into GPU memory.

Existing work such as [CODA](https://www.nature.com/articles/s41592-022-01650-9) already demonstrates serial histology reconstruction. Basic 3D reconstruction is not our novelty. **Potential contributions** are validated connectivity, uncertainty and provenance, real-world scalable browser workflows, multimodal methods, and measured human benefit.

## 3. Evidence definitions — never blur these categories

| Category | Meaning | Appropriate claim |
| --- | --- | --- |
| Measured | A physical retained section scanned by a microscope/WSI scanner | Direct source evidence for what is visible on that section |
| Registered | Measured image warped into a common frame | Source-based estimate of alignment; record transform and QA |
| Segmented | Manual or algorithmic assignment of tissue identity/region | An interpretation requiring validation and provenance |
| Interpolated | Pixels or geometry inferred between observed planes for display or analysis | Not a newly measured section |
| AI-predicted | Generated missing slice, stain, geometry, or correspondence | Model hypothesis; display separately and test on withheld data |
| Unresolved | Missing cut, tear, indistinguishable profiles, or insufficient annotation | An acceptable and important research outcome |

**Calibration rule:** Section thickness and section-to-section sampling interval can differ. 300 samples at 4 µm intervals span 299 × 4 µm = **1.196 mm between first and last sample centers**, assuming no missed intervals. A 1-pixel Z array index does not imply a 1 µm physical step. Unknown X/Y/Z calibration means **index-only visualization**, never physical length or volume measurements.

## 4. Current scientific and deployment baseline (2026-11-23)

**Production site:** https://3d-histo-recon.vercel.app/  
**Vercel production build checked:** READY at Git commit **c5b4c453f26082ac25fe826ac9a5b2f5dec16eea** on main. Vercel metadata confirmed the deployment and alias, but the live UI could not be independently interaction-tested during this review. A green build means a successful deployment, **not** valid anatomy.

**Stacked merges matter:** PR #5 was merged into the research branch just before PR #4 brought that branch into main. Therefore the **FAFB neuronal bifurcation and H01 vascular-fork work from PR #5 is already present in deployed source**, even though PR #5 did not target main directly. PRs **#6–#8** are marked merged but were merged **into subsequent research branches**; they are **not yet part of the production main history** reviewed here. Always verify deployed commit ancestry and actual assets rather than reading GitHub “merged” badges as “live.”

| Case | Specific evidence | Current interpretation |
| --- | --- | --- |
| Synthetic Y-shaped duct — [PR #3](https://github.com/adriandarian/3D-histological-reconstruction/pull/3) | 32 simulated, already-aligned sections; graph recovers split and tips; Dice **0.9923** | **Controlled implementation success**. Does not validate deformation, stains or anatomical generalization |
| Roy pancreas H&E — [dataset review](docs/DATA.md) | 36 real images; bright cavity persists over sections 6–15; physical Z spacing unknown; 3 held-out landmarks mean residual **14.1 preview px** | Unconfirmed duct/vessel identity; no calibrated volumetric measurement or independently supported topology |
| H01 human cortical capillary EM — [PR #4](https://github.com/adriandarian/3D-histological-reconstruction/pull/4), [report](docs/H01_CAPILLARY.md) | 32 EM planes; 31/31 expected principal links at IoU 0.50; Dice **0.8858** vs stationary seed **0.8789**; **21 extra links**, 5 extra splits, 4 extra merges | Shows real source-linked capillary correspondence, but limited gain over trivial baseline and concerning false topology; no reference branch in window |
| FAFB fly-neuron bifurcation EM — [PR #5](https://github.com/adriandarian/3D-histological-reconstruction/pull/5), [report](docs/REAL_BIFURCATION.md) | 25 consecutive EM planes; both human-traced daughters supported at 17/17 and 16/16 reference points, separate for 8 planes; stationary mask does not resolve a split | Strongest current positive **topology control**, but EM rather than H&E, reference is sparse centerline data, membrane boundaries unadjudicated |
| H01 human vascular-fork candidate — [report](docs/H01_VASCULAR_FORK.md) | Two downstream profiles seen; 15 transitional planes uncertain | The actual vascular junction remains **unverified** |
| CODA lung H&E — [PR #6](https://github.com/adriandarian/3D-histological-reconstruction/pull/6), [acquisition](docs/CODA_LUNG.md) | 20 retained lung slides with scanner XY calibration and nominal 10 µm sample interval; first slide published outline; candidate reaches all 19 later AI-reader points and has adjacent-mask overlap | Promising **candidate**, not independent downstream identification. The points are not expert adjudication and continuity is favored by algorithm design. Research branch only |
| CODA pathology-review preparation — [PR #7](https://github.com/adriandarian/3D-histological-reconstruction/pull/7) | Native H&E reading packet and frozen candidate prepared | **Independent qualified review pending**. Research branch only |
| TCIA prostate H&E tumor interpolation — [PR #8](https://github.com/adriandarian/3D-histological-reconstruction/pull/8) | Held-out pathologist-contoured C/E levels: interpolation Dice **0.0091 / 0.0000**, nearest-anchor baseline **0.0434 / 0.0625** | **Important negative finding**: sparse-level smooth interpolation fails tumor localization. Keep as a failed experiment, not an apparent success. Research branch only |

**Bottom line:** The technology for linked 2D/3D navigation and an EM branching experiment is progressing. **A real gland, duct, or vessel connection in ordinary serial H&E has not yet been independently established**; nor has a 2D-vs-3D reader benefit been demonstrated. The current production code is ahead of the early plane-stack demo, but behind the latest research branch experiments.

## 5. The next decisive experiment: real H&E anatomical continuity

**First target:** A preselected, published bronchiole/duct/gland/vessel profile from a permitted, calibrated series of ~20–50 retained H&E slides; the existing CODA lung candidate is the natural first choice. The published CODA window contains alternating retained slide IDs and only one publisher-annotated slide, so it needs new independent downstream reference labels. If qualified review is unavailable, choose a different suitably annotated dataset rather than claiming success.

### Required experimental design

1. **Freeze the target before scoring:** source slide identifiers and hashes, crop, stain, section list, source-image permissions, X/Y pixel size, actual or nominal Z interval, registration parameters, predicted masks and graph, and code revision.
2. **Obtain independent blinded readings:** ideally two qualified pathology/histology experts marking the same structure in original slide coordinates through the window, including parent/daughter identities, nearby competitors, apparent joins, tears and abstentions. Record inter-reader disagreement and documented adjudication. A second AI reader is **not** a replacement for expert ground truth.
3. **Verify registration separately:** score unused landmarks near the target and distributed through depth, with absolute errors (µm only if calibrated), drift and sensitivity to alternative plausible transformations. Inspect badly folded or missing tissue, not just correlations.
4. **Score two different questions:** (a) where is the structure? per-plane Dice/IoU or boundary distances when annotated; (b) what actually connects? reference edges, false links, missed links, false splits, missed bifurcations, and unresolved intervals with denominators.
5. **Compare meaningful baselines:** stationary/transported seed, nearest existing section and simple interpolation; use disrupted/missing-cut controls to expose false continuity.
6. **Audit every claimed connection:** clicking an edge should show **both measured source sections**, coordinates, predicted and independent contours, registration QA and explicit uncertainty. Present interpolation or AI-generated material in a separate layer.
7. **Publish positive and negative cases:** report ambiguous transitions and null results; do not cherry-pick the easiest continuous profile.

### Scientific gate to label the result “independently supported H&E continuity”

- Real, ordered, source-auditable, appropriately permitted and calibrated serial H&E data.
- Frozen pre-evaluation target/predictions with independent qualified identity and adjacency review.
- Every claimed join/split supported by reviewed section evidence or marked unresolved.
- Registration uncertainty measured and reflected in topology confidence.
- False joins and baseline comparisons reported alongside positive matches.
- Reproducible processing and a source-linked viewer demonstrating the **same** frozen finding.

One passing case shows **specimen-specific feasibility**, not population-level accuracy or clinical utility. Repeat across held-out blocks and more difficult anatomies before general claims.

## 6. How to establish added value over 2D

After we have adjudicated H&E cases, run a reader experiment:

- **2D-only condition:** full serial slide series with high-quality navigation.
- **2D+3D condition:** the *same measured slides* plus aligned volume and evidence-linked anatomy.
- Randomize/counterbalance order across readers and specimens; reference remains hidden.
- Predefine correct vs incorrect connectivity judgment and **false joins** as primary outcomes. Track time, confidence and warranted abstention.
- Use multiple independent specimens and account for reader/case variability. Publish statistical uncertainty, including if 3D adds no measurable advantage.

Comparing 3D to one isolated 2D image is not an adequate scientific test; its proper baseline is **careful serial 2D review**.

## 7. Milestones with evidence gates

| Stage | Milestone | Required exit evidence |
| --- | --- | --- |
| **M0: Deployment truth** | Reconcile stacked PRs and integrate selected research cases to main through reviewed changes; verify source/data licensing and Vercel SHA | Public dataset selector and cases correspond to production; no local-only or restricted image redistribution |
| **M1: 3D mechanics** | Synthetic registration, volume rendering, orthogonal sections, linked coordinates, segmented branching mesh | Known synthetic geometry/topology and negative controls pass (largely achieved) |
| **M2: Verified H&E structure** | Frozen real serial H&E target, independent reviewer contours and identity links, registration QA | Measured-source evidence and error/false-link accounting support a specific biological connection |
| **M3: Cross-specimen reliability** | Independent blocks/structures, easy and hard positives, negatives and artifacts | Distribution of topology and geometry errors, not just one success or cherry-picked ROI |
| **M4: Reader utility** | Controlled 2D vs 2D+3D evaluation | Demonstrated benefit, or an explicitly reported null/negative result |
| **M5: 300+-section WSI scale** | Tile-based registration, chunked multiscale OME-Zarr or equivalent, source WSI OpenSeadragon links, ROI streaming | Retained spatial accuracy across Z plus measured RAM/VRAM, load, frame and source-link latency |
| **M6: Learning-assisted methods** | AI registration, correspondence, segmentation or missing-section estimation on held-out tissue | Outperforms non-AI baseline while controlling false joins; inferred material always distinguishable |

These are scientific **gates**, not dates, PR-count commitments or promises.

## 8. Standard report required for each research case

Every new case must state:

- **Data provenance:** specimen/block or non-identifying case, stain, file hashes, scanner resolution, retained order, Z interval, known missing slices, redistribution rights.
- **Processing:** rigid/deformable registration, transform convention, masks, segmentation source, training/validation isolation, pipeline version and reproducible commands.
- **Reference quality:** independent vs training-derived annotations, reader qualification, blinded protocol, per-plane/edge coverage, ambiguous regions.
- **Geometry:** landmark error, deformation uncertainty, physical units or explicit lack thereof, errors versus depth.
- **Biological topology:** true/false/missed links, branch/split/merge errors, graph definitions and uncertainty denominators.
- **Baselines:** motionless/nearest mask and simple interpolation where appropriate, plus negative controls.
- **Viewer audit:** native source-coordinate traceability, measured/registered/interpolated/predicted differentiation, access to raw pixels and both sides of a claimed link.
- **Result quality:** limitations, failures, actual tests executed, reproducibility, graph/region metrics and source links.

High Dice **alone** is insufficient. H01's stationary baseline and extra links, and the TCIA prediction's very low held-out Dice, are reminders to treat convincing pictures as *hypotheses* until independently tested.

## 9. Architecture requirements that directly support the goal

- An offline, reproducible **scientific pipeline** separate from the website, with checksum-linked case outputs.
- High-resolution **2D measured source navigation** (OpenSeadragon or equivalent) plus **3D volume/mesh inspection** (Three.js or equivalent), synchronized by source coordinates and physical section index.
- A **connection evidence inspector** showing source sections on both sides of any claimed edge, independent labels, registration error and uncertainty.
- Clear layers for measured, registered, segmented, display-interpolated and AI-predicted data. Never imply unknown Z is calibrated.
- Multiscale storage (OME-NGFF/OME-Zarr or interoperable alternatives) and ROI/chunk streaming for 300+ WSI volumes.
- A case selector that distinguishes **published on Vercel** from **local-only or research branch**, and states licensing/provenance.
- Performance budgets with representative hardware and repeatable measurements, not solely a green Vercel build.

## 10. What to do next

1. **Confirm and integrate the research stack deliberately:** PR #5 is in production via PR #4 ancestry; PRs #6–#8 are not. Review their merge ancestry, tests and licenses before promoting CODA/TCIA features. Do not confuse “merged” with “deployed.”
2. **Finish the CODA H&E independent reading:** complete the frozen 20-section bronchiole review packet prepared in PR #7, with qualified adjudication of uncertain sections. If necessary, select another properly labeled calibrated H&E window.
3. **Measure H&E false topology:** build the adjudicated connection graph; evaluate registration errors, false joins and simple baselines before claiming a true 3D junction.
4. **Keep the TCIA negative control:** investigate the collapse in held-out Dice without using those same withheld pathologist contours to tune and then claim an independent success.
5. **Only then run a reader comparison** to test whether linked 3D changes what a reader can correctly establish.
6. **Then extend to hundreds of slides** and consider uncertainty-aware learning, including Lila MOSAIC-style multimodal objectives, if independently measured improvements justify it.

## 11. Research and project references

- [Original POC plan](docs/POC_PLAN.md)
- [Research direction and reader-study proposal](docs/RESEARCH_DIRECTION.md)
- [Evidence and reproducibility index](docs/PROJECT_GUIDE.md)
- [Synthetic volume methods](docs/VOLUME_RECONSTRUCTION.md)
- [H01 capillary](docs/H01_CAPILLARY.md)
- [FAFB neuronal bifurcation](docs/REAL_BIFURCATION.md)
- [H01 fork uncertainty](docs/H01_VASCULAR_FORK.md)
- [CODA lung acquisition](docs/CODA_LUNG.md)
- [PR #6: CODA H&E bronchiole](https://github.com/adriandarian/3D-histological-reconstruction/pull/6)
- [PR #7: pathology review protocol](https://github.com/adriandarian/3D-histological-reconstruction/pull/7)
- [PR #8: failed TCIA tumor interpolation](https://github.com/adriandarian/3D-histological-reconstruction/pull/8)
- [CODA study](https://www.nature.com/articles/s41592-022-01650-9)
- [VALIS](https://valis.readthedocs.io/en/stable/)
- [OME-Zarr](https://ome-zarr.readthedocs.io/en/stable/)
- [Lila Sciences MOSAIC inspiration](https://www.lila.ai/news/seeing-molecules-from-any-direction)

---

### Standing decision rule

**A merged PR, green deployment, high Dice, beautiful ray-marched volume or source-linked 3D mesh is not, by itself, an anatomical discovery.** Promote a claim only when it passes its evidence gate. Preserve failed experiments and unresolved connections as first-class results.

**The destination remains: trustworthy, measurable 3D anatomy reconstructed from conventional serial H&E pathology slides — with proof of what the extra dimension adds.**
