#include "platform.h"
#include "main.h"
#include <string.h>
#include <stdlib.h>

extern I2C_HandleTypeDef hi2c1;

uint8_t VL53L8CX_RdByte(VL53L8CX_Platform *p_platform,
                         uint16_t RegisterAddress,
                         uint8_t  *p_value)
{
    uint8_t reg[2] = { RegisterAddress >> 8, RegisterAddress & 0xFF };
    HAL_I2C_Master_Transmit(&hi2c1, p_platform->address,
                             reg, 2, HAL_MAX_DELAY);
    HAL_I2C_Master_Receive (&hi2c1, p_platform->address,
                             p_value, 1, HAL_MAX_DELAY);
    return 0;
}

uint8_t VL53L8CX_WrByte(VL53L8CX_Platform *p_platform,
                          uint16_t RegisterAddress,
                          uint8_t   value)
{
    uint8_t buf[3] = { RegisterAddress >> 8, RegisterAddress & 0xFF, value };
    HAL_I2C_Master_Transmit(&hi2c1, p_platform->address,
                             buf, 3, HAL_MAX_DELAY);
    return 0;
}

uint8_t VL53L8CX_RdMulti(VL53L8CX_Platform *p_platform,
                           uint16_t RegisterAddress,
                           uint8_t  *p_values,
                           uint32_t  size)
{
    uint8_t reg[2] = { RegisterAddress >> 8, RegisterAddress & 0xFF };
    HAL_I2C_Master_Transmit(&hi2c1, p_platform->address,
                             reg, 2, HAL_MAX_DELAY);
    HAL_I2C_Master_Receive (&hi2c1, p_platform->address,
                             p_values, size, HAL_MAX_DELAY);
    return 0;
}

uint8_t VL53L8CX_WrMulti(VL53L8CX_Platform *p_platform,
                           uint16_t RegisterAddress,
                           uint8_t  *p_values,
                           uint32_t  size)
{
    uint8_t *buf = (uint8_t *)malloc(size + 2);
    if (buf == NULL) return 1;

    buf[0] = RegisterAddress >> 8;
    buf[1] = RegisterAddress & 0xFF;
    memcpy(&buf[2], p_values, size);

    HAL_I2C_Master_Transmit(&hi2c1, p_platform->address,
                             buf, size + 2, HAL_MAX_DELAY);
    free(buf);
    return 0;
}

void VL53L8CX_SwapBuffer(uint8_t *buffer, uint16_t size)
{
    uint32_t i, tmp;
    for (i = 0; i < size; i += 4)
    {
        tmp = ((uint32_t)buffer[i]   << 24)
            | ((uint32_t)buffer[i+1] << 16)
            | ((uint32_t)buffer[i+2] <<  8)
            | ((uint32_t)buffer[i+3]);
        memcpy(&buffer[i], &tmp, 4);
    }
}

void VL53L8CX_WaitMs(VL53L8CX_Platform *p_platform, uint32_t TimeMs)
{
    (void)p_platform;
    HAL_Delay(TimeMs);
}