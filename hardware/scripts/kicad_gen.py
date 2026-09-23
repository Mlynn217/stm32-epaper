"""Tiny KiCad 10 schematic writer used to bootstrap the first sheets.

This is scaffolding, not the source of truth: once a sheet has been opened and edited in Eeschema,
edit it there. Parts are connected by short wire stubs ending in net labels / power symbols, so
connectivity is explicit and checkable with `kicad-cli sch export netlist`.
"""
import copy
import math
import os
import uuid as _uuid

import custom_symbols
from sexp import Sym, dump, find, find1, parse

STOCK = os.environ.get('KICAD_SYMBOL_DIR', '')
YES, NO = Sym('yes'), Sym('no')
STUB = 2.54


def uid():
    return str(_uuid.uuid4())


def _pins_of(sym):
    """{number: (x, y, angle, name)} for body style 1 of a flattened lib symbol."""
    out = {}
    for sub in find(sym, 'symbol'):
        if sub[1].endswith('_2'):
            continue  # alternate (De Morgan) body style
        for p in find(sub, 'pin'):
            at = find1(p, 'at')
            out[find1(p, 'number')[1]] = (float(at[1]), float(at[2]), float(at[3]),
                                         find1(p, 'name')[1])
    return out


def load_stock(lib, name):
    path = os.path.join(STOCK, lib + '.kicad_symdir', name + '.kicad_sym')
    sym = find1(parse(open(path).read()), 'symbol')
    ext = find1(sym, 'extends')
    if not ext:
        return sym
    parent = copy.deepcopy(load_stock(lib, ext[1]))
    pname = parent[1]
    parent[1] = name
    for sub in find(parent, 'symbol'):
        sub[1] = name + sub[1][len(pname):]
    child_props = {p[1]: p for p in find(sym, 'property')}
    for i, x in enumerate(parent):
        if isinstance(x, list) and x and x[0] == 'property' and x[1] in child_props:
            parent[i] = child_props.pop(x[1])
    idx = max(i for i, x in enumerate(parent) if isinstance(x, list) and x[0] == 'property')
    for p in child_props.values():
        idx += 1
        parent.insert(idx, p)
    return parent


class Part:
    def __init__(self, ref, lib_id, x, y, pins):
        self.ref, self.lib_id, self.x, self.y, self.pins = ref, lib_id, x, y, pins

    def pin_xy(self, num):
        px, py, a, _ = self.pins[num]
        return self.x + px, self.y - py, a


def _eff(justify=None, hide=False, size=1.27):
    e = ['effects', ['font', ['size', size, size]]]
    if justify:
        e.append(['justify', *[Sym(j) for j in justify.split()]])
    if hide:
        e.append(['hide', YES])
    return e


def _prop(key, val, x, y, hide=False, justify=None, angle=0):
    p = ['property', key, val, ['at', x, y, angle]]
    if hide:
        p.append(['hide', YES])
    p.append(_eff(justify))
    return p


class Sheet:
    def __init__(self, project, path, page_uuid, title, power_nets, global_nets):
        self.project = project
        self.path = path  # instance path, e.g. "/<root uuid>/<sheet uuid>"
        self.uuid = page_uuid
        self.title = title
        self.power_nets = power_nets  # net name -> power lib symbol name
        self.global_nets = global_nets  # net name -> label shape
        self.lib = {}
        self.items = []
        self.pwr_n = 0
        self.pwr_points = {}  # net -> [(x, y)] where a power symbol already sits

    # ---- symbols -------------------------------------------------------------------------
    def _lib(self, lib_id):
        if lib_id not in self.lib:
            lib, name = lib_id.split(':')
            if lib == 'epaper':
                sym = custom_symbols.build(name)
            else:
                sym = load_stock(lib, name)
            sym = copy.deepcopy(sym)
            sym[1] = lib_id
            self.lib[lib_id] = sym
        return self.lib[lib_id]

    def part(self, ref, lib_id, value, x, y, footprint=None, fields=None, dnp=False):
        sym = self._lib(lib_id)
        pins = _pins_of(sym)
        lprops = {p[1]: p[2] for p in find(sym, 'property')}
        fp = footprint if footprint is not None else lprops.get('Footprint', '')
        is_pwr = ref.startswith('#')
        props = [self._field(sym, 'Reference', ref, x, y, force_hide=is_pwr),
                 self._field(sym, 'Value', value, x, y),
                 _prop('Footprint', fp, x, y, hide=True),
                 _prop('Datasheet', lprops.get('Datasheet', ''), x, y, hide=True),
                 _prop('Description', lprops.get('Description', ''), x, y, hide=True)]
        for k, v in (fields or {}).items():
            props.append(_prop(k, v, x, y, hide=True))
        inst = ['symbol', ['lib_id', lib_id], ['at', x, y, 0], ['unit', 1],
                ['exclude_from_sim', NO], ['in_bom', NO if is_pwr else YES], ['on_board', YES],
                ['dnp', YES if dnp else NO], ['uuid', uid()], *props]
        for num in pins:
            inst.append(['pin', num, ['uuid', uid()]])
        inst.append(['instances', ['project', self.project,
                                   ['path', self.path, ['reference', ref], ['unit', 1]]]])
        self.items.append(inst)
        return Part(ref, lib_id, x, y, pins)

    @staticmethod
    def _field(sym, key, val, x, y, force_hide=False):
        """Instance field placed where the library symbol puts it (lib Y axis is flipped)."""
        lp = next(p for p in find(sym, 'property') if p[1] == key)
        at = find1(lp, 'at')
        eff = copy.deepcopy(find1(lp, 'effects')) or _eff()
        f = ['property', key, val, ['at', x + float(at[1]), y - float(at[2]), float(at[3])]]
        if force_hide or find1(lp, 'hide'):
            f.append(['hide', YES])
        f.append(eff)
        return f

    # ---- connectivity --------------------------------------------------------------------
    def wire(self, x0, y0, x1, y1):
        self.items.append(['wire', ['pts', ['xy', x0, y0], ['xy', x1, y1]],
                           ['stroke', ['width', 0], ['type', Sym('default')]], ['uuid', uid()]])

    def no_connect(self, part, num):
        x, y, _ = part.pin_xy(num)
        self.items.append(['no_connect', ['at', x, y], ['uuid', uid()]])

    def net_at(self, net, x, y, out_dx, out_dy):
        """Attach net `net` at point (x, y); (out_dx, out_dy) is the outward direction."""
        if net in self.power_nets:
            for px, py in self.pwr_points.get(net, []):
                # A same-net power symbol right next door (e.g. GND + PGND pins): join, don't repeat.
                if (py == y and 0 < abs(px - x) <= 5.08) or (px == x and 0 < abs(py - y) <= 5.08):
                    self.wire(x, y, px, py)
                    return
            self.pwr_points.setdefault(net, []).append((x, y))
            self.pwr_n += 1
            lib_name = self.power_nets[net]
            self.part('#PWR%s%02d' % (self.title[:3].upper(), self.pwr_n),
                      'power:' + lib_name, net, x, y)
            return
        angle = {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(out_dx, out_dy)]
        just = 'left bottom' if angle in (0, 90) else 'right bottom'
        if net in self.global_nets:
            gj = 'left' if angle in (0, 90) else 'right'
            self.items.append(['global_label', net, ['shape', Sym(self.global_nets[net])],
                               ['at', x, y, angle], ['fields_autoplaced', YES], _eff(gj),
                               ['uuid', uid()],
                               _prop('Intersheetrefs', '${INTERSHEET_REFS}', x, y, hide=True,
                                     justify=gj)])
        else:
            self.items.append(['label', net, ['at', x, y, angle], _eff(just), ['uuid', uid()]])

    def conn(self, part, num, net, stub=STUB):
        """Wire a stub outward from pin `num` of `part` and attach `net` at its end."""
        x, y, a = part.pin_xy(num)
        # lib pin angle points from the pin tip into the body; outward is the opposite.
        dx = -round(math.cos(math.radians(a)))
        dy = round(math.sin(math.radians(a)))  # schematic Y axis points down
        if dx and net in self.power_nets and stub == STUB:
            stub = 2 * STUB  # keep side-mounted power symbols clear of neighbouring pin text
        ex, ey = x + dx * stub, y + dy * stub
        self.wire(x, y, ex, ey)
        self.net_at(net, ex, ey, dx, dy)

    def conns(self, part, mapping):
        for num, net in mapping.items():
            if net is None:
                self.no_connect(part, num)
            else:
                self.conn(part, num, net)

    def text(self, s, x, y, size=1.27):
        self.items.append(['text', s, ['exclude_from_sim', NO], ['at', x, y, 0],
                           _eff('left top', size=size), ['uuid', uid()]])

    # ---- output --------------------------------------------------------------------------
    def render(self, extra=None):
        doc = ['kicad_sch', ['version', 20250610], ['generator', 'eeschema'],
               ['generator_version', '10.0'], ['uuid', self.uuid], ['paper', 'A3'],
               ['title_block', ['title', self.title]],
               ['lib_symbols', *self.lib.values()], *self.items, *(extra or [])]
        doc.append(['embedded_fonts', NO])
        return dump(doc) + '\n'
