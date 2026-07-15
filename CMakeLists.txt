cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME stm32-epaper)

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

# Re-apply fixes for known CubeMX regeneration regressions (e.g. SPI1 clock
# getting reset to a speed the IT8951 doesn't support) - see the script for
# why this is needed. Runs on every configure (i.e. every `cmake --preset`),
# so if you regenerate from CubeMX, just re-run cmake before building and
# this self-heals; it's a no-op otherwise.
execute_process(
    COMMAND bash ${CMAKE_SOURCE_DIR}/scripts/patch-cubemx.sh
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    RESULT_VARIABLE PATCH_CUBEMX_RESULT
)
if(NOT PATCH_CUBEMX_RESULT EQUAL 0)
    message(FATAL_ERROR "scripts/patch-cubemx.sh failed (exit ${PATCH_CUBEMX_RESULT})")
endif()

# Enable CMake support for ASM and C languages
enable_language(C ASM)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user sources here
    Drivers/IT8951/e-Paper/EPD_IT8951.c
    Drivers/IT8951/Config/DEV_Config.c
    Drivers/Fonts/EPD_Text.c
    Drivers/Fonts/EPD_Layout.c
    Drivers/Fonts/font8.c
    Drivers/Fonts/font12.c
    Drivers/Fonts/font16.c
    Drivers/Fonts/font20.c
    Drivers/Fonts/font24.c
    Drivers/Fonts/Font32.c
    Drivers/Fonts/Font44.c
    Drivers/Fonts/Font60Bold.c
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined include paths
    Drivers/IT8951/e-Paper
    Drivers/IT8951/Config
    Drivers/Fonts
)

# Add project symbols (macros)
target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined symbols
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# newlib-nano (--specs=nano.specs) strips float support from printf/scanf by
# default to save flash; force it back in since the vendored IT8951 driver's
# Debug() logging uses %f (e.g. VCOM confirmation).
target_link_options(${CMAKE_PROJECT_NAME} PRIVATE
    -u _printf_float
)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx

    # Add user defined libraries
)
