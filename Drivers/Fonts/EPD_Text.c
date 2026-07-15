#include "EPD_Text.h"

static void SetPixel4bpp(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                          uint16_t x, uint16_t y, uint8_t value)
{
  if (x >= bufW || y >= bufH)
  {
    return;
  }

  uint32_t byteIndex = (uint32_t)y * stride + (x / 2);
  if ((x & 1) == 0)
  {
    buf[byteIndex] = (uint8_t)((buf[byteIndex] & 0xF0) | (value & 0x0F));
  }
  else
  {
    buf[byteIndex] = (uint8_t)((buf[byteIndex] & 0x0F) | ((value & 0x0F) << 4));
  }
}

void EPD_Text_DrawChar(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                        uint16_t x, uint16_t y, char c, const sFONT *font,
                        uint8_t fgNibble, uint8_t bgNibble, bool drawBackground)
{
  /* sFONT tables cover the printable ASCII range starting at ' ' (0x20). */
  if (c < ' ' || c > '~')
  {
    c = ' ';
  }

  uint16_t glyphIndex = (uint16_t)(c - ' ');
  uint16_t bytesPerRow = (uint16_t)((font->Width + 7) / 8);
  uint32_t glyphBytes = (uint32_t)bytesPerRow * font->Height;
  const uint8_t *glyph = font->table + (uint32_t)glyphIndex * glyphBytes;

  for (uint16_t row = 0; row < font->Height; row++)
  {
    for (uint16_t col = 0; col < font->Width; col++)
    {
      uint8_t rowByte = glyph[row * bytesPerRow + (col / 8)];
      bool bitSet = (rowByte & (0x80 >> (col % 8))) != 0;

      if (bitSet)
      {
        SetPixel4bpp(buf, stride, bufW, bufH, (uint16_t)(x + col), (uint16_t)(y + row), fgNibble);
      }
      else if (drawBackground)
      {
        SetPixel4bpp(buf, stride, bufW, bufH, (uint16_t)(x + col), (uint16_t)(y + row), bgNibble);
      }
    }
  }
}

void EPD_Text_DrawString(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                          uint16_t x, uint16_t y, const char *str, const sFONT *font,
                          uint8_t fgNibble, uint8_t bgNibble, bool drawBackground)
{
  uint16_t cursorX = x;

  for (const char *p = str; *p != '\0'; p++)
  {
    EPD_Text_DrawChar(buf, stride, bufW, bufH, cursorX, y, *p, font, fgNibble, bgNibble,
                       drawBackground);
    cursorX = (uint16_t)(cursorX + font->Width);
  }
}

uint16_t EPD_Text_DrawCharAA(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                              uint16_t x, uint16_t y, char c, const EPD_FontAA *font,
                              uint8_t fgNibble, uint8_t bgNibble)
{
  if (c < (char)font->firstChar || c > (char)font->lastChar)
  {
    c = ' ';
  }

  uint16_t glyphIndex = (uint16_t)(c - (char)font->firstChar);
  const EPD_GlyphAA *glyph = &font->glyphs[glyphIndex];
  uint16_t bytesPerRow = (uint16_t)((glyph->width + 1) / 2);

  for (uint16_t row = 0; row < font->height; row++)
  {
    for (uint16_t col = 0; col < glyph->width; col++)
    {
      uint8_t packedByte = glyph->bitmap[row * bytesPerRow + (col / 2)];
      uint8_t coverage = (col & 1) == 0 ? (packedByte & 0x0F) : (packedByte >> 4);

      /* Linear-interpolate between background and foreground by ink
         coverage (0=background, 15=foreground), rather than a hard on/off
         bit as in the plain sFONT path above - this is what makes the AA
         edges look smooth instead of jagged at these larger point sizes. */
      int16_t blended = (int16_t)bgNibble +
                         (((int16_t)coverage * ((int16_t)fgNibble - (int16_t)bgNibble)) / 15);

      SetPixel4bpp(buf, stride, bufW, bufH, (uint16_t)(x + col), (uint16_t)(y + row),
                   (uint8_t)blended);
    }
  }

  return (uint16_t)(x + glyph->width);
}

uint16_t EPD_Text_DrawStringAA(uint8_t *buf, uint32_t stride, uint16_t bufW, uint16_t bufH,
                                uint16_t x, uint16_t y, const char *str, const EPD_FontAA *font,
                                uint8_t fgNibble, uint8_t bgNibble)
{
  uint16_t cursorX = x;

  for (const char *p = str; *p != '\0'; p++)
  {
    cursorX = EPD_Text_DrawCharAA(buf, stride, bufW, bufH, cursorX, y, *p, font, fgNibble,
                                   bgNibble);
  }

  return cursorX;
}

uint16_t EPD_Text_MeasureCharAA(char c, const EPD_FontAA *font)
{
  if (c < (char)font->firstChar || c > (char)font->lastChar)
  {
    c = ' ';
  }
  return font->glyphs[(uint16_t)(c - (char)font->firstChar)].width;
}

uint16_t EPD_Text_MeasureSubstringAA(const char *str, uint32_t len, const EPD_FontAA *font)
{
  uint32_t total = 0;
  for (uint32_t i = 0; i < len; i++)
  {
    total += EPD_Text_MeasureCharAA(str[i], font);
  }
  return (uint16_t)total;
}
