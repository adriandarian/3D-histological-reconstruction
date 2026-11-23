# Proof of Concept: 3D Histological Reconstruction from Serial Sections

**Repository:** [adriandarian/3D-histological-reconstruction](https://github.com/adriandarian/3D-histological-reconstruction)  
**Document status:** Research-backed implementation proposal, 2026-11-22  
**Scope:** Research/engineering visualization POC only; not validated for diagnosis, clinical decisions, or patient care.

## 0. Executive summary

**Goal:** Turn a physically ordered collection of 2D histology sections from the **same tissue block** into a browsable 3D tissue volume. Provide a synchronized 2D view familiar to a digital pathology engineer (OpenSeadragon) and an interactive 3D view (Three.js / a reference volume viewer). Distinguish actual stained/scanned sections from algorithmically warped, interpolated, or predicted content.

**Recommended narrow first deliverable:** Use **30–50 adjacent sections** from an openly available small-image serial histology dataset. Build a reproducible CPU-first Python registration pipeline, export a 3D stack with metadata, and render selectable XY sections plus 3D tissue/segmentation geometry in a browser. Add explicit numerical and visual registration QA. Do **not** begin with 300 full-resolution WSIs or an AI model.

**Most useful first dataset:** [Roy et al., Serial Section Histopathology Image Dataset (Mendeley Data, DOI 10.17632/fzskwpzs5j.1)](https://data.mendeley.com/datasets/fzskwpzs5j/1), distributed under **CC BY 4.0**. It describes colon series of 48 images at 10× and 48 at 40×, plus pancreas series of 36 at 10× and 36 at 40×; RGB TIFFs are 1280×960. **Choose one tissue and one magnification first**. Double-check pairing, physical order, pixels-per-micrometer, cut thickness, and whether any sections are missing. The two magnifications do **not** necessarily represent distinct physical sections.

**Baseline scientific result:** CODA already reconstructed tissue from serial H&E sections at cellular scale. This POC's novelty should be in **reproducible data engineering, honest uncertainty/QA, and an accessible synchronized web experience**, not in claiming to invent 3D histology.

## 1. Scientific motivation and what this is *not*

A standard histology slide shows a thin 2D slice of a 3D structure. If a tissue block is sectioned repeatedly and each slice is stained and scanned in order, the slices sample successive depths in the original tissue. Registration plus stacking reconstructs an **estimate** of the source volume. It can help a viewer follow blood vessels, glands, ducts, nerves, stroma, and tumor boundaries between sections.

A tissue block **could** yield 300 sections, but there is no universal cut count. It depends on physical block depth, section thickness, interval between retained sections, missing/damaged sections, and other laboratory factors. A *section index* is not automatically a micrometer coordinate.

Example with **300 consecutive sampled slices 4 µm apart**:

| Quantity | Example |
|---|---:|
| Recorded X/Y sampling (40× example) | 0.25 µm/pixel |
| Z sampling interval | 4 µm per sampled section |
| Voxel spacing (Z,Y,X) | (4, 0.25, 0.25) µm |
| Nominal sampled depth | approximately 1.2 mm |
| Z vs X/Y spacing ratio | 16:1 |

A voxel **one array index** thick in Z still represents a 4 µm sampling step; it is **not** a 1 µm-thick physical voxel. The actual cut thickness and center-to-center sampling interval can differ: for example, processing every third 4 µm cut gives approximately 12 µm sampling intervals. Treat depth as a physical coordinate, not an inferred image pixel count.

Also distinguish:

- **Measured:** a real scanned, retained section.
- **Registered:** the measured image spatially warped into a common coordinate frame.
- **Interpolated:** a display-only image estimated between measured sections.
- **Inferred/generative:** a model prediction of unobserved anatomy or a stain/modality.

A visually smooth 3D surface is **not** proof of anatomical accuracy. Thin structures might appear, disappear, branch, or tear between slices. A transformed stack cannot restore missing physical material by itself.

### Relationship to Lila Sciences MOSAIC

The triggering inspiration was [Lila Sciences, “Seeing molecules from any direction” (Nov. 20, 2026)](https://www.lila.ai/news/seeing-molecules-from-any-direction), describing [MOSAIC, “Every Measurement, Every Direction, All at Once” (arXiv:2611.22098)](https://arxiv.org/abs/2611.22098). MOSAIC learns any-to-any translation across molecular structure and IR, UV, and Raman spectral data. **It does not generate 3D histology or solve registration.** It is relevant only as an *experimental downstream training objective*: learn from paired H&E/IHC/spatial measurements and observed neighboring sections, with held-out testing and visible uncertainty.

**Decision:** No foundation model or synthetic sections in POC v1. Add that work only after the non-AI reconstruction and QA baseline succeeds.

## 2. Evidence and existing research

| Work | What it demonstrates | POC use / caution |
|---|---|---|
| [CODA, Kiemen et al., Nature Methods 2022](https://www.nature.com/articles/s41592-022-01650-9) and [open access manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC10500590/) | Serial H&E registration, 3D tissue reconstruction and cell/tissue analysis; in the study, 0.5 µm lateral and 4 µm section spacing are described | Strong scientific baseline; main code involves MATLAB, so do not assume a drop-in Python dependency |
| [CODA code](https://github.com/ashleylk/CODA) and [usage guide](https://labs.pathology.jhu.edu/kiemen/wp-content/uploads/sites/39/2023/12/Instructions-for-applying-CODA.pdf) | Complete reference pipeline and a separate **150-image lung** example | Lung example is 20× NDPI, approximately 0.5 µm/pixel and **10 µm section intervals**; acquisition/downloading and licenses should be checked |
| [VALIS, Gatenbee et al.](https://valis.readthedocs.io/en/stable/) | Rigid and nonrigid registration of WSI series; deformation QA and full-resolution warping | Strong candidate for later WSI phase; compare with simpler OpenCV registration first |
| [VALIS installation](https://valis.readthedocs.io/en/stable/installation.html) | Python, native image libraries, Java/Bio-Formats setup | Its stable docs target **Python 3.9/3.10** and extra system dependencies; isolate in a dedicated environment/container if selected |
| [RAPID, Schouten et al., Scientific Reports 2026](https://www.nature.com/articles/s41598-026-46776-4) and [source](https://github.com/computationalpathologygroup/rapid) | Feature-based registration of gigapixel pathology sections, including sparse prostatectomy sections | Comparative/phase-3 option; published workflow includes GPU-focused Docker instructions. Do not assume the sample dataset is already downloadable |
| [OME-NGFF / OME-Zarr](https://ome-zarr.readthedocs.io/en/stable/explanation/ome_ngff_overview.html) | Multiscale 2D/3D microscopy arrays, axes, units, transforms and label data | Recommended durable, interoperable volume output after first NumPy proof |
| [Vol-E](https://vole.allencell.org/) and [its React/Three.js code](https://github.com/allen-cell-animated/vole-app) | Browser 2D slice and 3D volume visualization with OME-Zarr support | Use as a rendering benchmark or potential integration; check format and licensing before reuse |
| [Neuroglancer](https://github.com/google/neuroglancer) | Mature scalable browser viewer for volumetric data / Zarr | External reference for cross sections, chunking and navigation; not necessarily needed for first UI |
| [OpenSeadragon viewport coordinates](https://openseadragon.github.io/examples/viewport-coordinates/) | Conversion between image, viewport and browser coordinate spaces | Essential for linking the selected image point to the correct physical 3D location |
| [Three.js Data3DTexture](https://threejs.org/docs/pages/Data3DTexture.html) | WebGL 3D texture primitive | Option for a small browser-held volume; not a whole-slide streaming solution |

Published data/method details are not interchangeable. In particular, CODA's 4 µm clinical sections and 10 µm-spaced lung example are **different acquisition protocols**; never transfer their spacing metadata to another dataset.

## 3. Data sources: recommended priority

### A. Start here — Mendeley 2D serial histology dataset

- **URL:** https://data.mendeley.com/datasets/fzskwpzs5j/1
- **DOI:** 10.17632/fzskwpzs5j.1
- **Reported contents:** Colon: 48 @ 10× plus 48 @ 40×; pancreas: 36 @ 10× plus 36 @ 40×; RGB TIFF 1280×960.
- **Reported license:** CC BY 4.0; keep attribution to Roy, Gupta, and Goswami.
- **Why:** Manageable size and uncomplicated TIFF loading; suitable to validate registration and browser interaction before WSI scaling.
- **Before ingestion:** Verify numeric order; ensure a set comes from the same block and magnification; inspect duplicated/blank/misaligned images; look for documented physical pixel resolution, section interval and section thickness. If physical Z spacing is unavailable, treat Z as **section index** and label geometry **illustrative—not metrically calibrated**. The page alone does not establish all of this metadata.
- **Download policy:** Put original downloaded data in local ignored storage; do not commit large third-party images to the repo.

### B. Follow-up — CODA lung example

- **CODA guide:** https://labs.pathology.jhu.edu/kiemen/wp-content/uploads/sites/39/2023/12/Instructions-for-applying-CODA.pdf
- **Linked sample folder from CODA instructions:** https://drive.google.com/drive/folders/1K-wY_ArVGbEhebQD4AjOeERwx6-4Fw3G?usp=sharing
- **Reported contents:** 150 ordered 20× Hamamatsu NDPI lung section images, approximately 0.5 µm/pixel, spaced 10 µm apart, with annotations in the demonstration.
- **Why:** True serial WSI-style acquisition for later validation.
- **Cautions:** May be substantially larger; linked availability and permissions must be checked at download time. CODA's original pipeline uses MATLAB/toolboxes; borrowing ideas is different from running it unmodified.

### C. Advanced — RAPID sample case

- **Code:** https://github.com/computationalpathologygroup/rapid
- **Paper:** https://www.nature.com/articles/s41598-026-46776-4
- **Status at this document's date:** Repository text says the sample dataset will be provided on Zenodo, but do not depend on that promise until the actual downloadable asset is verified. Code provides Docker guidance and a CSV/XLSX job overview.

### D. Optional registration benchmarks

- [ANHIR histology image registration benchmark](https://anhir.grand-challenge.org/) — useful for measuring registration quality, **not** automatically a genuine evenly spaced 3D serial volume.
- [ACROBAT registration challenge](https://acrobat.grand-challenge.org/) — H&E/IHC registration benchmark, **not** a substitute for ordered adjacent Z sections.
- [VALIS dataset guidance](https://valis.readthedocs.io/en/stable/) — useful for locating compatible test cases.

## 4. POC architecture

~~~text
Openly licensed serial images + acquisition/section manifest
                       |
                       v
     [Python offline processing pipeline]
    ingest -> metadata validation -> QC/masks
                       |
                       v
       low-resolution registration baseline
        rigid/affine -> optional nonrigid
                       |
                       v
        transform outputs + QA report
                       |
                       v
       warping/cropping to common XY frame
                       |
                       v
     3D image array + segmentation/mask array
                       |
                       v
  [MVP: PNG/NumPy/JSON] -> [Later: multiscale OME-Zarr]
                       |
                static/API hosting
                       |
                 [Web application]
                 /              \
     OpenSeadragon (2D)     Three.js (3D)
          \                    /
             shared XYZ, Z index,
             transform + selection state
~~~

**Separation of concerns:** No registration during browser interaction. The Python pipeline owns image geometry and QA. The frontend reads precomputed, versioned assets and never silently turns an inferred voxel into measured data.

### Proposed repository structure (planned; not yet implemented)

~~~text
3D-histological-reconstruction/
├── README.md
├── docs/
│   └── POC_PLAN.md
├── data/
│   ├── README.md                   # Sources, licenses and acquisition instructions
│   └── raw/                        # Git-ignored; downloaded slides
├── examples/
│   └── manifest.example.json
├── pipeline/
│   ├── pyproject.toml
│   ├── src/historecon/
│   │   ├── ingest.py               # Sort, validate, import
│   │   ├── preprocess.py           # RGB normalization/tissue mask
│   │   ├── register.py             # Reference, rigid, affine, optional deformable
│   │   ├── qa.py                   # Plots, landmarks, failure flags
│   │   ├── reconstruct.py          # Spaced (Z,Y,X) volume + labels
│   │   └── export.py               # PNG/JSON, OME-Zarr later
│   └── tests/
│       ├── test_synthetic_transforms.py
│       └── test_coordinates.py
├── viewer/
│   ├── package.json
│   └── src/                        # React + TypeScript + OpenSeadragon + Three.js
└── outputs/                        # Git-ignored; generated datasets
~~~

The structure is a recommendation, **not** an assertion that those files or features already exist.

## 5. Data contract and coordinate system

### Metadata that must be captured

| Field | Requirement |
|---|---|
| Dataset/case/block ID | Stable, non-identifying research identifier |
| File path and checksum | Enables reproducible processing |
| Section order | Integer, **not** locale-sensitive filename sorting |
| Retained section index and missing indices | Separate actual cuts from images available to us |
| Section thickness (µm) | Report only if measured/documented |
| Slice center Z / sampling interval (µm) | Must distinguish cut thickness and image-to-image interval |
| Pixel size X and Y (µm/px) | From calibrated scanner metadata or trusted acquisition records |
| Original image size and orientation | Width, height, flip/rotation conventions |
| Stain and imaging protocol | H&E, IHC, color space, scanner, magnification |
| Image registration transform | Reference section, affine matrix and optional deformation field |
| QA | Pairwise score, failed/flagged sections, manual audit outcome |
| Provenance | Dataset DOI/URL, original license, algorithm/package versions and config |
| Per-voxel provenance | Measured/warped vs interpolated vs model-predicted |

Illustrative manifest (values explicitly **examples, not Mendeley metadata**):

~~~json
{
  "dataset_id": "synthetic-demo",
  "license": "generated-synthetic",
  "stain": "H&E-like synthetic",
  "coordinate_convention": "z-y-x, micrometers, pixel centers",
  "pixel_size_um": {"x": 0.5, "y": 0.5},
  "section_thickness_um": 4.0,
  "section_interval_um": 4.0,
  "sections": [
    {"section_id": "s000", "index": 0, "z_um": 0.0, "path": "raw/s000.tif", "status": "measured"},
    {"section_id": "s001", "index": 1, "z_um": 4.0, "path": "raw/s001.tif", "status": "measured"}
  ]
}
~~~

If Mendeley (or another dataset) lacks physical calibration, replace unavailable values with **null** and use a "section-index-only" mode; never fill in CODA values or default to 1 µm/pixel and present the result as physical truth.

### Coordinate mapping

Canonical array order: **(z, y, x)** for scalar labels or **(z, y, x, 3)** for RGB. For a calibrated, regularly spaced stack:

~~~text
physical_x_um = (image_x_px + 0.5) * pixel_size_x_um
physical_y_um = (image_y_px + 0.5) * pixel_size_y_um
physical_z_um = recorded_z_um[section_index]

volume shape = (number_of_sections, height_px, width_px)
~~~

Define origin, row direction, and pixel-center convention once; document any Y-axis flip required by Three.js. Registration transformations must be invertible/traceable back to original source slide coordinates for UI selections. For nonuniform Z positions, preserve an explicit per-section Z array or carefully resample into a *labeled derived volume*, never pretend Z spacing is uniform.

For OpenSeadragon, convert between native image and viewport positions using the appropriate TiledImage conversion APIs, then apply the saved registration transform to reach the common XY space. The shared frontend state should store **physical or registered image coordinates**, not DOM pixels.

## 6. Processing pipeline — practical algorithms

### Stage 1: Ingestion and QC

1. Manually download one Mendeley series (e.g., pancreas at 10×). Preserve attribution/license and original filenames.
2. Enumerate TIFFs; inspect image sizes, RGB channels, dtype and orientation. Determine whether filename sort matches actual section order; override with explicit manifest if needed.
3. Detect repeated scans, missing indices, blank sections, folded/torn tissue, heavy stain variation, dust or markings.
4. Generate a contact sheet with labeled indices and a tissue-area plot. Preserve unaltered originals.
5. Normalize only what is necessary for matching; keep the original RGB pixels for side-by-side viewing.

Suggested Python packages: **numpy, scipy, tifffile, Pillow, OpenCV, scikit-image, matplotlib, pytest**. Use a lightweight Python virtual environment; add Dask/Zarr/OME-Zarr only when exports demand them.

### Stage 2: Tissue masking

H&E brightfield images have mostly white background. A naïve RGB volume render can make background opaque and hide everything. Generate tissue foreground masks (e.g., HSV saturation/brightness or Otsu after carefully chosen optical-density processing). Check the mask against representative slides. Keep raw RGB slices in the 2D viewer, but render **tissue opacity, a scalar hematoxylin/optical-density channel, or semantic segmentation** in 3D.

### Stage 3: Registration (baseline first)

Run an incremental comparison:

1. **No registration:** Stack sections as acquired; generate baseline overlay animations and metrics.
2. **Translation/rigid registration:** Estimate translation and rotation using phase correlation, normalized grayscale, or feature matching; robustly reject mismatches.
3. **Affine registration:** Try ORB/SIFT-like keypoints + RANSAC, or enhanced correlation coefficient (ECC), for mild scale/shear differences.
4. **Deformable registration (optional):** Trial VALIS or a constrained B-spline/flow approach *only after* examining affine outcomes. Record deformation fields and visually inspect whether tissue architecture is being distorted.

Choose the **middle slice** as the reference, align toward it, and check accumulated drift. Optimize at low resolution and apply transformations to selected higher-resolution tiles only later. Keep transforms, source/moving/fixed IDs, method and parameters as reproducible artifacts.

**Failure mode:** Strong overlap after overaggressive deformable alignment can be misleading: a real branch present on only one section should not be warped into a false connection. Mask tears and missing material instead of "healing" them without disclosure.

### Stage 4: Reconstruct

- Warp/crop each measured slice into a common XY canvas.
- Stack in correct section order. Keep mask/background/invalid-pixel data distinct.
- Preserve physical pixel and Z spacing; write acquisition metadata in a sidecar.
- Build an initial scalar tissue-opacity / segmentation volume for 3D rendering.
- Support simple orthogonal XY/XZ/YZ section inspection first.
- Optionally extract a surface mesh from a validated tissue mask with [scikit-image marching cubes](https://scikit-image.org/docs/stable/api/skimage.measure.html#skimage.measure.marching_cubes). Set mesh vertex scale using actual voxel spacing, not array indices.

**Important:** Surface geometry derived from a tissue/noise mask is not equivalent to correctly segmented vessels or tumor. Organ-specific semantic segmentation is a separate research task.

### Stage 5: Export

For the tiny POC:
- Original TIFFs local only.
- Warped PNGs / thumbnails or TIFFs, a compact NumPy stack, registration transforms, QA JSON and image overlays.
- A strict JSON manifest for the frontend, with file source, Z index, units and display provenance.

For WSI-scale and interoperability:
- Prefer **OME-Zarr** (OME-NGFF), with named axes, accurate physical scales, multiscale image pyramids and associated label arrays.
- Review [OME-Zarr writer API](https://ome-zarr.readthedocs.io/en/stable/api/writer.html), [OME-Zarr Python tools](https://ome-zarr.readthedocs.io/en/stable/) and [NGFF validator](https://ome.github.io/ome-ngff-validator/).
- Verify whether a consuming viewer supports OME-Zarr v0.4 or v0.5; currently ome-zarr-py commonly defaults to v0.5 while not every viewer supports all versions.
- Chunk for actual display access patterns; do not materialize a huge dense WSI stack in frontend memory.

## 7. Browser POC

### Recommended stack

- **Frontend:** Vite + React + TypeScript.
- **2D:** OpenSeadragon with original/registered section switch, synchronized Z slider, pan/zoom, pointer coordinates, and tissue/annotation overlays.
- **3D:** Three.js with constrained memory footprint, orbit camera, XY clipping plane and an opacity-controlled label/tissue volume or surface mesh.
- **Controls:** section slider, registered/unregistered toggle, synchronized crosshair, axis orientation, physical scale indicator when calibrated, tissue visibility, overlay opacity, QA badge per section.
- **Backend:** First version can load precomputed **static** JSON/images and small 3D assets. A FastAPI data service and chunk streaming are future work, not POC prerequisites.
- **Reference viewer:** Test the same export in Vol-E or Neuroglancer to check whether interpretation bugs are in the pipeline or custom renderer.

### Interaction contract

1. Selecting Z = N shows **actual** section N in the 2D view, not a generated intermediate.
2. Clicking at (x,y) in 2D transforms the location into registered common XY coordinates and marks it on the 3D slice plane.
3. Selecting a 3D position jumps to its nearest **measured** section; if between slices, the UI states that it was snapped.
4. 2D pan/zoom and 3D camera interaction are independent; the **sampled physical point and plane** remain shared.
5. Missing/unusable sections are displayed as gaps (or optional distinctly styled interpolation), never silently omitted and renumbered.
6. A 3D object tooltip reports source section(s), stain, effective resolution and whether geometry is measured, registered, interpolated or predicted.

### Rendering practicality

Small image volume estimate for **36 × 1280 × 960 RGB uint8**: about **133 MB decimal (127 MiB)** uncompressed, before GPU copies, masks and pyramids. For a 40× WSI assumed to be **80,000 × 60,000 × 3 channels**, one section is approximately **14.4 GB** uncompressed and 300 sections approximately **4.32 TB**. These are hypothetical dimensions and raw-memory estimates, not scanner-independent norms.

- Start with < 512 px XY / 30–50 slices rendered in GPU, and stream/select bigger 2D tiles separately.
- Use downsampled volume textures, ROI cropping and levels of detail; keep separate source-resolution 2D inspection.
- Prefer segmented surface geometry if direct optical-density volume rendering is awkward.
- Investigate [Three.js Data3DTexture](https://threejs.org/docs/pages/Data3DTexture.html), but confirm browser, shader and GPU support.
- Do not assume CUDA: a Windows AMD Radeon RX 6950 XT / Mac M2 workflow should begin with a **CPU-viable baseline**. RAPID's published Docker example uses CUDA-style GPU flags; account for platform compatibility separately.

## 8. Minimal local setup (instructions to implement, not commands already tested for this repo)

~~~bash
git clone https://github.com/adriandarian/3D-histological-reconstruction.git
cd 3D-histological-reconstruction

# Suggested initial Python prototype environment (actual pipeline is not yet committed).
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell alternative:
# .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install numpy scipy tifffile pillow opencv-python-headless scikit-image matplotlib pytest

# Proposed frontend setup (not yet committed):
# pnpm create vite viewer --template react-ts
# cd viewer
# pnpm add openseadragon three
# pnpm add -D @types/openseadragon @types/three
~~~

Prefer a dedicated environment for VALIS if you later use it; follow its current Python and native-library compatibility guide rather than mixing it into the minimal environment above.

**Suggested future CLI contract** (illustrative; these commands **do not exist yet**):

~~~bash
python -m historecon ingest --manifest examples/manifest.json --out outputs/case-001
python -m historecon register --case outputs/case-001 --method affine
python -m historecon qa --case outputs/case-001 --out outputs/case-001/qa
python -m historecon export --case outputs/case-001 --format web-static
~~~

## 9. Acceptance criteria and testing

A compelling 3D image is not enough. Minimum POC "done" criteria:

| Area | Acceptance criterion |
|---|---|
| Reproducibility | A clean run on the same input, manifest and versions produces equivalent transforms, output dimensions and QA metrics |
| Data integrity | Every original and resulting section is traceable by ID; missing sections and unknown physical units stay explicit |
| Correct registration | Manual landmark target registration error (TRE) improves **at least 50% vs the unregistered baseline**, on a prespecified set of representative adjacent pairs. Report pixel error; report µm only if calibrated |
| Gross failures | Independently inspect at least 10 adjacent pairs distributed throughout the stack, and flag every obvious fold/tear/non-overlap/registration failure rather than hiding them |
| Coordinate correctness | Known synthetic x/y/z points map into the right crosshair and return to the same registered location within a small numerical tolerance |
| 3D coherence | Orthogonal sections and the reconstructed surface show no accidental transpose, flip, reversed Z order or aspect-ratio distortion |
| Viewer | Keyboard/mouse Z navigation, correct 2D source image, 3D orbit, synchronized selected point, visible units/provenance and registered/unregistered comparison |
| Performance | The selected local ROI loads and interacts without memory crashes on the target developer machine; log dataset size, CPU/RAM/GPU and initialization times |
| Independent check | Open exported data in a separate viewer or inspect a checksum/sampled array values independently of the custom frontend |
| Safety | No patient-identifiable data, unauthorized proprietary slides, or unsupported clinical claims in repository or demo |

The **50% TRE improvement** is a *proposed engineering milestone*, not a published diagnostic accuracy standard; record absolute TRE and unsuccessful cases as well. Dice/SSIM alone may reward incorrect deformation or simply preserve a large mask overlap; use landmarks and visual review together.

### Tests to write first

- Synthetic image with known translation/rotation/affine transform: estimated inverse transform is correct within tolerance.
- File order is numeric, not lexicographic (e.g., section 2 precedes section 10).
- Duplicate IDs, missing indices, conflicting resolutions, missing physical units and zero-sized images fail clearly.
- Warp transform round-trips selected synthetic points.
- Pixel-to-micrometer-to-pixel mapping including pixel centers, Y flip, Z gaps and nonuniform sections.
- Volume array order (Z,Y,X) and channel placement are explicit; no axis swap.
- Known synthetic 3D vessel/branch remains connected with appropriate sampling, without fabricated branches.
- Foreground mask and 3D opacity exclude blank background.
- Web UI crosshair and slide selection are consistent between 2D and 3D.

## 10. Delivery sequence / backlog

### Phase 0 — Dataset and scientific constraints
- [ ] Download one specific Mendeley series; document exact files, acquisition provenance and licensing.
- [ ] Determine whether true sequential sections and physical section interval are confirmed. If not, maintain **section-index-only demo** status.
- [ ] Create source manifest, contact sheet, checksum list and initial QC labels.
- [ ] Commit only **manifest templates, scripts and small generated synthetic test fixtures**, not large slides.

### Phase 1 — Python baseline and measured reconstruction
- [ ] Make deterministic ingestion and tissue masking.
- [ ] Implement unregistered, rigid and affine baselines.
- [ ] Save transforms and before/after checkerboards, overlays and slice animations.
- [ ] Measure landmark TRE and identify failure cases.
- [ ] Export a small aligned (Z,Y,X[,C]) volume plus labels/provenance.
- [ ] Run orthogonal view and orientation checks in Python.

### Phase 2 — Linked web experience
- [ ] Bootstrap TypeScript/React app.
- [ ] Show current 2D section in OpenSeadragon with Z control and scan metadata.
- [ ] Show a small 3D volume/mesh in Three.js.
- [ ] Share a coordinate state across the two viewers.
- [ ] Add clipping plane, opacity/segmentation controls, quality warning and measured-vs-interpolated legend.
- [ ] Record a short demo with the exact dataset version and limitations.

### Phase 3 — Whole-slide scaling
- [ ] Evaluate CODA's lung WSI sample and VALIS for real WSI registration.
- [ ] Replace in-memory full-image warping with tile/ROI-based operations.
- [ ] Export valid multiscale OME-Zarr with correct axes and physical transforms.
- [ ] Test independent rendering in Vol-E / Neuroglancer; profile local GPU and web performance.
- [ ] Review RAPID only if sparse-section or gigapixel matching justifies added complexity.

### Phase 4 — Biological and multimodal research (optional)
- [ ] Acquire permitted validated labels or produce reproducible annotations, e.g. [QuPath GeoJSON](https://qupath.readthedocs.io/en/stable/docs/advanced/exporting_annotations.html).
- [ ] Quantify vessels/ducts/tumor structure in 3D against manual annotations.
- [ ] Compare measured-only, interpolation and an explicit uncertainty-aware generative baseline on held-out sections.
- [ ] Explore any-to-any H&E/IHC/spatial modality training inspired by MOSAIC; label outputs as model predictions and prohibit indistinguishable display from actual images.

## 11. Risks and non-goals

**High-risk scientific gaps:** tissue deformation from microtomy, spatially varying staining, non-consecutive slides, missing/destroyed sections, sampling that misses small structures, gross warp artifacts, uncertain slice spacing, and unverified segmentation. Clarify these before interpreting a volume biologically.

**Technical risks:** giant WSI memory use, naive opaque-white RGB volume rendering, interpolation mistaken for observation, coordinate mismatch between OpenSeadragon and Three.js, browser GPU limitations, library version coupling, and a dataset whose license permits different reuse than expected.

**Governance:** This is a public personal research repository. Avoid PHI, patient data, corporate-owned scans/code, diagnostic claims, and confidential data. Use public samples or appropriately authorized, properly de-identified research data and honor dataset/software licenses. If the project becomes clinical research, establish appropriate permissions, validation, privacy and regulatory review before broader use.

**Explicit non-goals for v1:** 300-slide gigapixel ingestion, automated diagnosis, perfect cell-scale structure recovery, neurally hallucinated missing anatomy, cloud deployment, proprietary slide formats, radiology-pathology fusion, full WSI segmentation, and trying to reproduce MOSAIC itself.

## 12. Research and engineering links (bookmark list)

### Foundational papers and direct inspiration
1. [Kiemen et al., CODA (Nature Methods, 2022)](https://www.nature.com/articles/s41592-022-01650-9) — research foundation.
2. [CODA open-access text and methods (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10500590/) — physical sampling/protocol nuances.
3. [CODA source code](https://github.com/ashleylk/CODA) — example reference implementation.
4. [CODA instructions and lung sample download](https://labs.pathology.jhu.edu/kiemen/wp-content/uploads/sites/39/2023/12/Instructions-for-applying-CODA.pdf) — 150 serial lung scans.
5. [VALIS paper/tool docs](https://valis.readthedocs.io/en/stable/) — registration.
6. [VALIS installation](https://valis.readthedocs.io/en/stable/installation.html) — dependency and Python compatibility.
7. [RAPID paper (2026)](https://www.nature.com/articles/s41598-026-46776-4) and [GitHub](https://github.com/computationalpathologygroup/rapid) — high-resolution and sparse-section reconstruction.
8. [Lila Sciences' MOSAIC explanation](https://www.lila.ai/news/seeing-molecules-from-any-direction) and [MOSAIC preprint](https://arxiv.org/abs/2611.22098) — possible future multimodal ML research, **not a reconstruction algorithm**.

### Data and registration benchmarks
9. [Mendeley Serial Section Histopathology Image Dataset](https://data.mendeley.com/datasets/fzskwpzs5j/1) — recommended POC.
10. [ANHIR](https://anhir.grand-challenge.org/) — histology registration benchmark.
11. [ACROBAT](https://acrobat.grand-challenge.org/) — cross-stain registration benchmark.

### Image/volume tools and formats
12. [OpenSlide](https://openslide.org/) — digital slide reading.
13. [libvips](https://www.libvips.org/) — large-image operations and tiling.
14. [scikit-image](https://scikit-image.org/docs/stable/) — registration/segmentation/measurements.
15. [OME-NGFF specification](https://ngff.openmicroscopy.org/) — multidimensional microscopy metadata.
16. [OME-Zarr Python](https://ome-zarr.readthedocs.io/en/stable/) and [writer API](https://ome-zarr.readthedocs.io/en/stable/api/writer.html) — multiscale volume export.
17. [OME-NGFF Validator](https://ome.github.io/ome-ngff-validator/) — independent metadata validation.
18. [OpenSeadragon docs](https://openseadragon.github.io/docs/) and [coordinate guide](https://openseadragon.github.io/examples/viewport-coordinates/) — 2D high-resolution browser navigation.
19. [Three.js 3D texture docs](https://threejs.org/docs/pages/Data3DTexture.html) — 3D rendering primitive.
20. [Vol-E](https://vole.allencell.org/) and [source](https://github.com/allen-cell-animated/vole-app) — open-source browser volume-viewer reference.
21. [Neuroglancer](https://github.com/google/neuroglancer) — scalable multiresolution 3D navigation.
22. [QuPath annotation export](https://qupath.readthedocs.io/en/stable/docs/advanced/exporting_annotations.html) — labeled ROI transfer and overlays.

## 13. The very next implementation task

**Issue suggestion:** "Build reproducible TIFF serial-section ingestion and registration baseline."

**Inputs:** One specifically documented colon or pancreas series from the Mendeley dataset, with local files and manifest.

**Deliverables:**
1. The proposed Python project skeleton and README for obtaining the public sample data.
2. Ingest/contact sheet with deterministic ordering and explicit unknown-physical-spacing handling.
3. Rigid/affine registration with saved transformations.
4. Side-by-side and overlay before/after artifact for representative sections.
5. Quantitative landmark and mask QC summary with failed cases visible.
6. Small image stack export with a schema that a future 2D/3D viewer can consume.
7. Synthetic transform and coordinate tests passing on CPU.

**Done when:** A second engineer can reproduce the output on downloaded public data, inspect registration objectively, understand provenance and limitations, and hand the export to a browser renderer without changing underlying slide geometry.

---

### Source interpretation notes

References were reviewed for planning as of **2026-11-22**. Exact versions, dataset access, dependencies, and sample licensing can change. Statements labeled **proposed**, **illustrative**, **optional**, or **future** are design recommendations rather than published findings or already-implemented project capabilities.
