#!/usr/bin/env python3
"""Build hardware/electrode/electrode.kicad_pcb with KiCad's own pcbnew API.

Run with KiCad's bundled Python (it has the pcbnew module):
    kicad python3.11 hardware/scripts/gen_electrode_pcb.py        # ~/.local/bin/kicad = the AppImage

Needs the schematic from gen_electrode.py first (footprints are linked to its symbols, so DRC's
schematic-parity check works). Safe to re-run: the board is fully generated. Board frame: X runs
along the board (device Y, from its bottom end), Y across it (device Z); the FRONT copper faces
the enclosure wall and carries only the two mask-covered electrode pads.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'enclosure'))
sys.path.insert(0, HERE)

import gen_electrode as ge  # noqa: E402  (pad size, footprint names; no KiCad imports)
import params  # noqa: E402
from sexp import find, find1, parse  # noqa: E402

OUT = os.path.join(HERE, '..', 'electrode')
BOARD = os.path.join(OUT, 'electrode.kicad_pcb')
X0, Y0 = 100.0, 100.0          # board origin on the sheet (mm)
TRACK, VIA_D, VIA_DRILL = 0.25, 0.6, 0.3
EDGE_KEEP = 1.5                # channel lips overlap the board ends: keep them clear


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))


def xy(v):
    return pcbnew.ToMM(v.x) - X0, pcbnew.ToMM(v.y) - Y0


def stock_footprint_dir():
    d = os.environ.get('KICAD10_FOOTPRINT_DIR')
    if d and os.path.isdir(d):
        return d
    # AppImage layout: <mount>/shared/lib/python3.11/dist-packages/pcbnew.py
    root = os.path.abspath(os.path.join(os.path.dirname(pcbnew.__file__), *(['..'] * 4)))
    return os.path.join(root, 'usr', 'share', 'kicad', 'footprints')


def symbols():
    """{ref: (uuid, {field: value})} for the schematic's real (non-power) symbols."""
    doc = parse(open(os.path.join(OUT, ge.PROJECT + '.kicad_sch')).read())
    out = {}
    for sym in find(doc, 'symbol'):
        props = {p[1]: p[2] for p in find(sym, 'property')}
        if not props.get('Reference', '#').startswith('#'):
            out[props['Reference']] = (find1(sym, 'uuid')[1], props)
    return out


def main():
    board = pcbnew.CreateEmptyBoard()
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(params.EB_T))
    L, W = params.EB_L, params.EB_W

    edge = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    edge.SetStart(pt(0, 0))
    edge.SetEnd(pt(L, W))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(mm(0.05))
    board.Add(edge)

    nets = {}
    for name in ('GND', '/TOUCH_1', '/TOUCH_2'):
        nets[name] = pcbnew.NETINFO_ITEM(board, name)
        board.Add(nets[name])

    syms = symbols()
    fp_libs = {'electrode': os.path.join(OUT, 'electrode.pretty')}

    def place(ref, lib_fp, value, x, y, back=False, angle=0.0):
        lib, name = lib_fp.split(':')
        path = fp_libs.get(lib) or os.path.join(stock_footprint_dir(), lib + '.pretty')
        fp = pcbnew.FootprintLoad(path, name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(ref)
        fp.SetValue(value)
        uuid, props = syms[ref]
        fp.SetPath(pcbnew.KIID_PATH('/' + uuid))
        board.Add(fp)
        for key, val in props.items():  # what "Update PCB from Schematic" would copy
            if key not in ('Reference', 'Value', 'Footprint'):
                fp.SetField(key, val)
                fp.GetField(key).SetVisible(False)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(angle)
        if back:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        return fp

    # Electrode pads, centred on the thumb zones (device Y -> board X).
    pad_x = [yc - params.EB_Y0 for yc in params.ELECTRODE_Y]
    e1 = place('E1', 'electrode:' + ge.PAD_FP, 'Electrode (lower zone)', pad_x[0], W / 2)
    e2 = place('E2', 'electrode:' + ge.PAD_FP, 'Electrode (upper zone)', pad_x[1], W / 2)
    e1.Pads()[0].SetNet(nets['/TOUCH_1'])
    e2.Pads()[0].SetNet(nets['/TOUCH_2'])

    # Connector on the back, cable entry pointing at the main PCB (board -X = device -Y). The
    # entry is on the mounting-pad side of the body, opposite the signal pins.
    cx = params.EB_CONN_Y - params.EB_Y0
    for angle in (0, 90, 180, 270):
        j1 = place('J1', ge.CONN_FP, 'To main board', cx, W / 2, back=True, angle=angle)
        sig = [p for p in j1.Pads() if p.GetNumber() in ('1', '2', '3')]
        mp = [p for p in j1.Pads() if p.GetNumber() == 'MP']
        sx = sum(xy(p.GetPosition())[0] for p in sig) / 3
        mx = sum(xy(p.GetPosition())[0] for p in mp) / len(mp)
        if mx < sx - 1.0:
            break
        board.Remove(j1)
    else:
        sys.exit('no connector orientation points the cable at -X')
    pin = {p.GetNumber(): xy(p.GetPosition()) for p in sig}
    for p in sig:
        p.SetNet(nets[{'1': '/TOUCH_1', '2': 'GND', '3': '/TOUCH_2'}[p.GetNumber()]])
    body_x0 = min(xy(p.GetPosition())[0] for p in mp) - 1.5

    def track(a, b, net):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pt(*a))
        t.SetEnd(pt(*b))
        t.SetWidth(mm(TRACK))
        t.SetLayer(pcbnew.B_Cu)
        t.SetNet(nets[net])
        board.Add(t)

    def via(p, net):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pt(*p))
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[net])
        board.Add(v)

    # TOUCH_2: via just inside the upper pad, straight along pin 3's line to the pin.
    v2 = (pad_x[1] - params.ELECTRODE_H / 2 + 1.5, pin['3'][1])
    via(v2, '/TOUCH_2')
    track(v2, pin['3'], '/TOUCH_2')

    # TOUCH_1: out of pin 1 away from the body, to the long edge on pin 1's side, back past the
    # connector body, and down a via into the lower pad.
    x1, y1 = pin['1']
    edge_y = ge.PAD_MARGIN + 0.3 if y1 < W / 2 else W - ge.PAD_MARGIN - 0.3
    jog = x1 + 1.2
    v1 = (body_x0, edge_y)
    assert pad_x[0] - params.ELECTRODE_H / 2 + 1 < v1[0] < pad_x[0] + params.ELECTRODE_H / 2 - 1
    for a, b in (((x1, y1), (jog, y1)), ((jog, y1), (jog, edge_y)), ((jog, edge_y), v1)):
        track(a, b, '/TOUCH_1')
    via(v1, '/TOUCH_1')

    # GND: a stub off pin 2 (the pins are too close for the pour to reach between them).
    track(pin['2'], (pin['2'][0] + 2.5, pin['2'][1]), 'GND')

    # Hatched GND pour on the back only (shields the pads from the internals without the full
    # parasitic capacitance of a solid plane). None on the front: the pads sense through it.
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(nets['GND'])
    ol = z.Outline()
    ol.NewOutline()
    for p in ((0.3, 0.3), (L - 0.3, 0.3), (L - 0.3, W - 0.3), (0.3, W - 0.3)):
        ol.Append(mm(X0 + p[0]), mm(Y0 + p[1]))
    z.SetFillMode(pcbnew.ZONE_FILL_MODE_HATCH_PATTERN)
    z.SetHatchThickness(mm(0.25))
    z.SetHatchGap(mm(1.0))
    z.SetMinThickness(mm(0.25))
    z.SetLocalClearance(mm(0.3))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    board.Add(z)

    # Back silkscreen (mirrored, readable from the back).
    for text, y in (('EPAPER SIDE ELECTRODE v1', W / 2 - 1.2), ('PADS FACE THE WALL', W / 2 + 1.2)):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.B_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        t.SetTextThickness(mm(0.15))
        t.SetMirrored(True)
        t.SetPosition(pt((pad_x[1] + cx) / 2 + 6, y))
        board.Add(t)

    assert EDGE_KEEP < pad_x[0] - params.ELECTRODE_H / 2 and pad_x[1] + params.ELECTRODE_H / 2 < L - EDGE_KEEP

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print('wrote', os.path.relpath(BOARD))


if __name__ == '__main__':
    main()
