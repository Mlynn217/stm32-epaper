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
- [x] Exercise the FMC/SDRAM with an actual read/write test (pattern fill + read-back) to confirm
      the timing config works, before trusting it as the IT8951 frame buffer — **confirmed on real
      hardware, full 16MB pass**. Two things were needed: (1) CubeMX only configured the FMC
      controller's *timing* via `HAL_SDRAM_Init()`; the SDRAM chip's own JEDEC power-up command
      sequence (clock enable → precharge all → auto-refresh x8 → load mode register → refresh rate)
      was missing and had to be added to `MX_FMC_Init()`'s `USER CODE` section, using ST's own
      reference values for this exact chip (`stm32469i_discovery_sdram.c` in the cached
      `STM32Cube_FW_F4` package) — base `0xC0000000`, size `0x1000000` (16MB), refresh count
      `0x0569`; (2) the test itself (`SDRAM_Test()` in `main.c`) writes each 32-bit word its own
      address-derived value across all 4,194,304 words and reads it back — 0 mismatches. Also added
      a second on-panel visual marker (solid black = pass, striped = fail) alongside the checkerboard
      so pass/fail is visible without a serial monitor
- [x] Route the IT8951 frame buffer through FMC/SDRAM — **confirmed on real hardware, smooth
      16-level gradient across the full panel, no artifacts, confirmed by direct visual
      inspection**: a raw pointer at `SDRAM_BASE_ADDR` (0xC0000000) works directly since SDRAM is
      memory-mapped, no linker script changes needed. This took several rounds to get right —
      three distinct issues were found along the way, in the order they were fixed:
  - [x] **The actual root cause, found last: a 16-bit integer overflow in the vendored driver.**
        Every `EPD_IT8951_HostAreaPackedPixelWrite_*` function (1bp/2bp/4bp/4bp_Chunked) declared
        its word-count as `UWORD Source_Buffer_Length` (`uint16_t`, max 65535). For a full panel at
        4bpp, `Width(362) * Height(1072) = 388064` — silently wraps to `60384`. Only ~15% of every
        full-panel transfer (~166 of 1072 rows) actually went out before `LoadImgEnd` cut it short;
        the rest of the panel kept showing whatever was already in the chip's buffer. This
        reproduced **identically regardless of content** (solid white, solid black, and the
        gradient all showed the same banding) — that content-independence was the key clue it
        wasn't a pixel-data or write-pacing bug at all. Small transfers (checkerboard/marker, a few
        KB) never hit this since their word counts fit in 16 bits. Fixed by widening
        `Source_Buffer_Length` to `UDOUBLE` (`uint32_t`) in all four functions in `EPD_IT8951.c`.
  - [x] `Packed_Write=true` (the fast bulk-write path, `EPD_IT8951_WriteMuitiData`) checks busy/HRDY
        once before the whole burst starts and never again during it — a real correctness/robustness
        concern for very large continuous transfers (no backpressure if the chip's internal write
        pipeline falls behind), even though it turned out not to be the actual cause of the banding
        above. Addressed by adding `EPD_IT8951_WriteMuitiDataChunked` /
        `EPD_IT8951_4bp_Refresh_Chunked` (checks busy every `IT8951_WRITE_CHUNK_WORDS`, 2048 words,
        instead of never) — also a nice performance win, full-panel writes dropped from ~20-30s
        (the fully per-word `Packed_Write=false` path) to ~800ms-1.2s.
  - [x] 4bpp nibble order was backwards — the IT8951 programming guide documents P0 (first/
        lower-X pixel) in the **low** nibble and P1 in the **high** nibble of each byte; had it
        reversed. Didn't show up in the checkerboard/marker tests since solid fills are invariant
        to nibble order — only visible on an asymmetric pattern like the gradient.
  - [x] Side quest: the ST-LINK intermittently vanished from `lsusb` throughout this debugging
        session, which turned out to be real — kernel log showed an actual `USB disconnect` event,
        and `usbcore.autosuspend` is set to a 2-second idle timeout system-wide. Fixed with a udev
        rule (`/etc/udev/rules.d/99-stlink-no-suspend.rules`) disabling autosuspend specifically for
        the ST-LINK's VID:PID (0483:374b), confirmed via `power/control` reading `on` afterward.
- [x] Confirm both full refresh (GC16) and fast/partial (A2 mode) refresh work — **confirmed on
      real hardware**. Test: a 400x400 top-left region toggled black/white/black/white via
      `EPD_IT8951_1bp_Refresh(..., A2_Mode, ...)`, `Packed_Write=false` (proven-safe slow path, not
      yet chunked for 1bpp). Visually clean — the A2 region updated correctly with no disturbance to
      the surrounding full-panel gradient. Timing (real measurement, one run): A2 passes took
      390ms each (888ms for the first, which includes waiting for the preceding GC16 refresh to
      finish) vs. full-panel GC16 refreshes at 4368-4729ms — meaningfully faster, consistent with
      A2 being a binary/no-grayscale-settling waveform mode.
  - [ ] **Unexplained**: that same run's full-panel GC16 refreshes (4368-4729ms) were 4-5x slower
        than earlier measurements of the identical code path (~800-1200ms). No code changed between
        runs. Possible cause: panel temperature (GC16's waveform timing is temperature-compensated
        internally, and the panel had been refreshed repeatedly in a short span) or something
        environmental — not investigated further, logged here for later if it recurs or matters.
  - [ ] 1bpp/A2 full-panel writes still use the proven-safe slow path (`Packed_Write=false`), not a
        chunked variant like the 4bpp one — fine for a 400x400 test, but full-panel 1bpp would want
        the same chunked-write speedup treatment before relying on it for real page turns.

### Later milestones (not yet scoped in detail)
- [ ] Storage (SD card / file system) for book files
- [ ] Page rendering / text layout
- [ ] Ebook format parsing (EPUB/TXT)
- [ ] UI / input handling
- [ ] Power management / battery life
