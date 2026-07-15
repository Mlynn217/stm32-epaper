#include "EPD_Layout.h"
#include "EPD_Text.h"
#include <stddef.h>

const char *EPD_Layout_DrawParagraph(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                                      uint16_t left, uint16_t top, uint16_t right, uint16_t bottom,
                                      const char *text, const EPD_FontAA *font,
                                      uint8_t fgNibble, uint8_t bgNibble, uint16_t lineSpacing)
{
  uint16_t lineHeight = (uint16_t)(font->height + lineSpacing);
  uint16_t cursorX = left;
  uint16_t cursorY = top;
  const char *p = text;

  if ((uint16_t)(cursorY + font->height) > bottom)
  {
    /* No room for even one line - nothing drawn, resume here. */
    return text;
  }

  while (*p != '\0')
  {
    if (*p == '\n')
    {
      p++;
      cursorX = left;
      cursorY = (uint16_t)(cursorY + lineHeight);
      if ((uint16_t)(cursorY + font->height) > bottom)
      {
        return p;
      }
      continue;
    }

    /* Drop leading spaces at the start of a line - either the very first
       line or right after a wrap/explicit break. */
    if (*p == ' ' && cursorX == left)
    {
      p++;
      continue;
    }

    const char *wordStart = p;
    while (*p != '\0' && *p != ' ' && *p != '\n')
    {
      p++;
    }
    uint32_t wordLen = (uint32_t)(p - wordStart);
    uint16_t wordWidth = EPD_Text_MeasureSubstringAA(wordStart, wordLen, font);
    uint16_t spaceWidth = (cursorX != left) ? EPD_Text_MeasureCharAA(' ', font) : 0;

    if (cursorX != left && (uint16_t)(cursorX + spaceWidth + wordWidth) > right)
    {
      /* Word doesn't fit on this line - wrap first, then place it (or, if
         there's no vertical room left either, stop here so the caller can
         resume this exact word on the next page). */
      cursorX = left;
      cursorY = (uint16_t)(cursorY + lineHeight);
      if ((uint16_t)(cursorY + font->height) > bottom)
      {
        return wordStart;
      }
    }
    else if (cursorX != left)
    {
      cursorX = EPD_Text_DrawCharAA(buf, stride, bufW, bufH, cursorX, cursorY, ' ', font,
                                     fgNibble, bgNibble);
    }

    for (uint32_t i = 0; i < wordLen; i++)
    {
      cursorX = EPD_Text_DrawCharAA(buf, stride, bufW, bufH, cursorX, cursorY, wordStart[i],
                                     font, fgNibble, bgNibble);
    }

    if (*p == ' ')
    {
      p++;
    }
  }

  return NULL;
}
