#include "EPUB_Html.h"
#include "EPUB_Xml.h"
#include <string.h>
#include <stdbool.h>

static bool IsAsciiAlnum(char c)
{
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9');
}

static bool MatchesTagName(const char *name, size_t len, const char *literal)
{
  size_t litLen = strlen(literal);
  if (len != litLen)
  {
    return false;
  }
  for (size_t i = 0; i < len; i++)
  {
    char a = name[i];
    char b = literal[i];
    if (a >= 'A' && a <= 'Z') a = (char)(a - 'A' + 'a');
    if (a != b)
    {
      return false;
    }
  }
  return true;
}

static bool IsBlockTag(const char *name, size_t len)
{
  static const char *const blockTags[] = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "br"
  };
  for (size_t i = 0; i < sizeof(blockTags) / sizeof(blockTags[0]); i++)
  {
    if (MatchesTagName(name, len, blockTags[i]))
    {
      return true;
    }
  }
  return false;
}

static void FlushPending(char *out, size_t outSize, size_t *outPos, bool *pendingParaBreak,
                          bool *pendingSpace, bool anyOutputYet)
{
  if (*pendingParaBreak)
  {
    if (anyOutputYet && *outPos + 2 < outSize)
    {
      out[(*outPos)++] = '\n';
      out[(*outPos)++] = '\n';
    }
    *pendingParaBreak = false;
    *pendingSpace = false;
  }
  else if (*pendingSpace)
  {
    if (anyOutputYet && *outPos + 1 < outSize)
    {
      out[(*outPos)++] = ' ';
    }
    *pendingSpace = false;
  }
}

size_t EPUB_Html_ToPlainText(const char *html, char *out, size_t outSize)
{
  const char *p = html;
  size_t outPos = 0;
  bool pendingSpace = false;
  bool pendingParaBreak = false;
  bool anyOutputYet = false;
  char skipping[8] = { 0 }; /* "script"/"style"/"title" while inside one, else empty */

  while (*p != '\0' && outPos + 1 < outSize)
  {
    /* Discard text content while inside a skipped element - only '<' (a
       potential closing tag) needs a real look; anything else here is
       skipped-element body text, not something a reader should ever see. */
    if (skipping[0] != '\0' && *p != '<')
    {
      p++;
      continue;
    }

    if (*p == '<')
    {
      if (strncmp(p, "<!--", 4) == 0)
      {
        const char *end = strstr(p + 4, "-->");
        p = (end != NULL) ? end + 3 : p + strlen(p);
        continue;
      }

      const char *tagNameStart = p + 1;
      bool closing = false;
      if (*tagNameStart == '/')
      {
        closing = true;
        tagNameStart++;
      }
      const char *tagNameEnd = tagNameStart;
      while (IsAsciiAlnum(*tagNameEnd))
      {
        tagNameEnd++;
      }
      size_t tagNameLen = (size_t)(tagNameEnd - tagNameStart);

      const char *tagEnd = EPUB_Xml_TagEnd(p);
      const char *afterTag = (tagEnd != NULL) ? tagEnd : (p + strlen(p));
      /* Self-closing ("<title/>", common for an empty per-chapter <title>
         in real-world EPUBs) has no body to skip - if treated the same as
         "<title>", skip mode would never see the (nonexistent) </title>
         and would silently swallow the entire rest of the document. */
      bool selfClosing = (tagEnd != NULL && tagEnd - p >= 2 && *(tagEnd - 2) == '/');

      if (skipping[0] != '\0')
      {
        if (closing && MatchesTagName(tagNameStart, tagNameLen, skipping))
        {
          skipping[0] = '\0';
        }
        p = afterTag;
        continue;
      }

      if (!closing && !selfClosing)
      {
        /* Elements whose text content should never reach the reader:
           script/style bodies aren't prose, and <title> duplicates the
           heading as document metadata rather than visible body text. */
        static const char *const skippableTags[] = { "script", "style", "title" };
        bool startedSkipping = false;
        for (size_t i = 0; i < sizeof(skippableTags) / sizeof(skippableTags[0]); i++)
        {
          if (MatchesTagName(tagNameStart, tagNameLen, skippableTags[i]))
          {
            strcpy(skipping, skippableTags[i]);
            startedSkipping = true;
            break;
          }
        }
        if (startedSkipping)
        {
          p = afterTag;
          continue;
        }
      }

      if (IsBlockTag(tagNameStart, tagNameLen))
      {
        pendingParaBreak = true;
      }

      p = afterTag;
      continue;
    }

    if (*p == '&')
    {
      char decoded[8];
      size_t consumed = EPUB_DecodeEntity(p, decoded, sizeof(decoded));
      if (consumed > 0)
      {
        for (const char *d = decoded; *d != '\0' && outPos + 1 < outSize; d++)
        {
          FlushPending(out, outSize, &outPos, &pendingParaBreak, &pendingSpace, anyOutputYet);
          out[outPos++] = *d;
          anyOutputYet = true;
        }
        p += consumed;
        continue;
      }
      /* Not a recognized entity - fall through and emit '&' literally. */
    }

    if (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
    {
      pendingSpace = true;
      p++;
      continue;
    }

    if ((unsigned char)*p >= 0x80)
    {
      /* Real EPUB body text almost always uses the literal UTF-8 character
         for smart quotes/dashes/ellipsis rather than an HTML entity
         reference - fold the common ones the same way EPUB_DecodeEntity
         folds their named/numeric entity equivalents just above. Anything
         else non-ASCII (accented Latin letters, etc.) is dropped rather
         than passed byte-by-byte to fonts that can only render 0x20-0x7E
         (see EPD_FontAA.h) - each byte would otherwise render as a blank
         space, which reads worse than simply not being there. */
      char decoded[8];
      size_t consumed = EPUB_DecodeUtf8SmartPunct(p, decoded, sizeof(decoded));
      if (consumed > 0)
      {
        for (const char *d = decoded; *d != '\0' && outPos + 1 < outSize; d++)
        {
          FlushPending(out, outSize, &outPos, &pendingParaBreak, &pendingSpace, anyOutputYet);
          out[outPos++] = *d;
          anyOutputYet = true;
        }
        p += consumed;
      }
      else
      {
        p++;
      }
      continue;
    }

    FlushPending(out, outSize, &outPos, &pendingParaBreak, &pendingSpace, anyOutputYet);
    out[outPos++] = *p;
    anyOutputYet = true;
    p++;
  }

  out[outPos] = '\0';
  return outPos;
}
