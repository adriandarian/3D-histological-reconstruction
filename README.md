# Section Atlas · 3D histological reconstruction

Section Atlas reconstructs structures from serial tissue sections and links each selected surface point to its source image. The WebGL2 workspace provides volume rendering, labeled surfaces, orthogonal reslices, clipping, and independent comparison against source annotations where available.

**Project north star:** [GOAL.md](GOAL.md) defines the scientific mission, current evidence, deployment status, validation requirements, and milestone gates. Start there to distinguish a convincing 3D visualization from trustworthy, independently supported histological anatomy.

The research goal is to determine whether serial H&E slides can establish which tissue structures connect and whether access to the reconstruction improves a reader's judgment. The [research direction](docs/RESEARCH_DIRECTION.md) defines the next H&E experiment and a comparison with conventional serial-slide review.

The [project guide](docs/PROJECT_GUIDE.md) indexes every experiment, its data and units, reproduction commands, validation evidence, and development history. For the two-daughter experiment, start with the [real bifurcation study](docs/REAL_BIFURCATION.md).

Open `?dataset=bifurcation` in the built app to follow both daughters of a manually traced fly projection neuron. The mesh resolves distinct daughter profiles on eight consecutive EM sections. A separate human cortical vascular candidate is available at `?dataset=vascular-fork`. [Vascular evidence and unresolved junction](docs/H01_VASCULAR_FORK.md)

![Measured EM sections with the predicted neuronal boundary and independent daughter annotations](docs/fafb-daughters.png)

## Real capillary validation

Select **H01 cortical capillary** in the volume explorer (or append `?dataset=capillary` to the app URL). Inspect a seeded lumen trace against published, human-corrected annotations on 32 consecutive registered serial EM planes. The viewer links every prediction to its measured image, its position in H01 and the source label TIFF. All 31 main-lumen links survived at IoU 0.50. There were also 21 extra links relative to that reference graph. [Validation report, controls and reproduction](docs/H01_CAPILLARY.md)

## Run the published demo

From a clean checkout, use Node.js 22.16 or newer and a system `tar` command.

```sh
npm ci
npm run build
npm run preview
```

Open the URL printed by Vite to use the volume cases and both 36-section comparison stacks. The production build downloads the two versioned exports, verifies their SHA-256 checksums, and installs them in `dist/data/`. Vercel uses the same build command and serves `dist/` as a static site. [Published demo datasets](https://github.com/adriandarian/3D-histological-reconstruction/releases/tag/demo-datasets-v1)

## Generate the synthetic demonstration locally

From the repository root, use Python 3.11–3.13 in a virtual environment and Node.js 22.16 or newer.

```sh
python -m pip install -r requirements.txt
python -m pipeline --output public/data/synthetic
npm ci
npm run dev
```

Open the local URL printed by Vite. Drag the stack to rotate it, move the section slider, and click in the section to locate that point in 3D. Switch between original and registered images to see the effect of registration. The 36-section phantom uses seeded acquisition offsets and known sampling.

## Run the measured pancreas series

```sh
python scripts/download_real.py
python -m pipeline --input data/real --output public/data/real --local-refinement he-contour --name "Pancreas · 10x" --attribution "Roy, Gupta and Goswami (2023), DOI 10.17632/fzskwpzs5j.1, CC BY 4.0"
```

To compare the anatomy volume with a new pancreas registration, run `python -m pipeline.pancreas public/data/real public/pancreas` after registration. This associates the candidate with those exact transforms.

The comparison panels display **Synthetic series** and **Pancreas histology** together. Each has its own section navigator, cursor, zoom and 3D camera. The pancreas example refines H&E color alignment around matched tissue tips at the slide background. This export uses preview pixels for XY and section indices for depth. The original TIFFs stay in `data/real/`. See [data provenance and ordering](docs/DATA.md).

## Inspect an export

Each output directory must be new or empty. To process your own series, pass a directory of single-frame images from one block and one magnification to `--input`. Filenames must share a pattern with one varying numeric field that supplies the order. Use `--max-side` to set the maximum preview dimension.

- `manifest.json` links each input filename to its preview, registered image and masked 3D texture. The 2-by-3 matrix maps source pixels into the rigid frame, with X increasing right and Y increasing down.
- With local refinement (`intensity`, `he`, or `he-contour`), each section also exports a bilinear `pullGrid` sampled across the registered image, including both endpoints. At registered pixel `p`, the corresponding rigid-frame point is `p + grid(p)`. Section images, 3D textures and the linked cursor use the same mapping. Omit the flag to reproduce rigid registration.
- `volume.npz` contains registered RGB samples in Z,Y,X,channel order and separate tissue and valid-pixel masks in Z,Y,X order. The mask uses color thresholds. It can include artifacts and miss pale tissue.
- Registration searches for adjacent translations, refines them with bounded rigid rotation, and composes accepted transforms toward the middle reference section. Inspect the status and before/after correlation of each pair. An identity fallback inherits the fixed section's transform. Chaining can accumulate drift, and rigid registration cannot correct tears or local distortion.
- The comparison stack displays individual section planes. Missing tissue between samples, anatomical boundaries and physical depth require independent evidence.

Render ten evenly distributed adjacent overlays for review. Red and cyan fringes indicate differences between neighboring sections.

```sh
python scripts/review_pairs.py public/data/real/manifest.json data/real-review.png
python scripts/landmark_error.py public/data/real/manifest.json docs/pancreas_landmarks.csv
python scripts/landmark_error.py public/data/real/manifest.json docs/pancreas_check_landmarks.csv
```

## Verify and build

```sh
python -m unittest discover -s tests
npx playwright install chromium
npm run test:e2e
npm run build
npm run preview
```

Generate the synthetic export before running browser tests. The real-series test also runs when its local export exists. Use `npm run dev` for locally generated datasets. To update the production demo, publish new export archives in a new release and update the release URL and SHA-256 values in `scripts/install-demo-data.mjs`.

The pipeline holds preview arrays in memory and the viewer loads downsampled textures. Whole-slide ingestion, tiled multiresolution export and chunked 3D access are future work. The [POC plan](docs/POC_PLAN.md) describes the path to larger series and the proposed independent landmark validation.
