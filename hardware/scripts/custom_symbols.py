"""Project-local symbols for parts missing from KiCad's stock libraries.

Pin numbers/names are transcribed from the manufacturer datasheets:
  TPS63802  TI SLVSEU9D, "Pin Functions" (VSON-HR 10-pin "DLA", no exposed pad)
  TPS63900  TI SLVSET3D, Table 5-1 (WSON-10 2.5x2.5 "DSK", thermal pad = pin 11)
  TPS61023  TI SLVSF14B, "Pin Functions" (SOT-563 "DRL")
  CAP1188   Microchip/SMSC CAP1188 datasheet rev 1.32, Table 1.1 (QFN-24 4x4, EP = GND = pin 25)
  TPS22965  TI SLVSBJ0F, "Pin Functions" (WSON-8 2x2 "DSG", thermal pad = pin 9)

Each spec is (number, name, electrical type, side, slot, hidden). Pins sharing a side+slot are
stacked (same connection point); the stacked duplicates are hidden AND forced to 'passive' (as the
stock libraries do) — a hidden power_in pin becomes an implicit global net named after the pin,
which silently shorted every "VIN" in the design together in the first draft.
"""

SYMBOLS = {
    'TPS63802': dict(
        ref='U', width=20.32, slots=4,
        footprint='epaper:Texas_DLA0010A_VSON-HR-10_2x3mm_P0.5mm',  # project fp, see gen_footprints.py
        datasheet='https://www.ti.com/lit/ds/symlink/tps63802.pdf',
        description='1.3-5.5V in (start >1.8V), 2A buck-boost, 11uA Iq, precise EN threshold, VSON-HR 10 (DLA)',
        pins=[
            ('10', 'VIN', 'power_in', 'L', 0, False),
            ('1', 'EN', 'input', 'L', 2, False),
            ('2', 'MODE', 'input', 'L', 3, False),
            ('6', 'VOUT', 'power_out', 'R', 0, False),
            ('4', 'FB', 'input', 'R', 2, False),
            ('5', 'PG', 'open_collector', 'R', 3, False),
            ('9', 'L1', 'passive', 'T', 1, False),
            ('7', 'L2', 'passive', 'T', 0, False),
            ('3', 'AGND', 'power_in', 'B', 0, False),
            ('8', 'GND', 'power_in', 'B', 1, False),
        ]),
    'TPS63900': dict(
        ref='U', width=20.32, slots=5,
        footprint='Package_SON:WSON-10-1EP_2.5x2.5mm_P0.5mm_EP1.2x2mm',  # TI DSK0010A (stock fp was drawn for TPS63030DSK)
        datasheet='https://www.ti.com/lit/ds/symlink/tps63900.pdf',
        description='1.8-5.5V in buck-boost, 75nA Iq, >400mA, resistor-programmed VOUT, WSON-10 2.5x2.5 (DSK)',
        pins=[
            ('10', 'VIN', 'power_in', 'L', 0, False),
            ('1', 'EN', 'input', 'L', 2, False),
            ('2', 'SEL', 'input', 'L', 3, False),
            ('6', 'VOUT', 'power_out', 'R', 0, False),
            ('3', 'CFG1', 'passive', 'R', 2, False),
            ('4', 'CFG2', 'passive', 'R', 3, False),
            ('5', 'CFG3', 'passive', 'R', 4, False),
            ('9', 'LX1', 'passive', 'T', 1, False),
            ('7', 'LX2', 'passive', 'T', 0, False),
            ('8', 'GND', 'power_in', 'B', 0, False),
            ('11', 'EP', 'passive', 'B', 1, False),
        ]),
    'TPS61023': dict(
        ref='U', width=20.32, slots=3,
        footprint='Package_TO_SOT_SMD:SOT-563',
        datasheet='https://www.ti.com/lit/ds/symlink/tps61023.pdf',
        description='0.5-5.5V in synchronous boost, 3.7A valley limit, true shutdown disconnect, SOT-563',
        pins=[
            ('3', 'VIN', 'power_in', 'L', 0, False),
            ('2', 'EN', 'input', 'L', 2, False),
            ('6', 'VOUT', 'power_out', 'R', 0, False),
            ('1', 'FB', 'input', 'R', 2, False),
            ('5', 'SW', 'passive', 'T', 0, False),
            ('4', 'GND', 'power_in', 'B', 0, False),
        ]),
    'CAP1188': dict(
        ref='U', width=27.94, slots=17,
        footprint='Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm',
        datasheet='https://ww1.microchip.com/downloads/en/DeviceDoc/CAP1188%20.pdf',
        description='8-channel capacitive touch controller, SMBus/I2C or SPI, 8 LED drivers, QFN-24',
        pins=[
            ('23', 'VDD', 'power_in', 'L', 0, False),
            ('3', 'SMDATA/SPI_MISO', 'bidirectional', 'L', 2, False),
            ('4', 'SMCLK/SPI_CLK', 'input', 'L', 3, False),
            ('13', 'ALERT#', 'open_collector', 'L', 4, False),
            ('24', 'RESET', 'input', 'L', 5, False),
            ('2', 'WAKE/SPI_MOSI', 'bidirectional', 'L', 7, False),
            ('1', 'SPI_CS#', 'input', 'L', 8, False),
            ('14', 'ADDR_COMM', 'passive', 'L', 10, False),
        ] + [(str(23 - i), 'CS%d' % i, 'passive', 'R', i - 1, False) for i in range(1, 9)]
          # LEDx are open-drain drivers, typed passive: unused ones are tied to GND per Table 1.1
          # and ERC treats open-collector-to-GND as a conflict with GND's power flag.
          + [(str(4 + i), 'LED%d' % i, 'passive', 'R', i + 8, False) for i in range(1, 9)]
          + [('25', 'GND', 'power_in', 'B', 0, False)]),
    'TPS22965': dict(
        ref='U', width=15.24, slots=4,
        footprint='Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm',
        datasheet='https://www.ti.com/lit/ds/symlink/tps22965.pdf',
        description='5.7V 4A 16mOhm load switch with adjustable rise time, WSON-8 2x2',
        pins=[
            ('1', 'VIN', 'power_in', 'L', 0, False),
            ('2', 'VIN', 'power_in', 'L', 0, True),
            ('4', 'VBIAS', 'power_in', 'L', 1, False),
            ('3', 'ON', 'input', 'L', 3, False),
            ('7', 'VOUT', 'power_out', 'R', 0, False),
            ('8', 'VOUT', 'power_out', 'R', 0, True),
            ('6', 'CT', 'passive', 'R', 2, False),
            ('5', 'GND', 'power_in', 'B', 0, False),
            ('9', 'EP', 'passive', 'B', 1, False),
        ]),
}

PIN_LEN = 2.54
PITCH = 2.54


def geometry(spec):
    """Return {pin_number: (x, y, angle)} in symbol-library coordinates (Y up), plus body box."""
    w = spec['width']
    h = (spec['slots'] + 1) * PITCH
    top = h / 2
    half = w / 2
    pos = {}
    for num, name, etype, side, slot, hidden in spec['pins']:
        if side == 'L':
            pos[num] = (-half - PIN_LEN, top - PITCH * (slot + 1), 0)
        elif side == 'R':
            pos[num] = (half + PIN_LEN, top - PITCH * (slot + 1), 180)
        elif side == 'T':
            pos[num] = (half - PITCH * (slot + 2), top + PIN_LEN, 270)  # right: clear of ref/value
        else:  # 'B'
            pos[num] = (-half + PITCH * (slot + 2), -top - PIN_LEN, 90)
    return pos, (-half, top, half, -top)


def _font():
    return ['effects', ['font', ['size', 1.27, 1.27]]]


def _prop(key, val, x, y, hide=False, justify=None):
    from sexp import Sym
    eff = _font()
    if justify:
        eff.append(['justify', Sym(justify)])
    p = ['property', key, val, ['at', x, y, 0]]
    if hide:
        p.append(['hide', Sym('yes')])
    p.append(eff)
    return p


def build(name, lib_prefix=''):
    """Build the (symbol ...) S-expression for one custom part."""
    from sexp import Sym
    spec = SYMBOLS[name]
    pos, (x0, y0, x1, y1) = geometry(spec)
    full = lib_prefix + name
    y_no = Sym('no')
    y_yes = Sym('yes')
    sym = ['symbol', full,
           ['exclude_from_sim', y_no], ['in_bom', y_yes], ['on_board', y_yes],
           _prop('Reference', spec['ref'], x0, y0 + 3.81, justify='left bottom'),
           _prop('Value', name, x0, y0 + 1.27, justify='left bottom'),
           _prop('Footprint', spec['footprint'], 0, y1 - 5.08, hide=True),
           _prop('Datasheet', spec['datasheet'], 0, y1 - 7.62, hide=True),
           _prop('Description', spec['description'], 0, y1 - 10.16, hide=True)]
    body = ['symbol', name + '_0_1',
            ['rectangle', ['start', x0, y0], ['end', x1, y1],
             ['stroke', ['width', 0.254], ['type', Sym('default')]],
             ['fill', ['type', Sym('background')]]]]
    pins = ['symbol', name + '_1_1']
    for num, pname, etype, side, slot, hidden in spec['pins']:
        x, y, a = pos[num]
        if hidden:
            etype = 'passive'
        p = ['pin', Sym(etype), Sym('line'), ['at', x, y, a], ['length', PIN_LEN]]
        if hidden:
            p.append(['hide', y_yes])
        p.append(['name', pname, _font()])
        p.append(['number', num, _font()])
        pins.append(p)
    sym += [body, pins, ['embedded_fonts', y_no]]
    return sym
