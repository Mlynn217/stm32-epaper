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
- No license chosen yet

## Overview

Goal: a standalone e-reader built around Waveshare's [6inch HD e-Paper HAT](https://www.waveshare.com/6inch-hd-e-paper-hat.htm)
(1448×1072, 16-level grayscale, IT8951 controller), driven by an STM32 host.

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
