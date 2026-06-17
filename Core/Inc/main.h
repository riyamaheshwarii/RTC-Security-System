/* main.h */
/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef MAIN_H
#define MAIN_H
#ifdef __cplusplus
extern "C" {
#endif
/* Includes ------------------------------------------------------------------*/
#include "stm32l4xx_hal.h"
/* Exported defines ----------------------------------------------------------*/
/* B1 (Blue push-button) */
#define B1_Pin           GPIO_PIN_13
#define B1_GPIO_Port     GPIOC
#define B1_Pin               GPIO_PIN_13
#define B1_GPIO_Port         GPIOC
/* LD2 (Green LED) */
#define LD2_Pin          GPIO_PIN_5
#define LD2_GPIO_Port    GPIOA
#define LD2_Pin              GPIO_PIN_5
#define LD2_GPIO_Port        GPIOA
/* USART2 TX / RX  (PA2 = TX, PA3 = RX  — used by stm32l4xx_hal_msp.c) */
#define USART_TX_Pin         GPIO_PIN_2
#define USART_TX_GPIO_Port   GPIOA
#define USART_RX_Pin         GPIO_PIN_3
#define USART_RX_GPIO_Port   GPIOA
/* Exported function prototypes ----------------------------------------------*/
void Error_Handler(void);
#ifdef __cplusplus
}
#endif
#endif /* MAIN_H */
