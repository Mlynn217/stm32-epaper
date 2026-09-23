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
- [x] **`EPD_IT8951_Clear_Refresh()`'s stdlib `malloc`/`free` usage — checked and fixed.** This
      project's newlib/FreeRTOS integration provides **no** heap locking at all: `Core/Src/sysmem.c`'s
      `_sbrk()` (newlib's only allocation primitive here) has no critical section/mutex around the
      heap-end bump, `Core/Inc/FreeRTOSConfig.h` doesn't set `configUSE_NEWLIB_REENTRANT`, and there
      are no `__malloc_lock`/`__malloc_unlock` hooks anywhere in the repo — so concurrent newlib
      `malloc`/`free` calls from more than one task genuinely would race and could corrupt the heap.
      In *current* practice this specific call was never actually exercised: `grep` found no call
      sites anywhere in the app (only the function's own definition/declaration), and the app only
      ever runs one FreeRTOS task (`StartDefaultTask`) regardless. Fixed anyway rather than leaving a
      footgun for whoever wires it in next: `EPD_IT8951_Clear_Refresh()` was the *only* one of the
      `*_Refresh` family that allocated its own scratch buffer internally — every sibling
      (`1bp`/`2bp`/`4bp`/`8bp_Refresh`) already takes `Frame_Buf` as a caller-supplied parameter.
      Brought `Clear_Refresh` in line with that existing convention instead of introducing a static
      buffer: it now takes `UBYTE* Frame_Buf` as its first parameter (matching the others) and just
      `memset`s it to `0xFF`, with no heap involved at all
      (`Drivers/IT8951/e-Paper/EPD_IT8951.c/h`). A static buffer wasn't viable here anyway — this
      panel's clear buffer is ~758KB (`1448*4/8 * 1072`), far too big for the F469's 384KB internal
      SRAM; a caller-supplied SDRAM buffer (e.g. the existing `fullImgBuf`/`SDRAM_BASE_ADDR` frame
      buffer in `main.c`) is the only buffer big enough anyway, and this way the driver doesn't need
      its own hardcoded SDRAM address alongside `main.c`'s existing partitioning scheme. **Validated
      on real hardware**: temporarily called it from `StartDefaultTask` right after `EPD_IT8951_Init()`
      (passing `fullImgBuf`, `GC16_Mode`), reflashed, confirmed via serial log a clean 9279ms run
      (consistent with previously logged full-panel GC16 timings) with no fault/hang, followed by
      both book pages rendering and displaying correctly exactly as before — then reverted the temp
      call (consistent with this project's practice of not leaving one-off bring-up test code
      permanently wired into boot, see the "Removed the boot-time visual demo/bring-up blocks" entry
      below) and reflashed again to confirm the board returns to its normal boot sequence
      byte-for-byte. Didn't get a webcam photo of the mid-test blank-white state specifically (camera
      was blocked by someone in frame at the time) — the serial-log evidence (successful completion,
      correct timing, no corruption in the pages rendered immediately afterward) was judged sufficient
      for what is a heap-safety fix with no change to rendered output.
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
- [x] **Plain-text (.txt) file reading from the SD card — confirmed on real hardware.** Replaces the
      embedded test string with a real file-read -> paginate -> render pipeline.
  - [x] Partitioned SDRAM into two regions (`Core/Src/main.c`, `USER CODE BEGIN PD`):
        `SDRAM_BASE_ADDR` for the IT8951 frame buffer (as before, max ~776KB for this panel at 4bpp)
        and `TEXT_BUFFER_BASE` (1MB in, 4MB capacity) for file content - comfortably more than any
        plain-text book needs, with headroom between the two regions.
  - [x] On boot, checks for `ALICE.TXT` on the SD card (`f_stat`); if missing, seeds it by writing
        the same public-domain "Alice's Adventures in Wonderland" excerpt used in the earlier
        embedded-string test, then always reads back whatever is actually on the card into the text
        buffer (`f_read`, null-terminated) - so a real book just has to replace/append to this file by
        any means (there's no way yet to copy an arbitrary file onto this physically-connected card
        from the dev host - USB mass storage mode or a card reader would do it, not implemented) and
        the read/paginate path underneath doesn't change.
  - [x] Test: **confirmed on real hardware**. First boot: "ALICE.TXT not found, seeding... (1328
        bytes)" -> wrote -> read back 1328 bytes -> paginated identically to the earlier embedded-
        string test (982 chars page 1, 346 chars page 2). Then did a board reset (no reflash) to
        confirm persistence: second boot went straight to "read 1328 bytes from ALICE.TXT" with no
        re-seed message - the file genuinely persisted on the SD card, not just in RAM.
  - [ ] Not yet done: reading files larger than fit in one `f_read` call / streaming a file too big
        for the 4MB text buffer (not a concern for typical plain-text books, but worth remembering
        before assuming any file "just works")
  - [x] Turns out there already is a way to get a real file onto this card: a card reader on the dev
        host, used directly (not USB mass storage mode from the firmware) — a real EPUB
        (`Mistborn...epub`, 731718 bytes) showed up on the card this way. USB mass storage mode is
        still worth having eventually (load a book without pulling the card), but isn't the only
        option as previously assumed.
- [x] **SD card directory listing — confirmed on real hardware.** Added a root-directory listing
      (`f_opendir`/`f_readdir`/`f_closedir`) right after the mount/free-space printout in `main.c`,
      so what's actually on the card is visible in the serial log without pulling it. Test: showed
      `EPTEST.TXT` (27 bytes), `ALICE.TXT` (1328 bytes), and the real EPUB the user copied on via a
      card reader — `MISTBO~1.EPU` (731718 bytes).
  - [x] **Long filename (LFN) support added** — the 8.3-only caveat above is fixed. Set
        `_USE_LFN=3` in `ffconf.h` (heap-based working buffer, not `1`/static-BSS or `2`/stack - `3`
        is the only one of the three that's actually thread-safe per FatFs's own docs, and this
        project's vendored FatFs already had everything wired up for it: `_FS_REENTRANT=1`, plus
        `ff_memalloc()`/`ff_memfree()` in `Middlewares/.../FatFs/src/option/syscall.c` - only compiled
        in when `_USE_LFN==3` - forwarding to `ff_malloc`/`ff_free`, already `#define`'d at the bottom
        of `ffconf.h` as FreeRTOS's `pvPortMalloc`/`vPortFree`. All of that was sitting there unused
        with `_USE_LFN=0`.) Also had to vendor two more FatFs option-package files that weren't
        already in the repo: `option/unicode.c` and the `option/ccsbcs.c` it `#include`s for
        single-byte code pages (ours is `_CODE_PAGE=850`) - `ff.c` needs their `ff_convert()`/
        `ff_wtoupper()` whenever LFN is on (link failure without them). Copied both from the cached
        `STM32Cube_FW_F4_V1.28.3` package (confirmed identical FatFs revision, R0.12c, to what's
        already vendored here). Added `unicode.c` to the top-level `CMakeLists.txt`, not
        `cmake/stm32cubemx/CMakeLists.txt`'s `FatFs_Src` list - that list is CubeMX-generated and
        would silently drop it on the next regeneration (the same class of problem as the SPI1
        prescaler regression above), so it goes wherever this project's other hand-added sources
        already live instead.
  - [x] Test: **confirmed on real hardware**. Directory listing now shows the real EPUB title -
        `Mistborn_ Secret History.epub` (731718 bytes) - instead of the truncated `MISTBO~1.EPU`.
        Rest of boot sequence (SDRAM test, SD read/write test, ALICE.TXT read, page layout/
        pagination) unaffected - identical page 1/2 split as before.
- [x] **Removed the boot-time visual demo/bring-up blocks** (black/white flash-clear, full-panel
      16-level gradient, A2 mode 400x400 toggle test) from `main.c` — they'd already served their
      purpose validating the write path (see the full-panel-writes debugging story above) and were
      just adding ~20s of boot time and log noise before the real content (book pages) rendered.
      Each page in the layout loop already clears to white before drawing, so no ghosting-mitigation
      behavior was lost. Confirmed on real hardware: boot to first page displayed dropped from
      ~26s to ~10s, page content unchanged (verified via webcam capture, byte-for-byte identical
      page 1/2 split as before the cleanup). SDRAM test and the EPTEST.TXT SD read/write check were
      kept (silent correctness checks, not visual demos).
- [x] **EPUB parsing — confirmed on real hardware with a real book.** A minimal ZIP reader + DEFLATE
      decompressor + tiny XML/HTML helpers, enough to pull a chapter's plain text out of a real
      `.epub` and feed it into the existing page-layout pipeline. New modules, all in
      `Drivers/Epub/` and `Drivers/Inflate/`:
  - [x] `Drivers/Inflate/puff.c/h` — vendored Mark Adler's reference DEFLATE decompressor (zlib
        license, from `madler/zlib`'s `contrib/puff`) rather than writing one from scratch.
  - [x] `EPUB_Zip.c/h` — minimal ZIP central-directory reader: locates the End Of Central
        Directory record, walks central directory entries, extracts a named entry's data (stored
        or deflated via `puff()`). Decoupled from any file API via an `EPUB_IO` struct
        (read/size/reset callbacks) so it's usable against a real file or, as it turned out,
        plain memory.
  - [x] `EPUB_Xml.c/h` — tiny attribute/tag scanner (find a tag by name respecting word
        boundaries, find its closing `>`, extract an attribute value) plus entity/UTF-8-smart-
        punctuation decoding - not a general XML parser, just enough for EPUB's fixed
        `container.xml`/OPF structure.
  - [x] `EPUB_Html.c/h` — XHTML-to-plain-text: strips tags, discards `<script>`/`<style>`/`<title>`
        element content, decodes entities and literal UTF-8 smart punctuation (curly quotes/dashes/
        ellipsis - ASCII-folded since this project's fonts are ASCII-only, ISO Latin accented
        letters are dropped), inserts paragraph breaks at block-tag boundaries.
  - [x] `EPUB_Book.c/h` — orchestration: parses `META-INF/container.xml` for the OPF path, the
        OPF's manifest+spine for reading order, extracts+converts any chapter to plain text on
        demand; also grabs `<dc:title>` for display.
  - [x] Native test harness (`tools/`-style, run on this dev machine, not the firmware) validated
        all of the above against a synthetic EPUB (Python `zipfile`, mixed stored/deflated entries)
        before ever touching hardware - caught two real bugs cheaply (script/style content leaking
        because skip-mode wasn't checked for plain text between tags, and `<title>` swallowing
        the rest of the document - see below) that would have been much slower to find via
        flash-and-check cycles.
  - [x] **Real, deep hardware bug found and fixed**: reading the actual EPUB (`Mistborn: Secret
        History`, 731718 bytes, 72 zip entries) via repeated `f_lseek()`+`f_read()` calls at
        different offsets on the same open FatFs file handle reliably returned stale/wrong data -
        specifically, alternating between reads near the end of the file (ZIP central directory)
        and reads near the beginning (actual entry data, e.g. `OEBPS/content.opf`'s local header)
        would corrupt the earlier-file read in a way that was stable/reproducible (not random) but
        depended on prior access history. Diagnosed by cross-checking extracted bytes against
        Python's own `zlib`/`zipfile` (same failure = not a decompressor bug) and against the
        *original* file directly (`/home/michael/Downloads/Mistborn_ Secret History.epub`, same
        size, byte-identical central directory - so not SD-copy corruption either). Neither closing
        + reopening the FatFs file handle nor a full `f_mount()` remount fixed it (both tested,
        both reproduced the identical failure) - ruling out both FatFs's file-level and volume-
        level state. **Fix**: since the whole file (a few hundred KB - a few MB for a typical book)
        comfortably fits in the 16MB of SDRAM, load it once via a single sequential `f_read()` at
        open time and have `EPUB_IO` operate on that in-RAM copy for everything afterwards - no
        more repeated FatFs seeks, so nothing left to go stale. Confirmed on hardware: correct ZIP/
        OPF parsing immediately after this change (`Title="Mistborn: Secret History" Chapters=40`).
        Root cause not fully isolated beyond "not FatFs's own file/volume-level caches" - could be
        the SDIO/DMA driver layer or FatFs's cluster-chain-walking in `f_lseek()` - not pursued
        further since the workaround is simple, robust, and well within the RAM budget.
  - [x] **Two more real bugs found via the actual book file** (native tests didn't cover these -
        both are real-world EPUB-producer quirks the synthetic test didn't happen to include until
        added afterward): (1) self-closing `<title/>` (empty per-chapter title, common in
        Calibre-produced books) was treated the same as `<title>...</title>`, so skip-mode entered
        and never saw the (nonexistent) closing tag - silently swallowing the rest of the chapter.
        Fixed by detecting self-closing tags and not entering skip-mode for them. (2) Real body
        text uses literal UTF-8 smart-quote/dash/ellipsis characters, not HTML entities - manifested
        as blank gaps where every apostrophe should be. Fixed by adding `EPUB_DecodeUtf8SmartPunct`
        (same ASCII-folding as the entity decoder, for the equivalent raw UTF-8 sequences).
  - [x] Test: **confirmed on real hardware via webcam capture** - a genuine page of the real book's
        Preface, correctly word-wrapped/paginated, title heading reading "Mistborn: Secret History
        (2/4)", body text clean and correctly punctuated ("anything I've done before", "it's finally
        time", "three years' time").
  - [ ] Not yet done: only the first chapter with >50 characters of text is shown (skips
        cover/title/copyright-style apparatus pages automatically, but there's no real page-turn/
        chapter-navigation UI yet - see below); accented Latin letters and any other non-ASCII
        character without a specific fold are silently dropped rather than transliterated; only
        tested against one real book so far.
- [ ] UI / input handling — physical input (encoder, cap touch, button) and the navigation state
      machine are both not started; see the Custom PCB section below for the current draft input
      hardware (CAP1188 cap touch for prev/next, PEC11R encoder for menu scroll/select, tactile power
      button) — testing this now on the Discovery board with a Bourns PEC11R-4215F-S0024 encoder and
      an Adafruit CAP1188 breakout (ordered 2026-09-22), so this hardware choice gets validated
      before the PCB locks it in
- [ ] Power management / battery life — key lever is deep-sleep between page turns (STOP mode,
      SDRAM either in self-refresh or fully powered down and repopulated from SD on wake), not
      rendering speed — the IT8951 holds the displayed image with zero host involvement once a
      refresh completes

### Custom PCB (in progress — Power sheet drafted; choices still open to change)
See README.md's [Custom PCB (Planned)](README.md#custom-pcb-planned) section for the part list,
power tree, board scope and alternatives considered. **BoM review done 2026-09-22.** Decisions:
- v1 keeps the Waveshare HAT external on an SPI connector; the bare IT8951 moves to a later revision.
- TPS63070 → TPS63802 (starts from 1.8 V instead of 3.0 V; 11 µA quiescent instead of 50 µA).
- MAX17222 → TPS63900 (the MAX17222 is boost-only and can't regulate a 3.65 V cell down to 3.3 V).
- STM32F469IIT6 (LQFP176); W25Q128JV QSPI flash; PEC11R-4215F-S0024 encoder (24 detents).
- Layered undervoltage protection added (see README "Battery protection").
- Corrections: the IS42S16400J is 8 MB, not 16 MB. The bare IT8951 needs a 1.8 V core supply
  with a power-up order, a crystal and a waveform flash.

Next steps, in order:
- [x] **KiCad schematic — power sheet** — drafted 2026-09-22 in `hardware/kicad/power.kicad_sch`,
      then revised after the BoM review (README "Power Sheet (drafted in KiCad)" has the design
      decisions). ERC reports 0 violations, and `hardware/scripts/check_power_netlist.py` confirms all
      34 nets against the intended connectivity. **Not yet reviewed by a human, simulated or
      built.** Open items on it:
  - [ ] **TPS63802 footprint** — TI's DLA (VSON-HR 10, 1.4×2.3 mm HotRod) isn't in KiCad's stock
        library. Make it from TI's land pattern (or Ultra Librarian) and assign it to U2. (The
        reserved TPS63900 uses the stock `WSON-10-1EP_2.5x2.5mm` footprint, drawn for TI's DSK
        package; check it against the TPS63900 datasheet's DSK0010A drawing.)
  - [ ] **Inductors** — L1 is 0.47 µH DFE201612E (from TI's recommended list, 5.5 A saturation) on
        the stock 2016 footprint, which needs checking against the part's land pattern. L2 is a
        placeholder DFE201610P 1 µH; check its saturation current against the TPS61023's 3.7 A
        limit. L3 (TPS63900, DNP) is still to be chosen.
  - [ ] **Undervoltage cutoff thresholds** — R6/R15 = 1.8M/1.0M on TPS63802 EN (off below ~2.80 V,
        on above ~3.08 V). Check against the chosen cell's datasheet, and check that the ~3.08 V
        turn-on doesn't cause restart cycling as a nearly empty cell recovers after load
        is removed.
  - [ ] **Firmware battery measurement + graceful shutdown** — read the cell through the STM32's
        internal VBAT ADC channel (VBAT_RTC, one Schottky drop below the cell; calibrate the offset).
        At ~3.0 V: save state, draw a "please charge" screen, enter standby.
  - [ ] **Choose the cell** — capacity and format; prefer an LFP cell **with a protection board**
        (the only true disconnect for over-discharge and shorts). Charge current R_PROG follows
        from it.
  - [ ] **Soft power / EN control** — TPS63802 EN is currently just the undervoltage divider. The
        power-button scheme (if the button should cut the rail, not just wake the MCU) has to
        combine with it.
  - [ ] **TPS63900 EN (v2)** — its EN is a plain logic input (no precise threshold), so when the
        always-on rail is fitted it needs its own undervoltage cutoff.
  - [ ] **Battery connector polarity** — J2 pin 1 = +. LFP pouch cells with JST-PH leads aren't
        consistent; confirm against the actual cell.
  - [ ] **USB-C shield** — tied straight to GND for now; decide on an RC/ferrite.
  - [ ] **Fuel gauge** — LFP's flat voltage curve makes voltage-based charge estimates nearly
        useless, so a real % gauge needs coulomb counting. MAX17261 (in KiCad's stock library) is
        a candidate; check its LFP support. Firmware VBAT reading is enough for the cutoff, not
        for a % display.
  - [ ] **No cold-charge protection** — the MCP73123 has no thermistor input. Accept that (indoor
        device), or add firmware gating via `PROG` (a floating PROG disables charging) plus a
        temperature sensor.
      Gotcha found while building it: a **hidden `power_in` pin in a KiCad symbol creates an
      implicit global net named after the pin**. The first draft's stacked duplicate VIN pins
      silently shorted VSYS to +3V3. Only the netlist check caught it; ERC just printed a
      "multiple net names" warning. Stacked duplicates must be hidden *passive* pins, as the stock
      libraries do.
- [ ] **KiCad — MCU sheet** (STM32F469IIT6 LQFP176, 8 MHz HSE + 32.768 kHz crystals, IS42S16400J
      SDRAM via FMC, W25Q128JV via QSPI, microSD via SDIO, USB OTG_FS, SWD via TC2050). Power the
      MCU from `3V3_AON` (see the Power sheet). Check the LQFP176 pin budget in CubeMX first.
- [ ] **KiCad — peripheral sheet** (Waveshare HAT connector: SPI + HRDY + RST + 5V + GND;
      CAP1188 + side-wall electrode pads; PEC11R encoder; power button; ESD on anything
      user-touchable).
- [ ] **Firmware — input handling**: encoder (CLK/DT interrupt, SW GPIO), CAP1188 (I²C init +
      interrupt handler), power button (WKUP EXTI); wire all three to a simple event queue.
- [ ] **Firmware — navigation state machine**: page-turn events → next/prev page via the existing
      pagination API; chapter jump; library screen listing books from the SD card.
