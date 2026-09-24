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
| `electrode_board.json` | The side electrode board design: size, pad rectangles, connector position and pinout |
| `render_*.png` | Headless previews: front, interior, exploded, bottom edge, section |

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
| Power button | Bottom edge, x = −40 mm: an Alps SKRTLAE010 side-actuated switch on the PCB edge, pressed through a **flexure tab** in the wall (U-shaped slot, tab thinned to 1.2 mm, nub 0.1 mm off the plunger) | Keeps the switch on the main PCB; PA12 makes a durable living hinge, so there is no separate button part |
| Electrodes | 2 zones per side (25 mm tall), marked by 0.4 mm thumb dimples. The side wall is 2.2 mm (1.8 at the dimples). The pads are on **two identical 74 × 10 mm electrode boards** (0.8 mm FR4), pads facing the wall, slid into printed channels at each end and held by the back cover. A JST-SH cable runs to J302/J303 on the main PCB | README allows ≤ ~4 mm of plastic. The main PCB and the battery sit 2.5 mm in from the side walls to make room |
| Parts | Front shell, panel backer, back cover, knob | Back cover: 4 × M2 screws into heat-set inserts (Ø3.2 mm holes) in the shell's bosses. PCB: 4 × M2 thread-forming screws into standoffs on the back cover. Battery: L-shaped corner rails, sized for the 963450 + swell |
| Panel retention | Bezel ribs locate the panel and backer. The top bosses clamp the backer | Also stick the panel to the bezel with thin double-sided tape, as commercial e-readers do |

## Ordering (Craftcloud or similar)

- **Material: MJF (or SLS) nylon PA12**, dyed black. It's strong, snap-tolerant, needs no support
  marks, holds ~1 mm walls, and works as the electrode dielectric. The knob could also be SLA resin
  for a smoother finish.
- Upload the `.step` files, one per part. Tolerances assume a typical MJF service (±0.3 mm).
- Hardware: 4 × M2 heat-set inserts (3.2 mm OD, ~3 mm long), 4 × M2×6 screws (back cover),
  4 × M2×5 thread-forming screws (PCB), thin double-sided tape for the panel, 2 × JST-SH 3-pin
  cables (~50 mm, both ends SHR-03V-S), and 2 electrode boards (order with the main PCB).
- Before paying for the full set, consider ordering only the front shell's **chin section** (or the
  whole shell alone) as a fit check against the real panel, encoder and connectors.

## Fit-check print (order this first)

`build.py` also exports **`out/fitcheck_chin.step`**: the bottom 38.5 mm of the front shell (the
chin plus 12 mm of the display window, full depth, 106.8 × 38.5 × 16.2 mm, ~11 g of PA12). It also
exports **`out/fitcheck_knob.step`**. Together they're about a seventh of the full set's material,
and they test nearly everything that can go wrong mechanically.

**To order (Craftcloud):** upload both `.step` files, choose **MJF (HP Multi Jet Fusion) PA 12**
(dyed black is optional), quantity 1 each, and pick the cheapest offer with an acceptable
delivery time. Also order 2 × M2 heat-set inserts (3.2 mm OD) if you don't have them.

**When it arrives, check:**
- [ ] **Encoder:** the PEC11R's M7 bushing passes through the chin hole; the knob presses onto
      the 20 mm shaft (D-flat) firmly, turns freely, and clicks without touching the face.
- [ ] **USB-C:** a real cable plug (the thickest one you own) fits the bottom opening.
- [ ] **microSD:** a card slides through the slot; the finger scoop lets you pull it.
- [ ] **Power-button flexure:** it flexes without cracking; ~0.3 mm of travel feels right.
- [ ] **Heat-set inserts:** they go into the two chin bosses square and hold an M2 screw.
- [ ] **Panel:** its bottom edge sits against the locating rib behind the bezel, and the
      window edge shows no border. This is the quickest way to find out whether the panel is
      0.67 mm or 1.6 mm thick (see Open items).
- [ ] **Surface and fit tolerances:** note the print's actual wall thickness and hole sizes;
      adjust `FIT_CLEAR` / `SLIDE_CLEAR` in `params.py` if the service prints tight or loose.

## Open items (resolve before ordering)

1. **Measure the placeholders** (`PH` in `params.py`; `build.py` lists them): the panel's
   active-area offset, FPC width/bend and **thickness** (Waveshare says 0.67 mm, ED060KD1 listings
   1.6 mm), and the HAT's size and height. The part dimensions come from datasheets.
2. **Knob height:** 7.9 mm proud, set by the PEC11R's M7 bushing (13.5 mm above the PCB on the
   20 mm-shaft part) plus the 0.8 mm worst-case push travel. Cutting the shaft down later would
   lower it, at the cost of grip.
3. **Panel active-area position:** the window is centred on the panel. If the real active area is
   offset (usually away from the FPC edge), set `ACTIVE_DX/DY`.
4. **Electrode board KiCad project** (see TODO.md): the geometry is in `out/electrode_board.json`.

Decided 2026-09-23: keep the HAT's 2×20 Pi header for v1 (it sets the cavity depth, ~1.1 mm more
than the battery would); power button on the bottom edge; electrodes on small boards; knob on the
front face; RT1 as a leaded NTC taped to the pouch.
