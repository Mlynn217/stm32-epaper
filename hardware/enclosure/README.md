# Enclosure

Parametric enclosure model in [build123d](https://build123d.readthedocs.io/) (Python on the
OpenCascade kernel). **Status: v0 draft**. It builds, passes its own fit checks and exports print files,
but several inputs are still placeholders (see below). It hasn't been printed or reviewed by a person.
Don't order parts from it yet.

## Running it

One-time setup (a venv outside the repo):
```sh
python3 -m venv ~/.venvs/cad && ~/.venvs/cad/bin/pip install -r hardware/enclosure/requirements.txt
```
Build (about 30 s; about 10 s with `--no-render`):
```sh
~/.venvs/cad/bin/python hardware/enclosure/build.py
```
This prints the outer size, the weight of each part, every fit check and every placeholder
dimension. It exits non-zero if a check fails. It writes to `hardware/enclosure/out/`, which is
git-ignored (regenerate the files rather than committing them):

| File | What it's for |
|---|---|
| `<part>.step` | Upload to the print service (preferred). Also opens in FreeCAD for editing |
| `<part>.stl`, `<part>.3mf` | Mesh versions, if a service wants them |
| `assembly.step` | Everything, including the bought-in parts, coloured and named. For viewing, and for KiCad's 3D viewer |
| `pcb_outline.dxf` | Main PCB outline with mounting holes. KiCad: *File → Import → Graphics*, layer Edge.Cuts |
| `pcb_placement.json` | Where the enclosure needs things on the PCB: encoder axis, USB-C and microSD on the edge, holes, height limits, battery and electrode zones |
| `render_*.png` | Headless previews: front, interior, exploded, section |

**Viewing:**
- **Just the files:** open `out/assembly.step` (or any per-part `.step` or `.stl`) in a desktop
  viewer: F3D (`sudo apt install f3d`, lightweight), FreeCAD (can also edit), or Open Cascade's CAD
  Assistant.
- **Live from the code:** `show.py` sends the model over a local websocket to a separate viewer
  app, and each re-run updates the open view. Start the viewer with
  `~/.venvs/cad/bin/python -m ocp_viewer` and open http://127.0.0.1:3939/viewer (or use VSCode's
  **OCP CAD Viewer** extension pane instead). Then run
  `~/.venvs/cad/bin/python hardware/enclosure/show.py` (add `printed` to show only the printed parts).

## Files

- `params.py`: **every dimension**, each tagged `DOC` (from a datasheet or the README), `PH`
  (placeholder: measure before ordering) or `DC` (design choice). Change the design here.
- `model.py`: geometry. Envelopes of the bought-in parts (for checking) and the four printed parts.
- `checks.py`: fit checks. Pairwise interference between all parts and envelopes, wall rules, knob
  engagement and clearance, openings that admit a real USB-C plug and a microSD card, and the
  battery lead's reach.
- `build.py`, `render.py`, `show.py`: build and export, PNG renders, interactive viewer.

## The v0 design

| | Choice | Why |
|---|---|---|
| Outline | 106.8 × 171.4 × 17.8 mm (+4.6 mm knob), ~80 g printed | Panel + 2.2 mm walls, 4 mm top border, 24 mm chin |
| Orientation | Portrait, panel **FPC at the top** | The FPC folds straight back to the HAT. Firmware rotates the image 180° |
| Stack (front→back) | Bezel 1.4 · panel · backer plate 1.5 · 12.3 mm cavity · back 1.6 | The cavity is set by the tallest single item. Today that's the HAT with its Pi header (placeholder 12 mm) |
| Cavity layout | HAT at the top, battery at the left below it, main PCB a full-width 60 mm strip at the bottom | Nothing stacks on anything else. Thickness = the deepest single part |
| Encoder | Knob on the **front face, in the chin** | The PEC11R is a vertical part (shaft normal to the PCB). With the PCB behind the panel, the shaft points out the front, not the bottom edge. The knob's hub reaches through the front face so it grips 7.7 mm of shaft |
| USB-C, microSD | Bottom wall at x = +25 / −25 mm | Either side of the encoder. The USB opening admits a USB-IF maximum-size plug overmold (12.4 × 6.5 mm) |
| Power button | Opening in the top wall | See the open items: the KMR2 can't be pressed from the edge |
| Electrodes | 2 zones per side (25 mm tall), marked by 0.4 mm thumb dimples. The side wall is 2.2 mm (1.8 at the dimples) | README allows ≤ ~4 mm of plastic |
| Parts | Front shell, panel backer, back cover, knob | Back cover: 4 × M2 screws into heat-set inserts (Ø3.2 mm holes) in the shell's bosses. PCB: 4 × M2 thread-forming screws into standoffs on the back cover. Battery: L-shaped corner rails, sized for the 963450 + swell |
| Panel retention | Bezel ribs locate the panel and backer. The top bosses clamp the backer | Also stick the panel to the bezel with thin double-sided tape, as commercial e-readers do |

## Ordering (Craftcloud or similar)

- **Material: MJF (or SLS) nylon PA12**, dyed black. It's strong, snap-tolerant, needs no support
  marks, holds ~1 mm walls, and works as the electrode dielectric. The knob could also be SLA resin
  for a smoother finish.
- Upload the `.step` files, one per part. Tolerances assume a typical MJF service (±0.3 mm).
- Hardware: 4 × M2 heat-set inserts (3.2 mm OD, ~3 mm long), 4 × M2×6 screws (back cover),
  4 × M2×5 thread-forming screws (PCB), thin double-sided tape for the panel.
- Before paying for the full set, consider ordering only the front shell's **chin section** (or the
  whole shell alone) as a fit check against the real panel, encoder and connectors.

## Open items (resolve before ordering)

1. **Measure the placeholders** (`PH` in `params.py`; `build.py` lists them): the panel's
   active-area offset and FPC width/bend, the HAT's size and height, the PEC11R body height and push
   travel, and the microSD socket height.
2. **HAT height drives the device thickness.** With its 2×20 Pi header the HAT is ~12 mm tall. If
   the header is desoldered (we only use the 1×8 SPI header), the battery sets the depth at
   10.9 mm and the device loses ~1.1 mm.
3. **Power button:** the schematic's KMR2 is pressed from above, and the main PCB is at the other
   end of the device. Options: a side-actuated switch on a small daughterboard with a wire/flex to
   the main PCB, a flexure lever, or moving the button to the bottom edge (then it can be a
   right-angle switch on the main PCB).
4. **Electrodes:** the zones sit on the side walls at y = −37.5…−12.5 and +7.5…+32.5 mm. Only
   the lower zone overlaps the PCB strip (by about 14 mm), and the upper one is entirely above it. Pads on the
   PCB surface also face the wrong way to sense a finger on the side wall. Likely answer: copper tape
   or a small flex on the inside of each wall, connected to CAP1188 pads by a spring contact. This
   also settles the ESD question in TODO.md.
5. **RT1 (charger NTC)** must touch the pouch, but the battery sits beside the PCB, not over it.
   Put RT1 on a short pigtail, or extend a PCB tongue under the cell edge.
6. **Encoder shaft reference plane:** the model assumes the "15 mm" is measured from the PCB
   seating plane. If Bourns measures it from the bushing, the knob sits higher. Check the drawing.
7. **Panel active-area position:** the window is centred on the panel. If the real active area is
   offset (usually away from the FPC edge), set `ACTIVE_DX/DY`.
