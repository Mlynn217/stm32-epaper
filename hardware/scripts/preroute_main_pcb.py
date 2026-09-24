#!/usr/bin/env python3
"""Scripted pre-routing for the main board, locked so freerouting treats it as protected.

  - plane vias: every pad on a plane net (GND, 3V3_AON, 3V3_PERIPH, +3V3) gets a short stub and a
    via, where that net's plane is actually filled under the via;
  - MCU fanout (--fanout): each LQFP-176 signal pin gets a dog-bone (stub straight out from its
    side of the package + via), staggered in two rows so 0.5 mm pitch fits.
Every candidate is collision-checked against other nets' pads and the copper added so far, and
skipped (left to the autorouter) if it doesn't fit.

    kicad python3.11 hardware/scripts/preroute_main_pcb.py [--fanout]

Starts by deleting all tracks/vias, so run it on a placed, unrouted board (place_main_pcb.py).
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')
PLANE_NETS = {'GND': pcbnew.In1_Cu, '3V3_AON': pcbnew.In2_Cu, '3V3_PERIPH': pcbnew.In2_Cu,
              '+3V3': pcbnew.In2_Cu}
VIA_D, VIA_DRILL = 0.45, 0.2
CLEAR = 0.15          # a little over the 0.127 mm default clearance
MCU = 'U101'


def mm(v):
    return pcbnew.FromMM(v)


def tomm(v):
    return pcbnew.ToMM(v)


def main():
    fanout = '--fanout' in sys.argv
    board = pcbnew.LoadBoard(BOARD)
    for t in list(board.GetTracks()):
        board.Remove(t)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    # Obstacles: (x0, y0, x1, y1, netcode) in mm, board coordinates (y down).
    obst = []
    for pad in board.GetPads():
        bb = pad.GetBoundingBox()
        obst.append((tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()),
                     tomm(bb.GetBottom()), pad.GetNetCode()))
    edge = board.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = (tomm(edge.GetLeft()) + 0.5, tomm(edge.GetTop()) + 0.5,
                          tomm(edge.GetRight()) - 0.5, tomm(edge.GetBottom()) - 0.5)
    holes = [(tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)) for fp in board.GetFootprints()
             if fp.GetReference().startswith('H3')]

    def clear_box(x0, y0, x1, y1, net):
        for a0, b0, a1, b1, n in obst:
            if n == net and n != 0:
                continue
            if x1 + CLEAR > a0 and a1 + CLEAR > x0 and y1 + CLEAR > b0 and b1 + CLEAR > y0:
                return False
        return True

    def via_ok(x, y, net):
        r = VIA_D / 2
        if not (ex0 + r < x < ex1 - r and ey0 + r < y < ey1 - r):
            return False
        if any(math.hypot(x - hx, y - hy) < 2.2 for hx, hy in holes):
            return False
        return clear_box(x - r, y - r, x + r, y + r, net)

    def stub_ok(ax, ay, bx, by, net, w, own_pad_box):
        """Sample the stub; ignore its own pad."""
        steps = max(2, int(math.hypot(bx - ax, by - ay) / 0.1))
        for i in range(steps + 1):
            x, y = ax + (bx - ax) * i / steps, ay + (by - ay) * i / steps
            b = (x - w / 2, y - w / 2, x + w / 2, y + w / 2)
            for a0, b0, a1, b1, n in obst:
                if (n == net and n != 0) or (a0, b0, a1, b1) == own_pad_box:
                    continue
                if b[2] + CLEAR > a0 and a1 + CLEAR > b[0] and b[3] + CLEAR > b0 and b1 + CLEAR > b[1]:
                    return False
        return True

    def add(pad, vx, vy, w):
        net = pad.GetNet()
        p = pad.GetPosition()
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(p)
        t.SetEnd(pcbnew.VECTOR2I(mm(vx), mm(vy)))
        t.SetWidth(mm(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(net)
        t.SetLocked(True)
        board.Add(t)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy)))
        v.SetWidth(mm(VIA_D))
        v.SetDrill(mm(VIA_DRILL))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(net)
        v.SetLocked(True)
        board.Add(v)
        r = VIA_D / 2
        obst.append((vx - r, vy - r, vx + r, vy + r, pad.GetNetCode()))
        lo_x, hi_x = sorted((tomm(p.x), vx))
        lo_y, hi_y = sorted((tomm(p.y), vy))
        obst.append((lo_x - w / 2, lo_y - w / 2, hi_x + w / 2, hi_y + w / 2, pad.GetNetCode()))

    def plane_at(net, x, y):
        layer = PLANE_NETS[net]
        pt = pcbnew.VECTOR2I(mm(x), mm(y))
        for z in board.Zones():
            if z.GetNetname() == net and z.GetLayer() == layer and z.HitTestFilledArea(layer, pt, 0):
                return True
        return False

    stats = {'plane': 0, 'plane_skipped': 0, 'fanout': 0, 'fanout_skipped': 0}

    # 1. Plane vias.
    for pad in board.GetPads():
        net = pad.GetNetname()
        if net not in PLANE_NETS or not pad.IsOnLayer(pcbnew.F_Cu) or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        fp = pad.GetParentFootprint()
        px, py = tomm(pad.GetPosition().x), tomm(pad.GetPosition().y)
        cx, cy = tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)
        bb = pad.GetBoundingBox()
        own = (tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom()), pad.GetNetCode())
        half = max(tomm(bb.GetWidth()), tomm(bb.GetHeight())) / 2
        away = math.atan2(py - cy, px - cx) if (px, py) != (cx, cy) else 0.0
        done = False
        for d in (half + VIA_D / 2 + 0.25, half + VIA_D / 2 + 0.6, half + VIA_D / 2 + 1.0):
            for k in range(8):
                a = away + (k // 2) * (math.pi / 4) * (1 if k % 2 == 0 else -1)
                vx, vy = px + d * math.cos(a), py + d * math.sin(a)
                if via_ok(vx, vy, pad.GetNetCode()) and plane_at(net, vx, vy) and \
                        stub_ok(px, py, vx, vy, pad.GetNetCode(), 0.25, own[:4]):
                    add(pad, vx, vy, 0.25)
                    done = True
                    break
            if done:
                break
        stats['plane' if done else 'plane_skipped'] += 1

    # 2. MCU dog-bone fanout of signal pins.
    if fanout:
        mcu = next(fp for fp in board.GetFootprints() if fp.GetReference() == MCU)
        cx, cy = tomm(mcu.GetPosition().x), tomm(mcu.GetPosition().y)
        pads = sorted(mcu.Pads(), key=lambda p: int(p.GetNumber()) if p.GetNumber().isdigit() else 0)
        for i, pad in enumerate(pads):
            net = pad.GetNetname()
            if not net or net in PLANE_NETS or net.startswith('unconnected-'):
                continue
            px, py = tomm(pad.GetPosition().x), tomm(pad.GetPosition().y)
            dx, dy = px - cx, py - cy
            ux, uy = (math.copysign(1, dx), 0.0) if abs(dx) > abs(dy) else (0.0, math.copysign(1, dy))
            bb = pad.GetBoundingBox()
            own = (tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom()))
            reach = max(tomm(bb.GetWidth()), tomm(bb.GetHeight())) / 2
            ok = False
            for d in ((0.75, 1.5) if i % 2 == 0 else (1.5, 0.75)):
                vx, vy = px + ux * (reach + d), py + uy * (reach + d)
                if via_ok(vx, vy, pad.GetNetCode()) and stub_ok(px, py, vx, vy, pad.GetNetCode(), 0.15, own):
                    add(pad, vx, vy, 0.15)
                    ok = True
                    break
            stats['fanout' if ok else 'fanout_skipped'] += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)
    print('pre-routed (locked): %(plane)d plane vias (%(plane_skipped)d skipped), '
          '%(fanout)d MCU fanouts (%(fanout_skipped)d skipped)' % stats)


if __name__ == '__main__':
    main()
