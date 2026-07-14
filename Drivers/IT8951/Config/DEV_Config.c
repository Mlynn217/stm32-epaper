/*****************************************************************************
* | File      	:   DEV_Config.c
* | Function    :   Hardware underlying interface
* | Info        :
*                STM32 (HAL) port of Waveshare's DEV_Config hardware
*                abstraction layer. Talks to the IT8951 over hspi1 (SPI1),
*                using the SPI1_CS/RST/HRDY GPIOs configured via
*                STM32CubeMX. GPIO/SPI peripherals themselves are already
*                initialized by MX_GPIO_Init()/MX_SPI1_Init() before this
*                driver is used, so DEV_Module_Init() has nothing to do.
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
#include "DEV_Config.h"
#include "main.h"

extern SPI_HandleTypeDef hspi1;

void DEV_Digital_Write(UWORD Pin, UBYTE Value)
{
    GPIO_PinState state = Value ? GPIO_PIN_SET : GPIO_PIN_RESET;

    switch (Pin)
    {
    case EPD_RST_PIN:
        HAL_GPIO_WritePin(RST_GPIO_Port, RST_Pin, state);
        break;
    case EPD_CS_PIN:
        HAL_GPIO_WritePin(SPI1_CS_GPIO_Port, SPI1_CS_Pin, state);
        break;
    default:
        break;
    }
}

UBYTE DEV_Digital_Read(UWORD Pin)
{
    switch (Pin)
    {
    case EPD_BUSY_PIN:
        return (UBYTE)HAL_GPIO_ReadPin(HRDY_GPIO_Port, HRDY_Pin);
    default:
        return 0;
    }
}

void DEV_SPI_WriteByte(UBYTE Value)
{
    UBYTE rx;
    HAL_SPI_TransmitReceive(&hspi1, &Value, &rx, 1, HAL_MAX_DELAY);
}

UBYTE DEV_SPI_ReadByte(void)
{
    UBYTE tx = 0x00;
    UBYTE rx = 0x00;
    HAL_SPI_TransmitReceive(&hspi1, &tx, &rx, 1, HAL_MAX_DELAY);
    return rx;
}

void DEV_Delay_ms(UDOUBLE xms)
{
    HAL_Delay(xms);
}

void DEV_Delay_us(UDOUBLE xus)
{
    /* Best-effort microsecond delay. Not on any currently-exercised path
       (EPD_IT8951.c only calls DEV_Delay_ms), so precision doesn't matter yet. */
    volatile UDOUBLE count = xus * (SystemCoreClock / 1000000U / 4U);
    while (count--)
    {
        __NOP();
    }
}

UBYTE DEV_Module_Init(void)
{
    /* GPIO/SPI1 are already brought up by MX_GPIO_Init()/MX_SPI1_Init()
       before this driver is used - nothing else to do here. */
    return 0;
}

void DEV_Module_Exit(void)
{
}
