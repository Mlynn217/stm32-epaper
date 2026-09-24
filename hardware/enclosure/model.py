"""Enclosure geometry: bought-in component envelopes (for fit checks) and the printed parts.

Everything is built from params.py; see its docstring for the coordinate system. build() returns
two dicts of build123d Parts, `printed` and `components`, keyed by name.
"""

from build123d import (Align, Axis, Box, Cylinder, Part, Pos, Rot, fillet)

from params import *  # noqa: F401,F403  (dimension constants are the whole point of params.py)

C, MIN, MAX = Align.CENTER, Align.MIN, Align.MAX


# --- helpers ------------------------------------------------------------------------------------
def slab(w, h, z0, z1, cx=0.0, cy=0.0, r=0.0):
    """Box w (X) by h (Y) from z0 to z1, centred on (cx, cy), optional plan-view corner radius."""
    b = Box(w, h, z1 - z0, align=(C, C, MIN))
    if r > 0:
        b = fillet(b.edges().filter_by(Axis.Z), r)
    return Pos(cx, cy, z0) * b


def span(x0, x1, y0, y1, z0, z1):
    """Box from corner ranges (easier to read for things placed against walls)."""
    return slab(x1 - x0, y1 - y0, z0, z1, (x0 + x1) / 2, (y0 + y1) / 2)


def post(d, z0, z1, cx, cy):
    """Cylinder along Z."""
    return Pos(cx, cy, z0) * Cylinder(d / 2, z1 - z0, align=(C, C, MIN))


def wall_hole(w, t, cx, cz, y_wall_in, y_wall_out, r=0.0):
    """Opening through a top/bottom wall: w (X) by t (Z), rounded corners, spanning the wall in Y."""
    y0, y1 = sorted((y_wall_in, y_wall_out))
    b = Box(w, y1 - y0 + 2, t)
    if r > 0:
        b = fillet(b.edges().filter_by(Axis.Y), min(r, t / 2 - 0.01, w / 2 - 0.01))
    return Pos(cx, (y0 + y1) / 2, cz) * b


# --- placement (derived; the numbers that feed PCB layout are exported by build.py) -------------
IN_L, IN_R = -INNER_W / 2, INNER_W / 2
IN_B, IN_T = -INNER_H / 2, INNER_H / 2
OUT_B, OUT_T = -OUTER_H / 2, OUTER_H / 2

PANEL_TOP = PANEL_CY + PANEL_H / 2
PANEL_BOT = PANEL_CY - PANEL_H / 2

# Screw bosses: two full-depth in the chin corners, two in the top corners that stop at the panel
# backer (they sit behind the panel and clamp the backer plate against it).
BOSS_X = IN_R - BOSS_OD / 2 + 1.0           # overlaps the side wall by 1 mm so it fuses with it
BOSS_Y_BOT = IN_B + BOSS_OD / 2 - 1.0
BOSS_Y_TOP = IN_T - BOSS_OD / 2 + 1.0
BOSSES = [(sx * BOSS_X, y, z_top)
          for sx in (-1, 1)
          for (y, z_top) in ((BOSS_Y_BOT, Z_BEZEL), (BOSS_Y_TOP, Z_BACKER))]

PCB_X0, PCB_X1 = IN_L + PCB_SIDE_GAP, IN_R - PCB_SIDE_GAP
PCB_Y0 = IN_B + FIT_CLEAR
PCB_Y1 = PCB_Y0 + PCB_H
PCB_NOTCH_D = BOSS_OD + 2 * FIT_CLEAR
PCB_HOLE_D = 2.2                             # M2 thread-forming screw into the standoff
STANDOFF_OD = 5.0
STANDOFF_PILOT_D = 1.6                       # M2 thread-forming pilot in PA12
PCB_HOLES = [(sx * (PCB_X1 - 6.0), y) for sx in (-1, 1) for y in (PCB_Y0 + 12.0, PCB_Y1 - 5.0)]

HAT_X = 0.0
HAT_Y1 = PANEL_TOP - 2.0                     # under the backer, clear of the FPC fold
HAT_Y0 = HAT_Y1 - HAT_H
BATT_X0 = IN_L + PCB_SIDE_GAP
BATT_Y1 = HAT_Y0 - 2.0
BATT_ZONE_W = BATT_W + 2 * BATT_SWELL
BATT_ZONE_L = BATT_L + 2 * BATT_SWELL
BATT_Y0 = BATT_Y1 - BATT_ZONE_L               # PCM strip + lead exit on this (bottom) edge

ENC_X, ENC_Y = 0.0, CHIN_CY
KNOB_HOLE_D = ENC_BUSH_D + 2 * SLIDE_CLEAR   # the bushing comes up through the front face
Z_ENC_TOP = Z_PCB_TOP + ENC_BODY_T
Z_BUSH_TOP = Z_ENC_TOP + ENC_BUSH_L
Z_SHAFT_TIP = Z_PCB_TOP + ENC_SHAFT_L
Z_KNOB_CAP0 = OUTER_T + KNOB_GAP
# The knob's D-bore starts above the bushing by the push travel (+0.2) so pressing never lands the
# knob on the bushing; below that a counterbore clears the bushing. Through-bore, shaft end flush
# with the top (a closed top would add a 1 mm wall to an already tall knob).
Z_KNOB_BORE0 = max(Z_BUSH_TOP, Z_KNOB_CAP0) + ENC_PUSH_TRAVEL + 0.2
Z_KNOB_TOP = Z_SHAFT_TIP

USB_DEPTH = 7.35                             # USB4105 body depth (Y)
USB_ZC = Z_PCB_TOP + USB_T / 2
SD_ZC = Z_PCB_TOP + SD_SOCKET_T / 2
SD_SOCKET_W, SD_SOCKET_D = 14.0, 15.0        # PH: Molex 104031 body, check drawing

# Power button: plunger tip on the PCB's bottom edge, pressed by a nub on a flexure tab.
BTN_ZC = Z_PCB_TOP + BTN_BODY_T / 2
BTN_TIP_Y = PCB_Y0                           # plunger tip flush with the PCB edge
BTN_TAB_Z0 = BTN_ZC - BTN_TAB_L / 2          # free end (towards the back)
BTN_TAB_Z1 = BTN_TAB_Z0 + BTN_TAB_L          # hinge (towards the front)
BTN_NUB_Y = BTN_TIP_Y - BTN_PRELOAD_GAP      # nub face

# Electrode boards: against the inner side walls, pads outwards, slid into channels from the back.
EB_Z0 = Z_BACK_IN + 0.2
EB_Z1 = EB_Z0 + EB_W
EB_CH_WALL = 1.0                             # channel lip thickness
EB_CH_LAP = 1.5                              # how far the lip overlaps the board end
PA12_DENSITY = 1.01e-3                       # g/mm^3, MJF PA12 (HP datasheet)


# --- bought-in parts (envelopes) ----------------------------------------------------------------
def components():
    c = {}
    c["panel"] = slab(PANEL_W, PANEL_H, Z_PANEL, Z_PANEL + PANEL_T, 0, PANEL_CY)
    # FPC wraps round the backer's top edge on its way to the HAT.
    c["panel_fpc_fold"] = span(-FPC_W / 2, FPC_W / 2, PANEL_TOP, PANEL_TOP + FPC_BEND,
                               Z_BACKER - 0.5, Z_PANEL + PANEL_T)
    c["hat"] = span(HAT_X - HAT_W / 2, HAT_X + HAT_W / 2, HAT_Y0, HAT_Y1, Z_BACK_IN, Z_BACK_IN + HAT_T)
    c["battery_zone"] = span(BATT_X0, BATT_X0 + BATT_ZONE_W, BATT_Y0, BATT_Y1,
                             Z_BACK_IN, Z_BACK_IN + BATT_ZONE_T)
    c["pcb"] = pcb()
    c["encoder_body"] = slab(ENC_BODY_W, ENC_BODY_D, Z_PCB_TOP, Z_ENC_TOP, ENC_X, ENC_Y)
    c["encoder_bushing"] = post(ENC_BUSH_D, Z_ENC_TOP, Z_BUSH_TOP, ENC_X, ENC_Y)
    c["encoder_shaft"] = post(ENC_SHAFT_D, Z_BUSH_TOP, Z_SHAFT_TIP, ENC_X, ENC_Y)
    c["usb_c"] = span(USB_X - USB_W / 2, USB_X + USB_W / 2, PCB_Y0, PCB_Y0 + USB_DEPTH,
                      Z_PCB_TOP, Z_PCB_TOP + USB_T)
    # A mated plug (USB-IF max overmold) - proves the opening admits real cables.
    c["usb_plug"] = span(USB_X - USB_PLUG_W / 2, USB_X + USB_PLUG_W / 2, OUT_B - 20, PCB_Y0,
                         USB_ZC - USB_PLUG_T / 2, USB_ZC + USB_PLUG_T / 2)
    c["sd_socket"] = span(SD_X - SD_SOCKET_W / 2, SD_X + SD_SOCKET_W / 2, PCB_Y0, PCB_Y0 + SD_SOCKET_D,
                          Z_PCB_TOP, Z_PCB_TOP + SD_SOCKET_T)
    # The card's insertion path, from outside the wall into the socket.
    c["sd_card_path"] = span(SD_X - SD_CARD_W / 2, SD_X + SD_CARD_W / 2, OUT_B - 5, PCB_Y0 + 1,
                             SD_ZC - SD_CARD_T / 2, SD_ZC + SD_CARD_T / 2)
    body_y0 = BTN_TIP_Y + BTN_ACT_L
    c["power_switch"] = (
        span(BTN_X - BTN_BODY_W / 2, BTN_X + BTN_BODY_W / 2, body_y0, body_y0 + BTN_BODY_D,
             Z_PCB_TOP, Z_PCB_TOP + BTN_BODY_T)
        + span(BTN_X - BTN_ACT_W / 2, BTN_X + BTN_ACT_W / 2, BTN_TIP_Y, body_y0 + 0.1,
               BTN_ZC - 0.6, BTN_ZC + 0.6))
    cw, cz, cx = EB_CONN
    ezc = (EB_Z0 + EB_Z1) / 2
    for sx, side in ((-1, "L"), (1, "R")):
        face = sx * IN_R
        xa, xb = face, face - sx * EB_T
        c[f"electrode_board_{side}"] = span(min(xa, xb), max(xa, xb), EB_Y0, EB_Y1, EB_Z0, EB_Z1)
        xc = xb - sx * cx
        c[f"electrode_conn_{side}"] = span(min(xb, xc), max(xb, xc), EB_CONN_Y - cw / 2,
                                           EB_CONN_Y + cw / 2, ezc - cz / 2, ezc + cz / 2)
    return c


def pcb():
    """Main PCB outline (the source of truth for KiCad Edge.Cuts), extruded to PCB_T."""
    p = span(PCB_X0, PCB_X1, PCB_Y0, PCB_Y1, Z_PCB, Z_PCB_TOP)
    for x, y, z_top in BOSSES:
        if y < PCB_Y1:
            p -= post(PCB_NOTCH_D, Z_PCB - 1, Z_PCB_TOP + 1, x, y)
    for x, y in PCB_HOLES:
        p -= post(PCB_HOLE_D, Z_PCB - 1, Z_PCB_TOP + 1, x, y)
    return p


# --- printed parts ------------------------------------------------------------------------------
def front_shell():
    s = slab(OUTER_W, OUTER_H, Z_BACK_IN, OUTER_T, r=CORNER_R)
    s = fillet(s.edges().group_by(Axis.Z)[-1], EDGE_FILLET)
    s -= slab(INNER_W, INNER_H, Z_BACK_IN - 1, Z_BEZEL, r=max(CORNER_R - SIDE_WALL, 0.5))

    # Display window.
    s -= slab(ACTIVE_W + 2 * WINDOW_MARGIN, ACTIVE_H + 2 * WINDOW_MARGIN, Z_BEZEL - 1, OUTER_T + 1,
              ACTIVE_DX, PANEL_CY + ACTIVE_DY, r=1.0)

    # Panel/backer locating ribs: one below the panel, two above it either side of the FPC.
    rib = 1.2
    s += span(IN_L + BOSS_OD, IN_R - BOSS_OD, PANEL_BOT - FIT_CLEAR - rib, PANEL_BOT - FIT_CLEAR,
              Z_BACKER, Z_BEZEL + 0.1)
    for sx in (-1, 1):
        x_in, x_out = sx * (FPC_W / 2 + 2.0), sx * (IN_R - 1.0)
        s += span(min(x_in, x_out), max(x_in, x_out), PANEL_TOP + FIT_CLEAR, PANEL_TOP + FIT_CLEAR + rib,
                  Z_BACKER, Z_BEZEL + 0.1)

    # Screw bosses with M2 heat-set inserts at their back ends.
    for x, y, z_top in BOSSES:
        s += post(BOSS_OD, Z_BACK_IN, min(z_top, Z_BEZEL) + (0.1 if z_top >= Z_BEZEL else 0), x, y)
        s -= post(INSERT_D, Z_BACK_IN - 1, Z_BACK_IN + INSERT_L, x, y)

    # Knob hub hole in the chin.
    s -= post(KNOB_HOLE_D, Z_BEZEL - 1, OUTER_T + 1, ENC_X, ENC_Y)

    # Bottom wall: USB-C (sized for the plug overmold) and microSD (card + finger scoop).
    s -= wall_hole(USB_PLUG_W + 2 * SLIDE_CLEAR, USB_PLUG_T + 2 * SLIDE_CLEAR, USB_X, USB_ZC,
                   IN_B + 1, OUT_B - 1, r=1.5)
    s -= wall_hole(SD_CARD_W + 2 * SLIDE_CLEAR, SD_CARD_T + 2 * 0.4, SD_X, SD_ZC, IN_B + 1, OUT_B - 1)
    s -= Pos(SD_X, OUT_B, SD_ZC) * Rot(90, 0, 0) * Cylinder(SD_FINGER_NOTCH / 2 + 2, 2 * 1.0)

    # Bottom wall: power button flexure. A U-shaped slot frees a tab hinged on its front edge; the
    # tab is thinned from the inside and a nub on it rests just off the switch plunger.
    x0, x1 = BTN_X - BTN_TAB_W / 2, BTN_X + BTN_TAB_W / 2
    y_out, y_in = OUT_B - 1, IN_B + 1
    for sx0, sx1 in ((x0 - BTN_SLOT, x0), (x1, x1 + BTN_SLOT)):
        s -= span(sx0, sx1, y_out, y_in, BTN_TAB_Z0 - BTN_SLOT, BTN_TAB_Z1)
    s -= span(x0 - BTN_SLOT, x1 + BTN_SLOT, y_out, y_in, BTN_TAB_Z0 - BTN_SLOT, BTN_TAB_Z0)
    s -= span(x0, x1, OUT_B + BTN_TAB_T, y_in, BTN_TAB_Z0 - 1, BTN_TAB_Z1)
    s += span(BTN_X - 1.5, BTN_X + 1.5, OUT_B + BTN_TAB_T - 0.05, BTN_NUB_Y,
              BTN_ZC - 1.0, BTN_ZC + 1.0)

    # Electrode board channels: a lipped block at each end of each board, open towards the back
    # so the boards slide in before the back cover closes them in.
    for sx in (-1, 1):
        def xr(d0, d1):  # x range d0..d1 mm in from this side's inner wall face
            a, b = sx * (IN_R - d0), sx * (IN_R - d1)
            return min(a, b), max(a, b)
        for y_end, d in ((EB_Y0, -1), (EB_Y1, 1)):
            ya, yb = y_end - d * EB_CH_LAP, y_end + d * (FIT_CLEAR + EB_CH_WALL)
            s += span(*xr(-0.1, EB_T + 0.15 + EB_CH_WALL), min(ya, yb), max(ya, yb),
                      Z_BACK_IN, EB_Z1 + 1.0)
            ya, yb = y_end - d * (EB_CH_LAP + 1), y_end + d * FIT_CLEAR
            s -= span(*xr(0, EB_T + 0.15), min(ya, yb), max(ya, yb), Z_BACK_IN - 1, EB_Z1 + 0.2)

    # Thumb dimples marking the capacitive zones (thin the wall a little, too).
    for sx in (-1, 1):
        for yc in ELECTRODE_Y:
            s -= _dimple(sx, yc)
    return s


DIMPLE_DEPTH = 0.4


def _dimple(sx, yc):
    x_out = sx * (OUTER_W / 2 + 1)
    x_in = sx * (OUTER_W / 2 - DIMPLE_DEPTH)
    return span(min(x_in, x_out), max(x_in, x_out), yc - ELECTRODE_H / 2, yc + ELECTRODE_H / 2,
                Z_BACK_IN + 3.0, Z_BEZEL - 3.0)


def backer():
    """Flat plate behind the panel; the FPC wraps round its top edge."""
    return slab(PANEL_W, PANEL_H, Z_BACKER, Z_PANEL, 0, PANEL_CY, r=1.0)


def back_cover():
    b = slab(OUTER_W, OUTER_H, 0, BACK_T, r=CORNER_R)
    b = fillet(b.edges().group_by(Axis.Z)[0], min(EDGE_FILLET, BACK_T - 0.2))
    for x, y, _ in BOSSES:
        b -= post(SCREW_CLEAR_D, -1, BACK_T + 1, x, y)

    # PCB standoffs (thread-forming M2 pilots).
    for x, y in PCB_HOLES:
        b += post(STANDOFF_OD, BACK_T - 0.1, Z_PCB, x, y)
        b -= post(STANDOFF_PILOT_D, BACK_T - 0.5, Z_PCB + 1, x, y)

    # Battery bay rails (outside the swell zone) - an L at each corner keeps the lead edge open.
    rail_t, rail_h, leg = 1.2, 2.0, 10.0
    x0, x1 = BATT_X0 - rail_t, BATT_X0 + BATT_ZONE_W
    y0, y1 = BATT_Y0 - rail_t, BATT_Y1
    for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        xa = cx if dx > 0 else cx + rail_t
        ya = cy if dy > 0 else cy + rail_t
        b += span(min(xa, xa + dx * leg), max(xa, xa + dx * leg), min(ya, ya + dy * rail_t),
                  max(ya, ya + dy * rail_t), BACK_T - 0.1, BACK_T + rail_h)
        b += span(min(xa, xa + dx * rail_t), max(xa, xa + dx * rail_t), min(ya, ya + dy * leg),
                  max(ya, ya + dy * leg), BACK_T - 0.1, BACK_T + rail_h)
    return b


def knob():
    k = post(KNOB_D, Z_KNOB_CAP0, Z_KNOB_TOP, ENC_X, ENC_Y)
    k = fillet(k.edges().group_by(Axis.Z)[-1], 1.5)
    k -= post(ENC_BUSH_D + 2 * 0.4, Z_KNOB_CAP0 - 1, Z_KNOB_BORE0, ENC_X, ENC_Y)
    # D-flat bore: 6 mm shaft, 4.5 across the flat (PEC11R "F" shaft), + 0.1 press-fit clearance.
    bore = post(ENC_SHAFT_D + 0.1, Z_KNOB_BORE0 - 0.1, Z_KNOB_TOP + 1, ENC_X, ENC_Y)
    key = span(ENC_X - ENC_SHAFT_D, ENC_X + ENC_SHAFT_D, ENC_Y + ENC_SHAFT_D / 2 - 1.5 + 0.05,
               ENC_Y + ENC_SHAFT_D, Z_KNOB_BORE0 - 0.1, Z_KNOB_TOP + 1)
    k -= bore - key
    # Grip flutes round the rim.
    for i in range(18):
        k -= Pos(ENC_X, ENC_Y, 0) * Rot(0, 0, i * 20) * post(1.6, Z_KNOB_CAP0 + 0.8, Z_KNOB_TOP + 1,
                                                             KNOB_D / 2 + 0.3, 0)
    return k


def build():
    printed = {
        "front_shell": front_shell(),
        "panel_backer": backer(),
        "back_cover": back_cover(),
        "knob": knob(),
    }
    return printed, components()
