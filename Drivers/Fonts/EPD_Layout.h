#ifndef EPD_LAYOUT_H
#define EPD_LAYOUT_H

#include <stdint.h>
#include "EPD_FontAA.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Word-wraps and draws `text` into the rectangle [left,right) x [top,bottom)
   using an anti-aliased font (see EPD_FontAA.h / EPD_Text.h), stopping
   either at the end of the text or when the next line would no longer fit
   above `bottom`. Returns a pointer into `text` where drawing stopped - the
   position a following page should resume from - or NULL if all of `text`
   was drawn. This lets a caller paginate through a text buffer one screen
   at a time without laying out (or even holding in memory) more than one
   page at once.

   lineSpacing is extra pixels of gap between lines, on top of the font's
   own line height. A '\n' in the text forces a line break. Words wider than
   (right-left) are not hyphenated/split - drawn as-is, may overflow past
   `right`. Leading spaces after a wrap are dropped (standard word-wrap
   behavior), matching how text editors/renderers typically handle
   reflowed whitespace. */
const char *EPD_Layout_DrawParagraph(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                                      uint16_t left, uint16_t top, uint16_t right, uint16_t bottom,
                                      const char *text, const EPD_FontAA *font,
                                      uint8_t fgNibble, uint8_t bgNibble, uint16_t lineSpacing);

#ifdef __cplusplus
}
#endif

#endif /* EPD_LAYOUT_H */
