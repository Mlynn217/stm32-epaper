# TODO

### Documentation / Planning
- [x] Document hardware choice & rationale
- [x] Confirm final GPIO pin mapping for SPI + control lines (avoid conflicts with the Discovery
      board's onboard LCD/SDRAM/USB/camera pins) — SCK/PA5, MISO/PB4, MOSI/PB5, CS/PA4, RST/PB1,
      HRDY/PA2; documented in README with physical connector/pin (CN12/CN8/CN7/CN6)
- [x] Record this panel's VCOM value once hardware arrives — `-2.59V` (see README, Display section)
- [ ] Decide on a license

### Environment / Tooling
- [x] Install `arm-none-eabi-gcc` toolchain
- [x] Install OpenOCD for ST-Link debugging
- [x] Install Ninja
- [x] Install VSCode extensions: CMake Tools, C/C++, Cortex-Debug
- [x] Generate STM32CubeMX project (`.ioc`) for STM32F469I-DISCO, targeting the CMake toolchain
  - [x] FMC/SDRAM present in the board template (CAS latency 3, burst read enabled) — configured,
        not yet exercised with an actual read/write test (see firmware TODO below)
  - [x] Configure SPI peripheral + GPIOs for IT8951 control lines (CS/RST/HRDY) — SPI1 Full-Duplex
        Master, Mode 0, software NSS, prescaler `/8` (11.25MHz, under the IT8951's 24MHz max per
        its datasheet); CS/RST push-pull idle-high, HRDY input; all builds/flashes clean
  - [x] Validated end-to-end on physical hardware: `cmake --preset Debug` + `cmake --build` produces
        `stm32-epaper.elf`, OpenOCD (`interface/stlink.cfg` + `target/stm32f4x.cfg`) flashes and
        verifies it over the onboard ST-LINK/V2.1, and the board runs post-reset with the FreeRTOS
        scheduler started (PC in flash, PSP in use, no fault) — decided to keep FreeRTOS + the full
        board demo peripheral set (USB Host, FatFS/SDIO, LTDC/DSIHOST, SAI1, dual I2C/USART, QSPI)
        rather than trim it, since it builds/boots cleanly as-is
- [ ] Set up VSCode `tasks.json` / `launch.json` for build + flash + debug
  - [x] Confirm J-Link tooling available as an alternate probe (`JLinkGDBServer` installed, OpenOCD
        has `interface/jlink.cfg`, Cortex-Debug supports `jlink` servertype) — default to onboard
        ST-LINK for day-to-day debug, use J-Link for faster reflash / RTT logging
  - [ ] Check UM2092 (F469-Disco user manual) for whether parallel trace pins (TRACECLK/TRACED0-3)
        are broken out on a header — needed to use J-Trace's ETM instruction trace, not just SWO
  - [ ] Install `gdb-multiarch` (needed by Cortex-Debug; `gcc-arm-none-eabi` didn't bundle
        `arm-none-eabi-gdb` on this Ubuntu version)

### Firmware — display bring-up milestone (current focus)
- [x] Vendor + adapt Waveshare's IT8951 driver source (SPI mode) into this repo — used their
      Raspberry Pi driver (genuinely SPI-based) rather than the STM32 demo (I80-only in practice);
      `Drivers/IT8951/e-Paper/EPD_IT8951.c/h` vendored near-verbatim, `Drivers/IT8951/Config/`
      rewritten for STM32 HAL (hspi1 + SPI1_CS/RST/HRDY pins); builds and links cleanly
- [x] Physically wire the HAT to the board per the README wiring table (CN12 + CN8 + CN7 + CN6)
- [x] Bring up SPI and verify communication with the IT8951 (read device info) — **confirmed working
      on real hardware**: `EPD_IT8951_Init()` reads back `Panel(W,H) = (1448,1072)` (exact match to
      the panel spec), `FW Version = SWv_0.6.`, `LUT Version = M841_TFAB512` — real data, not
      floating-pin noise. Called from `StartDefaultTask` in `main.c`.
  - [x] Fixed along the way: newlib-nano (`--specs=nano.specs`) strips float support from
        `printf`/`Debug()`, so the driver's VCOM confirmation (`%.02f`) printed as empty (`-V`
        instead of `-2.59V`). Fixed by adding `-u _printf_float` to linker flags in `CMakeLists.txt`.
- [x] Set the panel's VCOM value in firmware — `EPD_IT8951_Init(2590)` (this panel's `-2.59V`),
      confirmed via the VCOM confirmation printout after the printf-float fix
- [ ] Note: `EPD_IT8951_Clear_Refresh()` calls stdlib `malloc`/`free` — check this is safe under
      FreeRTOS (newlib heap locking) before relying on it, or swap for a static buffer
- [x] Draw a test pattern/image and confirm it renders on the panel — **confirmed on real hardware**:
      a 100x100px 10px-block checkerboard, written via a small `static` 4bpp buffer (~5KB, plain
      SRAM, no SDRAM needed) and `EPD_IT8951_4bp_Refresh()`, rendered correctly on the panel
- [ ] Exercise the FMC/SDRAM with an actual read/write test (pattern fill + read-back) to confirm
      the timing config works, before trusting it as the IT8951 frame buffer
- [ ] Route the IT8951 frame buffer through FMC/SDRAM — needed once we go full-panel: a full 4bpp
      frame is ~758KB (1448x1072), vs. our 32KB FreeRTOS heap and limited internal SRAM, so the
      source buffer for a full-screen image has to live in SDRAM as a static/fixed-address array
- [ ] Confirm both full refresh (GC16, used by the checkerboard test) and fast/partial (A2 mode)
      refresh work

### Later milestones (not yet scoped in detail)
- [ ] Storage (SD card / file system) for book files
- [ ] Page rendering / text layout
- [ ] Ebook format parsing (EPUB/TXT)
- [ ] UI / input handling
- [ ] Power management / battery life
