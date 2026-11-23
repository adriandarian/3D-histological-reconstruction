# H01 vascular fork

This window contains 48 registered EM planes of human temporal cortex, native z2930–2977. In the coarse published vascular atlas, a parent profile continues into two long, diverging vascular profiles. A separate source-only read could identify the two profiles on each of the final 20 measured planes. The table reports what the predicted mesh covers in this window.

| Evidence on measured planes | Parent | NW daughter A | SE daughter B |
| --- | ---: | ---: | ---: |
| Marked point inside prediction | 13 / 13 | 20 / 20 | 20 / 20 |
| Marked point reachable from the initial parent via forward face contacts | 13 / 13 | 20 / 20 | 20 / 20 |
| Contacts on adjacent sections where the same arm was scored | 12 / 12 | 19 / 19 | 19 / 19 |

Both daughter points occupy distinct predicted regions on all 20 scored daughter planes. Repeating the first mask throughout the window separates the two marked regions on zero planes. These contacts include repeated 66 nm model slabs. Only ten unique model Z positions underlie the twenty scored daughter planes. This test measures localization and trajectory support for vascular profiles. It cannot establish exact vessel boundaries, lumen patency, flow direction or sensitivity to unannotated branches. Registration and cut thickness were supplied by the archive and lack local independent calibration in this case.

## Where the evidence comes from

- **Case selection.** We inspected the publisher's manual vascular mask for a single profile splitting into two persistent regions. In the retained 25.6 µm square XY box, the 128 × 128 × 1056 nm atlas grid shows one profile on atlas z80–92 and two on z93–100. Several neighboring atlas planes contain identical contours. The box was chosen because of its coarse split and cannot estimate whole-volume performance. [H01 description of manual vessel segmentation](https://h01-release.storage.googleapis.com/explore.html)
- **Acquisition.** The 4 nm raster origin is x617984, y295040. From the 32 × 32 × 33 nm registered EM level, the crop is 800 × 800 pixels with one sample per released digital z. Two-by-two area averaging gives the 400 × 400 grayscale PNGs. The display uses a second two-by-two area average, yielding 128 × 128 × 33 nm voxels. Each point maps by pixel-center coordinates between frames. [Original H01 release, image coordinates and CC BY 4.0 license](https://h01-release.storage.googleapis.com/data.html)
- **Reconstruction.** The publisher's automated tissue class 4 denotes blood vessel. Its finest release has 64 × 64 × 66 nm sampling. For each predicted section, enclosed holes are filled to estimate the whole profile, including cellular contents. A display XY voxel requires a strict majority of its four prediction pixels. The exported mask is the three-dimensional face-connected object containing the largest profile on the first plane. Its exposed voxel faces form the mesh. Each model slab spans two measured planes. No model was trained in this repository. Upstream training overlap with the coarse atlas is unknown, so we use the atlas for identity and selection. [Released model](https://h01-release.storage.googleapis.com/data.html) · [Publisher's class labels](https://h01-release.storage.googleapis.com/data/20210601/masking/segment_properties/info)
- **Native-plane validation.** One model-assisted reader saw only the measured grayscale images and the vascular target description. The reader inspected every plane, placed approximate interior points and withheld uncertain identities. Registration, masks and outcomes from the prediction were withheld from the reader. No human expert adjudicated these landmarks. The reconstruction settings were frozen before the point scores were computed. [Original source-coordinate observations](vascular-fork-reader/annotations.csv) · [Reader's interpretation and uncertainty](vascular-fork-reader/README.md)
- **Uncertain junction.** A single apparent parent was marked on z2930–2942. The reader could not place a confident junction on z2943–2957. Both spatially separated profiles were recognizable on z2958–2977. A tangent or wall apposition cannot be ruled out from these local plane landmarks alone. The single-to-double topology of the extended atlas contributes additional evidence at coarse resolution. The coarse atlas does not locate an exact native-section branch point. [Per-plane scores](../public/vascular-fork/validation.json)

## Reproduce and inspect

From the project root, install the normal pipeline requirements and TensorStore, then run the following commands. The downloader retrieves three public H01 rasters and the export verifies all input buffer hashes. The point reference stays separate from the reconstruction. The regression test deletes one observed daughter component and checks that two adjacent links are lost while the other arm's results remain intact.

~~~sh
python -m pip install -r requirements.txt tensorstore
python scripts/download_h01_fork.py
python -m pipeline.h01_fork
python -m unittest discover -s tests -p test_vascular_fork.py
~~~

The viewer opens this case at `?dataset=vascular-fork`. Daughter A denotes NW and daughter B denotes SE in image coordinates. The source sections and rendered mesh derive from the Lichtman laboratory and Connectomics at Google H01 release. The provided crops, processed masks and surface geometry are derivatives distributed with attribution under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). [Acquisition paper](https://doi.org/10.1126/science.adk4858)
