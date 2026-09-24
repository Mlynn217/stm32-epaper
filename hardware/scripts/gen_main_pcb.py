#!/usr/bin/env python3
"""Start the main board layout: hardware/kicad/stm32-epaper.kicad_pcb.

Creates the 4-layer board with the outline the enclosure dictates, loads every footprint from the
schematic netlist (nets and symbol links included, so DRC's schematic-parity check works), places
the parts whose position the ENCLOSURE fixes (encoder, bottom-edge USB-C / microSD / power switch,
top-edge cable connectors, mounting holes), and stages everything else beside the board, grouped
by sheet, for real placement and routing in the KiCad GUI.

This is a one-shot bootstrap like gen_schematic.py: once the board has been edited in pcbnew it is
the source of truth, so this refuses to overwrite it without --force.

Run with KiCad's bundled Python, after the enclosure build (for out/pcb_placement.json):
    ~/.venvs/cad/bin/python hardware/enclosure/build.py --no-render
    kicad-cli sch export netlist --format kicadxml -o /tmp/main.xml hardware/kicad/stm32-epaper.kicad_sch
    kicad python3.11 hardware/scripts/gen_main_pcb.py /tmp/main.xml [--force]
"""
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
KICAD = os.path.join(HERE, '..', 'kicad')
BOARD = os.path.join(KICAD, 'stm32-epaper.kicad_pcb')
PLACEMENT = os.path.join(HERE, '..', 'enclosure', 'out', 'pcb_placement.json')
X0, Y0 = 100.0, 100.0          # board lower-left corner on the sheet is (X0, Y0 + H)
# (name, track, clearance, via, drill, net-name patterns)
NETCLASSES = [
    # ~1 A paths and converter switch nodes. 0.3 mm carries ~1 A on outer 1 oz copper and still
    # enters the 0.25 mm pads of the 0.5 mm-pitch converter ICs (0.5 mm couldn't: freerouting
    # doesn't neck tracks down, so those nets never routed).
    ('Power', 0.3, 0.15, 0.6, 0.3, ['VBUS', 'VSYS', '+BATT', '+5V', '*/BB_L1', '*/BB_L2',
                                    '*/BST_SW', '*/AON_LX*']),
    ('Rail3V3', 0.3, 0.15, 0.45, 0.2, ['+3V3', '3V3_AON', '3V3_PERIPH', 'VBAT_RTC']),
    # Capacitive touch: thin (low capacitance), double clearance (nothing runs close by). 0.4 mm
    # couldn't escape the CAP1188 / ESD chip's 0.5 mm-pitch pins.
    ('Touch', 0.15, 0.25, 0.45, 0.2, ['*TOUCH_*']),
    # Memory clocks: extra spacing against crosstalk.
    ('Clock', 0.15, 0.2, 0.45, 0.2, ['FMC_SDCLK', 'SDRAM_CLK', 'SDIO_CK', 'SDCARD_CLK',
                                     'QUADSPI_CLK', 'QSPI_FLASH_CLK']),
]


def mm(v):
    return pcbnew.FromMM(v)


def stock_footprint_dir():
    d = os.environ.get('KICAD10_FOOTPRINT_DIR')
    if d and os.path.isdir(d):
        return d
    root = os.path.abspath(os.path.join(os.path.dirname(pcbnew.__file__), *(['..'] * 4)))
    return os.path.join(root, 'usr', 'share', 'kicad', 'footprints')


def read_netlist(path):
    """[(ref, footprint, value, symbol path, {field: value})], {net: [(ref, pin)]}"""
    root = ET.parse(path).getroot()
    comps = []
    for c in root.iter('comp'):
        sp = c.find('sheetpath').get('tstamps')
        fields = {f.get('name'): (f.text or '') for f in c.iter('field')}
        props = {p.get('name') for p in c.iter('property')}
        comps.append((c.get('ref'), c.findtext('footprint'), c.findtext('value'),
                      sp + c.findtext('tstamps').split()[0], c.find('sheetpath').get('names'),
                      fields, 'dnp' in props, 'exclude_from_bom' in props))

    def netname(n):  # KiCad escapes '/' inside auto-named "unconnected-(REF-PIN-PadN)" nets
        return n.replace('/', '{slash}') if n.startswith('unconnected-(') else n
    nets = {netname(n.get('name')): [(x.get('ref'), x.get('pin')) for x in n.iter('node')]
            for n in root.iter('net')}
    return comps, nets


def fab_bbox(fp):
    """Body outline (F.Fab / B.Fab graphics) in board mm: (x0, y0, x1, y1)."""
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
            bb = g.GetBoundingBox()
            xs += [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetRight())]
            ys += [pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetBottom())]
    if not xs:
        bb = fp.GetBoundingBox(False)
        return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    return min(xs), min(ys), max(xs), max(ys)


def pad_centroid(fp, pred):
    ps = [p for p in fp.Pads() if pred(p.GetNumber())]
    return (sum(pcbnew.ToMM(p.GetPosition().x) for p in ps) / len(ps),
            sum(pcbnew.ToMM(p.GetPosition().y) for p in ps) / len(ps))


def facing(fp, rule):
    """Unit vector of the side a part 'faces' (its opening / plunger), from its pads.
    rule 'mp': towards the MP pads (JST side-entry, Alps SKRT plunger).
    rule 'away': away from the signal pads (USB-C mouth, microSD card slot)."""
    sig = pad_centroid(fp, lambda n: n not in ('MP', 'SH', ''))
    if rule == 'mp':
        other = pad_centroid(fp, lambda n: n == 'MP')
        v = (other[0] - sig[0], other[1] - sig[1])
    else:
        x0, y0, x1, y1 = fab_bbox(fp)
        v = ((x0 + x1) / 2 - sig[0], (y0 + y1) / 2 - sig[1])
    n = math.hypot(*v)
    return v[0] / n, v[1] / n


def outline(board, W, H, notches, notch_d):
    """Rectangle with circular corner notches (for the enclosure's screw bosses)."""
    r = notch_d / 2

    def P(x, y):  # PCB frame (origin lower-left, y up) -> board coordinates
        return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + H - y))

    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.05))
        board.Add(s)

    def arc(a, m, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(*a), P(*m), P(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.05))
        board.Add(s)

    # Only bottom-corner notches are expected (the chin bosses); each cuts the bottom edge at
    # xb and the side edge at ys.
    cut = {}
    for cx, cy in notches:
        side_x = 0.0 if cx < W / 2 else W
        dx = abs(side_x - cx)
        xb = cx + (1 if side_x == 0 else -1) * math.sqrt(r * r - cy * cy)
        ys = cy + math.sqrt(r * r - dx * dx)
        ang = math.atan2(((0 + ys) / 2) - cy, ((xb + side_x) / 2) - cx)  # bisector, inwards
        mid = (cx + r * math.cos(ang), cy + r * math.sin(ang))
        cut[side_x] = (xb, ys, mid)
    xl, yl, ml = cut.get(0.0, (0.0, 0.0, None))
    xr, yr, mr = cut.get(W, (W, 0.0, None))
    seg((xl, 0), (xr, 0))
    seg((W, yr), (W, H))
    seg((W, H), (0, H))
    seg((0, H), (0, yl))
    if ml:
        arc((0, yl), ml, (xl, 0))
    if mr:
        arc((xr, 0), mr, (W, yr))
    return P


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if os.path.exists(BOARD) and '--force' not in sys.argv:
        sys.exit('refusing to overwrite %s (it may have layout edits); pass --force' % BOARD)
    place_info = json.load(open(PLACEMENT))
    W, H = place_info['pcb_size_mm']
    comps, nets = read_netlist(sys.argv[1])

    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    # Fab rules for a standard 4-layer service (JLCPCB-class): 0.1 mm clearance/track, 0.2 mm
    # hole-to-copper, 0.45/0.2 mm vias. KiCad's generic 0.2 mm default clearance fails the
    # parts' own 0.5 mm-pitch land patterns (SOT-563, LQFP-176).
    ds.m_MinClearance = mm(0.1)
    ds.m_TrackMinWidth = mm(0.1)
    ds.m_HoleClearance = mm(0.2)
    ds.m_ViasMinSize = mm(0.45)
    ds.m_MinThroughDrill = mm(0.2)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(0.127))
    nc.SetTrackWidth(mm(0.15))
    nc.SetViaDiameter(mm(0.45))
    nc.SetViaDrill(mm(0.2))
    # Net classes: exported in the Specctra DSN, so freerouting obeys their widths/clearances.
    # (Length/skew limits can't be expressed there: they live in stm32-epaper.kicad_dru and are
    # checked by KiCad's DRC after routing.)
    ns = ds.m_NetSettings
    for name, width, clearance, via, drill, patterns in NETCLASSES:
        c = pcbnew.NETCLASS(name)
        c.SetTrackWidth(mm(width))
        c.SetClearance(mm(clearance))
        c.SetViaDiameter(mm(via))
        c.SetViaDrill(mm(drill))
        ns.SetNetclass(name, c)
        for pat in patterns:
            ns.SetNetclassPatternAssignment(pat, name)
    P = outline(board, W, H, place_info['boss_notches_pcb_xy'], place_info['boss_notch_d_mm'])

    netinfo = {}
    for name in nets:
        netinfo[name] = pcbnew.NETINFO_ITEM(board, name)
        board.Add(netinfo[name])
    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}

    libs = {'epaper': os.path.join(KICAD, 'epaper.pretty')}
    fps = {}
    for ref, fpid, value, path, sheet, fields, dnp, no_bom in comps:
        lib, name = fpid.split(':')
        fp = pcbnew.FootprintLoad(libs.get(lib) or os.path.join(stock_footprint_dir(), lib + '.pretty'),
                                  name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(value)
        fp.SetPath(pcbnew.KIID_PATH(path))
        fp.SetDNP(dnp)
        fp.SetExcludedFromBOM(no_bom)
        board.Add(fp)
        for key, val in fields.items():
            if key not in ('Reference', 'Value', 'Footprint') and val:
                fp.SetField(key, val)
                fp.GetField(key).SetVisible(False)
        for pad in fp.Pads():
            net = pin_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(netinfo[net])
        fps[ref] = (fp, sheet)

    def put(ref, x, y, angle=0.0):
        fp = fps[ref][0]
        fp.SetOrientationDegrees(angle)
        fp.SetPosition(P(x, y))
        return fp

    def to_edge(ref, x, edge, rule):
        """Place `ref` centred on PCB x, facing out of the bottom ('b') or top ('t') edge, with
        its body flush with that edge."""
        want = (0.0, 1.0) if edge == 'b' else (0.0, -1.0)   # board y grows downwards
        best = max((0, 90, 180, 270),
                   key=lambda a: (put(ref, x, H / 2, a), facing(fps[ref][0], rule))[1][1] * want[1])
        fp = put(ref, x, H / 2, best)
        x0, y0, x1, y1 = fab_bbox(fp)
        cx = (x0 + x1) / 2
        pos = fp.GetPosition()
        if edge == 'b':
            dy = (Y0 + H) - y1
        else:
            dy = Y0 - y0
        fp.SetPosition(pcbnew.VECTOR2I(pos.x + mm(X0 + x - cx), pos.y + mm(dy)))
        # Pull it back in if any copper (or hole) is inside the board-edge clearance.
        keep = pcbnew.ToMM(ds.m_CopperEdgeClearance) + 0.05
        pad_y = [pcbnew.ToMM(p.GetBoundingBox().GetBottom() if edge == 'b' else p.GetBoundingBox().GetTop())
                 for p in fp.Pads()]
        if edge == 'b':
            over = max(pad_y) - (Y0 + H - keep)
        else:
            over = (Y0 + keep) - min(pad_y)
        if over > 0:
            pos = fp.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(pos.x, pos.y + mm(-over if edge == 'b' else over)))
            insets[ref] = over
        return best

    placed = set()
    insets = {}
    # Enclosure-fixed parts (pcb_placement.json, generated from hardware/enclosure/params.py).
    for (x, y), ref in zip(place_info['mounting_holes_pcb_xy'], ('H301', 'H302', 'H303', 'H304')):
        put(ref, x, y); placed.add(ref)
    put('SW301', *place_info['encoder_axis_pcb_xy']); placed.add('SW301')
    to_edge('J1', place_info['usb_c_centre_on_bottom_edge_pcb_x'], 'b', 'away'); placed.add('J1')
    to_edge('J201', place_info['microsd_card_centre_on_bottom_edge_pcb_x'], 'b', 'away')
    placed.add('J201')
    to_edge('SW302', place_info['power_switch_SW302']['centre_x_pcb'], 'b', 'mp'); placed.add('SW302')
    # Top edge: cables up to the electrode boards (outer corners), the battery and the HAT.
    to_edge('J302', 14.0, 't', 'mp'); placed.add('J302')
    to_edge('J303', W - 14.0, 't', 'mp'); placed.add('J303')
    to_edge('J2', 24.0, 't', 'mp'); placed.add('J2')
    put('RT1', 33.0, H - 3.0); placed.add('RT1')
    fp = put('J301', 0, H - 3.0, 90)
    xs = [pcbnew.ToMM(p.GetPosition().x) for p in fp.Pads()]
    pos = fp.GetPosition()
    fp.SetPosition(pcbnew.VECTOR2I(pos.x + mm(X0 + W / 2 + 15.0 - (min(xs) + max(xs)) / 2), pos.y))
    placed.add('J301')

    # Everything else: staged to the right of the board, one block per sheet.
    x_stage, y_cursor = W + 15.0, H
    for sheet in ('/Power/', '/MCU/', '/Memory/', '/Peripherals/'):
        refs = sorted((r for r, (f, s) in fps.items() if s == sheet and r not in placed),
                      key=lambda r: (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()) or 0)))
        x, row_h = x_stage, 0.0
        for ref in refs:
            fp = put(ref, 0, 0)
            bb = fp.GetBoundingBox(False)  # pads + graphics, no text
            org = fp.GetPosition()
            w = pcbnew.ToMM(bb.GetWidth()) + 1.5
            h = pcbnew.ToMM(bb.GetHeight()) + 1.5
            if x + w > x_stage + 110:
                x, y_cursor, row_h = x_stage, y_cursor - row_h, 0.0
            # put the bbox's top-left at (x, y_cursor) in the PCB frame
            ox = pcbnew.ToMM(org.x - bb.GetLeft())
            oy = pcbnew.ToMM(org.y - bb.GetTop())
            fp.SetPosition(pcbnew.VECTOR2I(mm(X0 + x + ox), mm(Y0 + H - y_cursor + oy)))
            x += w
            row_h = max(row_h, h)
        y_cursor -= row_h + 8.0

    pcbnew.SaveBoard(BOARD, board)
    print('wrote %s: %d footprints, %d placed by the enclosure' % (os.path.relpath(BOARD), len(fps),
                                                                  len(placed)))
    for ref, over in insets.items():
        print('  %s pulled %.2f mm in from the edge (copper-to-edge clearance)' % (ref, over))


if __name__ == '__main__':
    main()
