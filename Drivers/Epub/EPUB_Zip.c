#include "EPUB_Zip.h"
#include "puff.h"
#include <string.h>
#include <stdio.h>

#define EOCD_SIGNATURE      0x06054b50U
#define CENTRAL_DIR_SIGNATURE 0x02014b50U
#define LOCAL_HEADER_SIGNATURE 0x04034b50U

#define EOCD_FIXED_SIZE 22
#define CENTRAL_HEADER_FIXED_SIZE 46
#define LOCAL_HEADER_FIXED_SIZE 30

/* How far back from EOF to search for the EOCD signature. The EOCD record
   can in principle be preceded by a comment of up to 65535 bytes, but real
   EPUB-producing tools (Calibre, Sigil, pandoc, the various epub Python/JS
   libraries) don't add one - a small fixed window covers every EPUB this
   has actually been tested against, at a fraction of the buffer size a
   fully spec-compliant search would need. */
#define EOCD_SEARCH_WINDOW 1024

static uint16_t ReadU16LE(const uint8_t *p)
{
  return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t ReadU32LE(const uint8_t *p)
{
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

bool EPUB_Zip_Open(EPUB_Zip *zip, EPUB_IO io)
{
  memset(zip, 0, sizeof(*zip));
  zip->io = io;

  uint32_t fileSize = io.size(io.ctx);
  if (fileSize < EOCD_FIXED_SIZE)
  {
    return false;
  }

  uint32_t windowSize = fileSize < EOCD_SEARCH_WINDOW ? fileSize : EOCD_SEARCH_WINDOW;
  uint32_t windowStart = fileSize - windowSize;

  uint8_t buf[EOCD_SEARCH_WINDOW];
  if (!io.read(io.ctx, windowStart, buf, windowSize))
  {
    return false;
  }

  /* Search backward for the signature - if a real comment happens to
     contain these 4 bytes by coincidence, the trailing EOCD fields
     (particularly comment length) would fail a sanity check, but we don't
     bother with that here: scanning from the end and taking the first
     match is correct for the overwhelming majority of real files (no
     comment, or a short one not containing this exact byte sequence). */
  int32_t eocdOffsetInBuf = -1;
  for (int32_t i = (int32_t)windowSize - EOCD_FIXED_SIZE; i >= 0; i--)
  {
    if (ReadU32LE(&buf[i]) == EOCD_SIGNATURE)
    {
      eocdOffsetInBuf = i;
      break;
    }
  }
  if (eocdOffsetInBuf < 0)
  {
    printf("EPUB_Zip: EOCD signature not found in last %lu bytes (fileSize=%lu)\r\n",
           (unsigned long)windowSize, (unsigned long)fileSize);
    return false;
  }

  const uint8_t *eocd = &buf[eocdOffsetInBuf];
  zip->entryCount = ReadU16LE(eocd + 10);
  zip->centralDirSize = ReadU32LE(eocd + 12);
  zip->centralDirOffset = ReadU32LE(eocd + 16);

  return true;
}

uint32_t EPUB_Zip_ForEachEntry(EPUB_Zip *zip, EPUB_Zip_EntryCb cb, void *userData)
{
  uint32_t offset = zip->centralDirOffset;
  uint32_t end = zip->centralDirOffset + zip->centralDirSize;
  uint32_t visited = 0;

  while (offset + CENTRAL_HEADER_FIXED_SIZE <= end)
  {
    uint8_t header[CENTRAL_HEADER_FIXED_SIZE];
    if (!zip->io.read(zip->io.ctx, offset, header, sizeof(header)))
    {
      break;
    }
    if (ReadU32LE(header) != CENTRAL_DIR_SIGNATURE)
    {
      break;
    }

    uint16_t compressionMethod = ReadU16LE(header + 10);
    uint32_t compressedSize = ReadU32LE(header + 20);
    uint32_t uncompressedSize = ReadU32LE(header + 24);
    uint16_t nameLen = ReadU16LE(header + 28);
    uint16_t extraLen = ReadU16LE(header + 30);
    uint16_t commentLen = ReadU16LE(header + 32);
    uint32_t localHeaderOffset = ReadU32LE(header + 42);

    EPUB_ZipEntry entry;
    memset(&entry, 0, sizeof(entry));
    entry.compressionMethod = compressionMethod;
    entry.compressedSize = compressedSize;
    entry.uncompressedSize = uncompressedSize;
    entry.localHeaderOffset = localHeaderOffset;

    uint16_t nameCopyLen = nameLen < (EPUB_ZIP_MAX_NAME - 1) ? nameLen
                                                              : (EPUB_ZIP_MAX_NAME - 1);
    if (!zip->io.read(zip->io.ctx, offset + CENTRAL_HEADER_FIXED_SIZE, entry.name,
                       nameCopyLen))
    {
      break;
    }
    entry.name[nameCopyLen] = '\0';

    visited++;
    bool keepGoing = cb(&entry, userData);
    if (!keepGoing)
    {
      break;
    }

    offset += CENTRAL_HEADER_FIXED_SIZE + nameLen + extraLen + commentLen;
  }

  return visited;
}

typedef struct
{
  const char *targetName;
  bool found;
  EPUB_ZipEntry result;
} FindEntryCtx;

static bool FindEntryCb(const EPUB_ZipEntry *entry, void *userData)
{
  FindEntryCtx *ctx = (FindEntryCtx *)userData;
  if (strcmp(entry->name, ctx->targetName) == 0)
  {
    ctx->found = true;
    ctx->result = *entry;
    return false; /* stop iterating */
  }
  return true;
}

bool EPUB_Zip_FindEntry(EPUB_Zip *zip, const char *name, EPUB_ZipEntry *outEntry)
{
  FindEntryCtx ctx;
  ctx.targetName = name;
  ctx.found = false;

  EPUB_Zip_ForEachEntry(zip, FindEntryCb, &ctx);

  if (ctx.found)
  {
    *outEntry = ctx.result;
  }
  return ctx.found;
}

bool EPUB_Zip_Extract(EPUB_Zip *zip, const EPUB_ZipEntry *entry, uint8_t *outBuf,
                       uint32_t outBufSize, uint8_t *scratchBuf, uint32_t scratchBufSize)
{
  if (outBufSize < entry->uncompressedSize)
  {
    return false;
  }

  if (zip->io.reset != NULL && !zip->io.reset(zip->io.ctx))
  {
    return false;
  }

  /* The local header's name/extra field lengths can differ from the
     central directory's (extra fields especially - Zip64/Unix timestamps
     etc. are often only present in one or the other), so the actual data
     offset has to be computed from the local header, not assumed from the
     central directory alone. */
  uint8_t localHeader[LOCAL_HEADER_FIXED_SIZE];
  if (!zip->io.read(zip->io.ctx, entry->localHeaderOffset, localHeader, sizeof(localHeader)))
  {
    return false;
  }

  if (ReadU32LE(localHeader) != LOCAL_HEADER_SIGNATURE)
  {
    return false;
  }
  uint16_t localNameLen = ReadU16LE(localHeader + 26);
  uint16_t localExtraLen = ReadU16LE(localHeader + 28);
  uint32_t dataOffset = entry->localHeaderOffset + LOCAL_HEADER_FIXED_SIZE + localNameLen +
                         localExtraLen;

  if (entry->compressionMethod == 0)
  {
    return zip->io.read(zip->io.ctx, dataOffset, outBuf, entry->uncompressedSize);
  }

  if (entry->compressionMethod == 8)
  {
    if (scratchBuf == NULL || scratchBufSize < entry->compressedSize)
    {
      return false;
    }
    if (!zip->io.read(zip->io.ctx, dataOffset, scratchBuf, entry->compressedSize))
    {
      return false;
    }

    unsigned long destLen = entry->uncompressedSize;
    unsigned long sourceLen = entry->compressedSize;
    int result = puff(outBuf, &destLen, scratchBuf, &sourceLen);
    if (result != 0 || destLen != entry->uncompressedSize)
    {
      printf("EPUB_Zip_Extract: \"%s\" puff() failed (result=%d, got %lu of %lu expected "
             "bytes)\r\n", entry->name, result, (unsigned long)destLen,
             (unsigned long)entry->uncompressedSize);
    }
    return result == 0 && destLen == entry->uncompressedSize;
  }

  return false; /* unsupported compression method */
}
