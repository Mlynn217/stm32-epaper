"""Peripherals sheet: external Waveshare IT8951 HAT connector, CAP1188 cap-touch + side-wall
electrodes, PEC11R encoder, power button. Everything user-facing runs from 3V3_AON (the MCU rail)
so wake sources keep working with the peripheral rail gated (v2).
"""
from common import C0402, R0402, conn_by_name, new_sheet
from wiring import G, bank, by_name, path, pin, rail, two

LOCAL = {'HAT_SCK', 'HAT_MOSI', 'HAT_CS', 'ENC_A_RAW', 'ENC_B_RAW', 'CAP_ADDR', 'CAP_WAKE',
         'TOUCH_L1', 'TOUCH_L2', 'TOUCH_R1', 'TOUCH_R2'}


def hat(s):
    """J301: the eight header rows fan out to double pitch (a staircase of jogs, nearest row
    nearest the header) so the inline 33R series resistors and the HRDY pull-down have room."""
    s.text('External Waveshare 6" HD IT8951 HAT on a 1x8 2.54mm header (same signals the Disco\n'
           'wiring uses today). 33R series on the MCU-driven SPI lines (edge damping over the\n'
           'cable). The HAT gets +5V only while EPD_5V_EN is high: FIRMWARE MUST drive SCK/MOSI/\n'
           'CS/RST low (or float them) while the HAT is unpowered, or it back-powers the IT8951\n'
           'through its I/O clamp diodes.', 20.32, 30.48)
    j = s.part('J301', 'Connector_Generic:Conn_01x08', 'IT8951 HAT', 101.6, 88.9,
               footprint='Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
    s.text('J301: 1 +5V, 2 GND, 3 SCK, 4 MOSI, 5 MISO,\n6 CS, 7 RST, 8 HRDY (busy, active low)',
           114.3, 81.28)
    s.text('R316: HRDY would float while the HAT is unpowered;\n100k holds it low (reads "busy").\n'
           'No ESD on J301: it is an internal cable,\nnever user-accessible.', 114.3, 91.44)
    x_lab = 35.56
    x0, y0 = pin(j, '1')
    s.wire(x0, y0, x0 - 2 * G, y0)
    s.net_at('+5V', x0 - 2 * G, y0, 0, -1)
    # (row: MCU-side net, series resistor or None, header-side local net)
    rows = {3: ('SPI1_SCK', 'R301', 'HAT_SCK'), 4: ('SPI1_MOSI', 'R302', 'HAT_MOSI'),
            5: ('SPI1_MISO', None, None), 6: ('EPD_CS', 'R303', 'HAT_CS'),
            7: ('EPD_RST', None, None), 8: ('EPD_HRDY', None, None)}
    for n in range(2, 9):
        x, y = pin(j, str(n))
        xj = x0 - (11 - n) * G
        yf = y0 + (n - 1) * 2 * G
        if n == 2:
            path(s, [(x, y), (xj, y), (xj, yf)])
            s.net_at('GND', xj, yf, 0, 1)
            continue
        net, ref, local = rows[n]
        path(s, [(x, y), (xj, y), (xj, yf)])
        if ref:
            x_r = 45.72 if n == 4 else 58.42     # staggered: rows are too close for both
            path(s, [(xj, yf), (60.96, yf), (x_r, yf)])
            s.net_at(local, 60.96, yf, 1, 0)
            p2, _ = two(s, ref, 'Device:R', '33R', (x_r, yf), (-1, 0), footprint=R0402,
                        pin_a='2', pin_b='1')
            s.wire(p2[0], p2[1], x_lab, yf)
        elif n == 8:
            xr = 81.28
            path(s, [(xj, yf), (xr, yf), (x_lab, yf)])
            s.junction(xr, yf)
            p2, _ = two(s, 'R316', 'Device:R', '100k', (xr, yf), (0, 1), footprint=R0402)
            s.net_at('GND', p2[0], p2[1], 0, 1)
        else:
            s.wire(xj, yf, x_lab, yf)
        s.net_at(net, x_lab, yf, -1, 0)


def cap1188(s):
    s.text('CAP1188 cap-touch on I2C1. ADDR_COMM 150k -> SMBus address 0x29 (0101_001), same as\n'
           'the Adafruit breakout used for bring-up. SPI_CS# to GND (I2C mode), WAKE 100k\n'
           'pull-down, RESET (active high) 100k pull-down, ALERT# open-drain 10k pull-up, unused\n'
           'LED1-8 and unused CS inputs to GND (datasheet Table 1.1). Electrodes: left pair on\n'
           'CS3/CS4 (top side, away from VDD), right pair on CS5/CS6 (right side, towards J303) -\n'
           'chosen for layout: CS1-4 all on the top side fenced in the VDD pin. Two small electrode\n'
           'boards on short JST-SH cables (touch / GND / touch). Geometry: hardware/enclosure.',
           20.32, 132.08)
    u = s.part('U301', 'epaper:CAP1188', 'CAP1188-1-CP-TR', 101.6, 190.5,
               fields={'MPN': 'CAP1188-1-CP-TR'})
    un = by_name(u)
    left = ['VDD', 'SMDATA/SPI_MISO', 'SMCLK/SPI_CLK', 'ALERT#', 'RESET', 'WAKE/SPI_MOSI',
            'SPI_CS#', 'ADDR_COMM']
    right = ['CS%d' % i for i in range(1, 9)] + ['LED%d' % i for i in range(1, 9)]
    conn_by_name(s, u, {'GND': 'GND'}, strict=False)
    x_lab = 29.21

    # 3V3_AON rail above the chip: VDD comes up to it, the decoupling pair and the ALERT# pull-up
    # hang from it.
    x, y = pin(u, un['VDD'])
    y_r = 160.02
    x_v = x - G
    path(s, [(x, y), (x_v, y), (x_v, y_r)])
    x_al = 54.61
    p2, _ = two(s, 'R306', 'Device:R', '10k', (x_al, y_r), (0, 1), footprint=R0402)
    xa, ya = pin(u, un['ALERT#'])
    s.wire(p2[0], p2[1], x_al, ya)
    path(s, [(xa, ya), (x_al, ya), (x_lab, ya)])
    s.junction(x_al, ya)
    s.net_at('CAP_ALERT', x_lab, ya, -1, 0)
    bank(s, [('C301', '100nF', C0402, None), ('C302', '1uF', C0402, None)], 34.29, y_r,
         '3V3_AON', extra_top=[(x_al, y_r), (x_v, y_r)])
    for name, net in (('SMDATA/SPI_MISO', 'I2C1_SDA'), ('SMCLK/SPI_CLK', 'I2C1_SCL')):
        x, y = pin(u, un[name])
        s.wire(x, y, x_lab, y)
        s.net_at(net, x_lab, y, -1, 0)

    # Pull-downs (RESET, WAKE, ADDR_COMM) and SPI_CS# down onto a GND rail under the chip.
    y_top, y_g = 203.2, 210.82
    bottoms = []
    for name, ref, value, net, xc in (('RESET', 'R307', '100k', 'CAP_RESET', 62.23),
                                      ('WAKE/SPI_MOSI', 'R308', '100k', 'CAP_WAKE', 69.85),
                                      ('ADDR_COMM', 'R309', '150k 1%', 'CAP_ADDR', 80.01)):
        x, y = pin(u, un[name])
        path(s, [(x, y), (xc, y), (x_lab, y)])
        s.junction(xc, y)
        s.net_at(net, x_lab, y, -1, 0)
        if y != y_top:
            s.wire(xc, y, xc, y_top)
        two(s, ref, 'Device:R', value, (xc, y_top), (0, 1), footprint=R0402)
        bottoms.append((xc, y_g))
    x, y = pin(u, un['SPI_CS#'])
    xc = 74.93
    path(s, [(x, y), (xc, y), (xc, y_g)])
    bottoms.append((xc, y_g))
    rail(s, bottoms)
    s.net_at('GND', min(bottoms)[0], y_g, 0, 1)

    # Unused CS inputs and the LED outputs all onto one GND bus down the right-hand side; the
    # four electrode lines cross it on their way out.
    x_g = pin(u, un['CS1'])[0] + 2 * G
    taps = []
    for name in right:
        if name in ('CS3', 'CS4', 'CS5', 'CS6'):
            continue
        x, y = pin(u, un[name])
        s.wire(x, y, x_g, y)
        taps.append((x_g, y))
    y_end = taps[-1][1] + G
    taps.append((x_g, y_end))
    pts = sorted(taps, key=lambda p: p[1])
    for a, b in zip(pts, pts[1:]):
        s.wire(a[0], a[1], b[0], b[1])
    for p in pts[1:-1]:
        s.junction(*p)
    s.net_at('GND', x_g, y_end, 0, 1)

    # Electrode pairs: each line runs out to its JST-SH (drawn pins-down so the middle GND pin
    # drops clear between the two lines), with the pair's ESD part tapped on just before it.
    s.text('U302/U303: ESD on the electrode cables, one 2-channel part right at each\n'
           'connector (the boards sit behind 2.2 mm of PA12, but the back-cover seam is\n'
           '~0.2 mm from their edge). ~1.5 pF/line: negligible next to the pads.\n'
           'SC-70: 1 = IO1, 2 = IO2, 3 = GND.', 130.81, 200.66)
    for i, side in enumerate(['L', 'R']):
        n1, n2 = 'TOUCH_%s1' % side, 'TOUCH_%s2' % side
        (x1, y1), (x2, y2) = pin(u, un['CS%d' % (3 + 2 * i)]), pin(u, un['CS%d' % (4 + 2 * i)])
        dx = i * 45.72
        x_e, y_e = 139.7 + dx, y1 - 5 * G
        esd = s.part('U%d' % (302 + i), 'Power_Protection:TPD2E2U06DCK', 'TPD2E2U06DCKR',
                     x_e, y_e, fields={'MPN': 'TPD2E2U06DCKR'}, angle=90,
                     label_at=(-5.08, 0, 'right'))
        xc, yc = 160.02 + dx, y1 - 5 * G
        jt = s.part('J%d' % (302 + i), 'Connector_Generic:Conn_01x03', 'Electrodes ' + side,
                    xc, yc, footprint='Connector_JST:JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal',
                    fields={'MPN': 'SM03B-SRSS-TB'}, angle=90, label_at=(5.08, 0, 'left'))
        for (xp, yp), net, j_pin, e_pin in (((x1, y1), n1, '1', '1'), ((x2, y2), n2, '3', '2')):
            xj, yj = pin(jt, j_pin)
            xe, ye = pin(esd, e_pin)
            xl = xp + 3 * G
            path(s, [(xp, yp), (xl, yp), (xe, yp), (xj, yp), (xj, yj)])
            s.net_at(net, xl, yp, 1, 0)
            s.wire(xe, ye, xe, yp)
            s.junction(xe, yp)
        xg, yg = pin(jt, '2')
        s.wire(xg, yg, xg, yg + G)
        s.net_at('GND', xg, yg + G, 0, 1)
        xg, yg = pin(esd, '3')
        s.wire(xg, yg, xg + G, yg)
        s.net_at('GND', xg + G, yg, 0, 1)


def encoder(s):
    s.text('Bourns PEC11R-4220F-S0024 (24 detents, push switch, 20 mm shaft). Bourns suggested filter per\n'
           'channel: 10k pull-up, 10k series, 10nF to GND -> TIM3 encoder mode (PA6/PA7).\n'
           'Switch: 10k pull-up + 10nF, active low. Mounting lugs to GND (metal shaft ESD path).',
           218.44, 30.48)
    e = s.part('SW301', 'Device:RotaryEncoder_Switch_MP', 'PEC11R-4220F-S0024', 256.54, 83.82,
               footprint='epaper:RotaryEncoder_Bourns_Vertical_PEC11R-4xxxF-Sxxxx',
               fields={'MPN': 'PEC11R-4220F-S0024'})
    s.conns(e, {'S1': 'GND', 'MP': 'GND'})
    # Common (middle pin) to GND; A jogs up and B down out of the way, each through the Bourns
    # filter: pull-up on the raw line, 10k series, 10nF at the MCU side.
    x, y = pin(e, 'C')
    s.wire(x, y, x - 2 * G, y)
    s.net_at('GND', x - 2 * G, y, 0, 1)
    for p, jog, raw, (r_up, r_ser, c), out, up_dir in (
            ('A', -3 * G, 'ENC_A_RAW', ('R310', 'R311', 'C303'), 'ENC_A', -1),
            ('B', 3 * G, 'ENC_B_RAW', ('R312', 'R313', 'C304'), 'ENC_B', -1)):
        x, y = pin(e, p)
        yl = y + jog
        xs = x - G
        x_up, x_ser, x_c, x_lab = 228.6, 223.52, 208.28, 200.66
        path(s, [(x, y), (xs, y), (xs, yl), (xs - G, yl), (x_up, yl), (x_ser, yl)])
        s.net_at(raw, xs - G, yl, -1, 0)
        s.junction(x_up, yl)
        p1, _ = two(s, r_up, 'Device:R', '10k', (x_up, yl), (0, up_dir), footprint=R0402,
                    pin_a='2', pin_b='1')
        s.net_at('3V3_AON', p1[0], p1[1], 0, -1)
        p2, _ = two(s, r_ser, 'Device:R', '10k', (x_ser, yl), (-1, 0), footprint=R0402)
        path(s, [p2, (x_c, yl), (x_lab, yl)])
        s.junction(x_c, yl)
        pc, _ = two(s, c, 'Device:C', '10nF', (x_c, yl), (0, 1), footprint=C0402)
        s.net_at('GND', pc[0], pc[1], 0, 1)
        s.net_at(out, x_lab, yl, -1, 0)
    # Push switch: S2 out to the right with its pull-up and debounce cap.
    x, y = pin(e, 'S2')
    x_up, x_c, x_lab = 274.32, 281.94, 289.56
    path(s, [(x, y), (x_up, y), (x_c, y), (x_lab, y)])
    s.junction(x_up, y)
    s.junction(x_c, y)
    p1, _ = two(s, 'R314', 'Device:R', '10k', (x_up, y), (0, -1), footprint=R0402,
                pin_a='2', pin_b='1')
    s.net_at('3V3_AON', p1[0], p1[1], 0, -1)
    pc, _ = two(s, 'C305', 'Device:C', '10nF', (x_c, y), (0, 1), footprint=C0402)
    s.net_at('GND', pc[0], pc[1], 0, 1)
    s.net_at('ENC_SW', x_lab, y, 1, 0)


def power_button(s):
    s.text('Power / wake button to PA0 = WKUP (wakes STANDBY on a RISING edge), so the button\n'
           'pulls PWR_BTN up to 3V3_AON, with a 100k pull-down. Side-actuated, on the PCB\'s\n'
           'bottom edge (the enclosure\'s bottom wall has a flexure tab over it).', 218.44, 152.4)
    b = s.part('SW302', 'Switch:SW_Push', 'POWER', 256.54, 180.34,
               footprint='Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010',
               fields={'MPN': 'SKRTLAE010'})
    x, y = pin(b, '1')
    s.wire(x, y, x - 2 * G, y)
    s.net_at('3V3_AON', x - 2 * G, y, 0, -1)
    x, y = pin(b, '2')
    x_r, x_lab = x + 2 * G, x + 5 * G
    path(s, [(x, y), (x_r, y), (x_lab, y)])
    s.junction(x_r, y)
    p2, _ = two(s, 'R315', 'Device:R', '100k', (x_r, y), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('PWR_BTN', x_lab, y, 1, 0)


def build():
    s = new_sheet('Peripherals', lambda n: None if n in LOCAL else 'bidirectional')
    s.text('PERIPHERALS — HAT connector, cap-touch, encoder, power button.', 20.32, 12.7, size=2)
    hat(s)
    cap1188(s)
    # (I2C1 pull-ups R105/R106 are drawn on the MCU sheet, wired to PB8/PB9.)
    encoder(s)
    power_button(s)

    # ---- Mounting ----------------------------------------------------------------------------
    s.text('Mounting holes: M2 thread-forming screws into standoffs on the back cover. Positions\n'
           'come from hardware/enclosure (out/pcb_placement.json).', 218.44, 215.9)
    for i in range(4):
        s.part('H%d' % (301 + i), 'Mechanical:MountingHole', 'M2', 228.6 + i * 12.7, 231.14,
               footprint='MountingHole:MountingHole_2.2mm_M2', in_bom=False)
    return s
