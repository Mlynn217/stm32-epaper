#!/usr/bin/env python3
"""Generate the side-wall electrode board project (hardware/electrode/): schematic, the electrode
pad footprint and the library tables. The PCB itself is built by gen_electrode_pcb.py, which runs
under KiCad's own Python.

One board design is fitted twice (left and right side wall; the right one is the left one turned
over). Its geometry comes from hardware/enclosure/params.py, so the board always matches the
enclosure's channels and thumb zones.

Usage:  KICAD_SYMBOL_DIR=<kicad share>/symbols python3 gen_electrode.py [--force]
Like gen_schematic.py, it refuses to overwrite the schematic without --force.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'enclosure'))

import params  # noqa: E402  (enclosure dimensions)
from common import flag  # noqa: E402
from kicad_gen import Sheet  # noqa: E402
from sexp import Sym, dump  # noqa: E402

PROJECT = 'electrode'
ROOT_UUID = '6f1d3c2a-5b7e-4c1d-9a0f-0000000e1ec0'
OUT = os.path.join(HERE, '..', 'electrode')
PAD_MARGIN = 1.0  # pad inset from the board's long edges
PAD_W = params.EB_W - 2 * PAD_MARGIN
PAD_FP = 'Electrode_Pad_%gx%gmm' % (params.ELECTRODE_H, PAD_W)
CONN_FP = 'Connector_JST:JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal'


def build_schematic():
    s = Sheet(PROJECT, '/' + ROOT_UUID, ROOT_UUID, 'Side-wall electrode board', {'GND': 'GND'},
              lambda n: None, paper='A4')
    s.text('SIDE-WALL ELECTRODE BOARD - one design, fitted on both side walls (the right one is\n'
           'the left one turned over). Pads face the enclosure wall (the plastic is the dielectric)\n'
           'and are solder-mask covered. J1 cables to J302 (left) / J303 (right) on the main board:\n'
           '1 = lower zone, 2 = GND, 3 = upper zone. GND is a hatched pour on the back only.\n'
           'Geometry: hardware/enclosure/params.py (EB_*, ELECTRODE_*).', 20.32, 20.32)
    e1 = s.part('E1', 'Connector:TestPoint', 'Electrode (lower zone)', 60.96, 71.12,
                footprint='electrode:' + PAD_FP, in_bom=False)
    s.conns(e1, {'1': 'TOUCH_1'})
    e2 = s.part('E2', 'Connector:TestPoint', 'Electrode (upper zone)', 60.96, 91.44,
                footprint='electrode:' + PAD_FP, in_bom=False)
    s.conns(e2, {'1': 'TOUCH_2'})
    j = s.part('J1', 'Connector_Generic:Conn_01x03', 'To main board', 111.76, 81.28,
               footprint=CONN_FP, fields={'MPN': 'SM03B-SRSS-TB'})
    s.conns(j, {'1': 'TOUCH_1', '2': 'GND', '3': 'TOUCH_2'})
    flag(s, 'GND', 132.08, 101.6)
    return s.render(extra=[['sheet_instances', ['path', '/', ['page', '1']]]])


def pad_footprint():
    """One electrode: a solder-mask-covered copper rectangle (F.Cu only - no mask opening, no
    paste), sized to the enclosure's thumb zone."""
    w, h = params.ELECTRODE_H, PAD_W
    Y, N = Sym('yes'), Sym('no')

    def text(key, val, y, layer, hide=False):
        p = ['property', key, val, ['at', 0, y, 0], ['layer', layer]]
        if hide:
            p.append(['hide', Y])
        return p + [['effects', ['font', ['size', 1, 1], ['thickness', 0.15]]]]

    def rect(layer, dx, dy, width):
        return ['fp_rect', ['start', -dx, -dy], ['end', dx, dy],
                ['stroke', ['width', width], ['type', Sym('solid')]], ['fill', N], ['layer', layer]]

    return ['footprint', PAD_FP, ['version', 20241229], ['generator', 'gen_electrode.py'],
            ['layer', 'F.Cu'],
            ['descr', 'Capacitive touch electrode %g x %g mm, solder-mask covered (sensed through '
                      'the enclosure wall). Generated from hardware/enclosure/params.py.' % (w, h)],
            ['tags', 'capacitive touch electrode'],
            text('Reference', 'REF**', -h / 2 - 1.5, 'F.SilkS', hide=True),
            text('Value', PAD_FP, h / 2 + 1.5, 'F.Fab', hide=True),
            ['attr', Sym('smd'), Sym('exclude_from_pos_files'), Sym('exclude_from_bom')],
            rect('F.Fab', w / 2, h / 2, 0.1),
            rect('F.CrtYd', w / 2 + 0.25, h / 2 + 0.25, 0.05),
            ['pad', '1', Sym('smd'), Sym('rect'), ['at', 0, 0], ['size', w, h], ['layers', 'F.Cu']]]


def main():
    os.makedirs(os.path.join(OUT, 'electrode.pretty'), exist_ok=True)
    sch = os.path.join(OUT, PROJECT + '.kicad_sch')
    if os.path.exists(sch) and '--force' not in sys.argv:
        sys.exit('refusing to overwrite %s (it may have GUI edits); pass --force' % sch)
    files = {
        PROJECT + '.kicad_sch': build_schematic(),
        os.path.join('electrode.pretty', PAD_FP + '.kicad_mod'): dump(pad_footprint()) + '\n',
        'fp-lib-table': '(fp_lib_table\n  (version 7)\n  (lib (name "electrode")(type "KiCad")'
                        '(uri "${KIPRJMOD}/electrode.pretty")(options "")'
                        '(descr "Electrode board footprints, see hardware/scripts/gen_electrode.py"))\n)\n',
    }
    pro = os.path.join(OUT, PROJECT + '.kicad_pro')
    if not os.path.exists(pro):
        files[PROJECT + '.kicad_pro'] = json.dumps(
            {'meta': {'filename': PROJECT + '.kicad_pro', 'version': 3}}, indent=2) + '\n'
    for name, text in files.items():
        with open(os.path.join(OUT, name), 'w') as f:
            f.write(text)
        print('wrote', os.path.relpath(os.path.join(OUT, name)))


if __name__ == '__main__':
    main()
