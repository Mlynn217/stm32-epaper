/*****************************************************************************
* | File      	:   DEV_Config.h
* | Function    :   Hardware underlying interface
* | Info        :
*                STM32 (HAL) port of Waveshare's DEV_Config hardware
*                abstraction layer, adapted from their Raspberry Pi
*                (bcm2835/lgpio) implementation to talk to SPI1 + the
*                SPI1_CS / RST / HRDY GPIOs configured via STM32CubeMX.
*----------------------------------------------------------------------------
* Original file:
* | Author      :   Waveshare team
* | This version:   V2.0
* | Date        :   2018-10-30
*
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
******************************************************************************/
#ifndef _DEV_CONFIG_H_
#define _DEV_CONFIG_H_

#include <stdint.h>
#include "Debug.h"

#define HIGH 0x1
#define LOW  0x0

/**
 * GPIO
 * These are opaque IDs (not real pin numbers) switched on in DEV_Config.c,
 * which maps them to the actual STM32 GPIO port/pin pairs CubeMX generated
 * (SPI1_CS_Pin/GPIOA, RST_Pin/GPIOB, HRDY_Pin/GPIOA).
 **/
#define EPD_RST_PIN  0
#define EPD_CS_PIN   1
#define EPD_BUSY_PIN 2

/**
 * data
 **/
#define UBYTE   uint8_t
#define UWORD   uint16_t
#define UDOUBLE uint32_t

/*------------------------------------------------------------------------------------------------------*/
void DEV_Digital_Write(UWORD Pin, UBYTE Value);
UBYTE DEV_Digital_Read(UWORD Pin);

void DEV_SPI_WriteByte(UBYTE Value);
UBYTE DEV_SPI_ReadByte(void);

void DEV_Delay_ms(UDOUBLE xms);
void DEV_Delay_us(UDOUBLE xus);

UBYTE DEV_Module_Init(void);
void DEV_Module_Exit(void);

#endif
