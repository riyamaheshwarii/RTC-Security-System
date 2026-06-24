/* uart.c */
/* Includes ------------------------------------------------------------------*/
#include "uart.h"
#include <string.h>
/* External handle declared in main.c / generated code ----------------------*/
extern UART_HandleTypeDef huart2;
/* -------------------------------------------------------------------------- */
/*                           Public Functions                                  */
/* -------------------------------------------------------------------------- */
/**
 * @brief  Transmits a null-terminated string over UART2.
 * @param  str: Pointer to the string to send.
 * @retval None
 */
void UART_SendString(char *str)
{
    HAL_UART_Transmit(&huart2,
                      (uint8_t *)str,
                      (uint16_t)strlen(str),
                      HAL_MAX_DELAY);
}
/**
 * @brief  Receives a single character from UART2 (blocking).
 * @retval Received character as char.
 */
char UART_GetChar(void)
{
    uint8_t ch;
    HAL_UART_Receive(&huart2,
                     &ch,
                     1,
                     HAL_MAX_DELAY);
    return (char)ch;
}
