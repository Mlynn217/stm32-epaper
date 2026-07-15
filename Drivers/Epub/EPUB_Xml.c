#include "EPUB_Xml.h"
#include <string.h>
#include <stdlib.h>

static bool IsIdentChar(char c)
{
  return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
         c == '-' || c == '_' || c == ':';
}

const char *EPUB_Xml_FindTag(const char *xml, const char *tagName, const char *searchFrom)
{
  size_t tagNameLen = strlen(tagName);
  const char *p = searchFrom != NULL ? searchFrom : xml;

  while ((p = strchr(p, '<')) != NULL)
  {
    const char *afterBracket = p + 1;
    if (*afterBracket == '/' || *afterBracket == '!' || *afterBracket == '?')
    {
      p++;
      continue;
    }
    if (strncmp(afterBracket, tagName, tagNameLen) == 0 && !IsIdentChar(afterBracket[tagNameLen]))
    {
      return p;
    }
    p++;
  }
  return NULL;
}

const char *EPUB_Xml_TagEnd(const char *tagStart)
{
  const char *p = tagStart;
  char inQuote = 0;

  while (*p != '\0')
  {
    if (inQuote != 0)
    {
      if (*p == inQuote)
      {
        inQuote = 0;
      }
    }
    else if (*p == '"' || *p == '\'')
    {
      inQuote = *p;
    }
    else if (*p == '>')
    {
      return p + 1;
    }
    p++;
  }
  return NULL;
}

bool EPUB_Xml_GetAttr(const char *tagStart, const char *tagEnd, const char *attrName,
                      char *out, size_t outSize)
{
  size_t attrLen = strlen(attrName);
  const char *p = tagStart;

  while (p + attrLen < tagEnd)
  {
    bool boundaryBefore = (p == tagStart) || !IsIdentChar(p[-1]);
    if (boundaryBefore && strncmp(p, attrName, attrLen) == 0 && !IsIdentChar(p[attrLen]))
    {
      const char *cursor = p + attrLen;
      while (cursor < tagEnd && (*cursor == ' ' || *cursor == '\t' || *cursor == '\n' ||
                                 *cursor == '\r'))
      {
        cursor++;
      }
      if (cursor < tagEnd && *cursor == '=')
      {
        cursor++;
        while (cursor < tagEnd && (*cursor == ' ' || *cursor == '\t'))
        {
          cursor++;
        }
        if (cursor < tagEnd && (*cursor == '"' || *cursor == '\''))
        {
          char quote = *cursor;
          cursor++;
          const char *valueStart = cursor;
          while (cursor < tagEnd && *cursor != quote)
          {
            cursor++;
          }
          if (cursor < tagEnd)
          {
            size_t rawLen = (size_t)(cursor - valueStart);
            size_t outPos = 0;
            for (size_t i = 0; i < rawLen && outPos + 1 < outSize; i++)
            {
              if (valueStart[i] == '&')
              {
                char decoded[8];
                size_t consumed = EPUB_DecodeEntity(&valueStart[i], decoded, sizeof(decoded));
                if (consumed > 0)
                {
                  size_t decodedLen = strlen(decoded);
                  size_t roomLeft = outSize - 1 - outPos;
                  size_t copyLen = decodedLen < roomLeft ? decodedLen : roomLeft;
                  memcpy(&out[outPos], decoded, copyLen);
                  outPos += copyLen;
                  i += consumed - 1; /* loop's i++ accounts for the last byte */
                  continue;
                }
              }
              out[outPos++] = valueStart[i];
            }
            out[outPos] = '\0';
            return true;
          }
        }
      }
    }
    p++;
  }
  return false;
}

/* Maps common named/numeric character entities down to this project's
   ASCII-only font range (see EPD_FontAA.h) - either a close visual
   equivalent (curly quotes/dashes/ellipsis) or dropped if there isn't a
   reasonable one (accented Latin letters, mostly). Real EPUB body text
   uses a fairly small, predictable set of these. */
size_t EPUB_DecodeEntity(const char *entity, char *out, size_t outSize)
{
  if (entity[0] != '&')
  {
    return 0;
  }

  const char *semicolon = strchr(entity, ';');
  if (semicolon == NULL || semicolon - entity > 12)
  {
    return 0; /* not a well-formed (or absurdly long) entity - not ours to decode */
  }
  size_t totalLen = (size_t)(semicolon - entity) + 1;

  char body[12];
  size_t bodyLen = totalLen - 2; /* strip leading '&' and trailing ';' */
  memcpy(body, entity + 1, bodyLen);
  body[bodyLen] = '\0';

  const char *result = NULL;
  char numericBuf[2] = { 0 };

  if (strcmp(body, "amp") == 0) result = "&";
  else if (strcmp(body, "lt") == 0) result = "<";
  else if (strcmp(body, "gt") == 0) result = ">";
  else if (strcmp(body, "quot") == 0) result = "\"";
  else if (strcmp(body, "apos") == 0) result = "'";
  else if (strcmp(body, "nbsp") == 0) result = " ";
  else if (strcmp(body, "hellip") == 0) result = "...";
  else if (strcmp(body, "mdash") == 0) result = "--";
  else if (strcmp(body, "ndash") == 0) result = "-";
  else if (strcmp(body, "lsquo") == 0 || strcmp(body, "rsquo") == 0) result = "'";
  else if (strcmp(body, "ldquo") == 0 || strcmp(body, "rdquo") == 0) result = "\"";
  else if (body[0] == '#')
  {
    long codepoint;
    if (body[1] == 'x' || body[1] == 'X')
    {
      codepoint = strtol(body + 2, NULL, 16);
    }
    else
    {
      codepoint = strtol(body + 1, NULL, 10);
    }

    if (codepoint >= 0x20 && codepoint <= 0x7E)
    {
      numericBuf[0] = (char)codepoint;
      result = numericBuf;
    }
    else
    {
      switch (codepoint)
      {
        case 0x2018: case 0x2019: result = "'"; break;
        case 0x201C: case 0x201D: result = "\""; break;
        case 0x2013: result = "-"; break;
        case 0x2014: result = "--"; break;
        case 0x2026: result = "..."; break;
        case 0xA0: result = " "; break;
        default: result = ""; break; /* out of range, no equivalent - drop it */
      }
    }
  }
  else
  {
    return 0; /* unrecognized named entity - leave it for the caller to copy verbatim */
  }

  size_t resultLen = strlen(result);
  size_t copyLen = resultLen < (outSize - 1) ? resultLen : (outSize - 1);
  memcpy(out, result, copyLen);
  out[copyLen] = '\0';
  return totalLen;
}

size_t EPUB_DecodeUtf8SmartPunct(const char *s, char *out, size_t outSize)
{
  const unsigned char *u = (const unsigned char *)s;
  const char *result = NULL;
  size_t consumed = 0;

  if (u[0] == 0xE2 && u[1] == 0x80)
  {
    /* u[1] confirmed non-null, so u[2] is guaranteed to be a real
       (possibly null) byte within the string - safe to read regardless of
       its value. */
    switch (u[2])
    {
      case 0x98: case 0x99: result = "'"; break;  /* left/right single quote */
      case 0x9C: case 0x9D: result = "\""; break; /* left/right double quote */
      case 0x93: result = "-"; break;             /* en dash */
      case 0x94: result = "--"; break;            /* em dash */
      case 0xA6: result = "..."; break;           /* ellipsis */
      default: break;
    }
    consumed = 3;
  }
  else if (u[0] == 0xC2 && u[1] == 0xA0)
  {
    result = " "; /* non-breaking space */
    consumed = 2;
  }

  if (result == NULL)
  {
    return 0;
  }

  size_t resultLen = strlen(result);
  size_t copyLen = resultLen < (outSize - 1) ? resultLen : (outSize - 1);
  memcpy(out, result, copyLen);
  out[copyLen] = '\0';
  return consumed;
}
