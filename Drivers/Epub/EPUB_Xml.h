#ifndef EPUB_XML_H
#define EPUB_XML_H

#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Minimal XML helpers - not a general parser. EPUB's container.xml and OPF
   files are small, fixed-structure, attribute-heavy XML produced by a
   handful of well-behaved tools (Calibre, Sigil, pandoc, etc.); these
   functions do just enough to find a tag and read one of its attributes,
   nothing more (no namespaces, no nested element text extraction, no
   entity resolution beyond the common few). All functions operate on
   null-terminated C strings. */

/* Finds the next start tag "<tagName ...>" or "<tagName .../>" at or after
   searchFrom (pass NULL to start from the beginning of xml). Skips closing
   tags ("</foo>"), comments ("<!--"), and processing
   instructions/doctype ("<?"/"<!"). Returns a pointer to the tag's '<', or
   NULL if not found. */
const char *EPUB_Xml_FindTag(const char *xml, const char *tagName, const char *searchFrom);

/* Returns a pointer just past a tag's closing '>' (tagStart must point at
   the tag's '<', e.g. as returned by EPUB_Xml_FindTag). Handles quoted
   attribute values that might contain '>'. Returns NULL if the string ends
   before a closing '>' is found. */
const char *EPUB_Xml_TagEnd(const char *tagStart);

/* Extracts and entity-decodes the value of attrName="..." (or '...')
   within [tagStart, tagEnd) - matches on attribute-name word boundaries, so
   searching "id" won't match "idref" or a "gridid"-style false substring.
   Returns true if found (even if the value is empty); out is always
   null-terminated. */
bool EPUB_Xml_GetAttr(const char *tagStart, const char *tagEnd, const char *attrName,
                      char *out, size_t outSize);

/* Decodes a single character entity starting at `entity` (which must point
   at '&'). Writes the ASCII-folded result (numeric references outside
   printable ASCII are folded to a close equivalent - curly quotes/dashes/
   ellipsis - or dropped if there isn't one, since this project's fonts are
   ASCII-only, see EPD_FontAA.h) to out (always null-terminated) and
   returns the number of source bytes consumed (including '&' and ';'), or
   0 if this isn't a recognized entity (out is left untouched - caller
   should copy the literal '&' through unchanged in that case). */
size_t EPUB_DecodeEntity(const char *entity, char *out, size_t outSize);

/* Real-world EPUB body text almost always uses the literal UTF-8 character
   for smart quotes/dashes/ellipsis/nbsp rather than an HTML entity
   reference (unlike hand-written test markup, which tends to use named
   entities) - this is the equivalent of EPUB_DecodeEntity for that case.
   Detects one of those specific UTF-8 sequences at `s` and ASCII-folds it
   the same way. Returns bytes consumed (2 or 3), or 0 if `s` doesn't start
   with one of these specific sequences (out is left untouched - caller
   should decide what to do with an unrecognized non-ASCII byte itself,
   e.g. drop it, since this project's fonts are ASCII-only). */
size_t EPUB_DecodeUtf8SmartPunct(const char *s, char *out, size_t outSize);

#ifdef __cplusplus
}
#endif

#endif /* EPUB_XML_H */
