# stm32-epaper

An STM32-based e-reader using the Waveshare 6inch HD e-Paper HAT (IT8951 controller).

## Current Status

**Reads a real EPUB off an SD card and renders actual book pages on the physical panel.** On real
hardware, confirmed working end to end:
- STM32CubeMX → CMake → arm-none-eabi-gcc/Ninja → OpenOCD → ST-LINK build/flash/debug loop, from
  inside VSCode (tasks + launch configs for build, flash, debug, and a serial monitor)
- SPI1 communication with the IT8951 (panel resolution/FW/LUT version read back correctly, this
  panel's VCOM `-2.59V` set), the FMC/SDRAM (16MB, full read/write test passes), full-panel GC16
  grayscale refresh, and A2 (fast black/white-only partial refresh) mode
- **SD card storage** — SDIO+FatFS mount/read/write, a directory listing on every boot, and long
  filename support (`_USE_LFN=3`, heap-based — see TODO.md for why not `1`/`2`)
- **Fonts and page layout** — anti-aliased proportional bitmap fonts at reading-appropriate sizes
  (generated from a real TTF via `tools/gen_font.py`, not the tiny fixed-width fonts a low-res TFT
  would use), word-wrap, and pagination (a continuation-pointer API that can paginate arbitrarily
  long text one screen at a time without holding more than one page in memory)
- **An EPUB reader** (`Drivers/Epub/`, `Drivers/Inflate/`) — a minimal ZIP reader, a vendored
  reference DEFLATE decompressor, and tiny XML/HTML helpers, enough to parse `container.xml` → the
  OPF's manifest/spine → a chapter's XHTML → clean plain text, fed straight into the page-layout
  pipeline above. Validated against a real book (a purchased copy of *Mistborn: Secret History*) —
  see TODO.md for the debugging story, including a real FatFs/SDIO stale-read bug found and worked
  around along the way

Not done yet — see [TODO.md](TODO.md) for the full list, but the near-term highlights:
- No page-turn/chapter-navigation UI yet (currently auto-picks the first chapter with real text and
  shows up to 4 pages of it); no physical input handling
- Power management/battery life not started
- Custom PCB: the **v1 schematic is drafted in full** in `hardware/kicad/` (Power, MCU, Memory and
  Peripherals sheets). It's ERC-clean and machine-checked (pin mux, nets, footprint pads), but not
  yet reviewed by a person, and there's no PCB layout yet. v1 scope: the Waveshare HAT stays
  external on an SPI connector (see [Custom PCB (Planned)](#custom-pcb-planned))
- No license chosen yet

## Overview

Goal: a standalone, **handheld, Kindle-style** e-reader built around Waveshare's
[6inch HD e-Paper HAT](https://www.waveshare.com/6inch-hd-e-paper-hat.htm) (1448×1072, 16-level
grayscale, IT8951 controller), driven by an STM32 host. The Discovery board is a bring-up platform;
the end goal is a custom PCB — see [Custom PCB (Planned)](#custom-pcb-planned) below for the current
draft of hardware decisions for that board.

**Phase 1 host: STM32F469I-DISCO.** It has its own onboard RGB LCD, but that's not why it was
picked — it's the FMC-attached SDRAM that matters. The IT8951 needs a host-side frame buffer too
large for any STM32's internal SRAM, which is exactly why Waveshare's own reference design pairs
the IT8951 with an STM32F429 board (Open429I) that has external SDRAM bolted on. The F469-Disco
already has SDRAM on the FMC bus (normally used for its own LCD), so we get that requirement for
free. It's a bring-up/development platform for proving out the driver and architecture — the final
product host may end up being a smaller, lower-power part once the design is proven.

## Hardware

### Display: Waveshare 6inch HD e-Paper HAT

- Panel: 6", 1448×1072, black/white, 16 grayscale levels (1–4 bpp)
- Controller: IT8951 (on the HAT/driver board)
- Full refresh: <1s. Refresh power ~0.6W typ, standby ~0.3W typ
- Host interface options: SPI / I80 (parallel) / I2C / USB (USB requires an NDA with Waveshare —
  not an option for us)
- **Using SPI** — Waveshare's own recommendation ("fewer pins, easy to use"). I80 is faster but
  needs 16 data pins plus control lines, which would compete with the Discovery board's other
  onboard peripherals; I2C is too slow for meaningful refresh rates.
- Operating voltage: 5V
- Outline: 138.4×101.8×0.67mm; active display area: 122.356×90.584mm
- Viewing angle: >170°; operating temp 0–50°C, storage -25–70°C
- Each physical panel has a unique **VCOM** value printed on its FPC cable that must be set in
  firmware for correct grayscale/contrast. **This panel's VCOM is `-2.59V`** → pass `2590` (mV
  magnitude) to `EPD_IT8951_Init()`/`EPD_IT8951_SetVCOM()`.

### Host: STM32F469I-DISCO

- STM32F469NIH6 — Cortex-M4F, 2MB flash, 384KB internal SRAM
- FMC-attached SDRAM onboard (normally the framebuffer for the board's own RGB LCD) — repurposed
  here as the IT8951 frame buffer
- Onboard ST-LINK/V2-1 — no external debug probe needed

### Wiring

Final pin assignment for the F469-Disco, chosen by checking every candidate pin against the MCU's
full alternate-function list and cross-referencing everything already enabled in the `.ioc` (FMC,
DSIHOST/LTDC, I2C1/2, SAI1, SDIO, QUADSPI, USART3/6, USB_OTG_FS, TIM1) — no conflicts:

| IT8951 HAT pin | Signal              | STM32 pin | Discovery connector      | Pin # | Silkscreen label | Wire color |
|----------------|---------------------|-----------|--------------------------|-------|-------------------|------------|
| 5V             | Power               | —         | CN6 (Arduino Power)      | 5     | `+5V`             | Grey       |
| GND            | Ground              | —         | CN6 (Arduino Power)      | 6/7   | `GND`             | Black      |
| SCK            | SPI1_SCK            | PA5       | CN12 (Extension header)  | 7     | —                 | Orange     |
| MISO           | SPI1_MISO           | PB4       | CN12 (Extension header)  | 5     | —                 | Blue       |
| MOSI           | SPI1_MOSI           | PB5       | CN12 (Extension header)  | 9     | —                 | Yellow     |
| CS             | GPIO_Output, PP, idle high | PA4 | CN8 (Arduino Analog)   | 6     | `A5`              | Green      |
| RST            | GPIO_Output, PP, idle high | PB1 | CN8 (Arduino Analog)   | 1     | `A0`              | White      |
| HRDY (busy)    | GPIO_Input          | PA2       | CN7 (Arduino Digital)    | 6     | `D5`              | Purple     |

Notes:
- SPI1's SCK/MISO/MOSI are only broken out on **CN12**, the 16-pin 2.54mm extension header on the
  underside of the board — not on the Arduino headers. CS/RST/HRDY are split across CN8 and CN7
  instead, so wiring the HAT means jumpers from three different connectors plus CN6, not one.
- CN8 pin 6 (`A5`) defaults to PA4 via solder bridges SB10/SB12 (closed by default) — worth a
  continuity check with a multimeter before trusting it, since those can be reconfigured.
- CS/RST are push-pull, idle **high** (both signals are active-low on the IT8951 side — CS is only
  pulled low during a transaction, RST is only pulsed low as a deliberate reset, driven by the
  driver's init code rather than left low by default).
- SPI1 clock: **11.25 MHz** (APB2/8 off a 90MHz APB2 clock). The IT8951's datasheet (Table 9-4, SPI
  AC Characteristics) caps `fSCLK` at 24MHz; 11.25MHz leaves comfortable margin for jumper-wire
  wiring rather than a tightly-routed PCB. `hspi1.Init.BaudRatePrescaler` in `Core/Src/main.c` and
  `SPI1.CalculateBaudRate` in the `.ioc` are both set to match.
- HRDY (busy) is active-low (low = busy). All three IT8951-side GPIOs are currently `GPIO_NOPULL`
  (no pull-up/down) — a defensive pull-up was considered for the brief post-reset window before
  `MX_GPIO_Init()` runs, but wasn't applied; not required since these are actively driven once init
  runs, just an optional safety margin if boot-order issues ever show up.

## Custom PCB (Planned)

In progress. The KiCad project is in `hardware/kicad/`, and the **v1 schematic is drafted in full**:
Power, MCU, Memory and Peripherals sheets. PCB layout is next (see TODO.md). These are the
**current draft hardware decisions**, recorded here so context isn't lost between sessions. They're still open to change
while the schematic takes shape. The Discovery board plus the Waveshare HAT above stays the bring-up
platform until the PCB is built.

**Board scope (decided 2026-09-22):**
- **v1 PCB:** power, MCU, memory, navigation/input and the other peripherals. The **Waveshare
  IT8951 HAT stays an external module**, connected over an SPI connector, with the board supplying
  its 5 V.
- **Deferred to a later revision:** a bare IT8951 IC with its own panel PMIC (see
  [Display](#display) for what that involves).

### Input System

| Control | Component | Interface | Notes |
|---|---|---|---|
| Prev / Next page | CAP1188-1-SL (Microchip) | I²C + ALERT interrupt | 8-channel; side-wall electrodes |
| Side-wall electrodes | PCB copper pads ×4 | — | 2 per side; plastic wall as dielectric; up to ~4mm wall thickness |
| Library / menu scroll | Bourns PEC11R-4215F-S0024 | 2× GPIO (A, B quadrature) | 24 detents / 24 pulses per revolution, 15mm flatted shaft |
| Confirm / select | Encoder push | 1× GPIO (SW) | Built into the PEC11R (the "S" in S0024) |
| Power / wake | Tactile switch (part TBD) | 1× GPIO (WKUP pin) | Top edge of device; physical, not capacitive |

Layout: cap-touch zones on left/right side walls (thumb rest), encoder on the bottom edge, power
button on the top edge.

**Considered and set aside (open to revisiting if requirements change):**
- PSP-style analog joystick (COM-09426): analog noise, no click function, and its resistive divider
  draws current continuously, which is wrong for a device that mostly sleeps.
- On-glass bezel capacitive (ITO film): manufacturing complexity; side-wall PCB copper pads achieve
  the same result more simply.

### MCU, Memory & Storage

| Component | Part | Interface | Role |
|---|---|---|---|
| MCU | STM32F469IIT6 (LQFP176) | — | Same die as the Disco's F469NI, but a hand-/JLC-assemblable package instead of TFBGA216. Confirm the pin budget (FMC SDRAM + SDIO + QSPI + SPI + I²C + USB) in CubeMX before layout |
| SDRAM | IS42S16400J-6TLI | FMC 16-bit | **64 Mbit = 8 MB** (earlier notes wrongly said 16 MB; that's the Disco's chip). Plenty: ~776 KB frame buffer + the 4 MB text/EPUB buffer. Keep it, because the whole-file-in-RAM FatFs/SDIO workaround depends on it |
| QSPI NOR Flash | W25Q128JV (16 MB) | QSPI | Firmware + fonts. (N25Q128A dropped: Micron's legacy line, superseded by MT25Q) |
| microSD slot | TBD (Molex 1040310811 or GCT MSD-4-A candidates) | SDIO 4-bit | Book library (user-swappable) |

SDRAM is volatile. It does **not** replace storage; book files live on microSD.

### Display

**v1:** the Waveshare 6" HD HAT, off-board on an SPI connector. The HAT takes 5 V (from the
TPS61023 boost) and has 3.3 V SPI logic.

**Later revision: a bare IT8951 IC.** The IT8951 datasheet (`docs/IT8951_D_V0.2.4.3_20170728.pdf`)
shows this is **not** a "just run everything from 3.3 V" change (an earlier note here claimed it
was). It needs:
- **A 1.8 V core supply** (VCCK, VCC18A and VCC_SDR, each 1.8 V ±0.09 V) as well as 3.3 V for I/O and
  analog.
- **A power-up order: 1.8 V stable first, then 3.3 V, then reset released.** A 1.8 V LDO fed
  *from* 3.3 V can't meet that. One fix: feed the LDO from VSYS and switch the IT8951's 3.3 V on
  afterwards with a load switch.
- **A 12 MHz crystal, and its own SPI NOR flash** holding the panel's **waveform file**. The
  waveform is panel-specific and comes from the panel maker; the HAT ships with it in its flash.
  **Getting it is the biggest risk of going bare-IC.**
- **A TPS65185/TPS65186 panel PMIC** with its own inductors, diodes and caps (for VCOM and the
  panel's high voltages), plus the panel FPC connector.
- The IT8951 has **built-in** SDRAM (32 Mb, or 64 Mb on the -64 variants), so it needs no external
  DRAM. It's rated 0–70 °C.

### Power Architecture

**Cell chemistry: LiFePO4 (LFP).** Chosen over standard LiPo for safety (no thermal runaway below
~270°C, vs ~150°C for LiCoO2), 2000–3000 cycle life, and a flat discharge curve. The trade-offs:
- Lower energy density (~120 Wh/kg vs ~200 for LiPo).
- 3.2 V nominal means an LDO alone can't hold 3.3 V across the full discharge range, so a
  buck-boost is mandatory.
- The flat curve makes voltage-based fuel gauging nearly useless (see TODO.md).

Running the whole system at 1.8 V was evaluated and rejected: the SDRAM and the HAT need 3.3 V/5 V
anyway, so a 1.8 V MCU rail would still need a 3.3 V converter for peripherals, plus level shifters,
for no real gain.

**Power tree, v1 (external Waveshare HAT):**
```
USB-C VBUS ──► MCP73123 ──► LiFePO4 cell (2.5–3.65V)       LFP charger (3.6V CV, NOT 4.2V)
VBUS ──Schottky──┐                                         load sharing (AN1149): USB feeds the
cell ──P-FET─────┴──► VSYS                                  system directly when present
VSYS ──► TPS63802 buck-boost → 3.3V                         STM32, SDRAM, QSPI, microSD, CAP1188, encoder, buttons
           └── EN = VSYS divider: OFF < ~2.80V, ON > ~3.08V (undervoltage cutoff)
VSYS ──► TPS61023 boost → 5V                                external Waveshare HAT (MCU-enabled)
cell ──► Schottky → MCU VBAT                                RTC backup + firmware battery measurement
```

**Battery protection (undervoltage).** The MCP73123 only charges; it does **nothing** to stop
over-discharge. Protection is layered:
1. **Firmware (primary).** Measure the cell through the STM32's internal VBAT ADC channel (the VBAT
   pin is fed from the cell through the RTC Schottky, so allow for the diode drop). At ~3.0 V, shut
   down gracefully: save state, leave a "please charge" screen on the e-ink (it holds with no
   power), then enter standby.
2. **Hardware backstop.** The TPS63802's EN pin has a precise threshold (1.10 V rising / 1.00 V
   falling). A 1.8 MΩ/1.0 MΩ divider from VSYS therefore turns the 3.3 V rail off below ~2.80 V and
   back on above ~3.08 V (±3%), costing ~1.2 µA. This catches a hung firmware or a drain during
   sleep.
3. **Cell level (recommended).** Buy the LFP cell with a protection board (PCM). Only a PCM truly
   disconnects the cell, stopping the remaining µA leakage (RTC, divider) and protecting against
   shorts.

**Sleep current:** the regulator's own draw is now ~11 µA (TPS63802), down from ~50 µA for the
TPS63070 it replaced. Total design floor ≈ 11 µA (TPS63802) + ~1.2 µA (cutoff divider) + ~2.4 µA
(MCU standby) + ~1 µA (CAP1188 sleep), before SDRAM self-refresh if the SDRAM is kept alive. The
target is <10 µA (not a v1 priority), via a two-rail power island:
- A **TPS63900** nanopower buck-boost (75 nA quiescent) as an always-on `3V3_AON` rail for the MCU
  and CAP1188. It replaced the earlier MAX17222 idea: that part is boost-only and can't bring a
  3.65 V cell down to 3.3 V.
- The TPS63802 rail for the peripherals (SDRAM, microSD), gated behind a TPS22965 load switch.

E-ink keeps its image without power, so this allows near-complete peripheral shutdown between page
turns. **Both are reserved on the v1 PCB as unpopulated footprints, with 0Ω links fitted. Don't
redesign the power tree to chase this for v1.**

### Connectivity & Debug

| Component | Part | Notes |
|---|---|---|
| USB-C connector | GCT USB4105-GF-A | Charging + USB FS data to the MCU (DFU/CDC). *Not* SWD: USB can't carry SWD on its own |
| ESD protection | USBLC6-2SC6 (SOT-23-6) | On USB-C D+/D− and VBUS |
| SWD debug header | TC2050-IDC (Tag-Connect) | No pins on the production board |
| Battery connector | JST-PH 2.0 2-pin | Pin 1 = +. LFP lead polarity isn't standardised, so check against the actual cell |
| Waveshare HAT connector | TBD (peripheral sheet) | SPI + HRDY + RST + 5V + GND |

### Clocks & Passives

| Component | Value / Part | Notes |
|---|---|---|
| HSE crystal | 8MHz (Abracon ABM8 or equiv.) | PLL source → 180MHz system clock |
| RTC crystal | 32.768kHz, part TBD | Pick a low-load-capacitance crystal (~6–7 pF) that the STM32's low-power oscillator drives reliably (ST AN2867) |
| Decoupling caps | 100nF + 10µF per supply pin | Standard STM32 layout |
| I²C pull-ups | 4.7kΩ to 3.3V | For I²C bus (CAP1188, fuel gauge) |
| Ferrite bead | Optional | Between analog and digital GND if needed |

### Power Sheet (drafted in KiCad)

`hardware/kicad/power.kicad_sch` implements the v1 power tree above. Details decided while drawing
it:

- **Load sharing (Microchip AN1149):** VBUS → Schottky (D1) → VSYS. An AO3401A P-FET (Q1, gate on
  VBUS, 10k pull-down) connects the cell to VSYS only when USB is absent. Without it the system
  load would draw through the charger and confuse its charge termination. The pull-down is 10k
  rather than the app note's 100k, so D1's reverse leakage when hot can't lift Q1's gate.
- **Charge current:** R_PROG = 2.37k → ~495 mA (MCP73123 Eq. 5-1: I = 1104·R^-0.93). Adjust it to
  the chosen cell. The linear charger dissipates ~0.9 W at that current, so it needs thermal vias
  under the exposed pad. The MCP73123 has **no thermistor input**, so it can't block charging below
  0 °C (which damages LFP). That's acceptable for an indoor device, but it's a known gap.
- **Charge status:** a red LED from VBUS to STAT (works with the MCU off), plus `CHG_STAT` to the
  MCU. That must go to a 5V-tolerant (FT) pin, because the LED path lets the line float up toward
  VBUS.
- **USB-C:** sink-only (5.1k Rd on each CC). A USBLC6-2SC6 protects D+/D−, which go to the MCU as
  `USB_DP`/`USB_DM` (OTG_FS).
- **TPS63802 → +3V3:** 511k/91k feedback → 3.308 V. MODE low (power-save mode). EN comes from the
  undervoltage divider R6/R15 described above. Soft-power control from the power button is still
  undecided and will have to work alongside this divider.
- **TPS61023 → +5V (external HAT):** 732k/100k → 4.99 V. EN is `EPD_5V_EN` from the MCU, with a 1M
  pull-down. It truly disconnects in shutdown, so the HAT is fully unpowered until enabled.
- **RTC:** cell → BAT54J → `VBAT_RTC`. A full 3.65 V cell minus the diode drop stays under the VBAT
  pin's 3.6 V max.
- **Reserved, DNP:**
  - TPS63900 always-on rail, CFG3 = 16.2k → 3.3 V. `3V3_AON` is fed from +3V3 through the fitted
    0Ω R18 on v1. **The MCU sheet should power the MCU and CAP1188 from `3V3_AON`**, so v2 only needs
    a BoM change.
  - TPS22965 load switch for `3V3_PERIPH`, with a fitted 0Ω bypass (R13).
- **Off-sheet connections:** signals leaving the sheet are global labels: `USB_DP`, `USB_DM`,
  `CHG_STAT`, `3V3_PG`, `EPD_5V_EN`, `VBAT_RTC`, `PERIPH_EN`. Rails are power symbols: `VBUS`,
  `VSYS`, `+BATT`, `+3V3`, `+5V`, `3V3_AON`, `3V3_PERIPH`, `GND`.

### MCU, Memory and Peripherals Sheets (drafted in KiCad)

**Pin assignment.** It lives in one place: `PINMAP` in `hardware/scripts/sheet_mcu.py`. It follows
the F469-Disco wherever a peripheral carries over, so the existing CubeMX config and firmware keep
working:

| Function | Pins | Notes |
|---|---|---|
| FMC SDRAM (bank 1) | Disco's pins, D0–D15 only | **16-bit here (Disco: 32-bit)**, so the FMC init needs a 16-bit data width |
| QUADSPI bank 1 | PF6–PF10, PB6 | Same as the Disco |
| SDIO 4-bit | PC8–PC12, PD2 | Same as the Disco. **Card detect moved PG2 → PG10** (PG2 would share interrupt line EXTI2 with HRDY on PA2) |
| HAT: SPI1 + control | PA5/PB4/PB5, CS PA4, RST PB1, HRDY PA2 | Exactly today's wiring. `EPD_5V_EN` (the HAT's 5 V) is PB0 |
| USART3 (serial log) | PB10 TX / PB11 RX | Same as the Disco's ST-LINK VCP, so the same log UART |
| I²C1 (CAP1188) | PB8/PB9 | ALERT# on PB7 (EXTI7), RESET on PB12 |
| Encoder | TIM3 CH1/CH2 on PA6/PA7 (encoder mode) | Switch on PD3 (EXTI3) |
| Power button | PA0 = WKUP | Wakes from standby on a **rising** edge, so the button pulls up |
| Power-sheet signals | CHG_STAT PD4, 3V3_PG PD5, PERIPH_EN PD7 | |
| USB OTG FS | PA11/PA12, VBUS sense PA9 through 1k | |
| Debug | SWD PA13/PA14, SWO PB3 | Tag-Connect TC2050-IDC-NL pads, pinned 1:1 like the standard ARM 10-pin connector |
| Status LED | PG6 | |

All 83 assigned pins were checked in two ways: automatically against the KiCad symbol's
alternate-function list, and by hand against the LQFP176 pin table in ST's DS11189. Every signal
that can see more than 3.3 V (VBUS sense, CHG_STAT) is on a 5V-tolerant (FT) pin.

**MCU support circuitry** (per DS11189 Fig. 24 and §2.18):
- **Decoupling:** 100 nF on each of the 13 VDD pins plus 4.7 µF; 100 nF on VDDUSB.
- **Analog supply:** VDDA and VREF+ are tied together, fed through a ferrite bead, with 1 µF + 100 nF
  each.
- **Core regulator:** 2.2 µF (ESR < 2 Ω) on each of VCAP1/VCAP2. PDR_ON is high and BYPASS_REG low.
- **DSI unused:** VDDDSI to VDD, VCAPDSI tied to VDD12DSI with no capacitor, VSSDSI to GND.
- **Clocks:** 8 MHz HSE and 32.768 kHz LSE. The load caps assume CL = 10 pF and 6 pF crystals;
  recheck them for the actual parts.
- **Boot:** BOOT0 has a 10k pull-down plus a **BOOT button** to 3.3 V. Hold it at reset to enter the
  ROM USB DFU bootloader. BOOT1 (PB2) is pulled low.
- **Supply rail:** the MCU runs from `3V3_AON`, so a v2 always-on rail is only a parts-list change.

**Memory** (all on `3V3_PERIPH`):
- IS42S16400J SDRAM with 100 nF per supply pin plus 10 µF.
- W25Q128JV QSPI flash, with a 10k pull-up on /CS.
- Molex 104031-0811 microSD socket: 47k pull-ups on CMD and DAT0–3, and 10 µF + 100 nF for
  hot-insertion inrush. The detect switch is pulled up to `3V3_AON`, so detection still works with
  the peripheral rail off.

Net names are the STM32 alternate-function names (`FMC_A3`, `SDIO_D0`, …), which lets the checker
confirm each memory pin reaches an MCU pin that really provides that function.

**Peripherals:**
- **HAT connector:** 1×8 2.54 mm header (1 +5V, 2 GND, 3 SCK, 4 MOSI, 5 MISO, 6 CS, 7 RST, 8 HRDY),
  with 33 Ω series resistors on SCK, MOSI and CS. **Firmware rule:** while `EPD_5V_EN` is low (HAT
  unpowered), drive SCK/MOSI/CS/RST low or leave them floating. Otherwise the MCU back-powers the
  IT8951 through its I/O clamp diodes.
- **CAP1188:** I²C address 0x29 (150k on ADDR_COMM, the same as the Adafruit breakout), CS1–4 to four
  side-wall electrode pads (placeholder geometry, to be settled at layout), unused inputs and LED
  pins to GND.
- **PEC11R encoder:** Bourns' suggested filter on each channel (10k pull-up, 10k series, 10 nF), and
  mounting lugs to GND.
- **Power button:** pulls PA0 up, with a 100k pull-down.
- **Everything user-facing runs from `3V3_AON`.**

**Custom library parts:** symbols in `hardware/kicad/epaper.kicad_sym` and footprints in
`hardware/kicad/epaper.pretty`, each citing its datasheet:
- **TPS63802 (DLA0010A):** TI land pattern, including the split paste on the GND bar.
- **Bourns PEC11R-4xxxF-S:** the Alps EC11E footprint does *not* fit (its tabs are 11.2 mm apart vs
  13.2 mm).

### Checking the Schematic

```sh
KICAD_SYMBOL_DIR=<kicad share>/symbols python3 hardware/scripts/check_schematic.py
```

This runs ERC and a netlist export, then checks:
1. The Power sheet's nets against an expected table.
2. Every MCU pin: its net and its required alternate function.
3. Memory buses end to end.
4. No net with a single connection (catches label typos).
5. Every connected pin exists as a pad on its footprint.

ERC alone isn't enough: it missed a real VSYS↔+3V3 short in the first draft (see TODO.md).

### Full System Block Diagram (v1)

```
USB-C ──VBUS──► MCP73123 ──charge──► LiFePO4 cell
VBUS / cell ──(load sharing)──► VSYS ──► TPS63802 ──3.3V──► STM32F469IIT6
                                                   ├──────────────► IS42S16400J  (FMC, 8 MB)
                                                   ├──────────────► W25Q128JV    (QSPI)
                                                   ├──────────────► microSD slot (SDIO)
                                                   ├──────────────► CAP1188      (I²C)
                                                   ├──────────────► Encoder      (GPIO)
                                                   └──────────────► Power btn    (WKUP)
VSYS ──► TPS61023 ──5V──► HAT connector ──► external Waveshare IT8951 HAT ──► 6" panel
STM32F469 ◄──SPI──────────► HAT connector
cell ──► Schottky ──► MCU VBAT (RTC backup + battery measurement)
STM32F469 ◄──SWD── TC2050 pads
USB-C D+/D− ──► STM32F469 OTG_FS
```

**Known gotcha:** an LFP charger must terminate at 3.6 V, not 4.2 V. The MCP73123 is correct; do
not substitute an MCP73831 (4.2 V termination, will damage LFP cells).

## Architecture / Approach

- **STM32CubeMX** for pin mux, clock tree, and FMC/SDRAM configuration — exporting a **CMake**
  toolchain project (not a Keil or STM32CubeIDE project file)
- **Build**: CMake + Ninja + arm-none-eabi-gcc
- **Editor/debug**: VSCode, using the CMake Tools and Cortex-Debug extensions (OpenOCD or
  STM32CubeProgrammer's ST-Link GDB server against the onboard ST-LINK/V2-1)
- **IT8951 driver**: vendored and adapted from Waveshare's reference implementation
  ([github.com/waveshare/IT8951-ePaper](https://github.com/waveshare/IT8951-ePaper)), specifically
  their **Raspberry Pi** driver (`Raspberry/lib/e-Paper/EPD_IT8951.c/h`) rather than their STM32 demo
  — the STM32 demo (targets Keil MDK on their Open429I board anyway) turned out to only actually
  implement **I80** mode; its `IT8951_Interface_SPI` `#define` is vestigial and never referenced in
  the code. The Raspberry Pi driver is genuinely SPI-based (matches our chosen interface) and is
  pure protocol logic on top of a small hardware-abstraction layer (`DEV_Config.c/h`), so only that
  thin layer needed rewriting for STM32 HAL — `EPD_IT8951.c/h` is vendored essentially unchanged.
  Lives at `Drivers/IT8951/` (`e-Paper/` = vendored protocol driver, `Config/` = our HAL port of
  `DEV_Config`).
- **Fonts**: `Drivers/Fonts/` has two font formats side by side — the plain fixed-width, bilevel
  `sFONT` tables (vendored from ST's BSP Fonts module, still used for a couple of test strings) and
  a custom anti-aliased proportional format generated by `tools/gen_font.py` (rasterizes a real TTF
  via Pillow, quantizes to the panel's 16 gray levels) — see `EPD_FontAA.h`/`EPD_Text.c`. Page
  layout (word-wrap + pagination) is `EPD_Layout.c/h`.
- **EPUB reading**: `Drivers/Epub/` (ZIP reader, tiny XML/HTML helpers, EPUB orchestration) plus
  `Drivers/Inflate/` (vendored DEFLATE decompressor) — see TODO.md for how this was built and
  validated (native test harness first, then real hardware).
- FreeRTOS (CMSIS-RTOS v1 API, `cmsis_os.h`) — a single application task (`StartDefaultTask` in
  `Core/Src/main.c`) does all the work; kept mainly because CubeMX's F469-Disco board template
  defaults to it and it built/booted cleanly as-is, not because concurrency is needed yet
- Whenever the `.ioc` changes (new pin, new peripheral), regenerate in CubeMX — it only touches its
  own generated blocks, so hand-written application code (in `USER CODE BEGIN/END` blocks) survives.
  CubeMX regeneration has, more than once, silently reverted hand-tuned settings in generated code
  (e.g. the SPI1 clock prescaler) — `scripts/patch-cubemx.sh` re-applies known cases automatically
  at every `cmake` configure as a safety net; if you hand-tune something in CubeMX-generated code,
  add a check there too.

## Development Environment Setup

Status of this machine: STM32CubeMX is already installed (`~/STM32CubeMX`); VSCode is installed but
still needs the `arm-none-eabi-gcc` toolchain, OpenOCD, Ninja, and the relevant extensions — see
[TODO.md](TODO.md).

1. Install `arm-none-eabi-gcc`, `ninja`, and `openocd`
2. Install VSCode extensions: `ms-vscode.cmake-tools`, `ms-vscode.cpptools`, `marus25.cortex-debug`
3. Open STM32CubeMX, create a project for the STM32F469I-DISCO board (not just the MCU, so pin
   defaults for onboard peripherals are pre-populated), enable FMC/SDRAM + SPI, set Toolchain/IDE
   to **CMake**, generate code
4. Open the generated project folder in VSCode; configure/build with CMake Tools; flash/debug with
   Cortex-Debug

## Repo Layout

- `stm32-epaper.ioc` — STM32CubeMX project (source of truth for pins/clocks/peripherals)
- `Core/`, `Drivers/STM32F4xx_HAL_Driver/`, `Drivers/CMSIS/`, `Middlewares/`, `FATFS/`, `USB_HOST/` —
  CubeMX-generated HAL/CMSIS/FreeRTOS/FatFS/USB Host scaffolding (regenerated by CubeMX; hand-written
  code lives in the `USER CODE BEGIN/END` blocks within, which survive regeneration)
- `Drivers/IT8951/` — vendored + adapted IT8951 SPI driver (see Architecture above)
- `Drivers/Fonts/` — bitmap fonts (plain + anti-aliased) and the text/page-layout drawing code
- `Drivers/Epub/`, `Drivers/Inflate/` — EPUB reader (ZIP + XML/HTML) and its DEFLATE decompressor
- `tools/gen_font.py` — regenerates the anti-aliased fonts in `Drivers/Fonts/` from a TTF/OTF
- `scripts/patch-cubemx.sh` — self-heals known CubeMX regeneration regressions (see Architecture)
- `cmake/`, `CMakeLists.txt`, `CMakePresets.json` — CubeMX's CMake export + our toolchain file
- `.vscode/` — `tasks.json` (build/flash/serial-monitor), `launch.json` (debug via OpenOCD or J-Link,
  plus a `node-terminal` entry for the minicom serial monitor), `c_cpp_properties.json`,
  `extensions.json`
- `hardware/kicad/` — KiCad 10 project for the custom PCB:
  - `stm32-epaper.kicad_pro` and the root sheet, plus `power`, `mcu`, `memory` and `peripherals`
    `.kicad_sch`.
  - `epaper.kicad_sym` and `epaper.pretty/`: project-local symbols and footprints for parts not in
    KiCad's stock libraries, each transcribed from the datasheet it cites.
- `hardware/scripts/`:
  - `gen_schematic.py`: a one-shot generator that bootstrapped every sheet, from `common.py` plus
    one `sheet_*.py` per sheet. It refuses to overwrite without `--force`. Once a sheet is edited
    in Eeschema, the `.kicad_sch` is the source of truth.
  - `gen_footprints.py`: the project footprints.
  - `check_schematic.py`: design-intent checks (see "Checking the Schematic"). Keep its tables in
    sync with deliberate edits.
- `docs/` — IT8951 datasheet + programming guide, F469-Disco user manual (UM1932)
- `TODO.md` — task list/roadmap

## Building / Flashing / Debugging

**Command line:**
```sh
cmake --preset Debug
cmake --build --preset Debug
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
  -c "program build/Debug/stm32-epaper.elf verify reset exit"
```

**VSCode:** Terminal → Run Task → `Build (Debug)` or `Flash (OpenOCD / ST-LINK)` (the latter builds
first automatically), or use the Run and Debug dropdown for `Debug (OpenOCD / ST-LINK)` /
`Debug (J-Link)`. `Serial Monitor (minicom)` is available both as a task and in the Run and Debug
dropdown — it opens `/dev/ttyACM0` at 115200 baud (the ST-LINK's virtual COM port, wired to USART3)
in an integrated terminal. Exit minicom with `Ctrl-A` then `X`.

Debugging needs `gdb-multiarch` (`arm-none-eabi-gdb` isn't packaged separately on this Ubuntu
version) — see [TODO.md](TODO.md).

## TODO

See [TODO.md](TODO.md) for the current task list and roadmap.

## License

None yet — all rights reserved until a license is chosen.
