"""Drawing helpers for conventional, wired schematics (on top of kicad_gen.Sheet).

The sheet generators started out connecting everything by net labels on short stubs, which is
electrically fine but doesn't read like a schematic. These helpers draw the parts of a circuit
actually wired together: runs out of a pin, two-pin parts placed along a direction, capacitor
banks on a rail, junction dots. Every coordinate stays on the 2.54 mm grid (pins land exactly on
wire ends), and each sheet's redraw is proven electrically identical with compare_netlists.py.
"""
import math

from kicad_gen import _pins_of, _rot

G = 2.54


def pin(part, num):
    x, y, _ = part.pin_xy(num)
    return x, y


def outward(part, num):
    """Unit direction pointing away from the part body at pin `num`."""
    _, _, a = part.pin_xy(num)
    return -round(math.cos(math.radians(a))), round(math.sin(math.radians(a)))


def path(s, pts):
    """Orthogonal polyline through `pts`."""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if (x0, y0) != (x1, y1):
            s.wire(x0, y0, x1, y1)


def two(s, ref, lib_id, value, p1, d, footprint=None, fields=None, pin_a='1', pin_b='2', dnp=False):
    """Place a two-pin part with `pin_a` exactly at p1 and `pin_b` along direction d = (dx, dy).
    Returns (pin_b position, part)."""
    pins = _pins_of(s._lib(lib_id))
    (ax, ay), (bx, by) = pins[pin_a][:2], pins[pin_b][:2]
    for ang in (0, 90, 180, 270):
        rax, ray = _rot(ax, ay, ang)
        rbx, rby = _rot(bx, by, ang)
        vx, vy = rbx - rax, -(rby - ray)          # schematic frame (y down)
        n = math.hypot(vx, vy)
        if abs(vx / n - d[0]) < 1e-6 and abs(vy / n - d[1]) < 1e-6:
            part = s.part(ref, lib_id, value, round(p1[0] - rax, 4), round(p1[1] + ray, 4),
                          footprint=footprint, fields=fields, dnp=dnp, angle=ang)
            return pin(part, pin_b), part
    raise ValueError('%s: no rotation gives direction %s' % (ref, d))


def rail(s, pts, junctions=True):
    """A straight rail through the given points (sorted along it), split at every point so each
    tee is a real wire end, with junction dots on the interior points."""
    pts = sorted(set(pts))
    for a, b in zip(pts, pts[1:]):
        s.wire(a[0], a[1], b[0], b[1])
    if junctions:
        for p in pts[1:-1]:
            s.junction(*p)


def bank(s, caps, x0, y_top, rail_net, gnd='GND', pitch=4 * G, extra_top=(), label_net=None):
    """A decoupling bank: capacitors side by side from x0, tops on a `rail_net` rail at y_top,
    bottoms on a GND rail 3*G below, one power symbol at each rail's left end.
    caps = [(ref, value, footprint, fields)]. `extra_top` = more points on the top rail (e.g.
    where IC pins join it). Returns the top rail's point list (for joining more wires)."""
    tops, bots = [], []
    for i, (ref, value, fp, fields) in enumerate(caps):
        x = x0 + i * pitch
        two(s, ref, 'Device:C', value, (x, y_top), (0, 1), footprint=fp, fields=fields)
        tops.append((x, y_top))
        bots.append((x, y_top + 3 * G))
    top_pts = tops + list(extra_top)
    rail(s, top_pts)
    rail(s, bots)
    left = min(top_pts)
    if label_net:
        s.net_at(label_net, left[0], left[1], -1, 0)
    else:
        s.net_at(rail_net, left[0], left[1], 0, -1)
    s.net_at(gnd, bots[0][0], bots[0][1], 0, 1)
    return top_pts
