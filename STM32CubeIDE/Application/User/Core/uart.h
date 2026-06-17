/* uart.h */
#ifndef UART_H
#define UART_H
/* Includes ------------------------------------------------------------------*/
#include "main.h"
/* Exported function prototypes ----------------------------------------------*/
/**
 * @brief  Transmits a null-terminated string over UART2.
 * @param  str: Pointer to the string to send.
 * @retval None
 */
void UART_SendString(char *str);
/**
 * @brief  Receives a single character from UART2 (blocking).
 * @retval Received character as char.
 */
char UART_GetChar(void);
#endif /* UART_H */
