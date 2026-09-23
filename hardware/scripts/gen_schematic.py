#!/usr/bin/env python3
"""Bootstrap generator for the hardware/kicad schematic (root + every sheet, project symbol lib,
library tables).

One-shot scaffolding: it OVERWRITES the generated .kicad_sch files. Once a sheet has been edited
in Eeschema, treat the .kicad_sch as the source of truth and stop re-running this (it refuses to
overwrite existing schematics without --force for exactly that reason).

Usage:  KICAD_SYMBOL_DIR=<kicad share>/symbols python3 gen_schematic.py [--force]
"""
import json
import os
import sys

import custom_symbols
import sheet_mcu
import sheet_memory
import sheet_peripherals
import sheet_power
from common import PROJECT, ROOT_UUID, SHEETS
from kicad_gen import NO, YES, _eff, _prop, uid
from sexp import Sym, dump

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'kicad')
BUILDERS = [('Power', sheet_power.build), ('MCU', sheet_mcu.build),
            ('Memory', sheet_memory.build), ('Peripherals', sheet_peripherals.build)]


def sheet_block(name, x, y, page):
    fname, sheet_uuid, _ = SHEETS[name]
    return ['sheet', ['at', x, y], ['size', 50.8, 25.4], ['exclude_from_sim', NO],
            ['in_bom', YES], ['on_board', YES], ['dnp', NO],
            ['stroke', ['width', 0.1524], ['type', Sym('solid')]],
            ['fill', ['color', 0, 0, 0, 0.0]], ['uuid', sheet_uuid],
            _prop('Sheetname', name, x, y - 0.7, justify='left bottom'),
            _prop('Sheetfile', fname, x, y + 26.0, justify='left top'),
            ['instances', ['project', PROJECT, ['path', '/' + ROOT_UUID, ['page', page]]]]]


def build_root():
    blocks = [sheet_block(name, 25.4 + (i % 2) * 76.2, 50.8 + (i // 2) * 50.8, str(i + 2))
              for i, (name, _) in enumerate(BUILDERS)]
    doc = ['kicad_sch', ['version', 20250610], ['generator', 'eeschema'],
           ['generator_version', '10.0'], ['uuid', ROOT_UUID], ['paper', 'A4'],
           ['title_block', ['title', 'STM32 e-reader']], ['lib_symbols'],
           ['text', 'STM32F469 e-reader, v1 board (Waveshare IT8951 HAT external on an SPI '
                    'connector).\nInter-sheet signals are global labels; rails are power '
                    'symbols. See README.md "Custom PCB (Planned)".',
            ['exclude_from_sim', NO], ['at', 25.4, 25.4, 0], _eff('left top'), ['uuid', uid()]],
           *blocks,
           ['sheet_instances', ['path', '/', ['page', '1']]],
           ['embedded_fonts', NO]]
    return dump(doc) + '\n'


def build_symbol_lib():
    doc = ['kicad_symbol_lib', ['version', 20241209], ['generator', 'kicad_symbol_editor'],
           ['generator_version', '10.0']]
    for name in custom_symbols.SYMBOLS:
        doc.append(custom_symbols.build(name))
    return dump(doc) + '\n'


def main():
    os.makedirs(OUT, exist_ok=True)
    schematics = [SHEETS[n][0] for n, _ in BUILDERS] + [PROJECT + '.kicad_sch']
    if '--force' not in sys.argv and any(os.path.exists(os.path.join(OUT, t)) for t in schematics):
        sys.exit('refusing to overwrite existing schematics (they may have GUI edits); '
                 'pass --force if you really mean it')
    files = {SHEETS[name][0]: build().render() for name, build in BUILDERS}
    files.update({
        PROJECT + '.kicad_sch': build_root(),
        'epaper.kicad_sym': build_symbol_lib(),
        'sym-lib-table': '(sym_lib_table\n  (version 7)\n  (lib (name "epaper")(type "KiCad")'
                         '(uri "${KIPRJMOD}/epaper.kicad_sym")(options "")'
                         '(descr "Project-local parts missing from stock libraries"))\n)\n',
        'fp-lib-table': '(fp_lib_table\n  (version 7)\n  (lib (name "epaper")(type "KiCad")'
                        '(uri "${KIPRJMOD}/epaper.pretty")(options "")'
                        '(descr "Project-local footprints, see hardware/scripts/gen_footprints.py"))\n)\n',
    })
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
