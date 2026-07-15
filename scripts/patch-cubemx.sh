#!/usr/bin/env bash
# Re-applies fixes for known STM32CubeMX regeneration regressions.
#
# CubeMX periodically reverts hand-tuned settings in generated files when the
# .ioc is re-opened/regenerated for something unrelated - even ones we've
# also tried to fix in the .ioc's own tracked fields (e.g. SPI1's
# "CalculateBaudRate" doesn't reliably round-trip through the GUI's internal
# model). This script re-checks/re-applies each known case. It's idempotent
# and only touches a file when a fix is actually needed, so it's safe to run
# on every CMake configure (see CMakeLists.txt) without causing spurious
# rebuilds.
#
# If you add a new hand-tuned tweak to CubeMX-generated code, add a check
# for it here too.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAIN_C="$REPO_ROOT/Core/Src/main.c"

# SPI1 must run at <=24MHz for the IT8951 (datasheet Table 9-4, SPI AC
# Characteristics). CubeMX's own default is BAUDRATEPRESCALER_2 (45MHz off a
# 90MHz APB2 clock) - it has reverted our fix to _16 (5.625MHz) at least once
# already after an unrelated SDIO regeneration.
if grep -q 'hspi1\.Init\.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_2;' "$MAIN_C" 2>/dev/null; then
  echo "patch-cubemx: SPI1 prescaler reverted to /2 (45MHz) - fixing to /16 (5.625MHz, IT8951 max is 24MHz)"
  sed -i 's/hspi1\.Init\.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_2;/hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_16;/' "$MAIN_C"
fi
