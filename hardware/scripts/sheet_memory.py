"""Memory sheet: IS42S16400J SDRAM (FMC, 16-bit), W25Q128JV QSPI NOR, microSD socket (SDIO 4-bit).

Everything here runs from 3V3_PERIPH (the rail the reserved TPS22965 can gate in v2; on v1 it is
+3V3 through the fitted 0R R13). Net names are the STM32 alternate-function names, so
check_schematic.py can confirm end to end that each memory pin reaches an MCU pin that really
provides that function.
"""
from common import C0402, C0603, C0805, R0402, conn_by_name, new_sheet
from wiring import G, bank, path, pin, two

LOCAL = set()

# IS42S16400J pin name -> FMC net (SDRAM bank 1: SDCKE0/SDNE0)
SDRAM = {'~{WE}': 'FMC_SDNWE', '~{CAS}': 'FMC_SDNCAS', '~{RAS}': 'FMC_SDNRAS',
         '~{CS}': 'FMC_SDNE0', 'CKE': 'FMC_SDCKE0', 'CLK': 'SDRAM_CLK',
         'BA0': 'FMC_BA0', 'BA1': 'FMC_BA1', 'LDQM': 'FMC_NBL0', 'UDQM': 'FMC_NBL1',
         'VDD': '3V3_PERIPH', 'VDDQ': '3V3_PERIPH', 'GND': 'GND', 'GNDQ': 'GND', 'NC': None}
SDRAM.update({'A%d' % i: 'FMC_A%d' % i for i in range(12)})
SDRAM.update({'DQ%d' % i: 'FMC_D%d' % i for i in range(16)})

QSPI = {'~{CS}': 'QUADSPI_BK1_NCS', 'CLK': 'QSPI_FLASH_CLK', 'DI/IO_{0}': 'QUADSPI_BK1_IO0',
        'DO/IO_{1}': 'QUADSPI_BK1_IO1', '~{WP}/IO_{2}': 'QUADSPI_BK1_IO2',
        '~{HOLD}/~{RESET}/IO_{3}': 'QUADSPI_BK1_IO3', 'VCC': '3V3_PERIPH', 'GND': 'GND'}

SD = {'DAT0': 'SDIO_D0', 'DAT1': 'SDIO_D1', 'DAT2': 'SDIO_D2', 'DAT3/CD': 'SDIO_D3',
      'CMD': 'SDIO_CMD', 'CLK': 'SDCARD_CLK', 'VDD': '3V3_PERIPH', 'VSS': 'GND', 'SHIELD': 'GND',
      'DET_B': 'SD_DETECT', 'DET_A': 'GND'}

# Source series resistors on the three memory clocks (placed at the MCU pin in layout): damp
# ringing/EMI on the point-to-point clock lines. device-side net -> (resistor, value, MCU net).
SERIES = {'SDRAM_CLK': ('R208', '22R', 'FMC_SDCLK'),
          'SDCARD_CLK': ('R209', '33R', 'SDIO_CK'),
          'QSPI_FLASH_CLK': ('R210', '22R', 'QUADSPI_CLK')}


def series_clock(s, pin_xy, dev_net, x_r, label_dx=G):
    """Clock run out of a device pin to the left, through its source series resistor (inline, as
    the signal flows), on to the MCU-side global label. The device-side net keeps its own name
    via a label standing up off the wire just before the resistor."""
    ref, value, mcu_net = SERIES[dev_net]
    x, y = pin_xy
    xl = x_r + label_dx
    path(s, [(x, y), (xl, y), (x_r, y)])
    s.net_at(dev_net, xl, y, 0, -1)
    p2, _ = two(s, ref, 'Device:R', value, (x_r, y), (-1, 0), footprint=R0402,
                pin_a='2', pin_b='1')
    s.wire(p2[0], p2[1], p2[0] - G, p2[1])
    s.net_at(mcu_net, p2[0] - G, p2[1], -1, 0)


def _by_name(part):
    """Pin number for each pin name (the lowest, for stacked duplicates)."""
    out = {}
    for num, (_, _, _, name) in sorted(part.pins.items(), key=lambda kv: int(kv[0])
                                       if kv[0].isdigit() else 999):
        out.setdefault(name, num)
    return out


def build():
    s = new_sheet('Memory', lambda n: None if n in LOCAL else 'bidirectional')
    s.text('MEMORY — all on 3V3_PERIPH. Net names = STM32 alternate functions (see sheet_mcu.PINMAP).',
           20.32, 12.7, size=2)
    s.text('Clock series resistors R208-R210 (22-33R source termination, up to 90 MHz) are drawn\n'
           'inline with each clock; in layout they sit right at the MCU pin.', 20.32, 20.32)

    # ---- SDRAM ---------------------------------------------------------------------------
    s.text('IS42S16400J-6TLI: 64 Mbit = 8 MB (1M x 16 x 4 banks), FMC SDRAM bank 1, 16-bit.\n'
           '12 row / 8 column address bits, 4 banks. Decoupling: 100nF per VDD/VDDQ pin + 10uF.\n'
           'Layout: keep the FMC bus short and length-matched-ish; SDCLK up to 90 MHz.',
           20.32, 30.48)
    u = s.part('U201', 'Memory_RAM:IS42S16400J-xT', 'IS42S16400J-6TLI', 76.2, 134.62,
               fields={'MPN': 'IS42S16400J-6TLI'})
    conn_by_name(s, u, SDRAM, drawn={'VDD', 'VDDQ', 'CLK'})
    un = _by_name(u)
    # VDD + VDDQ straight up onto the 3V3_PERIPH rail, the decoupling bank beside them.
    y_r = 99.06 - 6 * G
    tops = []
    for name in ('VDD', 'VDDQ'):
        x, y = pin(u, un[name])
        s.wire(x, y, x, y_r)
        tops.append((x, y_r))
    bank(s, [('C%d' % (201 + i), '100nF', C0402, None) for i in range(7)]
         + [('C208', '10uF', C0805, None)], 96.52, y_r, '3V3_PERIPH', extra_top=tops)
    series_clock(s, pin(u, un['CLK']), 'SDRAM_CLK', 63.5 - 9 * G)

    # ---- QSPI NOR ------------------------------------------------------------------------
    s.text('W25Q128JV 16 MB QSPI NOR (fonts/assets; firmware stays in internal flash).\n'
           '10k pull-up on /CS keeps the flash deselected while the MCU boots.', 218.44, 30.48)
    q = s.part('U202', 'Memory_Flash:W25Q128JVS', 'W25Q128JVSIQ', 256.54, 76.2,
               fields={'MPN': 'W25Q128JVSIQ'})
    conn_by_name(s, q, QSPI, drawn={'VCC', '~{CS}', 'CLK'})
    qn = _by_name(q)
    x, y = pin(q, qn['VCC'])
    y_r = y - 3 * G
    s.wire(x, y, x, y_r)
    bank(s, [('C209', '100nF', C0402, None)], x + 11 * G, y_r, '3V3_PERIPH', extra_top=[(x, y_r)])
    x, y = pin(q, qn['~{CS}'])
    xj = x - 3 * G
    path(s, [(x, y), (xj, y), (xj - 2 * G, y)])
    s.junction(xj, y)
    p1, _ = two(s, 'R201', 'Device:R', '10k', (xj, y), (0, -1), footprint=R0402,
                pin_a='2', pin_b='1')
    s.net_at('3V3_PERIPH', p1[0], p1[1], 0, -1)
    s.net_at('QUADSPI_BK1_NCS', xj - 2 * G, y, -1, 0)
    series_clock(s, pin(q, qn['CLK']), 'QSPI_FLASH_CLK', x - 16 * G)

    # ---- microSD ------------------------------------------------------------------------
    s.text('microSD (Molex 104031-0811, push-pull, detect switch). 47k pull-ups on CMD/DAT0-3\n'
           '(SD spec 10k-100k); card-detect switch to GND with a 100k pull-up to 3V3_AON (the MCU\n'
           'rail, so detect works even with 3V3_PERIPH gated). 10uF + 100nF at the socket for\n'
           'hot-insertion inrush.', 218.44, 129.54)
    j = s.part('J201', 'Connector:Micro_SD_Card_Det2', 'microSD', 256.54, 190.5,
               footprint='Connector_Card:microSD_HC_Molex_104031-0811',
               fields={'MPN': 'Molex 1040310811'})
    conn_by_name(s, j, SD, drawn={'DAT0', 'DAT1', 'DAT2', 'DAT3/CD', 'CMD', 'CLK', 'VDD', 'VSS',
                                  'DET_A', 'DET_B'})
    jn = _by_name(j)
    y_rail = 162.56
    x_lab = 167.64
    # Pull-ups hang from a 3V3_PERIPH rail above the socket, one column per signal (topmost pin
    # nearest the socket); each drops onto its signal line, which runs on to the global label.
    pullups = [('DAT2', 'R205', 226.06), ('DAT3/CD', 'R206', 215.9), ('CMD', 'R202', 205.74),
               ('DAT0', 'R203', 195.58), ('DAT1', 'R204', 185.42)]
    rail_pts = []
    for name, ref, xc in pullups:
        p2, _ = two(s, ref, 'Device:R', '47k', (xc, y_rail), (0, 1), footprint=R0402)
        x, y = pin(j, jn[name])
        s.wire(p2[0], p2[1], xc, y)
        path(s, [(x, y), (xc, y), (x_lab, y)])
        s.junction(xc, y)
        s.net_at(SD[name], x_lab, y, -1, 0)
        rail_pts.append((xc, y_rail))
    # Card detect: 100k to 3V3_AON (its own symbol, not the PERIPH rail).
    x, y = pin(j, jn['DET_B'])
    xc = 172.72
    p2, _ = two(s, 'R207', 'Device:R', '100k', (xc, y_rail), (0, 1), footprint=R0402)
    s.net_at('3V3_AON', xc, y_rail, 0, -1)
    s.wire(p2[0], p2[1], xc, y)
    path(s, [(x, y), (xc, y), (x_lab, y)])
    s.junction(xc, y)
    s.net_at('SD_DETECT', x_lab, y, -1, 0)
    # VDD up onto the same rail, which carries on over the socket to the bulk + HF caps.
    x, y = pin(j, jn['VDD'])
    x_v = x - G
    path(s, [(x, y), (x_v, y), (x_v, y_rail)])
    rail_pts.append((x_v, y_rail))
    bank(s, [('C210', '10uF', C0603, None), ('C211', '100nF', C0402, None)], 284.48, y_rail,
         '3V3_PERIPH', extra_top=rail_pts)
    # VSS and the detect switch's common (DET_A) down a GND column below the socket's pins.
    xs, ys = pin(j, jn['VSS'])
    xa, ya = pin(j, jn['DET_A'])
    y_g = pin(j, jn['DET_B'])[1] + G
    path(s, [(xs, ys), (x_v, ys), (x_v, ya), (x_v, y_g)])
    s.wire(xa, ya, x_v, ya)
    s.junction(x_v, ya)
    s.net_at('GND', x_v, y_g, 0, 1)
    # CLK: series resistor inline; the socket-side net's label sits on a short jog up into the
    # free row left by VDD (no room for a standing label between the pin rows).
    x, y = pin(j, jn['CLK'])
    xj = x - 2 * G
    path(s, [(x, y), (xj, y), (xj, y - G), (xj - G, y - G)])
    s.junction(xj, y)
    s.net_at('SDCARD_CLK', xj - G, y - G, -1, 0)
    ref, value, mcu_net = SERIES['SDCARD_CLK']
    xr = 208.28
    s.wire(xj, y, xr, y)
    p2, _ = two(s, ref, 'Device:R', value, (xr, y), (-1, 0), footprint=R0402,
                pin_a='2', pin_b='1')
    s.wire(p2[0], p2[1], x_lab, y)
    s.net_at(mcu_net, x_lab, y, -1, 0)
    return s
