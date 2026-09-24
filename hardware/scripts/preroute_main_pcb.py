#!/usr/bin/env python3
"""Scripted pre-routing for the main board, locked so freerouting treats it as protected.

  - plane vias: every pad on a plane net (GND, 3V3_AON, 3V3_PERIPH, +3V3) gets a short stub and a
    via, where that net's plane is actually filled under the via;
  - MCU fanout (--fanout): each LQFP-176 signal pin gets a dog-bone (stub straight out from its
    side of the package + via), staggered in two rows so 0.5 mm pitch fits.
Every candidate is collision-checked against other nets' pads and the copper added so far, and
skipped (left to the autorouter) if it doesn't fit.

    kicad python3.11 hardware/scripts/preroute_main_pcb.py [--fanout] [--board=path] [--list-skipped]

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
    path = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--board=')), BOARD)
    board = pcbnew.LoadBoard(path)
    skipped = []
    # Capture everything that needs a board query first: once board.Remove() has been called,
    # KiCad 10's SWIG wrapper can no longer iterate the board's collections in this session.
    old_tracks = list(board.GetTracks())
    all_pads = list(board.GetPads())
    zones = list(board.Zones())
    footprints = list(board.GetFootprints())
    netcodes = {code: net for code, net in board.GetNetsByNetcode().items()}
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    # Per-net clearance from the net classes (Touch 0.4, Power 0.2, ...): a pre-routed via or
    # stub must satisfy the larger of its own class and the obstacle's class.
    # (NETINFO_ITEM.GetNetClass() returns an untyped SWIG pointer in KiCad 10; the net settings'
    # effective-class lookup by name works.)
    ns = board.GetDesignSettings().m_NetSettings
    net_clear = {code: max(CLEAR, tomm(ns.GetEffectiveNetClass(net.GetNetname()).GetClearance()))
                 for code, net in netcodes.items()}
    vias_at = []          # (x, y) of every via added: holes need spacing whatever their net
    vias_net = []         # (x, y, netcode) of the same, for the shared-via fallback

    # Obstacles: (x0, y0, x1, y1, netcode) in mm, board coordinates (y down).
    obst = []
    for pad in all_pads:
        bb = pad.GetBoundingBox()
        obst.append((tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()),
                     tomm(bb.GetBottom()), pad.GetNetCode()))
    edge = board.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = (tomm(edge.GetLeft()) + 0.5, tomm(edge.GetTop()) + 0.5,
                          tomm(edge.GetRight()) - 0.5, tomm(edge.GetBottom()) - 0.5)
    holes = [(tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)) for fp in footprints
             if fp.GetReference().startswith('H3')]

    def clear_box(x0, y0, x1, y1, net):
        for a0, b0, a1, b1, n in obst:
            if n == net and n != 0:
                continue
            c = max(net_clear.get(net, CLEAR), net_clear.get(n, CLEAR))
            if x1 + c > a0 and a1 + c > x0 and y1 + c > b0 and b1 + c > y0:
                return False
        return True

    def via_ok(x, y, net):
        r = VIA_D / 2
        if not (ex0 + r < x < ex1 - r and ey0 + r < y < ey1 - r):
            return False
        if any(math.hypot(x - hx, y - hy) < 2.2 for hx, hy in holes):
            return False
        # Drill-to-drill spacing between any two vias, same net or not (0.25 mm + drills), and
        # room for the autorouter's own vias between ours.
        if any(math.hypot(x - vx, y - vy) < VIA_D + 0.3 for vx, vy in vias_at):
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
                c = max(net_clear.get(net, CLEAR), net_clear.get(n, CLEAR))
                if b[2] + c > a0 and a1 + c > b[0] and b[3] + c > b0 and b1 + c > b[1]:
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
        vias_at.append((vx, vy))
        vias_net.append((vx, vy, pad.GetNetCode()))
        obst.append((vx - r, vy - r, vx + r, vy + r, pad.GetNetCode()))
        lo_x, hi_x = sorted((tomm(p.x), vx))
        lo_y, hi_y = sorted((tomm(p.y), vy))
        obst.append((lo_x - w / 2, lo_y - w / 2, hi_x + w / 2, hi_y + w / 2, pad.GetNetCode()))

    def plane_at(net, x, y):
        layer = PLANE_NETS[net]
        pt = pcbnew.VECTOR2I(mm(x), mm(y))
        for z in zones:
            if z.GetNetname() == net and z.GetLayer() == layer and z.HitTestFilledArea(layer, pt, 0):
                return True
        return False

    stats = {'plane': 0, 'plane_shared': 0, 'plane_skipped': 0, 'in_pad': 0, 'fanout': 0,
             'fanout_skipped': 0, 'escapes': 0}

    # Only now remove the old copper (the queries above are done).
    for t in old_tracks:
        board.Remove(t)

    # 1. Plane vias.
    for pad in all_pads:
        net = pad.GetNetname()
        if net not in PLANE_NETS or not pad.IsOnLayer(pcbnew.F_Cu) or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        fp = pad.GetParentFootprint()
        px, py = tomm(pad.GetPosition().x), tomm(pad.GetPosition().y)
        cx, cy = tomm(fp.GetPosition().x), tomm(fp.GetPosition().y)
        bb = pad.GetBoundingBox()
        pw, ph = tomm(bb.GetWidth()), tomm(bb.GetHeight())
        if math.hypot(px - cx, py - cy) < 0.6 and pw * ph > 1.0:
            # Exposed/thermal pad at the package centre: vias inside the pad (a stub outward would
            # cross the IC's own pins). A small grid, 1.0 mm pitch, kept 0.3 mm inside the edge.
            nx = max(1, int((pw - 0.6) / 1.0) + 1)
            ny = max(1, int((ph - 0.6) / 1.0) + 1)
            n_added = 0
            for i in range(nx):
                for j in range(ny):
                    vx = px + (i - (nx - 1) / 2) * 1.0
                    vy = py + (j - (ny - 1) / 2) * 1.0
                    if plane_at(net, vx, vy):
                        v = pcbnew.PCB_VIA(board)
                        v.SetPosition(pcbnew.VECTOR2I(mm(vx), mm(vy)))
                        v.SetWidth(mm(VIA_D))
                        v.SetDrill(mm(VIA_DRILL))
                        v.SetViaType(pcbnew.VIATYPE_THROUGH)
                        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                        v.SetNet(pad.GetNet())
                        v.SetLocked(True)
                        board.Add(v)
                        vias_at.append((vx, vy))
                        vias_net.append((vx, vy, pad.GetNetCode()))
                        n_added += 1
            if n_added:
                stats['plane'] += 1
                stats['in_pad'] += n_added
                continue
        own = (tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom()), pad.GetNetCode())
        half = max(tomm(bb.GetWidth()), tomm(bb.GetHeight())) / 2
        away = math.atan2(py - cy, px - cx) if (px, py) != (cx, cy) else 0.0
        # Directions to try: for the MCU, straight IN first - perpendicular to the package side,
        # to a via under the LQFP body (the ring outside is full of pins and decoupling caps).
        # (The centre-to-pad angle is diagonal for pins away from mid-side: no good.)
        dirs = []
        if fp.GetReference() == MCU:
            dx, dy = px - cx, py - cy
            dirs.append(math.atan2(0.0, -math.copysign(1, dx)) if abs(dx) > abs(dy)
                        else math.atan2(-math.copysign(1, dy), 0.0))
        dirs += [away + sgn * k * math.pi / 4 for k in range(5) for sgn in ((1,) if k in (0, 4) else (1, -1))]
        done = False
        for d in (half + VIA_D / 2 + 0.25, half + VIA_D / 2 + 0.9, half + VIA_D / 2 + 1.6):
            for a in dirs:
                vx, vy = px + d * math.cos(a), py + d * math.sin(a)
                if via_ok(vx, vy, pad.GetNetCode()) and plane_at(net, vx, vy) and \
                        stub_ok(px, py, vx, vy, pad.GetNetCode(), 0.25, own[:4]):
                    add(pad, vx, vy, 0.25)
                    done = True
                    break
            if done:
                break
        if not done:
            # Fallback: stub to the nearest same-net via already placed (a neighbouring pin's),
            # when its own via spot is blocked (typically by a decoupling cap).
            targets = [(vx, vy, c) for vx, vy, c in vias_net if c == pad.GetNetCode()]
            # ...or the same-net pad of another part (e.g. an MCU power pin into its own
            # decoupling cap, whose via then serves both).
            targets += [(tomm(o.GetPosition().x), tomm(o.GetPosition().y), o.GetNetCode())
                        for o in all_pads if o.GetNetCode() == pad.GetNetCode()
                        and o.GetParentFootprint().GetReference() != fp.GetReference()]
            for vx, vy, code in sorted(targets, key=lambda v: math.hypot(v[0] - px, v[1] - py)):
                if math.hypot(vx - px, vy - py) > 2.5:
                    break
                if stub_ok(px, py, vx, vy, pad.GetNetCode(), 0.2, own[:4]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pad.GetPosition())
                    t.SetEnd(pcbnew.VECTOR2I(mm(vx), mm(vy)))
                    t.SetWidth(mm(0.2))
                    t.SetLayer(pcbnew.F_Cu)
                    t.SetNet(pad.GetNet())
                    t.SetLocked(True)
                    board.Add(t)
                    lo_x, hi_x = sorted((px, vx))
                    lo_y, hi_y = sorted((py, vy))
                    obst.append((lo_x - 0.1, lo_y - 0.1, hi_x + 0.1, hi_y + 0.1, pad.GetNetCode()))
                    done = True
                    stats['plane_shared'] += 1
                    break
        stats['plane' if done else 'plane_skipped'] += 1
        if not done:
            skipped.append('%s.%s(%s)' % (fp.GetReference(), pad.GetNumber(), net))

    # 2a. CAP1188 touch-pin escapes (always): the last few mm out of the QFN are where the touch
    #     lines failed; a dog-bone per pin gives the router a via to start from.
    cap = next((fp for fp in footprints if fp.GetReference() == 'U301'), None)
    if cap is not None:
        ccx, ccy = tomm(cap.GetPosition().x), tomm(cap.GetPosition().y)
        for pad in cap.Pads():
            if 'TOUCH_' not in pad.GetNetname():
                continue
            px, py = tomm(pad.GetPosition().x), tomm(pad.GetPosition().y)
            dx, dy = px - ccx, py - ccy
            ux, uy = (math.copysign(1, dx), 0.0) if abs(dx) > abs(dy) else (0.0, math.copysign(1, dy))
            bb = pad.GetBoundingBox()
            own = (tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()), tomm(bb.GetBottom()))
            reach = max(tomm(bb.GetWidth()), tomm(bb.GetHeight())) / 2
            for d in (0.6, 1.0, 1.4, 1.8, 2.2, 2.6, 3.0):
                vx, vy = px + ux * (reach + d), py + uy * (reach + d)
                if via_ok(vx, vy, pad.GetNetCode()) and stub_ok(px, py, vx, vy, pad.GetNetCode(), 0.15, own):
                    add(pad, vx, vy, 0.15)
                    stats['escapes'] += 1
                    break

    # 2b. MCU dog-bone fanout of signal pins.
    if fanout:
        mcu = next(fp for fp in footprints if fp.GetReference() == MCU)
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

    if not old_tracks:
        pcbnew.ZONE_FILLER(board).Fill(zones)
    pcbnew.SaveBoard(path, board)
    if '--list-skipped' in sys.argv:
        print('skipped plane pads:', ' '.join(sorted(skipped)))
    print('pre-routed (locked): %(plane)d plane pads connected (%(plane_shared)d via a neighbour\'s via, '
          '%(plane_skipped)d skipped; %(in_pad)d vias in thermal pads), '
          '%(escapes)d CAP1188 touch escapes, %(fanout)d MCU fanouts (%(fanout_skipped)d skipped)' % stats)


if __name__ == '__main__':
    main()
