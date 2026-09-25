"""Power sheet: USB-C input, LiPo charger with power path, 3V3/5V converters, RTC backup, reserved
low-power islands. See README "Power Sheet (drafted in KiCad)" for the design decisions."""
from common import C0402, C0603, C0805, R0402, R0603, flag, new_sheet
from wiring import G, bank, path, pin, rail, two

# Signals that leave this sheet for the (future) MCU sheet.
GLOBAL = {'USB_DP': 'bidirectional', 'USB_DM': 'bidirectional', 'CHG_STAT': 'output',
          '3V3_PG': 'output', 'EPD_5V_EN': 'input', 'VBAT_RTC': 'output', 'PERIPH_EN': 'input',
          'VBAT_SENSE': 'output', 'CHG_DIS': 'input', 'TS_SENSE': 'output'}


ABOVE = (0, -3.81, None)   # label_at: both fields stacked above a horizontal two-pin part
BELOW = (0, 3.81, None)


def pwr_flag(s, x, y):
    """PWR_FLAG sitting directly on a wire point (the caller puts a wire end/junction there)."""
    s.pwr_n += 1
    s.part('#FLG%s%02d' % (s.prefix, s.pwr_n), 'power:PWR_FLAG', 'PWR_FLAG', x, y)


def usb(s, y_vbus):
    """USB-C receptacle: CC pull-downs inline, D+/D- pairs joined and run to the MCU labels with
    the USBLC6 tapped on. Returns the points on the VBUS rail."""
    s.text('USB-C receptacle, UFP/sink only: 5.1k Rd on each CC.\nD+/D- to MCU USB OTG_FS '
           '(PA11/PA12) for DFU/CDC.\nSHIELD straight to GND: plastic case, no earth, so no ground loop for an\nRC to break, and it is the shortest ESD return (U5 returns to GND there too).',
           20.32, 30.48)
    j1 = s.part('J1', 'Connector:USB_C_Receptacle_USB2.0_16P', 'USB_C_Receptacle_USB2.0_16P',
                40.64, 76.2,
                footprint='Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal',
                fields={'MPN': 'GCT USB4105-GF-A'})
    s.conns(j1, {'A8': None, 'B8': None, 'A1': 'GND', 'SH': 'GND'})
    # VBUS up onto the rail.
    x, y = pin(j1, 'A4')
    path(s, [(x, y), (x + G, y), (x + G, y_vbus)])
    pts = [(x + G, y_vbus)]
    s.net_at('VBUS', x + G, y_vbus, 0, -1)
    # CC1 / CC2: 5.1k to a shared GND drop (resistors staggered so their text clears).
    x1, y1 = pin(j1, 'A5')
    x2, y2 = pin(j1, 'B5')
    x_g = 83.82
    s.wire(x1, y1, 63.5, y1)
    s.net_at('CC1', 63.5, y1, -1, 0)
    p2, _ = two(s, 'R1', 'Device:R', '5.1k', (63.5, y1), (1, 0), footprint=R0402, label_at=ABOVE)
    path(s, [p2, (x_g, y1), (x_g, y2)])
    s.wire(x2, y2, 73.66, y2)
    s.net_at('CC2', 73.66, y2, -1, 0)
    p2, _ = two(s, 'R2', 'Device:R', '5.1k', (73.66, y2), (1, 0), footprint=R0402, label_at=BELOW)
    s.wire(p2[0], p2[1], x_g, y2)
    s.junction(x_g, y2)
    s.net_at('GND', x_g, y2, 0, 1)
    # D+/D-: each pair's two pins joined, straight on to the MCU labels; the USBLC6 sits below
    # the pair with all four I/O pins tapped up onto it (I/O1 = D+, I/O2 = D-, both sides).
    u5 = s.part('U5', 'Power_Protection:USBLC6-2SC6', 'USBLC6-2SC6', 101.6, 93.98,
                label_at=(5.08, 7.62, 'left'))
    xj = x + G
    x_lab = 114.3
    for a, b, net in (('A7', 'B7', 'USB_DM'), ('B6', 'A6', 'USB_DP')):
        (xa, ya), (xb, yb) = pin(j1, a), pin(j1, b)
        path(s, [(xa, ya), (xj, ya), (xj, yb)])
        s.junction(xj, yb)
        taps = {'USB_DP': (93.98, 109.22), 'USB_DM': (91.44, 111.76)}[net]
        path(s, [(xb, yb), (xj, yb)] + [(t, yb) for t in taps] + [(x_lab, yb)])
        s.net_at(net, x_lab, yb, 1, 0)
        for num, xt in zip(('1', '6') if net == 'USB_DP' else ('3', '4'), taps):
            xp, yp = pin(u5, num)
            path(s, [(xp, yp), (xt, yp), (xt, yb)])
            s.junction(xt, yb)
    s.conn(u5, '2', 'GND')
    xv, yv = pin(u5, '5')
    s.net_at('VBUS', xv, yv, 0, -1)
    pts.append((78.74, y_vbus))
    pwr_flag(s, 78.74, y_vbus)
    return pts


def charger(s, y_vbus):
    """BQ24073: pin straps hang on a GND rail to the left, EN1's pull-up goes to the VBUS rail;
    OUT/BAT/TS/CHG wired out to the right. Returns its points on the VBUS rail."""
    s.text('BQ24073 1-cell Li-ion/LiPo charger with power path (TI SLUS810N): 4.2V CV, OUT =\n'
           'VSYS regulated to 4.4V with USB present (keeps the 5.5V-max converters safe), battery\n'
           'supplement when the load exceeds the input limit, 6.6V input OVP.\n'
           'ISET 3.01k -> 890/3.01k = ~296mA (265-324mA worst case): <= 0.3C of the 1100mAh cell,\n'
           'which is EEMB\'s limit for charging at 0-20C (either candidate cell is in spec anywhere).\n'
           'EN2=0/EN1=1 -> USB500 input limit (USB-C default power, no CC advertisement read).\n'
           'ILIM 1.54k (1.0A) must be fitted anyway: an open ILIM disables charging.\n'
           'TS: on-board 10k NTC against the cell; charger blocks charging outside ~0-50C. The\n'
           'cells allow only 0-45C and no NTC can narrow the window (TI eq. 8 needs a cold/hot\n'
           'resistance ratio of 7), so firmware reads TS_SENSE and drives CHG_DIS (CE, 100k\n'
           'pull-down = charging on while the MCU is off) to suspend charging at 43-50C.\n'
           'TMR 72k: fast-charge timer 7.2-12h (default 4-6h would expire on the 1800mAh cell).\n'
           'TD low (termination on). CHG: LED from VBUS + CHG_STAT to an FT GPIO.',
           137.16, 116.84)
    u1 = s.part('U1', 'Battery_Management:BQ24073RGT', 'BQ24073RGT', 203.2, 83.82,
                fields={'MPN': 'BQ24073RGTR'})
    s.conn(u1, '8', 'GND')
    s.no_connect(u1, '7')
    x_lab = 180.34          # local labels on the strap lines, just outside the pins
    y_t, y_g = 99.06, 106.68
    rail_pts = []
    # (pin, column, resistor/None, value, local label or None)
    straps = [('15', 144.78, None, None, None),                 # TD -> GND
              ('4', 149.86, 'R24', '100k', None),               # /CE = CHG_DIS, 100k down
              ('14', 154.94, 'R23', '72k 1%', 'TMR'),
              ('5', 165.1, None, None, None),                   # EN2 -> GND
              ('12', 170.18, 'R19', '1.54k 1%', 'ILIM'),
              ('16', 175.26, 'R3', '3.01k 1%', 'ISET')]
    for num, xc, ref, value, label in straps:
        x, y = pin(u1, num)
        pts = [(x, y)]
        if label:
            pts.append((x_lab, y))
        pts.append((xc, y))
        if num == '4':
            pts.append((xc - 3 * G, y))
            s.net_at('CHG_DIS', xc - 3 * G, y, -1, 0)
            s.junction(xc, y)
        path(s, pts)
        if label:
            s.net_at(label, x_lab, y, 1, 0)
        if ref:
            s.wire(xc, y, xc, y_t)
            two(s, ref, 'Device:R', value, (xc, y_t), (0, 1), footprint=R0402)
        else:
            s.wire(xc, y, xc, y_g)
        rail_pts.append((xc, y_g))
    rail(s, rail_pts)
    s.net_at('GND', rail_pts[0][0], y_g, 0, 1)
    # EN1: 100k up to VBUS.
    x, y = pin(u1, '6')
    xc = 160.02
    path(s, [(x, y), (x_lab, y), (xc, y)])
    s.net_at('CHG_EN1', x_lab, y, 1, 0)
    p2, _ = two(s, 'R20', 'Device:R', '100k', (xc, y_vbus), (0, 1), footprint=R0402)
    s.wire(p2[0], p2[1], xc, y)
    vbus_pts = [(xc, y_vbus)]
    # IN up to the rail, input cap beside it.
    x, y = pin(u1, '13')
    s.wire(x, y, x, y_vbus)
    vbus_pts.append((x, y_vbus))
    two(s, 'C1', 'Device:C', '4.7uF', (x + 3 * G, y_vbus), (0, 1), footprint=C0603,
        fields={'Voltage': '10V'})
    s.net_at('GND', x + 3 * G, y_vbus + 3 * G, 0, 1)
    vbus_pts.append((x + 3 * G, y_vbus))

    # OUT -> VSYS (up, with C15 on it).
    x, y = pin(u1, '10')
    xv, yv = x + 2 * G, y - 4 * G
    path(s, [(x, y), (xv, y), (xv, yv), (xv + 3 * G, yv)])
    s.net_at('VSYS', xv, yv, 0, -1)
    two(s, 'C15', 'Device:C', '10uF', (xv + 3 * G, yv), (0, 1), footprint=C0603,
        fields={'Voltage': '10V'})
    s.net_at('GND', xv + 3 * G, yv + 3 * G, 0, 1)
    # TS: NTC to GND, then 10k + 100nF filter out to TS_SENSE.
    x, y = pin(u1, '1')
    x_nt, x_r, x_c = x + 4 * G, x + 6 * G, x + 10 * G
    path(s, [(x, y), (x + G, y), (x_nt, y), (x_r, y)])
    s.net_at('TS', x + G, y, 1, 0)
    s.junction(x_nt, y)
    p2, _ = two(s, 'RT1', 'Device:Thermistor_NTC', '10k NTC', (x_nt, y), (0, 1),
                footprint='Connector_Wire:SolderWire-0.1sqmm_1x02_P3.6mm_D0.4mm_OD1mm',
                fields={'MPN': 'NXFT15XH103FA2B (Murata leaded film NTC: same 10k/B=3380 curve '
                               'as NCP15XH103; TS thresholds assume 103AT, B=3435) - leads '
                               'soldered here, head taped to the cell (it sits beside the PCB)'})
    s.net_at('GND', p2[0], p2[1], 0, 1)
    p2, _ = two(s, 'R25', 'Device:R', '10k', (x_r, y), (1, 0), footprint=R0402)
    path(s, [p2, (x_c, y), (x_c + 2 * G, y)])
    s.junction(x_c, y)
    p2, _ = two(s, 'C18', 'Device:C', '100nF', (x_c, y), (0, 1), footprint=C0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('TS_SENSE', x_c + 2 * G, y, 1, 0)
    # BAT -> +BATT (right, past the TS filter), C2 on it.
    x, y = pin(u1, '2')
    x_c2 = x + 20 * G
    path(s, [(x, y), (x_c2, y), (x_c2 + 2 * G, y)])
    s.junction(x_c2, y)
    p2, _ = two(s, 'C2', 'Device:C', '10uF', (x_c2, y), (0, 1), footprint=C0603,
                fields={'Voltage': '10V'})
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('+BATT', x_c2 + 2 * G, y, 0, -1)
    # /CHG: down under the TS parts, then LED + 1k up to VBUS; CHG_STAT label off the corner.
    x, y = pin(u1, '9')
    xk, yk = x + G, y + 4 * G
    path(s, [(x, y), (xk, y), (xk, yk), (xk + 2 * G, yk)])
    path(s, [(xk, yk), (xk, yk + 3 * G), (xk + 2 * G, yk + 3 * G)])
    s.junction(xk, yk)
    s.net_at('CHG_STAT', xk + 2 * G, yk + 3 * G, 1, 0)
    pa, _ = two(s, 'D2', 'Device:LED', 'CHG (red)', (xk + 2 * G, yk), (1, 0),
                footprint='LED_SMD:LED_0603_1608Metric')
    x_r4 = pa[0] + 5 * G
    path(s, [pa, (pa[0] + G, yk), (x_r4, yk)])
    s.net_at('CHG_LED', pa[0] + G, yk, 1, 0)
    p1, _ = two(s, 'R4', 'Device:R', '1k', (x_r4, yk), (1, 0), footprint=R0402,
                pin_a='2', pin_b='1')
    s.wire(p1[0], p1[1], p1[0] + G, p1[1])
    s.net_at('VBUS', p1[0] + G, p1[1], 0, -1)
    return vbus_pts


def rtc(s):
    s.text('RTC backup: cell -> MCP1700 3.0V LDO (1.6uA Iq) -> STM32 VBAT.\n'
           'A full LiPo (4.2V) minus a Schottky drop would still exceed VBAT\'s 3.6V max.\n'
           'Below ~3.2V the LDO drops out and VBAT tracks the cell (VBAT min 1.65V).',
           304.8, 30.48)
    u7 = s.part('U7', 'Regulator_Linear:MCP1700x-300xxTT', 'MCP1700T-3002E/TT', 330.2, 68.58,
                fields={'MPN': 'MCP1700T-3002E/TT'})
    s.conn(u7, '1', 'GND')
    x, y = pin(u7, '3')
    path(s, [(x, y), (x - 2 * G, y), (x - 4 * G, y)])
    s.junction(x - 2 * G, y)
    p2, _ = two(s, 'C16', 'Device:C', '1uF', (x - 2 * G, y), (0, 1), footprint=C0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('+BATT', x - 4 * G, y, 0, -1)
    x, y = pin(u7, '2')
    path(s, [(x, y), (x + 2 * G, y), (x + 5 * G, y)])
    s.junction(x + 2 * G, y)
    p2, _ = two(s, 'C3', 'Device:C', '1uF', (x + 2 * G, y), (0, 1), footprint=C0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('VBAT_RTC', x + 5 * G, y, 1, 0)


def aon(s):
    s.text('RESERVED (DNP) for low-power v2: TPS63900 always-on\n'
           '3V3_AON (75nA Iq) for MCU + CAP1188. Replaces MAX17222,\n'
           'which is boost-only and cannot regulate a 3.65V cell down.\n'
           'VO(1) = 3.3V via CFG3 = 16.2k (SEL low); CFG1/CFG2 = 0R\n'
           '-> no input current limit. v1: R18 0R feeds 3V3_AON from\n'
           '+3V3. v2 TODO: EN needs its own UVLO (logic-level EN).',
           398.78, 30.48)
    u6 = s.part('U6', 'epaper:TPS63900', 'TPS63900DSK', 431.8, 76.2, dnp=True,
                fields={'MPN': 'TPS63900DSKR'})
    s.conns(u6, {'8': 'GND', '11': 'GND'})
    # VIN up to a VSYS rail with C6 and the EN pull-up hanging from it.
    x, y = pin(u6, '10')
    y_r = y - 4 * G
    xv = x - G
    path(s, [(x, y), (xv, y), (xv, y_r)])
    x_en, x_c6 = xv - 2 * G, xv - 6 * G
    p2, _ = two(s, 'R17', 'Device:R', '100k', (x_en, y_r), (0, 1), footprint=R0402, dnp=True)
    xe, ye = pin(u6, '1')
    s.wire(p2[0], p2[1], x_en, ye)
    path(s, [(xe, ye), (x_en, ye), (x_en - G, ye)])
    s.junction(x_en, ye)
    s.net_at('AON_EN', x_en - G, ye, -1, 0)
    p2, _ = two(s, 'C6', 'Device:C', '10uF', (x_c6, y_r), (0, 1), footprint=C0603, dnp=True)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    rail(s, [(x_c6 - 2 * G, y_r), (x_c6, y_r), (x_en, y_r), (xv, y_r)])
    s.net_at('VSYS', x_c6 - 2 * G, y_r, 0, -1)
    xs, ys = pin(u6, '2')
    s.wire(xs, ys, xs - 2 * G, ys)
    s.net_at('GND', xs - 2 * G, ys, 0, 1)
    # L3 bridged over the top between LX1 and LX2.
    (x1, y1), (x2, y2) = pin(u6, '9'), pin(u6, '7')
    yl = y1 - 4 * G
    s.wire(x1, y1, x1, yl)
    p2, _ = two(s, 'L3', 'Device:L', '2.2uH', (x1, yl), (1, 0),
                footprint='Inductor_SMD:L_Murata_DFE201610P', dnp=True, label_at=ABOVE,
                fields={'MPN': 'DFE201612E-2R2M=P2 (TPS63900 datasheet Table 8-2; Isat 2.4A)'})
    path(s, [(x2, y2), (x2, y2 - 2 * G), (p2[0], y2 - 2 * G), p2])
    s.net_at('AON_LX1', x1, yl, -1, 0)
    s.net_at('AON_LX2', p2[0], y2 - 2 * G, 1, 0)
    # VOUT up to the 3V3_AON rail: C7, then R18 (0R, fitted on v1) from +3V3.
    x, y = pin(u6, '6')
    xo, yo = x + 4 * G, y - 4 * G
    path(s, [(x, y), (xo, y), (xo, yo), (xo + 3 * G, yo), (xo + 5 * G, yo)])
    s.junction(xo + 3 * G, yo)
    s.net_at('3V3_AON', xo, yo, 0, -1)
    p2, _ = two(s, 'C7', 'Device:C', '22uF', (xo + 3 * G, yo), (0, 1), footprint=C0603, dnp=True)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    p1, _ = two(s, 'R18', 'Device:R', '0R', (xo + 5 * G, yo), (1, 0), footprint=R0603,
                pin_a='2', pin_b='1')
    s.wire(p1[0], p1[1], p1[0] + G, p1[1])
    s.net_at('+3V3', p1[0] + G, p1[1], 0, -1)
    # CFG1/CFG2 tied to GND; CFG3 down through R16.
    (xa, ya), (xb, yb) = pin(u6, '3'), pin(u6, '4')
    xg = xa + 2 * G
    path(s, [(xa, ya), (xg, ya), (xg, yb)])
    s.wire(xb, yb, xg, yb)
    s.net_at('GND', xg, yb, 0, 1)
    x, y = pin(u6, '5')
    path(s, [(x, y), (x + G, y), (x + G, y + 4 * G)])
    s.net_at('AON_CFG3', x + G, y + 4 * G, -1, 0)
    p2, _ = two(s, 'R16', 'Device:R', '16.2k 1%', (x + G, y + 4 * G), (0, 1), footprint=R0402,
                dnp=True)
    s.net_at('GND', p2[0], p2[1], 0, 1)


def battery(s):
    s.text('Battery: 1-cell LiPo pouch (3.7V nominal, 4.2V full) WITH a protection board,\n'
           'JST-PH 2.0 lead. J2 pin 1 = + (Adafruit/SparkFun cells: check polarity before\n'
           'plugging in - it is not standardised across vendors). Power path is inside U1,\n'
           'so no discrete load-sharing parts are needed.',
           20.32, 154.94)
    j2 = s.part('J2', 'Connector_Generic:Conn_01x02', 'BATT (1S LiPo)', 101.6, 195.58,
                footprint='Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal')
    s.text('Cell voltage sense for firmware (fuel estimate + graceful shutdown at ~3.4V):\n'
           '1M/1M divider -> VBAT_SENSE (4.2V -> 2.1V) to PA3 / ADC1_IN3, 100nF for the ADC\n'
           'sample. ~2uA continuous. (VBAT_RTC can no longer be used: it sits behind the 3.0V LDO.)',
           20.32, 226.06)
    x, y = pin(j2, '1')
    x_r = 81.28
    path(s, [(x, y), (x_r, y), (66.04, y)])
    s.junction(x_r, y)
    s.net_at('+BATT', 66.04, y, 0, -1)
    p2, _ = two(s, 'R21', 'Device:R', '1M 1%', (x_r, y), (0, 1), footprint=R0402)
    yn = p2[1] + G
    s.wire(p2[0], p2[1], x_r, yn)
    path(s, [(73.66, yn), (x_r, yn), (88.9, yn)])
    s.junction(x_r, yn)
    s.net_at('VBAT_SENSE', 73.66, yn, -1, 0)
    p2, _ = two(s, 'R22', 'Device:R', '1M 1%', (x_r, yn), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    p2, _ = two(s, 'C17', 'Device:C', '100nF', (88.9, yn), (0, 1), footprint=C0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    x, y = pin(j2, '2')
    s.wire(x, y, x - 2 * G, y)
    s.net_at('GND', x - 2 * G, y, 0, 1)
    flag(s, 'GND', 106.68, 208.28)


def buck_boost(s):
    s.text('TPS63802 buck-boost -> +3V3 (VOUT = 0.5V*(1+R7/R8) = 3.308V, datasheet Fig. 10-1).\n'
           'MODE low = power-save (PFM). Starts from VIN > 1.8V, 11uA Iq.\n'
           'UNDERVOLTAGE CUTOFF: EN has a precise threshold (1.10V rising / 1.00V falling), so\n'
           'R6/R15 (2.2M/1M) from VSYS turn the rail OFF below ~3.20V and back ON above\n'
           '~3.52V (+-3%), ~1.1uA. Backstop only: firmware shuts down gracefully first (~3.4V,\n'
           'measured via an ADC). The charger does NOT stop over-discharge; the cell\n'
           'protection board is the last line. Footprint: project lib (TI DLA0010A).',
           137.16, 154.94)
    u2 = s.part('U2', 'epaper:TPS63802', 'TPS63802DLA', 177.8, 200.66,
                fields={'MPN': 'TPS63802DLAR'})
    s.conns(u2, {'3': 'GND', '8': 'GND'})
    # VIN up to the VSYS rail: input caps + the UVLO divider R6/R15 on EN.
    x, y = pin(u2, '10')
    xv, y_r = x - G, y - 5 * G
    path(s, [(x, y), (xv, y), (xv, y_r)])
    x_d = xv - 3 * G
    p2, _ = two(s, 'R6', 'Device:R', '2.2M 1%', (x_d, y_r), (0, 1), footprint=R0402)
    xe, ye = pin(u2, '1')
    s.wire(p2[0], p2[1], x_d, ye)
    path(s, [(xe, ye), (x_d + G, ye), (x_d, ye)])
    s.junction(x_d, ye)
    s.net_at('BB_EN', x_d + G, ye, 1, 0)
    p2, _ = two(s, 'R15', 'Device:R', '1M 1%', (x_d, ye), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    bank(s, [('C4', '10uF', C0603, {'Voltage': '10V'}), ('C5', '10uF', C0603, {'Voltage': '10V'})],
         x_d - 8 * G, y_r, 'VSYS', extra_top=[(x_d, y_r), (xv, y_r)])
    xm, ym = pin(u2, '2')
    s.wire(xm, ym, xm - G, ym)
    s.net_at('GND', xm - G, ym, 0, 1)
    # L1 bridged over the top between L1/L2.
    (x1, y1), (x2, y2) = pin(u2, '9'), pin(u2, '7')
    yl = y1 - 4 * G
    s.wire(x1, y1, x1, yl)
    p2, _ = two(s, 'L1', 'Device:L', '0.47uH', (x1, yl), (1, 0),
                footprint='Inductor_SMD:L_Murata_DFE201610P', label_at=ABOVE,
                fields={'MPN': 'DFE201612E-R47M=P2 (Isat 5.5A, 26mR; Murata land = this footprint)'})
    path(s, [(x2, y2), (x2, y2 - 2 * G), (p2[0], y2 - 2 * G), p2])
    s.net_at('BB_L1', x1, yl, -1, 0)
    s.net_at('BB_L2', p2[0], y2 - 2 * G, 1, 0)
    # VOUT up to the +3V3 rail: feedback divider and output caps.
    x, y = pin(u2, '6')
    xo, yo = x + 3 * G, y - 3 * G
    x_fb = xo + 2 * G
    path(s, [(x, y), (xo, y), (xo, yo)])
    s.net_at('+3V3', xo, yo, 0, -1)
    p2, _ = two(s, 'R7', 'Device:R', '511k 1%', (x_fb, yo), (0, 1), footprint=R0402)
    xf, yf = pin(u2, '4')
    s.wire(p2[0], p2[1], x_fb, yf)
    path(s, [(xf, yf), (xf + G, yf), (x_fb, yf)])
    s.junction(x_fb, yf)
    s.net_at('BB_FB', xf + G, yf, 1, 0)
    p2, _ = two(s, 'R8', 'Device:R', '91k 1%', (x_fb, yf), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    caps = []
    for i, ref in enumerate(('C8', 'C9')):
        xc = x_fb + (4 + 4 * i) * G
        two(s, ref, 'Device:C', '22uF', (xc, yo), (0, 1), footprint=C0603)
        caps.append((xc, yo + 3 * G))
    rail(s, [(xo, yo), (x_fb, yo)] + [(c[0], yo) for c in caps])
    rail(s, caps)
    s.net_at('GND', caps[0][0], caps[0][1], 0, 1)
    # PG: down past the divider, 100k pull-up to +3V3, out to 3V3_PG.
    x, y = pin(u2, '5')
    xp, yp = x + 2 * G, y + 4 * G
    x_pu = x_fb + 3 * G
    path(s, [(x, y), (xp, y), (xp, yp), (x_pu, yp), (x_pu + 3 * G, yp)])
    s.junction(x_pu, yp)
    p1, _ = two(s, 'R9', 'Device:R', '100k', (x_pu, yp), (0, -1), footprint=R0402,
                pin_a='2', pin_b='1')
    s.net_at('+3V3', p1[0], p1[1], 0, -1)
    s.net_at('3V3_PG', x_pu + 3 * G, yp, 1, 0)


def boost(s):
    s.text('TPS61023 boost -> +5V for the EXTERNAL Waveshare IT8951 HAT (v1 board: HAT on an\n'
           'SPI connector - connector lives on the peripheral sheet). VOUT = 0.6V*(1+R10/R11)\n'
           '= 4.99V. True disconnect in shutdown; R12 holds it OFF until the MCU drives EPD_5V_EN.',
           274.32, 154.94)
    u3 = s.part('U3', 'epaper:TPS61023', 'TPS61023DRL', 304.8, 200.66,
                fields={'MPN': 'TPS61023DRLR'})
    s.conn(u3, '4', 'GND')
    # VSYS rail: C11, VIN, then L2 in series to SW.
    x, y = pin(u3, '3')
    xv, y_r = x - G, y - 4 * G
    path(s, [(x, y), (xv, y), (xv, y_r)])
    x_c = xv - 2 * G
    two(s, 'C11', 'Device:C', '10uF', (x_c, y_r), (0, 1), footprint=C0603)
    s.net_at('GND', x_c, y_r + 3 * G, 0, 1)
    rail(s, [(x_c - 2 * G, y_r), (x_c, y_r), (xv, y_r), (xv + 2 * G, y_r)])
    s.net_at('VSYS', x_c - 2 * G, y_r, 0, -1)
    p2, _ = two(s, 'L2', 'Device:L', '1uH', (xv + 2 * G, y_r), (1, 0),
                footprint='Inductor_SMD:L_Murata_DFE201610P', label_at=ABOVE,
                fields={'MPN': 'DFE201612E-1R0M=P2 (Isat 4.0A >= TPS61023 3.7A valley limit, 48mR)'})
    xs, ys = pin(u3, '5')
    path(s, [p2, (xs, y_r), (xs, ys)])
    s.net_at('BST_SW', xs, y_r, 1, 0)
    # EN: 1M pull-down, EPD_5V_EN from the MCU.
    x, y = pin(u3, '2')
    xr = x - 3 * G
    path(s, [(x, y), (xr, y), (xr - 3 * G, y)])
    s.junction(xr, y)
    p2, _ = two(s, 'R12', 'Device:R', '1M', (xr, y), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('EPD_5V_EN', xr - 3 * G, y, -1, 0)
    # VOUT up to the +5V rail: feedback divider + output caps.
    x, y = pin(u3, '6')
    xo, yo = x + 2 * G, y - 3 * G
    x_fb = xo + 4 * G
    path(s, [(x, y), (xo, y), (xo, yo)])
    s.net_at('+5V', xo, yo, 0, -1)
    p2, _ = two(s, 'R10', 'Device:R', '732k 1%', (x_fb, yo), (0, 1), footprint=R0402)
    xf, yf = pin(u3, '1')
    s.wire(p2[0], p2[1], x_fb, yf)
    path(s, [(xf, yf), (xo, yf), (x_fb, yf)])
    s.junction(x_fb, yf)
    s.net_at('BST_FB', xo, yf, 1, 0)
    p2, _ = two(s, 'R11', 'Device:R', '100k 1%', (x_fb, yf), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    caps = []
    for i, ref in enumerate(('C12', 'C13')):
        xc = x_fb + (4 + 4 * i) * G
        two(s, ref, 'Device:C', '22uF', (xc, yo), (0, 1), footprint=C0805)
        caps.append((xc, yo + 3 * G))
    rail(s, [(xo, yo), (x_fb, yo)] + [(c[0], yo) for c in caps])
    rail(s, caps)
    s.net_at('GND', caps[0][0], caps[0][1], 0, 1)


def load_switch(s):
    s.text('TPS22965 load switch gating 3V3_PERIPH (SDRAM, QSPI, microSD) - FITTED on v1: without\n'
           'it those parts stay powered in STANDBY (~2-20mA idle floor). ON = PERIPH_EN (PD7) with a\n'
           '100k pull-down, so the rail is OFF at reset and in STANDBY (GPIO hi-Z) automatically.\n'
           'CT 1nF (25V, per datasheet) -> ~1.3ms rise at 3.3V -> ~50mA inrush into ~21uF of load\n'
           'decoupling (no dip on +3V3). QOD: 225R discharges the rail when off. R13 = 0R bypass\n'
           '(DNP fallback), drawn across the switch. FIRMWARE: raise PERIPH_EN before FMC/QSPI/SDIO\n'
           'init; before dropping it, set those pins to analog/low so the MCU does not back-power\n'
           'the unpowered parts.', 137.16, 241.3)
    u4 = s.part('U4', 'epaper:TPS22965', 'TPS22965DSG', 177.8, 289.56,
                fields={'MPN': 'TPS22965DSGR'})
    s.conns(u4, {'5': 'GND', '9': 'GND'})
    (xi, yi), (xb, yb) = pin(u4, '1'), pin(u4, '4')
    xv, yt = xi - G, yi - 5 * G
    path(s, [(xb, yb), (xv, yb), (xv, yi), (xv, yt)])
    s.wire(xi, yi, xv, yi)
    s.junction(xv, yi)
    s.net_at('+3V3', xv, yt, 0, -1)
    xo, yo = pin(u4, '7')
    xj = xo + 2 * G
    s.wire(xv, yt, xv + 2 * G, yt)
    p2, _ = two(s, 'R13', 'Device:R', '0R', (xv + 2 * G, yt), (1, 0), footprint=R0603, dnp=True,
                label_at=ABOVE)
    path(s, [p2, (xj, yt), (xj, yo)])
    path(s, [(xo, yo), (xj, yo), (xj + 2 * G, yo)])
    s.junction(xj, yo)
    s.net_at('3V3_PERIPH', xj + 2 * G, yo, 0, -1)
    x, y = pin(u4, '3')
    xr = x - 3 * G
    path(s, [(x, y), (xr, y), (xr - 2 * G, y)])
    s.junction(xr, y)
    p2, _ = two(s, 'R14', 'Device:R', '100k', (xr, y), (0, 1), footprint=R0402)
    s.net_at('GND', p2[0], p2[1], 0, 1)
    s.net_at('PERIPH_EN', xr - 2 * G, y, -1, 0)
    x, y = pin(u4, '6')
    xc = x + 4 * G
    path(s, [(x, y), (x + G, y), (xc, y)])
    s.net_at('LS_CT', x + G, y, 1, 0)
    p2, _ = two(s, 'C14', 'Device:C', '1nF', (xc, y), (0, 1), footprint=C0402,
                fields={'Voltage': '25V X7R (CT pin can reach 12V)'})
    s.net_at('GND', p2[0], p2[1], 0, 1)


def build():
    s = new_sheet('Power', GLOBAL, paper='A2')
    s.text('POWER — USB-C in, LiPo charger + power path, 3V3 buck-boost, 5V boost, RTC backup,\n'
           'peripheral load switch, reserved always-on rail. Generated by hardware/scripts/'
           'gen_schematic.py (sheet_power.py).', 20.32, 12.7, size=2)
    y_vbus = 53.34
    pts = usb(s, y_vbus) + charger(s, y_vbus)
    rail(s, pts)
    rtc(s)
    aon(s)
    battery(s)
    buck_boost(s)
    boost(s)
    load_switch(s)

    # ---- bring-up test points -------------------------------------------------------------
    s.text('Bring-up test points (one per rail).', 20.32, 254.0)
    for i, net in enumerate(['VBUS', 'VSYS', '+BATT', '+3V3', '+5V', 'GND']):
        tp = s.part('TP%d' % (1 + i), 'Connector:TestPoint', net, 30.48 + i * 15.24, 274.32,
                    footprint='TestPoint:TestPoint_Pad_D1.5mm')
        s.conns(tp, {'1': net})
    return s
