"""Shared constants/helpers for the schematic generator (see gen_schematic.py)."""
from kicad_gen import Sheet

PROJECT = 'stm32-epaper'
ROOT_UUID = '6f1d3c2a-5b7e-4c1d-9a0f-000000000001'
# name -> (file, sheet-symbol uuid, page uuid). UUIDs are fixed so regenerating keeps KiCad's
# instance paths (and anything keyed on them) stable.
SHEETS = {
    'Power': ('power.kicad_sch', '6f1d3c2a-5b7e-4c1d-9a0f-000000000002',
              '6f1d3c2a-5b7e-4c1d-9a0f-000000000003'),
    'MCU': ('mcu.kicad_sch', '6f1d3c2a-5b7e-4c1d-9a0f-000000000004',
            '6f1d3c2a-5b7e-4c1d-9a0f-000000000005'),
    'Memory': ('memory.kicad_sch', '6f1d3c2a-5b7e-4c1d-9a0f-000000000006',
               '6f1d3c2a-5b7e-4c1d-9a0f-000000000007'),
    'Peripherals': ('peripherals.kicad_sch', '6f1d3c2a-5b7e-4c1d-9a0f-000000000008',
                    '6f1d3c2a-5b7e-4c1d-9a0f-000000000009'),
}

# Rails that cross sheets: power symbols (global by definition). VSYS / 3V3_PERIPH / 3V3_AON have
# no stock symbol, so they reuse power:VCC with the Value renamed (KiCad names global power nets by
# Value — verified by netlist export, see check_power_netlist.py).
POWER = {'GND': 'GND', 'VBUS': 'VBUS', '+BATT': '+BATT', '+3V3': '+3V3', '+5V': '+5V',
         'VSYS': 'VCC', '3V3_PERIPH': 'VCC', '3V3_AON': 'VCC'}

R0402 = 'Resistor_SMD:R_0402_1005Metric'
R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'


def new_sheet(name, global_nets, paper='A3'):
    _, sheet_uuid, page_uuid = SHEETS[name]
    return Sheet(PROJECT, '/%s/%s' % (ROOT_UUID, sheet_uuid), page_uuid, name, POWER,
                 global_nets, paper)


def two_pin(s, ref, kind, value, x, y, top, bot, fp, **kw):
    """Vertical two-pin Device:<kind> part: pin 1 (top) on `top`, pin 2 (bottom) on `bot`."""
    p = s.part(ref, 'Device:' + kind, value, x, y, footprint=fp, **kw)
    s.conns(p, {'1': top, '2': bot})
    return p


def flag(s, net, x, y):
    """PWR_FLAG for ERC on a net that is fed only by passive/connector pins."""
    s.pwr_n += 1
    s.part('#FLG%s%02d' % (s.prefix, s.pwr_n), 'power:PWR_FLAG', 'PWR_FLAG', x, y)
    s.wire(x, y, x + 7.62, y)
    s.net_at(net, x + 7.62, y, 1, 0)


def hidden_pins(s, lib_id):
    """Pin numbers that are hidden in the library symbol (stacked duplicates of a visible pin)."""
    from sexp import find, find1
    out = set()
    for sub in find(s.lib[lib_id], 'symbol'):
        for p in find(sub, 'pin'):
            if find1(p, 'hide'):
                out.add(find1(p, 'number')[1])
    return out


def conn_by_name(s, part, mapping, strict=True, drawn=()):
    """Connect every pin whose *name* is in `mapping` (net, or None = no-connect). Hidden pins are
    skipped: they sit stacked on a visible pin of the same name. With strict, every visible pin
    of the part must be covered, so nothing is silently left floating. Pins named in `drawn` are
    covered but left alone: the caller wires them up itself."""
    hidden = hidden_pins(s, part.lib_id)
    seen = set()
    for num, (_, _, _, name) in part.pins.items():
        if name in mapping:
            seen.add(name)
            if num in hidden or name in drawn:
                continue
            if mapping[name] is None:
                s.no_connect(part, num)
            else:
                s.conn(part, num, mapping[name])
        elif strict and num not in hidden:
            raise ValueError('%s: pin %s (%s) not assigned' % (part.ref, num, name))
    missing = set(mapping) - seen
    if missing:
        raise ValueError('%s: no pins named %s' % (part.ref, sorted(missing)))
