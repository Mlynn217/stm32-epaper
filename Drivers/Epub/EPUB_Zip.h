#ifndef EPUB_ZIP_H
#define EPUB_ZIP_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Minimal ZIP central-directory reader - an EPUB file is just a ZIP archive
   (see EPUB_Book.h for the EPUB-specific structure on top of this). Only
   what's needed to locate and extract entries by name; no writing, no
   streaming decompression (whole entries are extracted into a caller
   buffer in one call).

   Deliberately decoupled from any particular file API via EPUB_IO, so this
   is equally usable against a FatFs FIL (the firmware) or a plain host
   file (native tests) - see EPUB_Zip.c's own comments for why an absolute
   seek+read interface, not a stream, is what's needed here. */
typedef struct
{
  void *ctx;
  bool (*read)(void *ctx, uint32_t offset, void *buf, uint32_t len);
  uint32_t (*size)(void *ctx);
  /* Optional (NULL is fine, e.g. for the native/stdio-backed test harness).
     On FatFs, repeated reads at different offsets on the same open file
     handle have been observed to return stale data from an internal
     single-sector cache (ff.c's move_window(), keyed only by absolute
     sector number - see EPUB_Zip.c's EPUB_Zip_Extract for how this was
     diagnosed) once several other seeks on that handle have happened in
     between. Closing and reopening the file resets FatFs's internal
     cluster-chain cursor and sidesteps it. Called before each independent
     extraction (EPUB_Zip_Extract). */
  bool (*reset)(void *ctx);
} EPUB_IO;

#define EPUB_ZIP_MAX_NAME 160

typedef struct
{
  char name[EPUB_ZIP_MAX_NAME]; /* truncated if longer - see EPUB_Zip.c */
  uint32_t compressedSize;
  uint32_t uncompressedSize;
  uint16_t compressionMethod; /* 0 = stored, 8 = deflate; others unsupported */
  uint32_t localHeaderOffset;
} EPUB_ZipEntry;

typedef struct
{
  EPUB_IO io;
  uint32_t centralDirOffset;
  uint32_t centralDirSize;
  uint16_t entryCount;
} EPUB_Zip;

/* Locates the End Of Central Directory record and the central directory it
   points to. Returns false if this doesn't look like a valid zip (or has
   an unusually large trailing comment - see EPUB_Zip.c). */
bool EPUB_Zip_Open(EPUB_Zip *zip, EPUB_IO io);

/* Calls cb for every entry in the central directory, in order, until cb
   returns false or entries are exhausted. Returns the number of entries
   actually visited (not necessarily the total entry count, if cb stopped
   early). */
typedef bool (*EPUB_Zip_EntryCb)(const EPUB_ZipEntry *entry, void *userData);
uint32_t EPUB_Zip_ForEachEntry(EPUB_Zip *zip, EPUB_Zip_EntryCb cb, void *userData);

/* Finds a single entry by exact (case-sensitive) name match. Returns true
   if found. */
bool EPUB_Zip_FindEntry(EPUB_Zip *zip, const char *name, EPUB_ZipEntry *outEntry);

/* Extracts (and decompresses, if needed) an entry's full contents into
   outBuf, which must be at least entry->uncompressedSize bytes. Deflated
   entries need somewhere to stage the still-compressed bytes before
   inflating them (puff() takes an in-memory source, not a stream) -
   scratchBuf must then be at least entry->compressedSize bytes; pass
   NULL/0 for stored (uncompressed) entries. Returns true on success. */
bool EPUB_Zip_Extract(EPUB_Zip *zip, const EPUB_ZipEntry *entry, uint8_t *outBuf,
                       uint32_t outBufSize, uint8_t *scratchBuf, uint32_t scratchBufSize);

#ifdef __cplusplus
}
#endif

#endif /* EPUB_ZIP_H */
