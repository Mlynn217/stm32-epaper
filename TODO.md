# TODO

### Documentation / Planning
- [x] Document hardware choice & rationale
- [ ] Confirm final GPIO pin mapping for SPI + control lines (avoid conflicts with the Discovery
      board's onboard LCD/SDRAM/USB/camera pins)
- [ ] Record this panel's VCOM value once hardware arrives
- [ ] Decide on a license

### Environment / Tooling
- [x] Install `arm-none-eabi-gcc` toolchain
- [x] Install OpenOCD for ST-Link debugging
- [x] Install Ninja
- [x] Install VSCode extensions: CMake Tools, C/C++, Cortex-Debug
- [ ] Generate STM32CubeMX project (`.ioc`) for STM32F469I-DISCO, targeting the CMake toolchain
  - [ ] Enable FMC/SDRAM matching the Discovery board's onboard SDRAM part
  - [ ] Configure SPI peripheral + GPIOs for IT8951 control lines (CS/RST/HRDY)
- [ ] Set up VSCode `tasks.json` / `launch.json` for build + flash + debug

### Firmware — display bring-up milestone (current focus)
- [ ] Vendor + adapt Waveshare's IT8951 driver source (SPI mode) into this repo
- [ ] Bring up SPI and verify communication with the IT8951 (read device info)
- [ ] Initialize FMC/SDRAM and route the IT8951 frame buffer through it
- [ ] Set the panel's VCOM value in firmware
- [ ] Draw a test pattern/image and confirm it renders on the panel
- [ ] Confirm both full refresh and fast/partial (A2 mode) refresh work

### Later milestones (not yet scoped in detail)
- [ ] Storage (SD card / file system) for book files
- [ ] Page rendering / text layout
- [ ] Ebook format parsing (EPUB/TXT)
- [ ] UI / input handling
- [ ] Power management / battery life
