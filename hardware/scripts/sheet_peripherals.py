"""Peripherals sheet: external Waveshare IT8951 HAT connector, CAP1188 cap-touch + side-wall
electrodes, PEC11R encoder, power button. Everything user-facing runs from 3V3_AON (the MCU rail)
so wake sources keep working with the peripheral rail gated (v2).
"""
from common import C0402, R0402, conn_by_name, new_sheet, two_pin

LOCAL = {'HAT_SCK', 'HAT_MOSI', 'HAT_CS', 'ENC_A_RAW', 'ENC_B_RAW', 'CAP_ADDR', 'CAP_WAKE',
         'TOUCH_L1', 'TOUCH_L2', 'TOUCH_R1', 'TOUCH_R2'}


def build():
    s = new_sheet('Peripherals', lambda n: None if n in LOCAL else 'bidirectional')
    s.text('PERIPHERALS — HAT connector, cap-touch, encoder, power button.', 20.32, 12.7, size=2)

    # ---- Waveshare HAT (external, v1) ----------------------------------------------------
    s.text('External Waveshare 6" HD IT8951 HAT on a 1x8 2.54mm header (same signals the Disco\n'
           'wiring uses today). 33R series on the MCU-driven SPI lines (edge damping over the\n'
           'cable). The HAT gets +5V only while EPD_5V_EN is high: FIRMWARE MUST drive SCK/MOSI/\n'
           'CS/RST low (or float them) while the HAT is unpowered, or it back-powers the IT8951\n'
           'through its I/O clamp diodes.', 20.32, 30.48)
    j = s.part('J301', 'Connector_Generic:Conn_01x08', 'IT8951 HAT', 101.6, 88.9,
               footprint='Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical')
    s.conns(j, {'1': '+5V', '2': 'GND', '3': 'HAT_SCK', '4': 'HAT_MOSI', '5': 'SPI1_MISO',
                '6': 'HAT_CS', '7': 'EPD_RST', '8': 'EPD_HRDY'})
    two_pin(s, 'R301', 'R', '33R', 30.48, 81.28, 'SPI1_SCK', 'HAT_SCK', R0402)
    two_pin(s, 'R302', 'R', '33R', 43.18, 81.28, 'SPI1_MOSI', 'HAT_MOSI', R0402)
    two_pin(s, 'R303', 'R', '33R', 55.88, 81.28, 'EPD_CS', 'HAT_CS', R0402)
    s.text('J301: 1 +5V, 2 GND, 3 SCK, 4 MOSI, 5 MISO, 6 CS, 7 RST, 8 HRDY (busy, active low)',
           20.32, 114.3)
    s.text('R316: HRDY would float while the HAT is unpowered; 100k holds it low (reads "busy").\n'
           'No ESD on J301: it is an internal cable, never user-accessible.', 20.32, 119.38)
    two_pin(s, 'R316', 'R', '100k', 137.16, 88.9, 'EPD_HRDY', 'GND', R0402)

    # ---- CAP1188 -------------------------------------------------------------------------
    s.text('CAP1188 cap-touch on I2C1. ADDR_COMM 150k -> SMBus address 0x29 (0101_001), same as\n'
           'the Adafruit breakout used for bring-up. SPI_CS# to GND (I2C mode), WAKE 100k\n'
           'pull-down, RESET (active high) 100k pull-down, ALERT# open-drain 10k pull-up, unused\n'
           'LED1-8 and unused CS inputs to GND (datasheet Table 1.1). Electrodes: left pair on\n'
           'CS3/CS4 (top side, away from VDD), right pair on CS5/CS6 (right side, towards J303) -\n'
           'chosen for layout: CS1-4 all on the top side fenced in the VDD pin. Two small electrode\n'
           'boards on short JST-SH cables (touch / GND / touch). Geometry: hardware/enclosure.',
           20.32, 132.08)
    u = s.part('U301', 'epaper:CAP1188', 'CAP1188-1-CP-TR', 76.2, 190.5,
               fields={'MPN': 'CAP1188-1-CP-TR'})
    cmap = {'VDD': '3V3_AON', 'SMDATA/SPI_MISO': 'I2C1_SDA', 'SMCLK/SPI_CLK': 'I2C1_SCL',
            'ALERT#': 'CAP_ALERT', 'RESET': 'CAP_RESET', 'WAKE/SPI_MOSI': 'CAP_WAKE',
            'SPI_CS#': 'GND', 'ADDR_COMM': 'CAP_ADDR', 'GND': 'GND',
            'CS3': 'TOUCH_L1', 'CS4': 'TOUCH_L2', 'CS5': 'TOUCH_R1', 'CS6': 'TOUCH_R2'}
    cmap.update({'CS%d' % i: 'GND' for i in (1, 2, 7, 8)})
    cmap.update({'LED%d' % i: 'GND' for i in range(1, 9)})
    conn_by_name(s, u, cmap)
    for i, side in enumerate(['L', 'R']):
        jt = s.part('J%d' % (302 + i), 'Connector_Generic:Conn_01x03', 'Electrodes ' + side,
                    147.32 + i * 25.4, 170.18,
                    footprint='Connector_JST:JST_SH_SM03B-SRSS-TB_1x03-1MP_P1.00mm_Horizontal',
                    fields={'MPN': 'SM03B-SRSS-TB'})
        s.conns(jt, {'1': 'TOUCH_%s1' % side, '2': 'GND', '3': 'TOUCH_%s2' % side})
    s.text('U302/U303: ESD on the electrode cables, one 2-channel part right at each connector\n'
           '(the boards sit behind 2.2 mm of PA12, but the back-cover seam is ~0.2 mm from their\n'
           'edge). ~1.5 pF/line: negligible next to the pads. SC-70: 1 = IO1, 2 = IO2, 3 = GND.',
           147.32, 195.58)
    for i, side in enumerate(['L', 'R']):
        esd = s.part('U%d' % (302 + i), 'Power_Protection:TPD2E2U06DCK', 'TPD2E2U06DCKR',
                     160.02 + i * 25.4, 215.9, fields={'MPN': 'TPD2E2U06DCKR'})
        s.conns(esd, {'1': 'TOUCH_%s1' % side, '2': 'TOUCH_%s2' % side, '3': 'GND'})
    # (I2C1 pull-ups R105/R106 are drawn on the MCU sheet, wired to PB8/PB9.)
    two_pin(s, 'R306', 'R', '10k', 50.8, 238.76, '3V3_AON', 'CAP_ALERT', R0402)
    two_pin(s, 'R307', 'R', '100k', 60.96, 238.76, 'CAP_RESET', 'GND', R0402)
    two_pin(s, 'R308', 'R', '100k', 71.12, 238.76, 'CAP_WAKE', 'GND', R0402)
    two_pin(s, 'R309', 'R', '150k 1%', 81.28, 238.76, 'CAP_ADDR', 'GND', R0402)
    two_pin(s, 'C301', 'C', '100nF', 91.44, 238.76, '3V3_AON', 'GND', C0402)
    two_pin(s, 'C302', 'C', '1uF', 101.6, 238.76, '3V3_AON', 'GND', C0402)

    # ---- Encoder -------------------------------------------------------------------------
    s.text('Bourns PEC11R-4220F-S0024 (24 detents, push switch, 20 mm shaft). Bourns suggested filter per\n'
           'channel: 10k pull-up, 10k series, 10nF to GND -> TIM3 encoder mode (PA6/PA7).\n'
           'Switch: 10k pull-up + 10nF, active low. Mounting lugs to GND (metal shaft ESD path).',
           218.44, 30.48)
    e = s.part('SW301', 'Device:RotaryEncoder_Switch_MP', 'PEC11R-4220F-S0024', 256.54, 83.82,
               footprint='epaper:RotaryEncoder_Bourns_Vertical_PEC11R-4xxxF-Sxxxx',
               fields={'MPN': 'PEC11R-4220F-S0024'})
    s.conns(e, {'A': 'ENC_A_RAW', 'B': 'ENC_B_RAW', 'C': 'GND', 'S1': 'GND', 'S2': 'ENC_SW',
                'MP': 'GND'})
    two_pin(s, 'R310', 'R', '10k', 297.18, 81.28, '3V3_AON', 'ENC_A_RAW', R0402)
    two_pin(s, 'R311', 'R', '10k', 307.34, 81.28, 'ENC_A_RAW', 'ENC_A', R0402)
    two_pin(s, 'C303', 'C', '10nF', 317.5, 81.28, 'ENC_A', 'GND', C0402)
    two_pin(s, 'R312', 'R', '10k', 332.74, 81.28, '3V3_AON', 'ENC_B_RAW', R0402)
    two_pin(s, 'R313', 'R', '10k', 342.9, 81.28, 'ENC_B_RAW', 'ENC_B', R0402)
    two_pin(s, 'C304', 'C', '10nF', 353.06, 81.28, 'ENC_B', 'GND', C0402)
    two_pin(s, 'R314', 'R', '10k', 297.18, 114.3, '3V3_AON', 'ENC_SW', R0402)
    two_pin(s, 'C305', 'C', '10nF', 307.34, 114.3, 'ENC_SW', 'GND', C0402)

    # ---- Power button ----------------------------------------------------------------------
    s.text('Power / wake button to PA0 = WKUP (wakes STANDBY on a RISING edge), so the button\n'
           'pulls PWR_BTN up to 3V3_AON, with a 100k pull-down. Side-actuated, on the PCB\'s\n'
           'bottom edge (the enclosure\'s bottom wall has a flexure tab over it).', 218.44, 152.4)
    b = s.part('SW302', 'Switch:SW_Push', 'POWER', 256.54, 180.34,
               footprint='Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010',
               fields={'MPN': 'SKRTLAE010'})
    s.conns(b, {'1': '3V3_AON', '2': 'PWR_BTN'})
    two_pin(s, 'R315', 'R', '100k', 287.02, 187.96, 'PWR_BTN', 'GND', R0402)

    # ---- Mounting ----------------------------------------------------------------------------
    s.text('Mounting holes: M2 thread-forming screws into standoffs on the back cover. Positions\n'
           'come from hardware/enclosure (out/pcb_placement.json).', 218.44, 215.9)
    for i in range(4):
        s.part('H%d' % (301 + i), 'Mechanical:MountingHole', 'M2', 228.6 + i * 12.7, 231.14,
               footprint='MountingHole:MountingHole_2.2mm_M2', in_bom=False)
    return s
