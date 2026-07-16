#!/usr/bin/env bash
# Serializes access to the single physical board (ST-LINK connection, serial
# port, SD card content, webcam) across multiple concurrent agents/sessions
# on this machine. There is exactly one board, one ST-LINK, one /dev/ttyACM0,
# one /dev/video0 - flashing, opening the serial port, and capturing a photo
# are all exclusive operations that must not race each other.
#
# Wrap any command that touches the board through this:
#   scripts/hw-lock.sh openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
#     -c "program build/Debug/stm32-epaper.elf verify reset exit"
#   scripts/hw-lock.sh ffmpeg -y -f v4l2 -video_size 1280x720 -i /dev/video0 \
#     -vframes 15 -vf "select=eq(n\,14)" -frames:v 1 output.jpg
#
# Do NOT wrap passive reads of the already-running minicom log file
# (tail/grep on minicom-*.log) - that's just reading a file, safe for any
# number of agents to do concurrently, and serializing it would add nothing.
#
# The lock is released automatically when the wrapped command's process
# terminates, however that happens (normal exit, crash, or SIGKILL) - no
# "forgot to release" failure mode, no separate release step to remember.
# This requires `exec`ing the wrapped command in place (replacing this
# script's own process image) rather than running it as a child: a plain
# child process would inherit the locked file descriptor across fork, so it
# would go on holding the lock even after something killed *this* wrapper
# script - tested and confirmed during development (kill -9 on the wrapper
# left the lock held by the orphaned child until the child itself exited).
# `exec` avoids that by making the wrapped command the same process as the
# lock holder, not a child of it.
#
# The lock file deliberately lives outside this repo (in /tmp, not per-
# worktree): multiple agents typically each work from their own git worktree
# (separate directories) but share the same physical hardware, so a
# repo-relative lock file would not be visible across worktrees and would
# fail to prevent exactly the races this exists to prevent. Override with
# STM32_EPAPER_HW_LOCK if /tmp isn't shared for some reason (e.g. containers).
set -euo pipefail

LOCK_FILE="${STM32_EPAPER_HW_LOCK:-/tmp/stm32-epaper-hw.lock}"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <command> [args...]" >&2
  echo "  e.g. $0 openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program ...\"" >&2
  exit 1
fi

exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  echo "hw-lock: hardware busy (another agent/session holds the lock) - waiting..." >&2
  flock 200
fi
echo "hw-lock: acquired (pid $$) - running: $*" >&2

exec "$@"
