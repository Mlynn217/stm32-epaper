#!/usr/bin/env python3
"""Generate project-local footprints (hardware/kicad/epaper.pretty) for parts with no stock footprint.

Each footprint is transcribed from the manufacturer's recommended land pattern; the source drawing
is cited in its descr. Unlike the schematic generator this is safe to re-run: footprints are not
hand-edited.
"""
import os

from sexp import Sym, dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'kicad', 'epaper.pretty')
Y, N = Sym('yes'), Sym('no')


def _text(key, val, x, y, layer, hide=False):
    p = ['property', key, val, ['at', x, y, 0], ['layer', layer]]
    if hide:
        p.append(['hide', Y])
    p.append(['effects', ['font', ['size', 1, 1], ['thickness', 0.15]]])
    return p


def _line(x0, y0, x1, y1, layer, w):
    return ['fp_line', ['start', x0, y0], ['end', x1, y1],
            ['stroke', ['width', w], ['type', Sym('solid')]], ['layer', layer]]


def _rect(x0, y0, x1, y1, layer, w):
    return [_line(x0, y0, x1, y0, layer, w), _line(x1, y0, x1, y1, layer, w),
            _line(x1, y1, x0, y1, layer, w), _line(x0, y1, x0, y0, layer, w)]


def _pad(num, x, y, w, h, layers=('F.Cu', 'F.Mask', 'F.Paste'), rr=0.2):
    return ['pad', num, Sym('smd'), Sym('roundrect'), ['at', x, y], ['size', w, h],
            ['layers', *layers], ['roundrect_rratio', rr]]


def tps63802_dla():
    """TI DLA0010A (VSON-HR 10, 2x3 mm) - TPS63802 datasheet SLVSEU9D pp. 35-37.

    Land pattern (top view, mm, pin 1 top-left): pins 1-5 are 0.6x0.25 pads centred at x=-0.9;
    pins 10,9,7,6 are 0.9x0.25 centred at x=+0.75; pin 8 (GND) is a 1.3x0.25 bar centred at
    x=+0.55. 0.5 mm pitch, R0.05 corners. Stencil: pin 8 printed as two 0.55x0.25 apertures at
    x=+0.175 / +0.925 (83% coverage); all other pads 1:1.
    """
    name = 'Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm'
    rr = 0.05 / 0.25
    rows = {1: -1.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 1.0, 10: -1.0, 9: -0.5, 8: 0.0, 7: 0.5, 6: 1.0}
    fp = ['footprint', name, ['version', 20260206], ['generator', 'pcbnew'], ['layer', 'F.Cu'],
          ['descr', 'TI DLA0010A VSON-HR 10 pin 2x3mm HotRod, land pattern per TPS63802 datasheet '
                    '(https://www.ti.com/lit/ds/symlink/tps63802.pdf#page=36)'],
          ['tags', 'VSON-HR HotRod DLA0010A TPS63802'],
          _text('Reference', 'REF**', 0, -2.3, 'F.SilkS'),
          _text('Value', name, 0, 2.3, 'F.Fab'),
          ['attr', Sym('smd')], ['duplicate_pad_numbers_are_jumpers', N]]
    # body (Fab), courtyard (+0.25 around pads/body), silk: top/bottom edges + pin-1 marker
    fp += _rect(-1.0, -1.5, 1.0, 1.5, 'F.Fab', 0.1)
    fp += _rect(-1.45, -1.75, 1.45, 1.75, 'F.CrtYd', 0.05)
    fp += [_line(-0.4, -1.61, 1.11, -1.61, 'F.SilkS', 0.12),
           _line(-1.11, 1.61, 1.11, 1.61, 'F.SilkS', 0.12),
           _line(-1.3, -1.61, -0.75, -1.61, 'F.SilkS', 0.12)]  # pin-1 side, longer stub
    for n in (1, 2, 3, 4, 5):
        fp.append(_pad(str(n), -0.9, rows[n], 0.6, 0.25, rr=rr))
    for n in (10, 9, 7, 6):
        fp.append(_pad(str(n), 0.75, rows[n], 0.9, 0.25, rr=rr))
    fp.append(_pad('8', 0.55, 0.0, 1.3, 0.25, layers=('F.Cu', 'F.Mask'), rr=rr))
    for x in (0.175, 0.925):  # paste-only apertures for the GND bar
        fp.append(_pad('', x, 0.0, 0.55, 0.25, layers=('F.Paste',), rr=rr))
    return name, fp


def _tht(num, x, y, drill, size, shape='circle'):
    return ['pad', num, Sym('thru_hole'), Sym(shape), ['at', x, y], ['size', size, size],
            ['drill', drill], ['layers', '*.Cu', '*.Mask']]


def _slot(num, x, y, dx, dy, px, py):
    return ['pad', num, Sym('thru_hole'), Sym('oval'), ['at', x, y], ['size', px, py],
            ['drill', Sym('oval'), dx, dy], ['layers', '*.Cu', '*.Mask']]


def bourns_pec11r_4xxxf_s():
    """Bourns PEC11R-4xxxF-Sxxxx (vertical, with push switch) - PEC11R datasheet p.2 PCB layout.

    Origin = mounting-tab centreline / shaft axis. A-C-B: 3x dia 1.0 +0.1 holes at 2.5 mm pitch,
    7.5 mm below the tab line. Switch 1/2: 2x dia 1.0 holes 5.0 mm apart, 7.0 mm above it.
    Mounting tabs: 2x 1.8 x 2.6 (+0.2) slots, 13.2 mm apart. The layout is symmetric, so a
    mirrored reading would only swap A/B (rotation sense, fixable in firmware).
    NOT the Alps EC11E footprint: its tabs are 11.2 mm apart.
    """
    name = 'RotaryEncoder_Bourns_Vertical_PEC11R-4xxxF-Sxxxx'
    fp = ['footprint', name, ['version', 20260206], ['generator', 'pcbnew'], ['layer', 'F.Cu'],
          ['descr', 'Bourns PEC11R-4xxxF-Sxxxx 12mm incremental encoder with switch, vertical '
                    '(https://www.bourns.com/docs/product-datasheets/pec11r.pdf)'],
          ['tags', 'rotary encoder PEC11R'],
          _text('Reference', 'REF**', 0, -10.0, 'F.SilkS'),
          _text('Value', name, 0, 10.5, 'F.Fab'),
          ['attr', Sym('through_hole')], ['duplicate_pad_numbers_are_jumpers', N]]
    fp += _rect(-6.25, -6.7, 6.25, 6.7, 'F.Fab', 0.1)   # 12.5 x 13.4 body
    fp += _rect(-6.37, -6.82, 6.37, 6.82, 'F.SilkS', 0.12)
    fp += _rect(-8.0, -8.5, 8.0, 9.0, 'F.CrtYd', 0.05)
    for num, x in (('A', -2.5), ('C', 0.0), ('B', 2.5)):
        fp.append(_tht(num, x, 7.5, 1.05, 1.8))
    fp.append(_tht('S1', -2.5, -7.0, 1.05, 1.8))
    fp.append(_tht('S2', 2.5, -7.0, 1.05, 1.8))
    for x in (-6.6, 6.6):
        fp.append(_slot('MP', x, 0.0, 1.9, 2.7, 2.7, 3.5))
    return name, fp


def main():
    os.makedirs(OUT, exist_ok=True)
    for build in (tps63802_dla, bourns_pec11r_4xxxf_s):
        name, fp = build()
        path = os.path.join(OUT, name + '.kicad_mod')
        with open(path, 'w') as f:
            f.write(dump(fp) + '\n')
        print('wrote', os.path.relpath(path))


if __name__ == '__main__':
    main()
