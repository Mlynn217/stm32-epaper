#include "EPUB_Book.h"
#include "EPUB_Xml.h"
#include "EPUB_Html.h"
#include <string.h>
#include <stdio.h>

static bool IsHexDigit(char c)
{
  return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

static int HexVal(char c)
{
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return c - 'A' + 10;
}

/* Manifest hrefs are meant to be URL-encoded per the OPF spec (e.g. spaces
   as %20); actual zip entry names are not. Decoding in place is safe since
   the decoded form is never longer than the input. */
static void PercentDecodeInPlace(char *s)
{
  char *w = s;
  for (const char *r = s; *r != '\0'; r++)
  {
    if (*r == '%' && IsHexDigit(r[1]) && IsHexDigit(r[2]))
    {
      *w++ = (char)((HexVal(r[1]) << 4) | HexVal(r[2]));
      r += 2;
    }
    else
    {
      *w++ = *r;
    }
  }
  *w = '\0';
}

static bool ResolveManifestHref(const char *opfXml, const char *targetId, char *outHref,
                                 size_t outHrefSize)
{
  const char *cursor = NULL;
  for (;;)
  {
    const char *itemTag = EPUB_Xml_FindTag(opfXml, "item", cursor);
    if (itemTag == NULL)
    {
      return false;
    }
    const char *itemTagEnd = EPUB_Xml_TagEnd(itemTag);
    if (itemTagEnd == NULL)
    {
      return false;
    }

    char id[64];
    if (EPUB_Xml_GetAttr(itemTag, itemTagEnd, "id", id, sizeof(id)) &&
        strcmp(id, targetId) == 0)
    {
      return EPUB_Xml_GetAttr(itemTag, itemTagEnd, "href", outHref, outHrefSize);
    }
    cursor = itemTagEnd;
  }
}

bool EPUB_Book_Open(EPUB_Book *book, EPUB_IO io, uint8_t *scratchBuf, uint32_t scratchBufSize)
{
  memset(book, 0, sizeof(*book));

  if (!EPUB_Zip_Open(&book->zip, io))
  {
    printf("EPUB_Book: not a valid zip\r\n");
    return false;
  }

  uint32_t halfSize = scratchBufSize / 2;
  uint8_t *compressedStage = scratchBuf;
  char *decodedStage = (char *)(scratchBuf + halfSize);

  /* Step 1: META-INF/container.xml -> the OPF's path. */
  EPUB_ZipEntry containerEntry;
  if (!EPUB_Zip_FindEntry(&book->zip, "META-INF/container.xml", &containerEntry))
  {
    printf("EPUB_Book: META-INF/container.xml not found\r\n");
    return false;
  }
  if (containerEntry.uncompressedSize >= halfSize ||
      !EPUB_Zip_Extract(&book->zip, &containerEntry, (uint8_t *)decodedStage, halfSize,
                        compressedStage, halfSize))
  {
    printf("EPUB_Book: container.xml extraction failed\r\n");
    return false;
  }
  decodedStage[containerEntry.uncompressedSize] = '\0';

  char opfPath[EPUB_MAX_HREF_LEN];
  const char *rootfileTag = EPUB_Xml_FindTag(decodedStage, "rootfile", NULL);
  const char *rootfileTagEnd = rootfileTag != NULL ? EPUB_Xml_TagEnd(rootfileTag) : NULL;
  if (rootfileTagEnd == NULL ||
      !EPUB_Xml_GetAttr(rootfileTag, rootfileTagEnd, "full-path", opfPath, sizeof(opfPath)))
  {
    printf("EPUB_Book: <rootfile full-path=...> not found in container.xml\r\n");
    return false;
  }
  PercentDecodeInPlace(opfPath);

  const char *lastSlash = strrchr(opfPath, '/');
  if (lastSlash != NULL)
  {
    size_t dirLen = (size_t)(lastSlash - opfPath) + 1; /* keep the slash */
    if (dirLen >= sizeof(book->opfDir))
    {
      dirLen = sizeof(book->opfDir) - 1;
    }
    memcpy(book->opfDir, opfPath, dirLen);
    book->opfDir[dirLen] = '\0';
  }

  /* Step 2: extract the OPF itself. */
  EPUB_ZipEntry opfEntry;
  if (!EPUB_Zip_FindEntry(&book->zip, opfPath, &opfEntry))
  {
    printf("EPUB_Book: OPF \"%s\" not found\r\n", opfPath);
    return false;
  }
  if (opfEntry.uncompressedSize >= halfSize ||
      !EPUB_Zip_Extract(&book->zip, &opfEntry, (uint8_t *)decodedStage, halfSize,
                        compressedStage, halfSize))
  {
    printf("EPUB_Book: OPF \"%s\" extraction failed\r\n", opfPath);
    return false;
  }
  decodedStage[opfEntry.uncompressedSize] = '\0';
  const char *opfXml = decodedStage;

  /* Step 2a (best-effort, not required): grab the first <dc:title> for display. */
  const char *titleTag = EPUB_Xml_FindTag(opfXml, "dc:title", NULL);
  if (titleTag != NULL)
  {
    const char *titleTagEnd = EPUB_Xml_TagEnd(titleTag);
    if (titleTagEnd != NULL)
    {
      const char *textEnd = strchr(titleTagEnd, '<');
      if (textEnd != NULL)
      {
        size_t len = (size_t)(textEnd - titleTagEnd);
        if (len >= sizeof(book->title))
        {
          len = sizeof(book->title) - 1;
        }
        memcpy(book->title, titleTagEnd, len);
        book->title[len] = '\0';
      }
    }
  }

  /* Step 3: walk <spine><itemref idref="..."/>...</spine> in document
     order, resolving each idref against the manifest's <item id="..."
     href="..."/> entries (searched across the whole document rather than
     a strictly-bounded <manifest> section - real OPF files only ever use
     <item> there in practice). */
  const char *spineTag = EPUB_Xml_FindTag(opfXml, "spine", NULL);
  const char *spineTagEnd = spineTag != NULL ? EPUB_Xml_TagEnd(spineTag) : NULL;
  if (spineTagEnd == NULL)
  {
    printf("EPUB_Book: <spine> not found in OPF\r\n");
    return false;
  }
  const char *spineClose = strstr(spineTagEnd, "</spine>");

  const char *cursor = spineTagEnd;
  book->spineCount = 0;
  while (book->spineCount < EPUB_MAX_SPINE_ITEMS)
  {
    const char *itemrefTag = EPUB_Xml_FindTag(opfXml, "itemref", cursor);
    if (itemrefTag == NULL || (spineClose != NULL && itemrefTag >= spineClose))
    {
      break;
    }
    const char *itemrefTagEnd = EPUB_Xml_TagEnd(itemrefTag);
    if (itemrefTagEnd == NULL)
    {
      break;
    }

    char idref[64];
    if (EPUB_Xml_GetAttr(itemrefTag, itemrefTagEnd, "idref", idref, sizeof(idref)))
    {
      char href[EPUB_MAX_HREF_LEN];
      if (ResolveManifestHref(opfXml, idref, href, sizeof(href)))
      {
        PercentDecodeInPlace(href);
        snprintf(book->spineHrefs[book->spineCount], EPUB_MAX_HREF_LEN, "%s%s", book->opfDir,
                 href);
        book->spineCount++;
      }
    }
    cursor = itemrefTagEnd;
  }

  return book->spineCount > 0;
}

bool EPUB_Book_GetChapterText(EPUB_Book *book, uint16_t index, uint8_t *scratchBuf,
                               uint32_t scratchBufSize, char *outText, uint32_t outTextSize)
{
  if (index >= book->spineCount)
  {
    return false;
  }

  EPUB_ZipEntry entry;
  if (!EPUB_Zip_FindEntry(&book->zip, book->spineHrefs[index], &entry))
  {
    printf("EPUB_Book: chapter %u (\"%s\") not found\r\n", index, book->spineHrefs[index]);
    return false;
  }

  uint32_t halfSize = scratchBufSize / 2;
  uint8_t *compressedStage = scratchBuf;
  char *decodedStage = (char *)(scratchBuf + halfSize);
  if (entry.uncompressedSize >= halfSize ||
      !EPUB_Zip_Extract(&book->zip, &entry, (uint8_t *)decodedStage, halfSize, compressedStage,
                        halfSize))
  {
    printf("EPUB_Book: chapter %u (\"%s\") extraction failed\r\n", index,
           book->spineHrefs[index]);
    return false;
  }
  decodedStage[entry.uncompressedSize] = '\0';

  EPUB_Html_ToPlainText(decodedStage, outText, outTextSize);
  return true;
}
