#ifndef EPUB_HTML_H
#define EPUB_HTML_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Converts (X)HTML content, as found in an EPUB chapter file, to plain text
   suitable for EPD_Layout_DrawParagraph(): strips all tags, discards
   <script>/<style> element content entirely, decodes entities (see
   EPUB_Xml.h - non-ASCII codepoints are folded to a close ASCII
   equivalent or dropped, since this project's fonts are ASCII-only),
   collapses whitespace runs from the source markup down to single spaces,
   and inserts a paragraph break ("\n\n") at block-level element boundaries
   (<p>, <div>, <h1>-<h6>, <li>, <blockquote>, <br>) so the result reads
   sensibly through the existing word-wrap/pagination pipeline. Truncates
   if the result doesn't fit in outSize (always null-terminated). Returns
   the number of bytes written, excluding the null terminator. */
size_t EPUB_Html_ToPlainText(const char *html, char *out, size_t outSize);

#ifdef __cplusplus
}
#endif

#endif /* EPUB_HTML_H */
