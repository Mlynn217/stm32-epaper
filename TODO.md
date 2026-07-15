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
- [x] **CubeMX regeneration regression discovered + patched**: regenerating for the SDIO DMA/NVIC
      config (below) silently reverted `hspi1.Init.BaudRatePrescaler` from `/16` back to CubeMX's
      own default `/2` (45MHz, over the IT8951's 24MHz max) — even though we'd "fixed" this twice
      before, including editing the `.ioc`'s own `SPI1.CalculateBaudRate` field, which apparently
      doesn't reliably round-trip through CubeMX's GUI model. Symptom was very distinctive: every
      value read back from `EPD_IT8951_GetSystemInfo()` was exactly right-shifted by one bit
      (`1448→724`, `1072→536`, garbled FW/LUT strings) — a clean bit-shift pattern, not random
      noise, which is what pointed at an SPI clock/timing issue rather than a logic bug. Reproduced
      identically across a manual reset and a full reflash before being traced to the prescaler.
      Fixed with `scripts/patch-cubemx.sh`, wired into `CMakeLists.txt` via `execute_process` at
      configure time — checks/re-applies known CubeMX regressions on every `cmake --preset`,
      idempotent (only touches the file when a fix is actually needed, so no spurious rebuilds).
      Tested: deliberately reverted the prescaler, ran `cmake --preset Debug`, confirmed it
      self-healed.
  - [x] Also did the "proper" fix at the source: CubeMX → SPI1 → Configuration → Parameter
        Settings → Prescaler for Baud Rate → `16`, set directly in the GUI rather than hand-editing
        the `.ioc` text (which hadn't reliably round-tripped before). The `.ioc` now tracks an
        explicit `SPI1.BaudRatePrescaler` key that wasn't present before, and `patch-cubemx.sh` is a
        confirmed no-op against the regenerated `main.c` — reflashed and confirmed on real hardware
        that the IT8951 still reads back correctly (`Panel=1448x1072 FWVer=SWv_0.6.
        LUTVer=M841_TFAB512`) after this regeneration.

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

### Storage
- [x] SD card + FatFS — **confirmed on real hardware**: mount, write, and read-back verified
      byte-for-byte on a real SD card (`SD mount OK`, `SD card: 15263 MB total, 15263 MB free`,
      wrote 27 bytes, read back 27 bytes, content matched). Two gaps found and fixed:
  - [x] **No DMA/interrupt configured for SDIO at all** — `sd_diskio.c` calls
        `BSP_SD_ReadBlocks_DMA`/`WriteBlocks_DMA`, which need a DMA channel and the SDIO interrupt
        enabled to signal completion, but CubeMX never generated either (same class of gap as the
        SDRAM JEDEC sequence: peripheral basics configured, but not everything the actual driver
        needs). Fixed via CubeMX: Connectivity → SDIO → DMA Settings → added a DMA request
        (auto-assigned DMA2_Stream3) → NVIC Settings → enabled SDIO global interrupt → regenerated;
        CubeMX correctly auto-generated `SDIO_IRQHandler`/`DMA2_Stream3_IRQHandler` on its own.
        Side effect of this regeneration: silently reverted the SPI1 clock fix (see the CubeMX
        regeneration regression entry above) — reflashing after any CubeMX regen and checking the
        panel still initializes correctly is worth doing as a habit.
  - [x] **8.3 filenames required** — `ffconf.h` has `_USE_LFN=0` (long filenames disabled), so a
        base filename over 8 characters (e.g. `epaper_test.txt`) fails with `FR_INVALID_NAME`
        (FRESULT 6). Fixed by using `EPTEST.TXT` for the test; worth remembering for real ebook
        filenames later, unless LFN gets enabled.
### Rendering
- [x] **Font rendering — first step confirmed on real hardware.** Decided against a runtime outline
      rasterizer (stb_truetype/FreeType): an e-reader only needs a handful of fixed sizes, so baking
      glyphs offline costs nothing and keeps render time (and therefore awake/battery time — see
      below) minimal and predictable. Also decided against pulling in LVGL's AA font pipeline for
      now — real quality upgrade, but more moving parts (LVGL font descriptor structs + `lv_font_conv`
      tooling) for a first pass.
  - [x] Vendored the plain `sFONT`-format bitmap fonts from the companion repo
        (`~/git/epaper/stm32f469i-disco-lvgl-demo/Utilities/Fonts/font{8,12,16,20,24}.c` — classic ST
        BSP format, 1bpp fixed-width glyph tables, no AA, no external tooling) into
        `Drivers/Fonts/` in this repo (all 5 sizes copied; `fonts.h`'s `LINE()` macro dropped since
        it depended on `BSP_LCD_GetFont()`, not applicable here)
  - [x] Wrote `Drivers/Fonts/EPD_Text.c/h`: `EPD_Text_DrawChar`/`DrawString` walk each glyph's row
        bitmap (MSB-first, `(Width+7)/8` bytes/row) and set the corresponding 4bpp nibble in the
        SDRAM framebuffer via a `SetPixel4bpp` read-modify-write helper (needed since the IT8951's
        4bpp packing is 2 pixels/byte — P0 low nibble/even x, P1 high nibble/odd x, same convention
        established by the gradient test)
  - [x] Test: rendered "Hello, e-paper!" (Font24) plus two lines of Font12 (an a-z/A-Z/0-9 sweep) into
        the SDRAM buffer, GC16 refresh — **confirmed on real hardware via webcam capture**, legible,
        rest of panel stayed clean white, no artifacts
  - [ ] **Observed, not yet addressed**: these BSP fonts were designed for small low-res TFTs, and at
        this panel's ~300 PPI they render physically small (Font24, the largest available, is
        legible but far from a comfortable reading size) — real body text will need either much
        larger bitmap fonts baked at this resolution, or the AA/`lv_font_conv` route below sized
        appropriately; worth deciding once page layout (line wrapping, margins) is in place and an
        actual target reading size is picked
- [x] **Proper anti-aliased fonts at reading-appropriate sizes — confirmed on real hardware.**
      Went with a custom lightweight format instead of LVGL's font pipeline (avoids a Node.js/
      `lv_font_conv` dependency; this project has no other Node tooling):
  - [x] `tools/gen_font.py` — Python/Pillow script that rasterizes a real TTF/OTF at a given pixel
        size (Pillow's built-in FreeType text rendering gives 8-bit AA coverage per pixel for free),
        quantizes to 4 bits (0=no ink, 15=full ink, matching the panel's 16 GC16 gray levels), packs
        2px/byte (same nibble convention as everywhere else: low nibble=even x, high nibble=odd x),
        and emits a ready-to-compile `.c` file. Proportional per-glyph widths (from the font's real
        advance metrics), not forced monospace — matters for a serif face to look right. Re-run this
        script to add sizes/typefaces; the generated `.c` files are not meant to be hand-edited.
  - [x] Typeface: **Liberation Serif** (Regular + Bold), SIL Open Font License 1.1, already installed
        system-wide (`fonts-liberation` package) — avoided introducing a new font download/dependency
        and its license permits embedding the rasterized glyph data in firmware. Attribution belongs
        in the README if a license file gets added to the repo.
  - [x] Generated three sizes into `Drivers/Fonts/`: `Font32` (Regular, 32px/36px line height),
        `Font44` (Regular, 44px/50px line height, the intended default body-text size), `Font60Bold`
        (Bold, 60px/67px line height, headings/chapter titles) — chosen against the earlier finding
        that the sFONT sizes (max 24px) were too small for comfortable reading at this panel's
        ~300 PPI; these are large enough to read normally in a hardware photo at arm's length.
  - [x] Added `EPD_FontAA.h` (glyph/font struct definitions for this format, separate from the plain
        sFONT structs) and `EPD_Text_DrawCharAA`/`DrawStringAA` in `EPD_Text.c/h` — per-pixel linear
        blend between fg/bg nibble by ink coverage (`bg + coverage*(fg-bg)/15`), which is what makes
        the AA edges look smooth instead of the old hard on/off bit test used for sFONT.
  - [x] Test: rendered the same string at all three sizes plus a "Chapter One"-style heading —
        **confirmed on real hardware via webcam capture**, clean smooth serif letterforms, correct
        proportional spacing, no artifacts; visually a clear step up from the bilevel sFONT test.
  - [ ] Not yet covered: only printable ASCII (0x20-0x7E) — real book text will eventually want
        curly quotes/em-dash/ellipsis (Latin-1 range) from `gen_font.py`, plus Italic weights if
        wanted
  - [ ] Floyd-Steinberg (below) could still apply here as an optional refinement — dithering AA
        glyph-edge coverage down to the 16 gray levels instead of direct quantization — but plain
        4-bit quantization already looks clean at these sizes, so not pursuing unless it's actually
        needed
- [x] **Page layout (word wrap + pagination) — confirmed on real hardware.**
  - [x] Added `Drivers/Fonts/EPD_Layout.c/h`: `EPD_Layout_DrawParagraph()` word-wraps text into a
        given rectangle (greedy wrap - measures each word via the new `EPD_Text_MeasureCharAA`/
        `MeasureSubstringAA` helpers in `EPD_Text.c/h` before committing pixels, breaks to a new
        line when the word wouldn't fit, drops the leading space after a wrap). Draws word-by-word
        directly (no intermediate line buffer/string copy needed). `'\n'` in the source text forces
        a paragraph break. Words wider than the available width are drawn as-is (not
        hyphenated/clipped) - acceptable for now, no real prose hits this.
  - [x] **Pagination via a continuation pointer**: `EPD_Layout_DrawParagraph()` returns a pointer
        into the input text where it stopped (because the next line wouldn't fit above the bottom
        margin), or `NULL` if all the text was drawn. This lets a caller paginate through arbitrarily
        long text one screen at a time - re-call with the returned pointer for the next page -
        without laying out (or holding in memory) more than one page at a time. Important for later
        reading a whole book off the SD card without needing the full text resident in RAM.
  - [x] Test: rendered the opening ~1300 characters of "Alice's Adventures in Wonderland" (public
        domain, embedded as a test string in `main.c`) with a bold "Chapter I (n/4)" heading
        (`Font60Bold`) + wrapped body text (`Font44`), looping on the continuation pointer —
        **confirmed on real hardware via webcam capture**: page 1 consumed 982 characters before
        running out of vertical room, page 2 consumed the remaining 346 and reported "all text
        drawn"; visually, page 2 correctly resumes mid-sentence with no word cut across the page
        break, clean word wrap throughout, no artifacts. This is the first genuinely book-page-like
        render in the project.
  - [ ] Not yet done: centered/justified text (current is left-aligned/ragged-right only),
        paragraph indentation or blank-line spacing beyond what `\n\n` already gives, hyphenation for
        oversized words, RTL/multi-column layouts (not needed for this project's scope)
- [ ] **Floyd-Steinberg dithering — filed for later image/cover-art rendering.** Needed when source
      image data doesn't already come as clean grayscale/16-level data (e.g. photos, book cover art,
      anything with more tonal range than the panel's 16 GC16 gray levels, or content going to 1bpp
      for A2 fast-refresh mode) — classic error-diffusion kernel (7/16, 3/16, 5/16, 1/16 to
      right/below-left/below/below-right neighbors) approximates continuous tone as a static dot
      pattern, which suits e-paper well since there's no motion/flicker to reveal the pattern. Not
      needed for plain bitmap-font text (see above) or for any source image that's already
      pre-quantized to grayscale — only add this step when an image's tonal range actually exceeds
      what the panel can represent directly.
- [ ] Ebook format parsing (EPUB/TXT)
- [ ] UI / input handling
- [ ] Power management / battery life — key lever is deep-sleep between page turns (STOP mode,
      SDRAM either in self-refresh or fully powered down and repopulated from SD on wake), not
      rendering speed — the IT8951 holds the displayed image with zero host involvement once a
      refresh completes
