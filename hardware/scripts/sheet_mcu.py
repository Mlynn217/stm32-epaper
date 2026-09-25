"""MCU sheet: STM32F469IIT6 (LQFP176) with supply decoupling, clocks, reset/boot, SWD, debug UART.

PINMAP is the single source of truth for the pin assignment. Each entry names the alternate
function the pin must provide (checked against the KiCad symbol's alternate list by
check_schematic.py), so a typo or an impossible mux shows up as a check failure rather than a
respin. Assignments follow the STM32F469I-DISCO wherever the peripheral carries over, so the
existing firmware / CubeMX config keeps working (see README "MCU sheet").
"""
from common import C0402, C0603, R0402, flag, hidden_pins, new_sheet, two_pin
from wiring import G, bank, path, pin, rail, two

MCU_LIB = 'MCU_ST_STM32F4:STM32F469IITx'

# (pin, net, required alternate function or None for a plain GPIO)
PINMAP = [
    # FMC SDRAM, bank 1 (SDCKE0/SDNE0 -> 0xC0000000, as on the Disco), 16-bit data
    ('PC0', 'FMC_SDNWE', 'FMC_SDNWE'),
    ('PH2', 'FMC_SDCKE0', 'FMC_SDCKE0'),
    ('PH3', 'FMC_SDNE0', 'FMC_SDNE0'),
    ('PG8', 'FMC_SDCLK', 'FMC_SDCLK'),
    ('PF11', 'FMC_SDNRAS', 'FMC_SDNRAS'),
    ('PG15', 'FMC_SDNCAS', 'FMC_SDNCAS'),
    ('PG4', 'FMC_BA0', 'FMC_BA0'),
    ('PG5', 'FMC_BA1', 'FMC_BA1'),
    ('PE0', 'FMC_NBL0', 'FMC_NBL0'),
    ('PE1', 'FMC_NBL1', 'FMC_NBL1'),
] + [(p, 'FMC_A%d' % i, 'FMC_A%d' % i) for i, p in enumerate(
    ['PF0', 'PF1', 'PF2', 'PF3', 'PF4', 'PF5', 'PF12', 'PF13', 'PF14', 'PF15', 'PG0', 'PG1'])
] + [(p, 'FMC_D%d' % i, 'FMC_D%d' % i) for i, p in enumerate(
    ['PD14', 'PD15', 'PD0', 'PD1', 'PE7', 'PE8', 'PE9', 'PE10', 'PE11', 'PE12', 'PE13', 'PE14',
     'PE15', 'PD8', 'PD9', 'PD10'])
] + [
    # QUADSPI bank 1 (Disco pins)
    ('PF10', 'QUADSPI_CLK', 'QUADSPI_CLK'),
    ('PB6', 'QUADSPI_BK1_NCS', 'QUADSPI_BK1_NCS'),
    ('PF8', 'QUADSPI_BK1_IO0', 'QUADSPI_BK1_IO0'),
    ('PF9', 'QUADSPI_BK1_IO1', 'QUADSPI_BK1_IO1'),
    ('PF7', 'QUADSPI_BK1_IO2', 'QUADSPI_BK1_IO2'),
    ('PF6', 'QUADSPI_BK1_IO3', 'QUADSPI_BK1_IO3'),
    # SDIO 4-bit (Disco pins); card detect moved PG2 -> PG10 so EXTI2 stays free for HRDY
    ('PC8', 'SDIO_D0', 'SDIO_D0'),
    ('PC9', 'SDIO_D1', 'SDIO_D1'),
    ('PC10', 'SDIO_D2', 'SDIO_D2'),
    ('PC11', 'SDIO_D3', 'SDIO_D3'),
    ('PC12', 'SDIO_CK', 'SDIO_CK'),
    ('PD2', 'SDIO_CMD', 'SDIO_CMD'),
    ('PG10', 'SD_DETECT', None),
    # Waveshare IT8951 HAT: SPI1 + control, exactly the pins the current firmware uses
    ('PA5', 'SPI1_SCK', 'SPI1_SCK'),
    ('PB4', 'SPI1_MISO', 'SPI1_MISO'),
    ('PB5', 'SPI1_MOSI', 'SPI1_MOSI'),
    ('PA4', 'EPD_CS', None),
    ('PB1', 'EPD_RST', None),
    ('PA2', 'EPD_HRDY', None),
    ('PB0', 'EPD_5V_EN', None),
    # USB OTG FS device (DFU/CDC). PA9 (FT) senses VBUS through R104 1k, which limits injection
    # current if VBUS arrives before VDD is up.
    ('PA11', 'USB_DM', 'USB_OTG_FS_DM'),
    ('PA12', 'USB_DP', 'USB_OTG_FS_DP'),
    ('PA9', 'VBUS_SENSE', 'USB_OTG_FS_VBUS'),
    # Debug: SWD + SWO to the TC2050 pads, USART3 = the Disco's ST-LINK VCP pins (same log UART)
    ('PA13', 'SWDIO', 'SYS_JTMS-SWDIO'),
    ('PA14', 'SWCLK', 'SYS_JTCK-SWCLK'),
    ('PB3', 'SWO', 'SYS_JTDO-SWO'),
    ('PB10', 'USART3_TX', 'USART3_TX'),
    ('PB11', 'USART3_RX', 'USART3_RX'),
    # Input: CAP1188 on I2C1 (Disco pins), encoder on TIM3 encoder mode, power button on WKUP
    ('PB8', 'I2C1_SCL', 'I2C1_SCL'),
    ('PB9', 'I2C1_SDA', 'I2C1_SDA'),
    ('PB7', 'CAP_ALERT', None),
    ('PB12', 'CAP_RESET', None),
    ('PA6', 'ENC_A', 'TIM3_CH1'),
    ('PA7', 'ENC_B', 'TIM3_CH2'),
    ('PD3', 'ENC_SW', None),
    ('PA0', 'PWR_BTN', 'SYS_WKUP'),
    # Power-sheet status/control
    ('PD4', 'CHG_STAT', None),  # FT: the charge LED path lets it float toward VBUS
    ('PD5', '3V3_PG', None),
    ('PD7', 'PERIPH_EN', None),
    ('PA3', 'VBAT_SENSE', 'ADC1_IN3'),  # cell voltage via 1M/1M divider on the Power sheet
    ('PC1', 'TS_SENSE', 'ADC1_IN11'),  # charger NTC voltage (75uA x R_NTC while charging)
    ('PD6', 'CHG_DIS', None),  # BQ24073 CE: high suspends charging (cell 45C limit)
    # Misc
    ('PG6', 'LED_STATUS', None),
    ('PB2', 'BOOT1', None),  # BOOT1: pulled low so BOOT0=1 selects the system (DFU) bootloader
    ('PH0', 'HSE_IN', 'RCC_OSC_IN'),
    ('PH1', 'HSE_OUT', 'RCC_OSC_OUT'),
    ('PC14', 'LSE_IN', 'RCC_OSC32_IN'),
    ('PC15', 'LSE_OUT', 'RCC_OSC32_OUT'),
]

# Non-GPIO pins, by symbol pin name (every visible pin with that name gets the net). DSI host is
# unused: per DS11189 §2.18 VDDDSI -> VDD, VCAPDSI tied to VDD12DSI with no capacitor, VSSDSI -> GND.
SUPPLY = {
    'VDD': '3V3_AON', 'VDDUSB': '3V3_AON', 'VDDDSI': '3V3_AON', 'PDR_ON': '3V3_AON',
    'VSS': 'GND', 'VSSA': 'GND', 'VSSDSI': 'GND', 'BYPASS_REG': 'GND',
    'VDDA': 'VDDA', 'VREF+': 'VDDA',
    'VCAP1': 'VCAP1', 'VCAP2': 'VCAP2', 'VCAPDSI': 'VDD12DSI', 'VDD12DSI': 'VDD12DSI',
    'BOOT0': 'BOOT0', 'NRST': 'NRST', 'VBAT': 'VBAT_RTC',
}

LOCAL = {'HSE_IN', 'HSE_OUT', 'LSE_IN', 'LSE_OUT', 'NRST', 'BOOT0', 'BOOT1', 'SWDIO', 'SWCLK',
         'SWO', 'USART3_TX', 'USART3_RX', 'VCAP1', 'VCAP2', 'VDD12DSI', 'VDDA', 'LED_STATUS',
         'LED1_A', 'VBUS_SENSE'}


# MCU pins drawn wired to their circuit on this sheet instead of a stub + label.
DRAWN = {'PB8', 'PB9', 'PH0', 'PH1', 'PC14', 'PC15', 'PB2', 'PA9', 'PG6'}


def i2c_pullups(s, u, by_name):
    """I2C1 pull-ups (4.7k to 3V3_AON) drawn on the MCU's SCL/SDA pins: both lines run out past
    the neighbouring pins' labels, jog apart (SCL up, SDA down) and each gets its pull-up hanging
    to a 3V3_AON rail symbol, with junction dots - then on to the CAP1188 via the global labels."""
    G = 2.54
    (scl,) = by_name['PB8']
    (sda,) = by_name['PB9']
    xs, ys, _ = u.pin_xy(scl)
    xd, yd, _ = u.pin_xy(sda)
    out = xs + 14 * G           # clear of the neighbours' labels
    end = xs + 22 * G
    for pin_x, pin_y, jog, net, ref, rx in ((xs, ys, -2 * G, 'I2C1_SCL', 'R105', xs + 17 * G),
                                            (xd, yd, 2 * G, 'I2C1_SDA', 'R106', xs + 19 * G)):
        line_y = pin_y + jog
        s.wire_path([(pin_x, pin_y), (out, pin_y), (out, line_y), (rx, line_y)])
        s.wire(rx, line_y, end, line_y)
        s.junction(rx, line_y)
        # Device:R pins sit at +-3.81 mm: pin 2 (bottom) on the line, pin 1 up to the rail.
        s.part(ref, 'Device:R', '4.7k', rx, line_y - 3.81, footprint=R0402)
        s.net_at('3V3_AON', rx, line_y - 7.62, 0, -1)
        s.net_at(net, end, line_y, 1, 0)
    s.text('I2C1 pull-ups (CAP1188 on the Peripherals sheet)', xs + 14 * G, ys - 9 * G, size=1.27)


def _global(net):
    return None if net in LOCAL else 'bidirectional'


def build():
    s = new_sheet('MCU', _global, paper='A2')
    s.text('MCU — STM32F469IIT6 (LQFP176). Pin assignment = PINMAP in hardware/scripts/sheet_mcu.py,\n'
           'checked against the symbol\'s alternate-function list by check_schematic.py. Follows the\n'
           'F469-Disco pins for FMC/QSPI/SDIO/SPI1/USART3/I2C1 so the firmware config carries over;\n'
           'SDRAM is 16-bit here (Disco: 32-bit) - FMC init needs updating.', 20.32, 12.7, size=2)

    mx, my = 297.18, 223.52
    u = s.part('U101', MCU_LIB, 'STM32F469IIT6', mx, my, fields={'MPN': 'STM32F469IIT6'})
    by_name = {}
    for num, (_, _, _, name) in u.pins.items():
        by_name.setdefault(name, []).append(num)
    used = set()
    for pin, net, _af in PINMAP:
        (num,) = by_name[pin]
        used.add(num)
        if pin in DRAWN:
            continue      # wired to its circuit below, not just a stub + label
        s.conn(u, num, net)
    hidden = hidden_pins(s, MCU_LIB)
    for name, net in SUPPLY.items():
        for num in by_name[name]:
            used.add(num)
            if name in SUPPLY_DRAWN:
                continue      # wired to its decoupling below
            if num not in hidden:  # hidden duplicates are stacked on a visible pin
                s.conn(u, num, net)
    for num in u.pins:
        if num not in used:
            s.no_connect(u, num)

    power_pins(s, u, by_name)
    vcap(s, u, by_name)
    clocks(s, u, by_name)
    i2c_pullups(s, u, by_name)
    right_side_resistors(s, u, by_name)
    status_led(s, u, by_name)
    reset_boot(s)

    # ---- debug: TC2050 (ARM 10-pin Cortex debug pinout, 1:1) + UART header ------------------
    s.text('SWD on TC2050-IDC-NL pads (no header on the board). The TC2050-IDC cable maps 1:1\n'
           'onto the standard ARM 10-pin Cortex debug connector, so an ST-LINK-V3 plugs\n'
           'straight in. USART3 (same pins as the Disco VCP) on a 3-pin 1.27mm header for the\n'
           'serial log.', 20.32, 162.56)
    j = s.part('J101', 'Connector:Conn_ARM_JTAG_SWD_10', 'TC2050-IDC-NL', 50.8, 203.2,
               footprint='Connector:Tag-Connect_TC2050-IDC-NL_2x05_P1.27mm_Vertical')
    s.conns(j, {'1': '3V3_AON', '2': 'SWDIO', '4': 'SWCLK', '6': 'SWO', '10': 'NRST',
                '3': 'GND', '5': 'GND', '9': 'GND', '7': None, '8': None})
    ju = s.part('J102', 'Connector_Generic:Conn_01x03', 'UART (TX RX GND)', 50.8, 248.92,
                footprint='Connector_PinHeader_1.27mm:PinHeader_1x03_P1.27mm_Vertical')
    s.conns(ju, {'1': 'USART3_TX', '2': 'USART3_RX', '3': 'GND'})
    return s


# Supply pins drawn wired to their decoupling instead of a stub + power symbol.
SUPPLY_DRAWN = {'VDD', 'VDDDSI', 'VDDUSB', 'VDDA', 'VBAT', 'VCAP1', 'VCAP2', 'BYPASS_REG',
                'PDR_ON'}


def power_pins(s, u, by_name):
    """Top edge: the 13 VDD pins on one 3V3_AON rail with the decoupling bank hanging from it;
    VDDDSI/VDDUSB on a second rail with C115; VDDA through FB101 with its own bank."""
    vdd = sorted(pin(u, n) for n in by_name['VDD'])
    y_r = vdd[0][1] - 2 * G
    for x, y in vdd:
        s.wire(x, y, x, y_r)
    caps = [('C%d' % (101 + i), '100nF', C0402, None) for i in range(13)]
    caps.append(('C114', '4.7uF', C0603, None))
    bank(s, caps, 114.3, y_r, '3V3_AON', extra_top=[(x, y_r) for x, _ in vdd])
    s.text('Decoupling (DS11189 Fig. 24): 100nF per VDD pin + 4.7uF; place each 100nF at its pin',
           114.3, y_r - 5 * G)

    # BYPASS_REG (tied low: regulator on) straight up into the bank's GND rail, which ends just
    # above it; PDR_ON (tied high) out far enough that its 3V3_AON symbol clears NRST's label.
    xg, yg = pin(u, by_name['BYPASS_REG'][0])
    x_gnd_end = 114.3 + 13 * 4 * G
    path(s, [(xg, yg), (x_gnd_end, yg), (x_gnd_end, y_r + 3 * G)])
    xp, yp = pin(u, by_name['PDR_ON'][0])
    s.wire(xp, yp, xp - 7 * G, yp)
    s.net_at('3V3_AON', xp - 7 * G, yp, 0, -1)

    # VBAT: the RTC supply from the power sheet, labelled to the left under the rail.
    xb, yb = pin(u, by_name['VBAT'][0])
    s.wire(xb, yb, xb, yb - G)
    s.net_at('VBAT_RTC', xb, yb - G, -1, 0)

    # VDDDSI + VDDUSB: second 3V3_AON rail, out to the right past the body, with C115.
    pts = [pin(u, n) for n in by_name['VDDDSI'] + by_name['VDDUSB']]
    for x, y in pts:
        s.wire(x, y, x, y_r)
    x_sym, x_cap = 332.74, 345.44
    rail(s, [(x, y_r) for x, _ in pts] + [(x_sym, y_r), (x_cap, y_r)])
    s.net_at('3V3_AON', x_sym, y_r, 0, -1)
    two(s, 'C115', 'Device:C', '100nF', (x_cap, y_r), (0, 1), footprint=C0402)
    s.net_at('GND', x_cap, y_r + 3 * G, 0, 1)
    s.text('VDDUSB', x_cap + G, y_r + 4 * G, size=1)

    # VDDA (tied to VREF+ on the left side): up to its own rail, FB101 from 3V3_AON, 2x(1uF+100nF).
    xa, ya = pin(u, by_name['VDDA'][0])
    y_a = ya - 8 * G
    s.wire(xa, ya, xa, y_a)
    caps = [('C116', '1uF', C0402, None), ('C117', '100nF', C0402, None),
            ('C118', '1uF', C0402, None), ('C119', '100nF', C0402, None)]
    x_fb = 350.52 + 4 * 4 * G + G
    tops = bank(s, caps, 350.52, y_a, 'VDDA', extra_top=[(xa, y_a), (x_fb, y_a)],
                label_net=None)
    s.net_at('VDDA', xa + 2 * G, y_a, 0, -1)
    p1, _ = two(s, 'FB101', 'Device:FerriteBead_Small', 'BLM18PG221SN1', (x_fb, y_a), (1, 0),
                footprint='Inductor_SMD:L_0603_1608Metric', pin_a='2', pin_b='1')
    s.wire(p1[0], p1[1], p1[0] + 2 * G, p1[1])
    s.net_at('3V3_AON', p1[0] + 2 * G, p1[1], 0, -1)
    # PWR_FLAG (ERC: VDDA is driven through a passive ferrite) right on the rail's corner.
    s.pwr_n += 1
    s.part('#FLG%s%02d' % (s.prefix, s.pwr_n), 'power:PWR_FLAG', 'PWR_FLAG', xa, y_a)
    s.text('VDDA / VREF+: FB101 + 2 x (1uF + 100nF)', 350.52, y_a - 10 * G)


def vcap(s, u, by_name):
    """VCAP1/VCAP2 (core regulator): 2.2uF each, ESR < 2 ohm, wired out past VCAPDSI's label."""
    for name, x_cap, ref in (('VCAP1', 223.52, 'C120'), ('VCAP2', 231.14, 'C121')):
        x, y = pin(u, by_name[name][0])
        s.wire(x, y, x_cap, y)
        s.net_at(name, x - 5 * G, y, -1, 0)
        p2, _ = two(s, ref, 'Device:C', '2.2uF', (x_cap, y), (0, 1), footprint=C0402,
                    fields={'Note': 'ESR < 2 ohm'})
        s.net_at('GND', p2[0], p2[1], 0, 1)


def clocks(s, u, by_name):
    """HSE crystal below PH0/PH1 and LSE crystal above PC14/PC15, each wired to its pins with its
    load capacitors to GND."""
    s.text('HSE 8MHz (PLL -> 180MHz), NDK NX3225GD CL = 8pF: C = 2*(CL - Cstray) = 2*(8 - 3) =\n'
           '10pF (C0G). LSE: NDK NX3215SA CL = 6pF, ESR <= 70k: C = 2*(6 - 3) = 6.2pF (C0G).\n'
           'AN2867 gm_crit = 4*ESR*(2*pi*f)^2*(C0+CL)^2: HSE ~0.16-0.25 mA/V vs 1 mA/V max (ok).\n'
           'LSE ~0.58 uA/V: OVER the 0.56 uA/V low-power max (DS Table 38), under the 1.5 uA/V\n'
           'high-drive max -> FIRMWARE MUST select LSE high-drive mode before enabling the LSE.',
           20.32, 30.48)
    # HSE: PH0 (upper) -> crystal pin 1 (left), PH1 -> pin 3 (right); crystal below the pins.
    p0, p1 = pin(u, by_name['PH0'][0]), pin(u, by_name['PH1'][0])
    xc, yc = 219.71, 205.74
    s.part('Y101', 'Device:Crystal_GND24', '8MHz CL8pF', xc, yc,
           footprint='Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
           fields={'MPN': 'NX3225GD-8MHZ-STD-CRA-3'})
    a, b = (xc - 3.81, yc), (xc + 3.81, yc)
    path(s, [p0, (a[0], p0[1]), a])
    path(s, [p1, (b[0], p1[1]), b])
    s.net_at('HSE_IN', p0[0] - 6 * G, p0[1], -1, 0)
    s.net_at('HSE_OUT', p1[0] - 6 * G, p1[1], -1, 0)
    s.net_at('GND', xc, yc + 2 * G, 0, 1)
    for node, x_cap, ref in ((a, a[0] - 3 * G, 'C122'), (b, b[0] + 3 * G, 'C123')):
        s.wire(node[0], node[1], x_cap, node[1])
        s.junction(*node)
        p2, _ = two(s, ref, 'Device:C', '10pF', (x_cap, node[1]), (0, 1), footprint=C0402)
        s.net_at('GND', p2[0], p2[1], 0, 1)

    # LSE: PC14 (upper) -> pin 1 (nearer), PC15 -> pin 2 (farther); crystal above the pins.
    q0, q1 = pin(u, by_name['PC14'][0]), pin(u, by_name['PC15'][0])
    xl, yl = 374.65, 220.98
    s.part('Y102', 'Device:Crystal', '32.768kHz CL6pF', xl, yl,
           footprint='Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm',
           fields={'MPN': 'NX3215SA-32.768KHZ-EXS00A-MU00525'})
    a, b = (xl - 3.81, yl), (xl + 3.81, yl)
    path(s, [q0, (a[0], q0[1]), a])
    path(s, [q1, (b[0], q1[1]), b])
    s.net_at('LSE_IN', q0[0] + 4 * G, q0[1], 1, 0)
    s.net_at('LSE_OUT', q1[0] + 4 * G, q1[1], 1, 0)
    for node, x_cap, ref in ((a, a[0] - 3 * G, 'C124'), (b, b[0] + 3 * G, 'C125')):
        s.wire(node[0], node[1], x_cap, node[1])
        s.junction(*node)
        p2, _ = two(s, ref, 'Device:C', '6.2pF', (x_cap, node[1]), (0, 1), footprint=C0402)
        s.net_at('GND', p2[0], p2[1], 0, 1)


def right_side_resistors(s, u, by_name):
    """PB2 (BOOT1) 10k pull-down and PA9 (VBUS_SENSE) 1k from VBUS, wired out past the labels."""
    x, y = pin(u, by_name['PB2'][0])
    s.wire(x, y, 365.76, y)
    s.net_at('BOOT1', x + 4 * G, y, 1, 0)
    p2, _ = two(s, 'R102', 'Device:R', '10k', (365.76, y), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)

    x, y = pin(u, by_name['PA9'][0])
    s.wire(x, y, 365.76, y)
    s.net_at('VBUS_SENSE', x + 4 * G, y, 1, 0)
    p1, _ = two(s, 'R104', 'Device:R', '1k', (365.76, y), (0, -1), footprint=R0402,
                pin_a='2', pin_b='1')
    s.net_at('VBUS', p1[0], p1[1], 0, -1)


def status_led(s, u, by_name):
    """PG6 -> 1k -> green LED -> GND, wired out to the left."""
    x, y = pin(u, by_name['PG6'][0])
    x_led = 220.98
    s.wire(x, y, x_led, y)
    s.net_at('LED_STATUS', x - 6 * G, y, -1, 0)
    p2, _ = two(s, 'R103', 'Device:R', '1k', (x_led, y), (0, 1), footprint=R0402)
    s.wire(p2[0], p2[1], p2[0], p2[1] + G)
    s.net_at('LED1_A', p2[0], p2[1] + G, -1, 0)
    k, _ = two(s, 'D101', 'Device:LED', 'STATUS (green)', (p2[0], p2[1] + G), (0, 1),
               footprint='LED_SMD:LED_0603_1608Metric', pin_a='2', pin_b='1')
    s.net_at('GND', k[0], k[1], 0, 1)


def reset_boot(s):
    """NRST and BOOT0 sit between side-mounted power symbols on the MCU's left edge (no room for
    a wire out), so their circuits are wired blocks joined to the pins by label."""
    s.text('Reset: 100nF on NRST (internal pull-up). BOOT0 10k pull-down + BOOT button to 3V3:\n'
           'hold BOOT while resetting (or plugging USB) to enter the ROM USB DFU bootloader.\n'
           'PB2 = BOOT1 pulled low (R102, by the MCU) so BOOT0=1 selects system memory.',
           20.32, 116.84)
    top = (30.48, 134.62)
    s.wire(top[0], top[1] - G, top[0], top[1])
    s.net_at('NRST', top[0], top[1] - G, 0, -1)
    p2, _ = two(s, 'C126', 'Device:C', '100nF', top, (0, 1), footprint=C0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)

    node = (60.96, 134.62)
    s.wire(node[0], node[1] - G, node[0], node[1])
    s.net_at('BOOT0', node[0], node[1] - G, 0, -1)
    p2, _ = two(s, 'R101', 'Device:R', '10k', node, (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.wire(node[0], node[1], node[0] + 2 * G, node[1])
    s.junction(*node)
    p1, _ = two(s, 'SW101', 'Switch:SW_Push', 'BOOT', (node[0] + 2 * G, node[1]), (1, 0),
                footprint='Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2', pin_a='2', pin_b='1')
    s.wire(p1[0], p1[1], p1[0] + 2 * G, p1[1])
    s.net_at('3V3_AON', p1[0] + 2 * G, p1[1], 0, -1)

