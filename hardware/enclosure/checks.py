"""Fit checks run on every build: the cheap way to catch mistakes before paying for a print.

Each check returns (ok, message). A failed check makes build.py exit non-zero.
"""

import itertools

import model as m
from params import *  # noqa: F401,F403

EPS_VOL = 0.01  # mm^3; anything below is a touching face, not an interference

# Pairs that overlap on purpose.
ALLOWED = {
    frozenset(("knob", "encoder_shaft")),    # the shaft sits in the knob's bore (D-flat vs round envelope)
    frozenset(("usb_c", "usb_plug")),        # the plug envelope starts at the receptacle mouth
    frozenset(("sd_socket", "sd_card_path")),  # the card goes into the socket
}


def interferences(printed, components):
    solids = {**printed, **components}
    results = []
    for (na, a), (nb, b) in itertools.combinations(solids.items(), 2):
        if frozenset((na, nb)) in ALLOWED:
            continue
        ba, bb = a.bounding_box(), b.bounding_box()
        if (ba.max.X <= bb.min.X or bb.max.X <= ba.min.X or ba.max.Y <= bb.min.Y
                or bb.max.Y <= ba.min.Y or ba.max.Z <= bb.min.Z or bb.max.Z <= ba.min.Z):
            continue
        common = a & b
        vol = common.volume if common is not None else 0.0
        if vol > EPS_VOL:
            results.append((False, f"interference: {na} x {nb} = {vol:.2f} mm^3"))
    if not results:
        results.append((True, f"no interferences among {len(solids)} parts/envelopes"))
    return results


def rules():
    r = []

    def check(ok, msg):
        r.append((bool(ok), msg))

    check(WALL_MIN <= SIDE_WALL - m.DIMPLE_DEPTH and SIDE_WALL <= ELECTRODE_WALL_MAX,
          f"side wall {SIDE_WALL} mm ({SIDE_WALL - m.DIMPLE_DEPTH:.1f} at the thumb dimples): "
          f">= {WALL_MIN} to print, <= {ELECTRODE_WALL_MAX} for the CAP1188 electrodes")
    for name, t in (("END_WALL", END_WALL), ("BEZEL_T", BEZEL_T), ("BACK_T", BACK_T),
                    ("BACKER_T", BACKER_T)):
        check(t >= WALL_MIN, f"{name} {t} mm >= WALL_MIN {WALL_MIN}")

    engage = m.Z_SHAFT_TIP - m.Z_KNOB_HUB0
    check(engage >= 5.0, f"knob grips {engage:.1f} mm of encoder shaft (want >= 5)")
    proud = m.Z_KNOB_TOP - OUTER_T
    check(3.0 <= proud <= 8.0, f"knob stands {proud:.1f} mm proud of the front face (want 3-8)")
    check(KNOB_GAP > ENC_PUSH_TRAVEL,
          f"knob skirt gap {KNOB_GAP} mm > push travel {ENC_PUSH_TRAVEL} mm (the click isn't blocked)")
    check(m.ENC_Y + KNOB_D / 2 < m.PANEL_BOT - 1.0,
          f"knob clears the display ({m.PANEL_BOT - m.ENC_Y - KNOB_D / 2:.1f} mm below the panel)")
    check(m.Z_ENC_TOP < Z_BEZEL, "encoder body fits under the chin")

    lead_gap = m.BATT_Y0 - m.PCB_Y1
    check(lead_gap <= 40.0,
          f"battery lead edge is {lead_gap:.1f} mm from the PCB top edge (50 mm lead, keep J2 within ~40)")
    check(m.PCB_Y1 <= m.BATT_Y0, "battery zone is clear of the PCB (RT1 NTC needs a pigtail/pad to reach the pouch)")

    for name, zc, h in (("USB-C", m.USB_ZC, USB_PLUG_T + 2 * SLIDE_CLEAR),
                        ("microSD", m.SD_ZC, SD_CARD_T + 0.8),
                        ("button", m.BTN_ZC, BTN_T + 2 * SLIDE_CLEAR)):
        lo, hi = zc - h / 2, zc + h / 2
        check(Z_BACK_IN + 0.5 <= lo and hi <= Z_BEZEL - 0.5,
              f"{name} opening z {lo:.1f}..{hi:.1f} leaves wall above/below "
              f"(cavity {Z_BACK_IN:.1f}..{Z_BEZEL:.1f})")
    return r


def thickness_driver():
    zones = {"battery (+swell)": BATT_ZONE_T, "PCB + parts": PCB_ZONE_T, "HAT": HAT_T}
    name = max(zones, key=zones.get)
    return name, zones
