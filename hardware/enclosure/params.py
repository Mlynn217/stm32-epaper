"""Every enclosure dimension, in mm, with where it came from.

Each value is registered through dim() with a source tag:
  DOC - from a datasheet or this repo's README (cited in the note)
  PH  - placeholder: a guess that must be measured or checked before ordering a print
  DC  - design choice: ours to change, no external source

build.py prints every PH entry on each run, so the unverified numbers are never out of sight.

Coordinates (all parts): origin at the centre of the device outline, on the BACK outer face.
+X = right and +Y = up as seen from the front (portrait, top edge = power button); +Z = towards the
viewer, so the front face is at z = OUTER_T.
"""

REGISTRY = []


def dim(name, value, src, note=""):
    assert src in ("DOC", "PH", "DC"), src
    REGISTRY.append((name, value, src, note))
    return value


# --- Fabrication (Craftcloud-style service, MJF/SLS nylon PA12) -------------------------------
WALL_MIN = dim("WALL_MIN", 1.0, "DOC", "MJF/SLS PA12 min. wall, typical service design rule")
FIT_CLEAR = dim("FIT_CLEAR", 0.3, "DC", "gap between a part and the pocket that locates it")
SLIDE_CLEAR = dim("SLIDE_CLEAR", 0.5, "DC", "gap around parts that must pass through an opening")
CORNER_R = dim("CORNER_R", 4.0, "DC", "outer corner radius in plan view")
EDGE_FILLET = dim("EDGE_FILLET", 1.5, "DC", "front/back perimeter edge rounding")

# --- Display: Waveshare 6" HD panel (README "Display: Waveshare 6inch HD e-Paper HAT") ---------
PANEL_W = dim("PANEL_W", 101.8, "DOC", "README outline 138.4 x 101.8 x 0.67 (portrait: W is the short side)")
PANEL_H = dim("PANEL_H", 138.4, "DOC", "README outline")
PANEL_T = dim("PANEL_T", 0.67, "DOC", "README outline")
ACTIVE_W = dim("ACTIVE_W", 90.584, "DOC", "README active area 122.356 x 90.584")
ACTIVE_H = dim("ACTIVE_H", 122.356, "DOC", "README active area")
ACTIVE_DX = dim("ACTIVE_DX", 0.0, "PH", "active-area offset from panel centre; assumed centred, "
                "get Waveshare's panel drawing (the FPC-side border is usually wider)")
ACTIVE_DY = dim("ACTIVE_DY", 0.0, "PH", "as ACTIVE_DX")
WINDOW_MARGIN = dim("WINDOW_MARGIN", 1.0, "DC", "bezel window = active area + this on each side")
FPC_W = dim("FPC_W", 30.0, "PH", "panel FPC width where it leaves the glass; measure")
FPC_BEND = dim("FPC_BEND", 3.0, "PH", "room for the FPC to fold behind the panel; measure bend radius")
# The FPC is assumed to leave the panel's short edge. The panel is mounted with that edge at the
# TOP so the FPC reaches the HAT (upper right) without crossing the main PCB; firmware rotates 180.

# --- HAT driver board (external module on v1, README "Board scope") --------------------------
HAT_W = dim("HAT_W", 65.0, "PH", "Waveshare IT8951 HAT board outline, from memory of the listing; measure")
HAT_H = dim("HAT_H", 30.2, "PH", "as HAT_W")
HAT_T = dim("HAT_T", 12.0, "PH", "board + tallest part (the 2x20 Pi header); measure, or desolder the header")

# --- Battery (README "Battery bay (enclosure input)") ----------------------------------------
BATT_W = dim("BATT_W", 34.5, "DOC", "EEMB LP963450-PCM-LD envelope 9.9 x 34.5 x 52")
BATT_L = dim("BATT_L", 52.0, "DOC", "as BATT_W; PCM strip + lead exit on one 34.5 mm edge")
BATT_T = dim("BATT_T", 9.9, "DOC", "thicker of the two cells; LP603449 is 6.3 -> ~3.6 mm spacer")
BATT_SWELL = dim("BATT_SWELL", 0.5, "DOC", "README: ~0.5 mm on each face for swelling")

# --- Main PCB (outline is an OUTPUT of this model: it feeds KiCad Edge.Cuts) ------------------
PCB_T = dim("PCB_T", 1.6, "DC", "standard FR4")
PCB_STANDOFF = dim("PCB_STANDOFF", 2.5, "DC", "back of PCB above the back cover's inner face "
                   "(room for bottom-side parts + boss heads)")
PCB_H = dim("PCB_H", 60.0, "DC", "main PCB height (Y); full inner width, along the bottom edge")
PCB_TOP_PARTS = dim("PCB_TOP_PARTS", 3.5, "PH", "tallest top-side part except encoder/USB/SD "
                    "(inductors, LQFP); confirm at layout")

# --- Encoder: Bourns PEC11R-4215F-S0024, vertical (epaper.pretty footprint) -------------------
ENC_BODY_W = dim("ENC_BODY_W", 12.5, "DOC", "gen_footprints.py F.Fab body 12.5 x 13.4")
ENC_BODY_D = dim("ENC_BODY_D", 13.4, "DOC", "as ENC_BODY_W")
ENC_BODY_T = dim("ENC_BODY_T", 6.5, "PH", "body height above PCB; check the PEC11R drawing")
ENC_SHAFT_L = dim("ENC_SHAFT_L", 15.0, "DOC", "'15' in the part number; measured from the PCB "
                  "seating plane (PH: confirm the reference plane on the drawing)")
ENC_SHAFT_D = dim("ENC_SHAFT_D", 6.0, "DOC", "PEC11R 6 mm flatted shaft")
KNOB_D = dim("KNOB_D", 18.0, "DC", "knob diameter")
KNOB_GAP = dim("KNOB_GAP", 0.6, "DC", "knob skirt to front face (must clear the push travel)")
ENC_PUSH_TRAVEL = dim("ENC_PUSH_TRAVEL", 0.5, "PH", "PEC11R push-switch travel; check datasheet")
# The PEC11R is a VERTICAL part (shaft normal to the PCB). With the PCB lying behind the panel,
# the knob comes out of the FRONT face in the chin below the display, not the bottom edge.

# --- USB-C: GCT USB4105 top-mount (Connector_USB footprint) -----------------------------------
USB_W = dim("USB_W", 8.94, "DOC", "USB4105 receptacle width")
USB_T = dim("USB_T", 3.26, "DOC", "USB4105 receptacle height above PCB")
USB_PLUG_W = dim("USB_PLUG_W", 12.4, "DOC", "USB-C plug overmold max width (USB-IF), so cables fit")
USB_PLUG_T = dim("USB_PLUG_T", 6.5, "DOC", "USB-C plug overmold max height (USB-IF)")
USB_X = dim("USB_X", 25.0, "DC", "bottom edge, right of the encoder (which is on the centreline)")

# --- microSD: Molex 104031-0811 (Connector_Card footprint) ------------------------------------
SD_CARD_W = dim("SD_CARD_W", 11.0, "DOC", "microSD card width (SD spec)")
SD_CARD_T = dim("SD_CARD_T", 1.0, "DOC", "microSD card thickness (SD spec)")
SD_SOCKET_T = dim("SD_SOCKET_T", 1.9, "PH", "socket height above PCB; card slot centre; check Molex drawing")
SD_X = dim("SD_X", -25.0, "DC", "bottom edge, left of the encoder")
SD_FINGER_NOTCH = dim("SD_FINGER_NOTCH", 8.0, "DC", "radius of the finger scoop so a flush card can be pushed/pulled")

# --- Power button: Alps SKRTLAE010 side-actuated tact switch on the PCB's bottom edge -----------
# Pressed through a flexure tab cut into the bottom wall (PA12 makes a good living hinge).
BTN_BODY_W = dim("BTN_BODY_W", 4.5, "DOC", "KiCad SKRTLAE010 footprint F.Fab body 4.5 x 2.56")
BTN_BODY_D = dim("BTN_BODY_D", 2.56, "DOC", "as BTN_BODY_W")
BTN_ACT_W = dim("BTN_ACT_W", 2.0, "DOC", "plunger width (footprint F.Fab)")
BTN_ACT_L = dim("BTN_ACT_L", 0.83, "DOC", "plunger protrusion beyond the body (footprint F.Fab)")
BTN_BODY_T = dim("BTN_BODY_T", 2.5, "PH", "body height above PCB; check the Alps SKRT drawing")
BTN_TRAVEL = dim("BTN_TRAVEL", 0.25, "PH", "SKRT travel; check the Alps SKRT drawing")
BTN_X = dim("BTN_X", -40.0, "DC", "bottom edge, left of the microSD slot")
BTN_TAB_W = dim("BTN_TAB_W", 8.0, "DC", "flexure tab width (X)")
BTN_TAB_L = dim("BTN_TAB_L", 8.0, "DC", "flexure tab length (Z), hinged on the front side")
BTN_TAB_T = dim("BTN_TAB_T", 1.2, "DC", "flexure tab thickness (wall thinned from inside)")
BTN_SLOT = dim("BTN_SLOT", 0.6, "DC", "slot width around the tab")
BTN_PRELOAD_GAP = dim("BTN_PRELOAD_GAP", 0.1, "DC", "nub to plunger gap at rest")

# --- Capacitive side-wall electrodes (CAP1188, README "Input System") -------------------------
# Two identical electrode boards (one per side), pads facing the wall, each on a JST-SH cable.
ELECTRODE_WALL_MAX = dim("ELECTRODE_WALL_MAX", 4.0, "DOC", "README: up to ~4 mm plastic dielectric")
ELECTRODE_H = dim("ELECTRODE_H", 25.0, "DC", "height of each of the 2 zones per side")
ELECTRODE_Y = dim("ELECTRODE_Y", (-25.0, 20.0), "DC", "zone centres (Y), lower = next page")
EB_T = dim("EB_T", 0.8, "DC", "electrode board thickness (JLC 0.8 mm FR4)")
EB_W = dim("EB_W", 10.0, "DC", "electrode board width (Z)")
EB_MARGIN = dim("EB_MARGIN", 2.0, "DC", "board length beyond the zones at each end")
EB_CONN_Y = dim("EB_CONN_Y", -15.0, "DC", "connector position (Y): between the PCB top and battery")
EB_CONN = dim("EB_CONN", (6.0, 4.3, 3.0), "PH", "JST SM03B-SRSS-TB envelope Y x Z x X (height off "
              "the board); check the JST drawing")
PCB_SIDE_GAP = dim("PCB_SIDE_GAP", 2.5, "DC", "main PCB / battery edge to side wall: room for an "
                   "electrode board and its retaining channel")

# --- Shell -------------------------------------------------------------------------------------
SIDE_WALL = dim("SIDE_WALL", 2.2, "DC", "left/right walls: the electrode dielectric; <= ELECTRODE_WALL_MAX")
END_WALL = dim("END_WALL", 2.2, "DC", "top/bottom walls")
BEZEL_T = dim("BEZEL_T", 1.4, "DC", "front face thickness over the panel")
BACK_T = dim("BACK_T", 1.6, "DC", "back cover thickness")
BACKER_T = dim("BACKER_T", 1.5, "DC", "panel backer plate (keeps the internals off the glass)")
PANEL_GAP = dim("PANEL_GAP", 0.3, "DC", "Z room for the panel + adhesive/foam behind the bezel")
TOP_BORDER = dim("TOP_BORDER", 4.0, "DC", "inner room above the panel (FPC fold lives here)")
CHIN = dim("CHIN", 24.0, "DC", "inner room below the panel: encoder knob + USB/SD behind it")
BOSS_OD = dim("BOSS_OD", 6.0, "DC", "screw boss outer diameter")
INSERT_D = dim("INSERT_D", 3.2, "DOC", "hole for M2 heat-set insert (typ. 3.2 mm, 3.0 long)")
INSERT_L = dim("INSERT_L", 4.0, "DOC", "insert hole depth (insert length + 1)")
SCREW_CLEAR_D = dim("SCREW_CLEAR_D", 2.4, "DOC", "M2 clearance hole")


# --- Derived -----------------------------------------------------------------------------------
INNER_W = PANEL_W + 2 * FIT_CLEAR
OUTER_W = INNER_W + 2 * SIDE_WALL
INNER_H = TOP_BORDER + PANEL_H + 2 * FIT_CLEAR + CHIN
OUTER_H = INNER_H + 2 * END_WALL

# Z stack, back to front. The deepest internal item sets the cavity depth: the battery (+ swell on
# both faces) or the PCB + its tallest non-edge part, whichever is deeper.
BATT_ZONE_T = BATT_T + 2 * BATT_SWELL
PCB_ZONE_T = PCB_STANDOFF + PCB_T + PCB_TOP_PARTS
CAVITY_T = max(BATT_ZONE_T, PCB_ZONE_T, HAT_T) + FIT_CLEAR
Z_BACK_IN = BACK_T                          # inner face of the back cover
Z_BACKER = Z_BACK_IN + CAVITY_T             # back face of the panel backer plate
Z_PANEL = Z_BACKER + BACKER_T               # back face of the panel
Z_BEZEL = Z_PANEL + PANEL_T + PANEL_GAP     # inner face of the bezel
OUTER_T = Z_BEZEL + BEZEL_T                 # front face

# Panel position: centred in X, top of panel TOP_BORDER below the inner top wall.
PANEL_CY = INNER_H / 2 - TOP_BORDER - FIT_CLEAR - PANEL_H / 2
CHIN_CY = -INNER_H / 2 + CHIN / 2           # centre of the chin (encoder axis)

Z_PCB = Z_BACK_IN + PCB_STANDOFF            # back face of the main PCB
Z_PCB_TOP = Z_PCB + PCB_T
