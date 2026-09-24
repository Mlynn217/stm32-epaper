#!/usr/bin/env python3
"""First-pass placement of the main board's core (hardware/kicad/stm32-epaper.kicad_pcb).

Leaves the enclosure-fixed parts from gen_main_pcb.py where they are, puts the big ICs on a hand
floorplan (FLOORPLAN below), then places every remaining part with a small greedy placer: as close
as possible to the pads it connects to, without courtyard overlaps, mounting holes or the edge.
Decoupling capacitors (parts on power nets only) go to the nearest unused power pin of their IC.
Finally adds the inner planes (In1 = GND; In2 = 3V3_AON with 3V3_PERIPH and +3V3 islands).

Run with KiCad's bundled Python:  kicad python3.11 hardware/scripts/place_main_pcb.py
It rewrites the positions of every part it places, so re-running discards hand moves of those parts:
once placement is being refined in pcbnew, stop running it.
"""
import json
import math
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')
PLACEMENT = os.path.join(HERE, '..', 'enclosure', 'out', 'pcb_placement.json')
X0, Y0 = 100.0, 100.0   # as gen_main_pcb.py: PCB-frame (x, y-up) origin = board (X0, Y0 + H)

POWER_NETS = {'GND', '+3V3', '3V3_AON', '3V3_PERIPH', 'VSYS', '+BATT', 'VBUS', '+5V', 'VBAT_RTC'}
FIXED = {'H301', 'H302', 'H303', 'H304', 'SW301', 'J1', 'J201', 'SW302', 'J302', 'J303', 'J2',
         'RT1', 'J301'}
# ref: (x, y, angle) in the PCB frame. MCU: its crystal pins (PC14/15, PH0/1) are on the left side.
FLOORPLAN = {
    # U101 (MCU), U201 (SDRAM) and U202 (QSPI) are not listed: optimise_core() picks the MCU
    # rotation and the memories' positions for the shortest bus ratsnest.
    'U301': (44.0, 55.0, 0),     # CAP1188: top-middle, between the electrode connectors J302/J303
    'U302': (39.5, 55.0, 0),     # electrode ESD, beside it (clear of RT1's pads)
    'U1': (21.0, 46.0, 0),       # BQ24073 charger, near the battery connector J2
    'U2': (9.0, 41.0, 0),        # TPS63802 -> +3V3
    'U3': (9.0, 26.0, 0),        # TPS61023 -> +5V (HAT)
    'U4': (27.0, 34.0, 0),       # TPS22965 peripheral load switch
    'U7': (27.0, 24.0, 0),       # MCP1700 RTC LDO
    'U6': (17.0, 33.0, 0),       # TPS63900 (DNP on v1)
    'U5': (73.7, 12.0, 0),       # USBLC6, beside J1
    'J101': (63.0, 15.0, 0),     # Tag-Connect SWD, bottom gap right of the encoder
    'SW101': (35.0, 16.0, 0),    # BOOT button, bottom gap left of the encoder
    'J102': (35.0, 7.0, 90),     # 1.27 mm header
}


def PLANES(full, rect):
    """(zone name, layer, net, priority, [outline polygons in the PCB frame])"""
    return [
        ('GND plane', pcbnew.In1_Cu, 'GND', 0, [full]),
        ('3V3_AON plane', pcbnew.In2_Cu, '3V3_AON', 0, [full]),
        ('3V3_PERIPH plane', pcbnew.In2_Cu, '3V3_PERIPH', 1,
         [rect(62.0, 16.0, 97.1, 52.0), rect(14.0, 0.3, 33.0, 14.5)]),
        ('+3V3 plane', pcbnew.In2_Cu, '+3V3', 1, [rect(0.3, 14.5, 31.0, 52.5)]),
    ]


# Placed before everything else, so the decoupling caps can't take the space at their pins:
# crystals and their load caps (short, sensitive nets), then the clock series resistors.
PRIORITY = ['Y101', 'Y102', 'C122', 'C123', 'C124', 'C125', 'R208', 'R209', 'R210']
BUS_PATTERNS = ['FMC_*', 'SDRAM_CLK', 'QUADSPI_*', 'QSPI_FLASH_CLK', 'SDIO_*', 'SDCARD_CLK',
                'USB_D?']
MCU_AT = (48.7, 36.5)


def optimise_core(fps, put, box, free, occupied, W):
    """Choose the MCU rotation and the SDRAM / QSPI positions with the smallest bus ratsnest
    (sum of MCU-pad to peer-pad distances over the bus nets). Places them, marks them occupied,
    and returns {ref: (x, y, angle)}."""
    import fnmatch

    def xy(pad):
        p = pad.GetPosition()
        return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)

    def is_bus(n):
        return any(fnmatch.fnmatchcase(n, p) for p in BUS_PATTERNS)

    def cost(refs):
        mcu = {p.GetNetname(): xy(p) for p in fps['U101'].Pads() if is_bus(p.GetNetname())}
        c = 0.0
        for ref in refs:
            for p in fps[ref].Pads():
                n = p.GetNetname()
                if n in mcu:
                    (ax, ay), (bx, by) = mcu[n], xy(p)
                    c += abs(ax - bx) + abs(ay - by)
        return c

    def best_spot(ref, angles, xs, ys, others):
        best = None
        for a in angles:
            for x in xs:
                for y in ys:
                    put(ref, x, y, a)
                    b = box(fps[ref])
                    if not free(b) or any(not (b[2] + 0.5 <= o[0] or o[2] + 0.5 <= b[0] or
                                               b[3] + 0.5 <= o[1] or o[3] + 0.5 <= b[1])
                                          for o in others):
                        continue
                    c = cost([ref])
                    if best is None or c < best[0]:
                        best = (c, x, y, a, b)
        return best

    fixed_peers = ['J201', 'J1']      # microSD socket and USB-C: placed by the enclosure
    xs = [60.0 + i for i in range(34)]
    ys = [18.0 + i for i in range(35)]
    results = []
    for mcu_a in (0, 90, 180, 270):
        put('U101', MCU_AT[0], MCU_AT[1], mcu_a)
        mb = box(fps['U101'])
        s1 = best_spot('U201', (0, 90), xs, ys, [mb])
        if not s1:
            continue
        put('U201', *s1[1:4])
        s2 = best_spot('U202', (0, 90, 180, 270), xs, ys, [mb, s1[4]])
        if not s2:
            continue
        put('U202', *s2[1:4])
        total = cost(['U201', 'U202'] + fixed_peers)
        results.append((total, mcu_a, s1, s2))
        print('  MCU %3d deg: bus ratsnest %.0f mm (SDRAM at %.0f,%.0f/%d, QSPI at %.0f,%.0f/%d)'
              % (mcu_a, total, s1[1], s1[2], s1[3], s2[1], s2[2], s2[3]))
    total, mcu_a, s1, s2 = min(results, key=lambda r: r[0])
    put('U101', MCU_AT[0], MCU_AT[1], mcu_a)
    put('U201', *s1[1:4])
    put('U202', *s2[1:4])
    for ref in ('U101', 'U201', 'U202'):
        occupied.append(box(fps[ref]))
    return {'U101': (MCU_AT[0], MCU_AT[1], mcu_a), 'U201': s1[1:4], 'U202': s2[1:4]}


MARGIN = 0.25                    # courtyard-to-courtyard gap
EDGE_KEEP = 0.6


def mm(v):
    return pcbnew.FromMM(v)


def main():
    info = json.load(open(PLACEMENT))
    W, H = info['pcb_size_mm']
    board = pcbnew.LoadBoard(BOARD)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def P(x, y):
        return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + H - y))

    def box(fp):
        """Courtyard bbox in PCB-frame mm (x0, y0, x1, y1), y up."""
        fp.BuildCourtyardCaches()
        poly = fp.GetCourtyard(pcbnew.F_CrtYd if not fp.IsFlipped() else pcbnew.B_CrtYd)
        bb = poly.BBox() if poly.OutlineCount() else fp.GetBoundingBox(False)
        x0, x1 = pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetRight()) - X0
        y0, y1 = Y0 + H - pcbnew.ToMM(bb.GetBottom()), Y0 + H - pcbnew.ToMM(bb.GetTop())
        return x0, y0, x1, y1

    def pad_xy(pad):
        p = pad.GetPosition()
        return pcbnew.ToMM(p.x) - X0, Y0 + H - pcbnew.ToMM(p.y)

    occupied = []
    for (x, y) in info['mounting_holes_pcb_xy']:
        occupied.append((x - 2.0, y - 2.0, x + 2.0, y + 2.0))   # hole + screw head
    for (x, y) in info['boss_notches_pcb_xy']:
        r = info['boss_notch_d_mm'] / 2 + 0.5
        occupied.append((x - r, y - r, x + r, y + r))

    def free(b):
        x0, y0, x1, y1 = b
        if x0 < EDGE_KEEP or y0 < EDGE_KEEP or x1 > W - EDGE_KEEP or y1 > H - EDGE_KEEP:
            return False
        return all(x1 + MARGIN <= a0 or a1 + MARGIN <= x0 or y1 + MARGIN <= b0 or b1 + MARGIN <= y0
                   for a0, b0, a1, b1 in occupied)

    def put(ref, x, y, angle):
        fp = fps[ref]
        fp.SetOrientationDegrees(angle)
        fp.SetPosition(P(x, y))

    for ref in FIXED:
        occupied.append(box(fps[ref]))
    # Fixed floorplan parts first, so the core optimiser works around them.
    for ref, (x, y, a) in FLOORPLAN.items():
        put(ref, x, y, a)
        b = box(fps[ref])
        assert free(b), 'floorplan collision: %s at %s' % (ref, b)
        occupied.append(b)
    core = optimise_core(fps, put, box, free, occupied, W)
    placed = set(FIXED) | set(FLOORPLAN) | set(core)

    # Power pins of the ICs, for decoupling assignment: {net: [(x, y, ic_ref)]}, consumed as used.
    power_pins = {}
    for ref in list(FLOORPLAN) + list(core):
        if ref.startswith('U'):
            for pad in fps[ref].Pads():
                n = pad.GetNetname()
                if n in POWER_NETS and n != 'GND':
                    power_pins.setdefault(n, []).append(pad_xy(pad) + (ref,))

    pads_by_net = {}
    for pad in board.GetPads():
        pads_by_net.setdefault(pad.GetNetname(), []).append(pad)

    def owner_ic(ref):
        """Which IC a power-only part (decoupling) belongs to, from the sheet numbering:
        1xx = MCU sheet, 2xx = Memory, 3xx = Peripherals, 1-2 digits = Power sheet."""
        num = int(''.join(c for c in ref if c.isdigit()) or 0)
        return 'U301' if num >= 300 else 'U201' if num >= 200 else 'U101' if num >= 100 else None

    def anchor(fp):
        pts = []
        for pad in fp.Pads():
            n = pad.GetNetname()
            if not n or n in POWER_NETS or n.startswith('unconnected-'):
                continue
            for other in pads_by_net.get(n, []):
                if other.GetParentFootprint().GetReference() in placed:
                    pts.append(pad_xy(other))
        if pts:
            return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        ic = owner_ic(fp.GetReference())
        for pad in fp.Pads():
            cands = power_pins.get(pad.GetNetname())
            if not cands:
                continue
            if ic:
                pref = [c for c in cands if c[2] == ic] or cands
            else:   # power sheet: the power IC pins, nearest to the power cluster
                pref = [c for c in cands if c[2] in ('U1', 'U2', 'U3', 'U4', 'U7')] or cands
                pref.sort(key=lambda c: math.hypot(c[0] - 15, c[1] - 35))
            c = pref[0]
            cands.remove(c)
            return c[0], c[1]
        # Every power pin of the IC already has a part next to it: go to the IC itself.
        for pad in fp.Pads():
            n = pad.GetNetname()
            if n in POWER_NETS and n != 'GND':
                ics = [ic] if ic else ['U1', 'U2', 'U3', 'U4', 'U7']
                pts = [pad_xy(o) for o in pads_by_net.get(n, [])
                       if o.GetParentFootprint().GetReference() in ics]
                if pts:
                    return sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)
        return None

    # Clock series resistors go right at their MCU pin (source termination).
    SOURCE_TERM = {'R208': 'FMC_SDCLK', 'R209': 'SDIO_CK', 'R210': 'QUADSPI_CLK'}

    def mcu_pin(net):
        for pad in pads_by_net.get(net, []):
            if pad.GetParentFootprint().GetReference() == 'U101':
                return pad_xy(pad)
        return None

    def spiral(ax, ay, fp):
        for r in [i * 0.5 for i in range(0, 120)]:
            steps = max(1, int(2 * math.pi * r / 0.5))
            for k in range(steps):
                t = 2 * math.pi * k / steps
                x, y = ax + r * math.cos(t), ay + r * math.sin(t)
                for a in (0, 90):
                    put(fp.GetReference(), x, y, a)
                    b = box(fp)
                    if free(b):
                        return b
        return None

    # Greedy: repeatedly place the unplaced part with the most connections into placed parts.
    remaining = [r for r in fps if r not in placed]
    unplaced = []
    while remaining:
        def links(ref):
            nets = {p.GetNetname() for p in fps[ref].Pads()} - POWER_NETS
            return sum(1 for r in placed for p in fps[r].Pads() if p.GetNetname() in nets)
        first = [r for r in PRIORITY if r in remaining]
        if first:
            ref = first[0]
            remaining.remove(ref)
        else:
            remaining.sort(key=lambda r: (-links(r), r))
            ref = remaining.pop(0)
        fp = fps[ref]
        # Bring-up test points: kept together in the bottom-right corner, easy to probe.
        if ref.startswith('TP'):
            a = (W - 8.0, 8.0)
        elif ref in SOURCE_TERM:
            a = mcu_pin(SOURCE_TERM[ref])
        else:
            a = anchor(fp)
        if a is None:
            a = (W - 8.0, 8.0)
        b = spiral(a[0], a[1], fp)
        if b is None:
            unplaced.append(ref)
            continue
        occupied.append(b)
        placed.add(ref)

    # Reference designators: keep them on silkscreen for ICs, connectors, switches, crystals
    # and test points; passives are too dense, so theirs go to F.Fab (assembly drawing) only.
    for ref, fp in fps.items():
        prefix = ref.rstrip('0123456789')
        if prefix in ('R', 'C', 'L', 'FB', 'D'):
            fp.Reference().SetLayer(pcbnew.F_Fab)

    # Inner planes (added once; a re-run keeps the existing ones - removing zones and adding new
    # ones in the same session trips a SWIG typing bug in KiCad 10's Python).
    # In1 = GND. In2 = the 3.3 V rails, split by where their pins are: 3V3_AON (MCU, CAP1188,
    # buttons, pull-ups - everywhere) as the base, with higher-priority islands for 3V3_PERIPH
    # (SDRAM/QSPI block, microSD socket) and +3V3 (the power stage).
    have = {z.GetZoneName() for z in board.Zones()}
    full = ((0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3))

    def rect(x0, y0, x1, y1):
        return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    for name, layer, net, prio, outlines in PLANES(full, rect):
        if name in have:
            continue
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(board.FindNet(net))
        ol = z.Outline()
        for poly in outlines:
            ol.NewOutline()
            for x, y in poly:
                ol.Append(P(x, y).x, P(x, y).y)
        z.SetAssignedPriority(prio)
        z.SetMinThickness(mm(0.2))
        z.SetLocalClearance(mm(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetZoneName(name)
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    pcbnew.SaveBoard(BOARD, board)
    print('placed %d parts (%d floorplanned); unplaced: %s'
          % (len(placed) - len(FIXED), len(FLOORPLAN), unplaced or 'none'))


if __name__ == '__main__':
    main()
