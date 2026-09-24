#!/usr/bin/env python3
"""Last-mile router: finish the connections the autorouter left open.

    kicad python3.11 hardware/scripts/lastmile_main_pcb.py <drc.json>

For each "missing connection" in a KiCad DRC JSON report, runs an A* search on a 0.1 mm grid over
F.Cu and B.Cu in a window around the gap. Other nets' pads/tracks/vias are obstacles, inflated by
the larger of the two net classes' clearances; changing layer costs a via and is only allowed
where one fits. For plane nets (GND and the 3.3 V rails) the goal is simply the nearest spot where
a via reaches that net's filled plane - one via solves an isolated island. Adds the tracks/vias
(net-class width) and saves; KiCad's DRC is the judge of the result.
"""
import heapq
import json
import math
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, '..', 'kicad', 'stm32-epaper.kicad_pcb')
PLANE = {'GND': pcbnew.In1_Cu, '3V3_AON': pcbnew.In2_Cu, '3V3_PERIPH': pcbnew.In2_Cu,
         '+3V3': pcbnew.In2_Cu}
RES = 0.1            # grid, mm
MARGIN = 4.0         # window margin around a gap, mm
VIA_D, VIA_DRILL = 0.45, 0.2
VIA_COST = 25        # in grid steps
EDGE = 0.5
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)


def mm(v):
    return pcbnew.FromMM(v)


def tomm(v):
    return pcbnew.ToMM(v)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def main():
    drc = json.load(open(sys.argv[1]))
    board = pcbnew.LoadBoard(BOARD)
    # Capture collections up front (KiCad 10 SWIG: iterate before modifying).
    pads = list(board.GetPads())
    tracks = list(board.GetTracks())
    zones = list(board.Zones())
    footprints = list(board.GetFootprints())
    ns = board.GetDesignSettings().m_NetSettings
    cls_cache = {}

    def cls(net):
        if net not in cls_cache:
            nc = ns.GetEffectiveNetClass(net)
            cls_cache[net] = (tomm(nc.GetClearance()), tomm(nc.GetTrackWidth()))
        return cls_cache[net]

    edge = board.GetBoardEdgesBoundingBox()
    ex0, ey0 = tomm(edge.GetLeft()) + EDGE, tomm(edge.GetTop()) + EDGE
    ex1, ey1 = tomm(edge.GetRight()) - EDGE, tomm(edge.GetBottom()) - EDGE
    holes = [(tomm(f.GetPosition().x), tomm(f.GetPosition().y)) for f in footprints
             if f.GetReference().startswith('H3')]

    # Copper items as (kind, layerset, geometry, net)
    items = []
    for p in pads:
        bb = p.GetBoundingBox()
        ls = [l for l in LAYERS if p.IsOnLayer(l)]
        items.append(('rect', ls, (tomm(bb.GetLeft()), tomm(bb.GetTop()), tomm(bb.GetRight()),
                                   tomm(bb.GetBottom())), p.GetNetname()))
    for t in tracks:
        if t.Type() == pcbnew.PCB_VIA_T:
            items.append(('circle', list(LAYERS), (tomm(t.GetPosition().x), tomm(t.GetPosition().y),
                                                   tomm(t.GetWidth()) / 2), t.GetNetname()))
        elif t.GetLayer() in LAYERS:
            items.append(('seg', [t.GetLayer()], (tomm(t.GetStart().x), tomm(t.GetStart().y),
                                                  tomm(t.GetEnd().x), tomm(t.GetEnd().y),
                                                  tomm(t.GetWidth()) / 2), t.GetNetname()))
    added = []   # new copper this run: also obstacles for later connections

    def plane_filled(net, x, y):
        layer = PLANE[net]
        pt = pcbnew.VECTOR2I(mm(x), mm(y))
        return any(z.GetNetname() == net and z.GetLayer() == layer and
                   z.HitTestFilledArea(layer, pt, 0) for z in zones)

    def route(net, a, b, a_layers, b_layers):
        clr, width = cls(net)
        width = max(width, 0.15)
        hw = width / 2
        x0 = max(ex0, min(a[0], b[0]) - MARGIN)
        y0 = max(ey0, min(a[1], b[1]) - MARGIN)
        x1 = min(ex1, max(a[0], b[0]) + MARGIN)
        y1 = min(ey1, max(a[1], b[1]) + MARGIN)
        nx, ny = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
        blocked = [bytearray(nx * ny) for _ in LAYERS]       # track centre can't go here
        via_blocked = bytearray(nx * ny)                     # via centre can't go here

        def mark(kind, geom, ls, inflate_t, inflate_v):
            if kind == 'rect':
                gx0, gy0, gx1, gy1 = geom
            elif kind == 'circle':
                cx, cy, r = geom
                gx0, gy0, gx1, gy1 = cx - r, cy - r, cx + r, cy + r
            else:
                ax, ay, bx, by, r = geom
                gx0, gy0, gx1, gy1 = min(ax, bx) - r, min(ay, by) - r, max(ax, bx) + r, max(ay, by) + r
            big = max(inflate_t, inflate_v)
            i0 = max(0, int((gx0 - big - x0) / RES)); i1 = min(nx - 1, int((gx1 + big - x0) / RES) + 1)
            j0 = max(0, int((gy0 - big - y0) / RES)); j1 = min(ny - 1, int((gy1 + big - y0) / RES) + 1)
            for j in range(j0, j1 + 1):
                py = y0 + j * RES
                for i in range(i0, i1 + 1):
                    px = x0 + i * RES
                    if kind == 'rect':
                        ddx = max(gx0 - px, 0, px - gx1)
                        ddy = max(gy0 - py, 0, py - gy1)
                        d = math.hypot(ddx, ddy)
                    elif kind == 'circle':
                        d = max(0.0, math.hypot(px - geom[0], py - geom[1]) - geom[2])
                    else:
                        d = max(0.0, seg_dist(px, py, *geom[:4]) - geom[4])
                    k = j * nx + i
                    if d < inflate_t:
                        for li, L in enumerate(LAYERS):
                            if L in ls:
                                blocked[li][k] = 1
                    if d < inflate_v:
                        via_blocked[k] = 1

        for kind, ls, geom, n in items + added:
            if n == net and n:
                if kind == 'circle':
                    # Same-net vias aren't copper obstacles, but drills still need 0.25 mm spacing.
                    # centre-to-centre >= drill + 0.25; mark() measures from its copper edge
                    mark(kind, geom, ls, 0.0, VIA_DRILL + 0.25 - geom[2])
                continue
            c = max(clr, cls(n)[0] if n else clr)
            mark(kind, geom, ls, c + hw, c + VIA_D / 2)
        for hx, hy in holes:
            mark('circle', (hx, hy, 1.1), list(LAYERS), 0.3 + hw, 0.3 + VIA_D / 2)

        def cell(x, y):
            return (min(nx - 1, max(0, int(round((x - x0) / RES)))),
                    min(ny - 1, max(0, int(round((y - y0) / RES)))))
        si, sj = cell(*a)
        plane_goal = net in PLANE
        ti, tj = cell(*b)
        goal_layers = set(LAYERS.index(l) for l in b_layers)
        # Start/target cells sit on their own copper: always allowed.
        start = [(li, si, sj) for li, L in enumerate(LAYERS) if L in a_layers]

        def h(i, j):
            return 0 if plane_goal else math.hypot(i - ti, j - tj)
        openq = []
        g = {}
        prev = {}
        for s in start:
            g[s] = 0.0
            heapq.heappush(openq, (h(s[1], s[2]), 0.0, s))
        steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        found = None
        budget = 400000
        while openq and budget:
            budget -= 1
            f, cost, node = heapq.heappop(openq)
            if cost > g.get(node, 1e18):
                continue
            li, i, j = node
            k = j * nx + i
            if plane_goal:
                if not via_blocked[k] and cost > 0 and plane_filled(net, x0 + i * RES, y0 + j * RES):
                    found = ('via', node)
                    break
            elif (i, j) == (ti, tj) and li in goal_layers:
                found = ('pt', node)
                break
            nbrs = []
            for di, dj, c in steps:
                ii, jj = i + di, j + dj
                if 0 <= ii < nx and 0 <= jj < ny:
                    kk = jj * nx + ii
                    if not blocked[li][kk] or (ii, jj) in ((ti, tj), (si, sj)):
                        nbrs.append(((li, ii, jj), c))
            if not via_blocked[k]:
                nbrs.append(((1 - li, i, j), VIA_COST))
            for nb, c in nbrs:
                ncost = cost + c
                if ncost < g.get(nb, 1e18):
                    g[nb] = ncost
                    prev[nb] = node
                    heapq.heappush(openq, (ncost + h(nb[1], nb[2]), ncost, nb))
        if not found:
            return None
        # Walk back: list of (layer_index, x, y); vias where the layer changes.
        path = [found[1]]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        return path, found[0], (x0, y0), width

    netinfo = {}

    def emit(net, path, end_kind, origin, width, a, b):
        x0, y0 = origin
        pts = [(li, x0 + i * RES, y0 + j * RES) for li, i, j in path]
        pts[0] = (pts[0][0], a[0], a[1])
        if end_kind == 'pt':
            pts[-1] = (pts[-1][0], b[0], b[1])
        n = netinfo.setdefault(net, board.FindNet(net))
        # Collapse collinear runs per layer.
        out = [pts[0]]
        for p in pts[1:]:
            out.append(p)
            if len(out) >= 3 and out[-1][0] == out[-2][0] == out[-3][0]:
                (_, ax, ay), (_, bx, by), (_, cx_, cy_) = out[-3], out[-2], out[-1]
                if abs((bx - ax) * (cy_ - ay) - (by - ay) * (cx_ - ax)) < 1e-6:
                    out.pop(-2)

        def via(x, y):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
            v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(n)
            board.Add(v)
            added.append(('circle', list(LAYERS), (x, y, VIA_D / 2), net))
        for p, q in zip(out, out[1:]):
            if p[0] != q[0]:
                via(p[1], p[2])
                continue
            if (p[1], p[2]) == (q[1], q[2]):
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(p[1]), mm(p[2])))
            t.SetEnd(pcbnew.VECTOR2I(mm(q[1]), mm(q[2])))
            t.SetWidth(mm(width))
            t.SetLayer(LAYERS[p[0]])
            t.SetNet(n)
            board.Add(t)
            added.append(('seg', [LAYERS[p[0]]], (p[1], p[2], q[1], q[2], width / 2), net))
        if end_kind == 'via':
            via(out[-1][1], out[-1][2])

    def layers_of(desc):
        if ' - ' in desc:
            return list(LAYERS)
        return [pcbnew.B_Cu] if 'on B.Cu' in desc else [pcbnew.F_Cu]

    done = failed = 0
    seen_islands = set()
    for u in drc.get('unconnected_items', []):
        ia, ib = u['items'][0], u['items'][1]
        net = re.search(r'\[([^\]]+)\]', ia['description']).group(1)
        a = (ia['pos']['x'], ia['pos']['y'])
        b = (ib['pos']['x'], ib['pos']['y'])
        if net in PLANE and ia['description'].startswith('Via') and \
                not ib['description'].startswith('Via'):
            # Start from the item that isn't already a via on the plane: starting at the via just
            # drops a second, useless via beside it and never touches the stranded pad/track.
            ia, ib, a, b = ib, ia, b, a
        if net in PLANE:
            key = (net, round(a[0], 1), round(a[1], 1))
            if key in seen_islands:
                continue
            seen_islands.add(key)
        r = route(net, a, b, layers_of(ia['description']), layers_of(ib['description']))
        if r is None and net in PLANE:   # try from the other end of the gap
            r = route(net, b, a, layers_of(ib['description']), layers_of(ia['description']))
            a, b = b, a
        if r is None:
            failed += 1
            print('  no path: %s %s -> %s' % (net, ia['description'][:40], ib['description'][:40]))
            continue
        path, kind, origin, width = r
        emit(net, path, kind, origin, width, a, b)
        done += 1
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())   # (only adds happened: safe to query)
    pcbnew.SaveBoard(BOARD, board)
    print('last-mile: %d gaps routed, %d without a path' % (done, failed))


if __name__ == '__main__':
    main()
