# Blinded visual read of the H01 EM crop

A single AI visual reader inspected the measured grayscale array (working file `data/h01-fork/em-wide.npy`) without access to atlas masks, algorithm output, or annotations from other readers. The assignment identified the central structure as a vessel. No expert or human adjudicated these observations.

The reader oriented on a sparse whole-crop overview and assessed every plane in the specified z2930–2977 interval. The interval was supplied during orientation. Coordinates are integer image pixels in the 400 × 400 plane. X increases to the right, Y downwards, and z is 2880 plus the zero-based array index. Points were read separately from gridded EM images, following recognizable internal texture across sections. Only approximate interior locations were requested. They can lie in wall or cellular contents. They do not identify lumen centers or quantify the caliber.

| Inclusive z | Read | Morphological evidence |
| --- | --- | --- |
| 2930–2942 | Apparent parent | The outline of the broad NW region with mottled nuclear material tapers into the slender SE extension. A point in the broad part identifies the target. Internal edges do not demonstrate a shared patent lumen. |
| 2943–2956 | Indeterminate neck | Juxtaposed contours emerge along the narrow connection. A pale cleft and a small intermediate profile develop. Assignment of that material to either outer margin would change the apparent first split. |
| 2957 | Borderline separation | The SE tip appears to retreat from the margin of the NW profile. The narrow intervening strip is difficult to follow confidently across this plane. |
| 2958–2977 | Two distinct profiles | At 2958, tissue texture is visible in a gap between the bounded tip of the oblique SE profile and the lower-right margin of the NW profile. That separation persists and the tissue interval widens. The NW mark follows the broad region, the SE mark the elongated, obliquely oriented region. An artifact overlies part of the NW region at 2964. Its mark is on readable material to the left. |

The first conservative separate-profile call is z2958. The data support persistent separation in the section plane. They leave open whether the earlier connection represents branching of a continuous vascular lumen, a tangential cut along a folded or curving wall, or apposition. The points support tests of profile coverage and identity. They are insufficient for boundary overlap, vascular connectivity or completeness of a reconstruction.

The CSV retains the 15 ambiguous planes with blank coordinates. The six `sections-*.png` sheets cover the complete interval in order. Yellow dots mark 25-pixel grid intersections. The `neck-*.png` sheets enlarge the neck at original x145–244 and y145–229. The `points-*.png` sheets use 10-pixel grids. `marked-daughters.png` overlays the accepted NW and SE coordinates in cyan and magenta. `verified-se.png` enlarges the slender profile with its recorded points.

The CSV and this reading record are the archived annotations. The reader used local inspection sheets; the corresponding measured window is preserved as the [48 section PNGs](../../public/vascular-fork/sections).
