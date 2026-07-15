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

```sh
cmake --preset Debug
cmake --build --preset Debug
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
  -c "program build/Debug/stm32-epaper.elf verify reset exit"
```

Or the equivalent VSCode tasks (`Build (Debug)`, `Flash (OpenOCD / ST-LINK)`) — see README.md's
Building/Flashing/Debugging section.

## Working conventions established in this repo

- **Validate on real hardware, not just compilation.** This project's standing practice is: flash
  every change and confirm it via the serial log (`minicom -C ...` produces a plain-text log file
  you can read directly) and, for anything visual, a webcam photo of the panel
  (`ffmpeg -f v4l2 ...`, see recent commits/TODO.md for the exact invocation). Don't report a
  feature as working without this. If hardware access isn't possible in a given session, say so
  explicitly rather than claiming success from a clean build.
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
