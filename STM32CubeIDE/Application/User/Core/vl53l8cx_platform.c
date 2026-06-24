#include "platform.h"
#include "main.h"

extern I2C_HandleTypeDef hi2c1;

uint8_t VL53L8CX_RdByte(VL53L8CX_Platform *p_platform, uint16_t RegisterAddress, uint8_t *p_value) {
    if (HAL_I2C_Mem_Read(&hi2c1, p_platform->address, RegisterAddress, I2C_MEMADD_SIZE_16BIT, p_value, 1, HAL_MAX_DELAY) == HAL_OK) return 0;
    return 1;
}

uint8_t VL53L8CX_WrByte(VL53L8CX_Platform *p_platform, uint16_t RegisterAddress, uint8_t value) {
    if (HAL_I2C_Mem_Write(&hi2c1, p_platform->address, RegisterAddress, I2C_MEMADD_SIZE_16BIT, &value, 1, HAL_MAX_DELAY) == HAL_OK) return 0;
    return 1;
}

/* Safely chunk massive reads to bypass 65KB limit */
/* Safely chunk massive reads */
uint8_t VL53L8CX_RdMulti(VL53L8CX_Platform *p_platform, uint16_t RegisterAddress, uint8_t *p_values, uint32_t size) {
    uint32_t position = 0;
    while (size > 0) {
        uint16_t chunk = (size > 4096) ? 4096 : size;
        if (HAL_I2C_Mem_Read(&hi2c1, p_platform->address, RegisterAddress + position, I2C_MEMADD_SIZE_16BIT, &p_values[position], chunk, HAL_MAX_DELAY) != HAL_OK) return 1;
        position += chunk;
        size -= chunk;
    }
    return 0;
}

/* Safely chunk massive firmware writes */
uint8_t VL53L8CX_WrMulti(VL53L8CX_Platform *p_platform, uint16_t RegisterAddress, uint8_t *p_values, uint32_t size) {
    uint32_t position = 0;
    while (size > 0) {
        uint16_t chunk = (size > 4096) ? 4096 : size;
        if (HAL_I2C_Mem_Write(&hi2c1, p_platform->address, RegisterAddress + position, I2C_MEMADD_SIZE_16BIT, &p_values[position], chunk, HAL_MAX_DELAY) != HAL_OK) return 1;
        position += chunk;
        size -= chunk;
    }
    return 0;
}
void VL53L8CX_SwapBuffer(uint8_t *buffer, uint16_t size) {
    uint32_t i;
    uint8_t tmp;
    for (i = 0; i < size; i = i + 4) {
        tmp = buffer[i]; buffer[i] = buffer[i + 3]; buffer[i + 3] = tmp;
        tmp = buffer[i + 1]; buffer[i + 1] = buffer[i + 2]; buffer[i + 2] = tmp;
    }
}

uint8_t VL53L8CX_WaitMs(VL53L8CX_Platform *p_platform, uint32_t TimeMs) {
    HAL_Delay(TimeMs);
    return 0;
}
