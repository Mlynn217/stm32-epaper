#ifndef EPD_TEXT_H
#define EPD_TEXT_H

#include <stdint.h>
#include <stdbool.h>
#include "fonts.h"
#include "EPD_FontAA.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Blits text into a 4bpp framebuffer (2 pixels/byte - low nibble is the
   even-x pixel, high nibble the odd-x pixel, matching the IT8951's P0/P1
   packing order used elsewhere in this project). fgNibble/bgNibble are
   0-15 grayscale values (0=black, 15=white on this panel). Fonts are the
   plain fixed-width sFONT tables in this directory (vendored from ST's BSP
   Fonts module) - no anti-aliasing, one bit per pixel in the source glyph
   data. */
void EPD_Text_DrawChar(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                        uint16_t x, uint16_t y, char c, const sFONT *font,
                        uint8_t fgNibble, uint8_t bgNibble, bool drawBackground);

void EPD_Text_DrawString(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                          uint16_t x, uint16_t y, const char *str, const sFONT *font,
                          uint8_t fgNibble, uint8_t bgNibble, bool drawBackground);

/* Anti-aliased variants (EPD_FontAA fonts, see EPD_FontAA.h) - each glyph
   pixel stores 0-15 ink coverage, blended per-pixel between fgNibble and
   bgNibble (linear interpolation) rather than drawn as a hard on/off bit.
   Returns the x position immediately after the drawn string (cursor
   advance), useful for laying out runs of mixed-width text. */
uint16_t EPD_Text_DrawCharAA(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                              uint16_t x, uint16_t y, char c, const EPD_FontAA *font,
                              uint8_t fgNibble, uint8_t bgNibble);

uint16_t EPD_Text_DrawStringAA(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                                uint16_t x, uint16_t y, const char *str, const EPD_FontAA *font,
                                uint8_t fgNibble, uint8_t bgNibble);

/* Glyph width lookups (no drawing) - used by EPD_Layout.c to decide word
   wrapping before committing pixels. */
uint16_t EPD_Text_MeasureCharAA(char c, const EPD_FontAA *font);
uint16_t EPD_Text_MeasureSubstringAA(const char *str, uint32_t len, const EPD_FontAA *font);

#ifdef __cplusplus
}
#endif

#endif /* EPD_TEXT_H */
