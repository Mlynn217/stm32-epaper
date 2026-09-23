"""MCU sheet: STM32F469IIT6 (LQFP176) with supply decoupling, clocks, reset/boot, SWD, debug UART.

PINMAP is the single source of truth for the pin assignment. Each entry names the alternate
function the pin must provide (checked against the KiCad symbol's alternate list by
check_schematic.py), so a typo or an impossible mux shows up as a check failure rather than a
respin. Assignments follow the STM32F469I-DISCO wherever the peripheral carries over, so the
existing firmware / CubeMX config keeps working (see README "MCU sheet").
"""
from common import C0402, C0603, R0402, flag, hidden_pins, new_sheet, two_pin

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
        s.conn(u, num, net)
        used.add(num)
    hidden = hidden_pins(s, MCU_LIB)
    for name, net in SUPPLY.items():
        for num in by_name[name]:
            used.add(num)
            if num not in hidden:  # hidden duplicates are stacked on a visible pin
                s.conn(u, num, net)
    for num in u.pins:
        if num not in used:
            s.no_connect(u, num)

    # ---- decoupling (DS11189 Fig. 24): 100nF per VDD + 4.7uF, VDDUSB, VDDA/VREF+, VCAPs ----
    s.text('Decoupling per DS11189 Fig. 24: 100nF on each of the 13 VDD pins + 4.7uF; 100nF on\n'
           'VDDUSB; VDDA and VREF+ (tied, fed through FB101) 1uF + 100nF each; VCAP1/VCAP2\n'
           '2.2uF (ESR < 2 ohm). Place each 100nF at its pin. VDD12DSI/VCAPDSI: no cap (DSI unused).',
           398.78, 30.48)
    x = 401.32
    for i in range(13):
        two_pin(s, 'C%d' % (101 + i), 'C', '100nF', x + i * 10.16, 60.96, '3V3_AON', 'GND', C0402)
    two_pin(s, 'C114', 'C', '4.7uF', x + 13 * 10.16, 60.96, '3V3_AON', 'GND', C0603)
    two_pin(s, 'C115', 'C', '100nF', x, 96.52, '3V3_AON', 'GND', C0402)  # VDDUSB
    s.text('VDDUSB', x - 2.54, 104.14, size=1)
    fb = s.part('FB101', 'Device:FerriteBead_Small', 'BLM18PG221SN1', x + 20.32, 96.52,
                footprint='Inductor_SMD:L_0603_1608Metric')
    s.conns(fb, {'1': '3V3_AON', '2': 'VDDA'})
    two_pin(s, 'C116', 'C', '1uF', x + 30.48, 96.52, 'VDDA', 'GND', C0402)
    two_pin(s, 'C117', 'C', '100nF', x + 40.64, 96.52, 'VDDA', 'GND', C0402)
    two_pin(s, 'C118', 'C', '1uF', x + 50.8, 96.52, 'VDDA', 'GND', C0402)
    two_pin(s, 'C119', 'C', '100nF', x + 60.96, 96.52, 'VDDA', 'GND', C0402)
    flag(s, 'VDDA', x + 71.12, 88.9)
    two_pin(s, 'C120', 'C', '2.2uF', x + 91.44, 96.52, 'VCAP1', 'GND', C0402,
            fields={'Note': 'ESR < 2 ohm'})
    two_pin(s, 'C121', 'C', '2.2uF', x + 101.6, 96.52, 'VCAP2', 'GND', C0402,
            fields={'Note': 'ESR < 2 ohm'})
    flag(s, 'VBAT_RTC', x + 111.76, 88.9)

    # ---- clocks ----------------------------------------------------------------------------
    s.text('HSE 8MHz (PLL -> 180MHz). Load caps C = 2*(CL - Cstray): for a CL = 10pF crystal\n'
           'and ~4pF stray, 12pF. LSE 32.768kHz: pick a low-CL (6-7pF) crystal the LSE\n'
           'oscillator drives reliably (ST AN2867); 6.8pF shown for CL = 6pF. Verify both\n'
           'against the chosen crystals.', 20.32, 30.48)
    y1 = s.part('Y101', 'Device:Crystal_GND24', '8MHz CL10pF', 40.64, 68.58,
                footprint='Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',
                fields={'MPN': 'Abracon ABM8 series, 8MHz, CL=10pF (verify)'})
    s.conns(y1, {'1': 'HSE_IN', '3': 'HSE_OUT', '2': 'GND', '4': 'GND'})
    two_pin(s, 'C122', 'C', '12pF', 30.48, 88.9, 'HSE_IN', 'GND', C0402)
    two_pin(s, 'C123', 'C', '12pF', 50.8, 88.9, 'HSE_OUT', 'GND', C0402)
    y2 = s.part('Y102', 'Device:Crystal', '32.768kHz CL6pF', 96.52, 68.58,
                footprint='Crystal:Crystal_SMD_2012-2Pin_2.0x1.2mm',
                fields={'MPN': '32.768kHz 2012, CL=6pF, low ESR (verify vs AN2867)'})
    s.conns(y2, {'1': 'LSE_IN', '2': 'LSE_OUT'})
    two_pin(s, 'C124', 'C', '6.8pF', 86.36, 88.9, 'LSE_IN', 'GND', C0402)
    two_pin(s, 'C125', 'C', '6.8pF', 106.68, 88.9, 'LSE_OUT', 'GND', C0402)

    # ---- reset / boot ----------------------------------------------------------------------
    s.text('Reset: 100nF on NRST (internal pull-up). BOOT0 10k pull-down + BOOT button to 3V3:\n'
           'hold BOOT while resetting (or plugging USB) to enter the ROM USB DFU bootloader.\n'
           'PB2 = BOOT1 pulled low so BOOT0=1 selects system memory.', 20.32, 116.84)
    two_pin(s, 'C126', 'C', '100nF', 30.48, 142.24, 'NRST', 'GND', C0402)
    two_pin(s, 'R101', 'R', '10k', 50.8, 142.24, 'BOOT0', 'GND', R0402)
    sw = s.part('SW101', 'Switch:SW_Push', 'BOOT', 71.12, 134.62,
                footprint='Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2')
    s.conns(sw, {'1': '3V3_AON', '2': 'BOOT0'})
    two_pin(s, 'R102', 'R', '10k', 96.52, 142.24, 'BOOT1', 'GND', R0402)

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

    two_pin(s, 'R104', 'R', '1k', 71.12, 287.02, 'VBUS', 'VBUS_SENSE', R0402)

    # ---- status LED ------------------------------------------------------------------------
    two_pin(s, 'R103', 'R', '1k', 30.48, 287.02, 'LED_STATUS', 'LED1_A', R0402)
    d = s.part('D101', 'Device:LED', 'STATUS (green)', 55.88, 297.18,
               footprint='LED_SMD:LED_0603_1608Metric')
    s.conns(d, {'2': 'LED1_A', '1': 'GND'})
    return s

