"""Memory sheet: IS42S16400J SDRAM (FMC, 16-bit), W25Q128JV QSPI NOR, microSD socket (SDIO 4-bit).

Everything here runs from 3V3_PERIPH (the rail the reserved TPS22965 can gate in v2; on v1 it is
+3V3 through the fitted 0R R13). Net names are the STM32 alternate-function names, so
check_schematic.py can confirm end to end that each memory pin reaches an MCU pin that really
provides that function.
"""
from common import C0402, C0603, C0805, R0402, conn_by_name, new_sheet, two_pin

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


def build():
    s = new_sheet('Memory', lambda n: None if n in LOCAL else 'bidirectional')
    s.text('MEMORY — all on 3V3_PERIPH. Net names = STM32 alternate functions (see sheet_mcu.PINMAP).',
           20.32, 12.7, size=2)

    # ---- SDRAM ---------------------------------------------------------------------------
    s.text('IS42S16400J-6TLI: 64 Mbit = 8 MB (1M x 16 x 4 banks), FMC SDRAM bank 1, 16-bit.\n'
           '12 row / 8 column address bits, 4 banks. Decoupling: 100nF per VDD/VDDQ pin + 10uF.\n'
           'Layout: keep the FMC bus short and length-matched-ish; SDCLK up to 90 MHz.',
           20.32, 30.48)
    u = s.part('U201', 'Memory_RAM:IS42S16400J-xT', 'IS42S16400J-6TLI', 76.2, 134.62,
               fields={'MPN': 'IS42S16400J-6TLI'})
    conn_by_name(s, u, SDRAM)
    for i in range(7):
        two_pin(s, 'C%d' % (201 + i), 'C', '100nF', 137.16 + i * 10.16, 76.2, '3V3_PERIPH', 'GND',
                C0402)
    two_pin(s, 'C208', 'C', '10uF', 137.16 + 7 * 10.16, 76.2, '3V3_PERIPH', 'GND', C0805)

    # ---- QSPI NOR ------------------------------------------------------------------------
    s.text('W25Q128JV 16 MB QSPI NOR (fonts/assets; firmware stays in internal flash).\n'
           '10k pull-up on /CS keeps the flash deselected while the MCU boots.', 218.44, 30.48)
    q = s.part('U202', 'Memory_Flash:W25Q128JVS', 'W25Q128JVSIQ', 256.54, 76.2,
               fields={'MPN': 'W25Q128JVSIQ'})
    conn_by_name(s, q, QSPI)
    two_pin(s, 'R201', 'R', '10k', 294.64, 76.2, '3V3_PERIPH', 'QUADSPI_BK1_NCS', R0402)
    two_pin(s, 'C209', 'C', '100nF', 304.8, 76.2, '3V3_PERIPH', 'GND', C0402)

    # ---- microSD ------------------------------------------------------------------------
    s.text('microSD (Molex 104031-0811, push-pull, detect switch). 47k pull-ups on CMD/DAT0-3\n'
           '(SD spec 10k-100k); card-detect switch to GND with a 100k pull-up to 3V3_AON (the MCU\n'
           'rail, so detect works even with 3V3_PERIPH gated). 10uF + 100nF at the socket for\n'
           'hot-insertion inrush.', 218.44, 129.54)
    j = s.part('J201', 'Connector:Micro_SD_Card_Det2', 'microSD', 256.54, 190.5,
               footprint='Connector_Card:microSD_HC_Molex_104031-0811',
               fields={'MPN': 'Molex 1040310811'})
    conn_by_name(s, j, SD)
    for i, net in enumerate(['SDIO_CMD', 'SDIO_D0', 'SDIO_D1', 'SDIO_D2', 'SDIO_D3']):
        two_pin(s, 'R%d' % (202 + i), 'R', '47k', 297.18 + i * 10.16, 170.18, '3V3_PERIPH', net,
                R0402)
    two_pin(s, 'R207', 'R', '100k', 347.98, 170.18, '3V3_AON', 'SD_DETECT', R0402)
    two_pin(s, 'C210', 'C', '10uF', 297.18, 215.9, '3V3_PERIPH', 'GND', C0603)
    two_pin(s, 'C211', 'C', '100nF', 307.34, 215.9, '3V3_PERIPH', 'GND', C0402)

    # ---- clock series resistors ---------------------------------------------------------------
    s.text('Clock series resistors (22-33R), placed right at the MCU pin: source termination\n'
           'for the SDRAM, microSD and QSPI clocks (point-to-point, up to 90 MHz).', 20.32, 238.76)
    for i, (dev_net, (ref, value, mcu_net)) in enumerate(SERIES.items()):
        two_pin(s, ref, 'R', value, 30.48 + i * 10.16, 256.54, mcu_net, dev_net, R0402)
    return s
