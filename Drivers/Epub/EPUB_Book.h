#ifndef EPUB_BOOK_H
#define EPUB_BOOK_H

#include <stdint.h>
#include <stdbool.h>
#include "EPUB_Zip.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Top-level EPUB orchestration on top of EPUB_Zip/EPUB_Xml/EPUB_Html:
   parses META-INF/container.xml to find the OPF (package document), then
   the OPF's manifest+spine to build an ordered list of chapter files, and
   can extract+convert any chapter to plain text on demand. Deliberately
   simple relative to the full EPUB spec - see the .c file for what's not
   handled (no "guide"/nav, no path normalization beyond simple
   directory-prefix + percent-decoding, first <dc:title> only). Good
   enough for real-world output from common tools (Calibre, Sigil,
   pandoc), which is what this was actually tested against. */

#define EPUB_MAX_SPINE_ITEMS 200
#define EPUB_MAX_HREF_LEN    128
#define EPUB_MAX_TITLE_LEN   128

typedef struct
{
  EPUB_Zip zip;
  char opfDir[EPUB_MAX_HREF_LEN]; /* directory containing the OPF, with trailing '/' (or empty) */
  char title[EPUB_MAX_TITLE_LEN]; /* first <dc:title>, or empty if not found */
  char spineHrefs[EPUB_MAX_SPINE_ITEMS][EPUB_MAX_HREF_LEN]; /* zip-relative paths, in reading order */
  uint16_t spineCount;
} EPUB_Book;

/* Opens the .epub via io and parses its structure (container.xml + OPF).
   scratchBuf is used transiently (split in half internally) for staging
   compressed/decompressed XML during parsing - big enough for the largest
   of container.xml or the OPF file, in either compressed or uncompressed
   form (a few hundred KB is comfortable for any real book; container.xml
   and the OPF are not needed again once this returns). Returns false if
   the file isn't a valid EPUB or parsing failed at any step. */
bool EPUB_Book_Open(EPUB_Book *book, EPUB_IO io, uint8_t *scratchBuf, uint32_t scratchBufSize);

/* Extracts spine chapter `index` (0-based, reading order) and converts it
   to plain text into outText. scratchBuf is used the same way as in
   EPUB_Book_Open (must be big enough for that chapter's XHTML, compressed
   and uncompressed). Returns false if index is out of range or extraction/
   conversion failed. */
bool EPUB_Book_GetChapterText(EPUB_Book *book, uint16_t index, uint8_t *scratchBuf,
                               uint32_t scratchBufSize, char *outText, uint32_t outTextSize);

#ifdef __cplusplus
}
#endif

#endif /* EPUB_BOOK_H */
