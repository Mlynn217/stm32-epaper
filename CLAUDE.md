# CLAUDE.md

Instructions for Claude Code sessions working in this repo.

**Read [README.md](README.md) and [TODO.md](TODO.md) before starting work.** Both are kept
accurate and current as part of this project's normal workflow — don't rediscover from source what's
already written down there. TODO.md in particular preserves debugging narratives (root causes, dead
ends, why a fix works) that are expensive to re-derive; skim it for the area you're touching before
assuming something is a fresh bug.

## What this is

STM32-based e-reader: STM32F469I-DISCO + Waveshare 6" HD e-Paper HAT (IT8951 controller). See
README.md's Overview/Architecture sections for the hardware and design rationale.

## Build / flash

First-time (or after `CMakeLists.txt`/`.ioc` changes) configure:
```sh
cmake --preset Debug
```
Then see "Iterating on hardware changes" below for the build-flash-validate loop, or use the
equivalent VSCode tasks (`Build (Debug)`, `Flash (OpenOCD / ST-LINK)`) — see README.md's
Building/Flashing/Debugging section.

## Iterating on hardware changes

The standard loop for validating any firmware change: build → flash → read the serial log →
(for anything visual) capture a photo of the panel.

**1. Confirm the ST-LINK is connected** before flashing:
```sh
lsusb | grep -i 0483
```

**2. Build and flash, checking the result:**
```sh
cmake --build --preset Debug
scripts/hw-lock.sh openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
  -c "program build/Debug/stm32-epaper.elf verify reset exit"
```
Look for `** Verified OK **` in the output. `program ... reset exit` resets and starts the board
running immediately, so the next boot's log output starts arriving right away. The build itself
doesn't touch the board, so it isn't wrapped — only the `openocd` call is.

**3. Read the serial log.** A `minicom` session logging to a timestamped file
(`minicom-YYYYMMDD-HHMMSS.log`, in the repo root) is typically *already running* in the
background for the whole session — check before starting a new one:
```sh
pgrep -af minicom                        # is one already running?
ls -t minicom-*.log | head -1            # most recent log file, if so
```
If none is running, start one through the hardware lock (it's a TUI app, but with nothing sent to
its stdin it just sits capturing serial data to the log file — fine to background):
```sh
scripts/hw-lock.sh minicom -D /dev/ttyACM0 -b 115200 -C "minicom-$(date +%Y%m%d-%H%M%S).log" &
```
(Once it's running, further reads of its log file are just reads — see below, no lock needed for
those. The lock only matters for the exclusive act of *opening* `/dev/ttyACM0`.)
The log file accumulates across every reflash in the session (each reboot's output just appends),
so after flashing, `tail`/`grep` the *end* of the current log rather than assuming it's fresh — the
per-boot `[   123]` millisecond-since-boot prefix resets to near-zero at each new boot, which is
the easiest way to tell where the latest one starts. Boot takes a few seconds to reach anything
interesting; poll for a specific expected line instead of guessing a fixed sleep, e.g.:
```sh
until tail -5 minicom-*.log | grep -q "IT8951 init done"; do sleep 2; done
```

**4. For anything visual, capture a photo of the panel** (a webcam works better than a phone/HEIC
round-trip — no format-conversion hassle):
```sh
scripts/hw-lock.sh ffmpeg -y -f v4l2 -video_size 1280x720 -i /dev/video0 \
  -vframes 15 -vf "select=eq(n\,14)" -frames:v 1 output.jpg
```
Capturing several frames and selecting the last one (`-vframes 15` + `select=eq(n\,14)`) gives the
webcam's auto-exposure a moment to settle — the very first frame is often too dark/black.

Don't report a hardware-facing change as working without having actually done steps 2-4 in the
current session and looked at the result yourself.

## Multiple agents / concurrent sessions

There is exactly **one** physical board — one ST-LINK, one serial port, one SD card, one webcam.
Code can be worked on in parallel (separate git worktrees, one per agent/task), but the board itself
is a single-lane resource: only one firmware image can ever be running on it, so hardware validation
cannot be parallelized no matter how many agents are active.

- **`scripts/hw-lock.sh <command...>`** wraps any command that touches the board (flashing, starting
  a new `minicom`, a webcam capture) in an `flock`-based mutex, shared across every worktree on this
  machine (the lock file lives in `/tmp`, not in the repo, on purpose — see the script's own
  comments). A second agent trying to flash while another holds the lock waits (with a
  `hardware busy... waiting` message) instead of racing OpenOCD against another instance. The lock
  releases automatically the instant the wrapped command's process ends, including on a crash or
  `kill -9` — nothing to remember to release, and no stale-lock cleanup needed.
- Reading the already-running minicom log file (`tail`/`grep` on `minicom-*.log`) does **not** need
  the lock — that's a passive file read, safe for any number of agents concurrently.
- The SD card's *content*, not just the physical connection, is also shared, mutable state — if two
  agents' tests both assume the same filename (`ALICE.TXT`, a specific `.epub`, etc.) they can
  clobber each other's fixtures. Give each agent's test artifacts distinct names, or coordinate who
  owns SD-card-content-dependent tests at any given time.
- Merge an agent's branch into `main` only after *that agent's own* hardware validation pass has
  actually run — a branch that only passed native tests hasn't been confirmed on the real board yet
  (see the native-test-harness convention above; it's a fast first pass, not a substitute for the
  real thing).
- More agents helps the parallelizable work (writing code, native-testable logic, docs); it does not
  speed up the hardware-validation bottleneck itself, which stays serial regardless of how many
  agents are active. Keep the number of agents needing hardware access at any one time small.

## Working conventions established in this repo

- **Validate on real hardware, not just compilation** — see "Iterating on hardware changes" above
  for the actual commands. If hardware access isn't possible in a given session, say so explicitly
  rather than claiming success from a clean build.
- **Commit only when explicitly asked.** Use a HEREDOC commit message, and never push without being
  asked separately.
- **CubeMX regenerations silently revert hand-tuned settings** in generated code (this has actually
  happened, more than once, to the SPI1 clock prescaler). `scripts/patch-cubemx.sh` re-applies known
  cases automatically at every `cmake` configure. If you hand-tune something in CubeMX-generated
  code, add a corresponding check to that script.
- **For parser/algorithm code** (as opposed to hardware-driver code), write a native test harness
  (plain `gcc`, no cross-compilation) against a synthetic fixture and iterate there before flashing —
  see how `Drivers/Epub/` was built (TODO.md has the story) for the pattern. It's much cheaper than a
  full build-flash-reboot-read-log cycle for catching structural bugs, though real hardware/real
  files still surface their own target-specific issues that a synthetic fixture won't.
- **Keep TODO.md and README.md up to date as you work.** They're this project's persistent memory
  across sessions and across agents — a change that isn't reflected there is effectively invisible to
  whoever picks this up next.
