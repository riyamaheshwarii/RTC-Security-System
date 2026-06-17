/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
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
/* Includes ------------------------------------------------------------------*/
#include "main.h"
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include "uart.h"
#include "rtc.h"
/* USER CODE END Includes */
/* Private variables ---------------------------------------------------------*/
RTC_HandleTypeDef hrtc;
UART_HandleTypeDef huart2;
/* USER CODE BEGIN PV */
/* All alarm state is managed through the AlarmConfig_t struct (see rtc.h) */
/* USER CODE END PV */
/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_RTC_Init(void);
static void MX_USART2_UART_Init(void);
/* -------------------------------------------------------------------------- */
/*                          Helpers: Parse Time Input                          */
/* -------------------------------------------------------------------------- */
/**
 * @brief  Prompts the user over UART, reads 6 digit characters (HHMMSS),
 *         and echoes them back.  Parses into hours / minutes / seconds.
 *
 * @param  prompt   : Message sent before reading input.
 * @param  outHour  : Parsed hour   (0-23).
 * @param  outMin   : Parsed minute (0-59).
 * @param  outSec   : Parsed second (0-59).
 */
static void ReadTimeFromUART(const char *prompt,
                             int *outHour,
                             int *outMin,
                             int *outSec)
{
    char buf[7];
    UART_SendString((char *)prompt);
    for (int i = 0; i < 6; i++)
    {
        buf[i] = UART_GetChar();
        /* Echo the received character */
        HAL_UART_Transmit(&huart2,
                          (uint8_t *)&buf[i],
                          1,
                          HAL_MAX_DELAY);
    }
    buf[6] = '\0';
    *outHour = (buf[0] - '0') * 10 + (buf[1] - '0');
    *outMin  = (buf[2] - '0') * 10 + (buf[3] - '0');
    *outSec  = (buf[4] - '0') * 10 + (buf[5] - '0');
}
/* -------------------------------------------------------------------------- */
/*                           Application Entry Point                           */
/* -------------------------------------------------------------------------- */
/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
    /* ---- MCU Init ---- */
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    MX_RTC_Init();
    MX_USART2_UART_Init();
    /* USER CODE BEGIN 2 */
    AlarmConfig_t alarm = {0};
    char msgBuf[60];
    /* ---- 1. Current Time ---- */
    int currentHour, currentMinute, currentSecond;
    ReadTimeFromUART("\r\nEnter Current Time (HHMMSS): ",
                     &currentHour, &currentMinute, &currentSecond);
    /* ---- 2. Alarm Enable Time ---- */
    ReadTimeFromUART("\r\n\nEnter Alarm Enable Time (HHMMSS): ",
                     &alarm.enableHour,
                     &alarm.enableMinute,
                     &alarm.enableSecond);
    sprintf(msgBuf,
            "\r\nAlarm Enable Time: %02d:%02d:%02d\r\n",
            alarm.enableHour,
            alarm.enableMinute,
            alarm.enableSecond);
    UART_SendString(msgBuf);
    /* ---- 3. Alarm Disable Time ---- */
    ReadTimeFromUART("\r\nEnter Alarm Disable Time (HHMMSS): ",
                     &alarm.disableHour,
                     &alarm.disableMinute,
                     &alarm.disableSecond);
    sprintf(msgBuf,
            "\r\nAlarm Disable Time: %02d:%02d:%02d\r\n",
            alarm.disableHour,
            alarm.disableMinute,
            alarm.disableSecond);
    UART_SendString(msgBuf);
    /* ---- 4. Set RTC ---- */
    RTC_SetCurrentTime(currentHour, currentMinute, currentSecond);
    UART_SendString("\r\nRTC Time Set Successfully\r\n");
    /* USER CODE END 2 */
    /* ---- Infinite Loop ---- */
    /* USER CODE BEGIN WHILE */
    UART_SendString("\r\n===== START =====\r\n");
    while (1)
    {
        RTC_TimeTypeDef gTime;
        RTC_DateTypeDef gDate;
        RTC_GetCurrentTime(&gTime, &gDate);
        sprintf(msgBuf,
                "\r\nCurrent Time: %02d:%02d:%02d",
                gTime.Hours,
                gTime.Minutes,
                gTime.Seconds);
        UART_SendString(msgBuf);
        /* Check if alarm should be enabled */
        if (RTC_CheckAlarmEnable(&gTime, &alarm))
        {
            UART_SendString("\r\nALARM ENABLED\r\n");
        }
        /* Check if alarm should be disabled */
        if (RTC_CheckAlarmDisable(&gTime, &alarm))
        {
            UART_SendString("\r\nALARM DISABLED\r\n");
            break;
        }
        HAL_Delay(1000);
    }
    /* USER CODE END WHILE */
    UART_SendString("\r\n====STOPPED====\r\n");
    /* Halt */
    while (1) { /* intentional infinite loop */ }
    /* USER CODE BEGIN 3 */
    /* USER CODE END 3 */
}
/* -------------------------------------------------------------------------- */
/*                    STM32 Peripheral Init (MX Generated)                     */
/* -------------------------------------------------------------------------- */
/**
  * @brief  System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
    if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
    {
        Error_Handler();
    }
    HAL_PWR_EnableBkUpAccess();
    __HAL_RCC_LSEDRIVE_CONFIG(RCC_LSEDRIVE_LOW);
    RCC_OscInitStruct.OscillatorType      = RCC_OSCILLATORTYPE_HSI | RCC_OSCILLATORTYPE_LSE;
    RCC_OscInitStruct.LSEState            = RCC_LSE_ON;
    RCC_OscInitStruct.HSIState            = RCC_HSI_ON;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState        = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource       = RCC_PLLSOURCE_HSI;
    RCC_OscInitStruct.PLL.PLLM            = 1;
    RCC_OscInitStruct.PLL.PLLN            = 10;
    RCC_OscInitStruct.PLL.PLLP            = RCC_PLLP_DIV7;
    RCC_OscInitStruct.PLL.PLLQ            = RCC_PLLQ_DIV2;
    RCC_OscInitStruct.PLL.PLLR            = RCC_PLLR_DIV2;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }
    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK  | RCC_CLOCKTYPE_SYSCLK
                                     | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK)
    {
        Error_Handler();
    }
}
/**
  * @brief  RTC Initialization Function
  * @retval None
  */
static void MX_RTC_Init(void)
{
    /* USER CODE BEGIN RTC_Init 0 */
    /* USER CODE END RTC_Init 0 */
    RTC_TimeTypeDef sTime  = {0};
    RTC_DateTypeDef sDate  = {0};
    RTC_AlarmTypeDef sAlarm = {0};
    /* USER CODE BEGIN RTC_Init 1 */
    /* USER CODE END RTC_Init 1 */
    hrtc.Instance            = RTC;
    hrtc.Init.HourFormat     = RTC_HOURFORMAT_24;
    hrtc.Init.AsynchPrediv   = 127;
    hrtc.Init.SynchPrediv    = 255;
    hrtc.Init.OutPut         = RTC_OUTPUT_DISABLE;
    hrtc.Init.OutPutRemap    = RTC_OUTPUT_REMAP_NONE;
    hrtc.Init.OutPutPolarity = RTC_OUTPUT_POLARITY_HIGH;
    hrtc.Init.OutPutType     = RTC_OUTPUT_TYPE_OPENDRAIN;
    if (HAL_RTC_Init(&hrtc) != HAL_OK)
    {
        Error_Handler();
    }
    /* USER CODE BEGIN Check_RTC_BKUP */
    /* USER CODE END Check_RTC_BKUP */
    /* Default Time = 00:00:00 */
    sTime.Hours          = 0x0;
    sTime.Minutes        = 0x0;
    sTime.Seconds        = 0x0;
    sTime.DayLightSaving = RTC_DAYLIGHTSAVING_NONE;
    sTime.StoreOperation = RTC_STOREOPERATION_RESET;
    if (HAL_RTC_SetTime(&hrtc, &sTime, RTC_FORMAT_BCD) != HAL_OK)
    {
        Error_Handler();
    }
    sDate.WeekDay = RTC_WEEKDAY_MONDAY;
    sDate.Month   = RTC_MONTH_JANUARY;
    sDate.Date    = 0x1;
    sDate.Year    = 0x0;
    if (HAL_RTC_SetDate(&hrtc, &sDate, RTC_FORMAT_BCD) != HAL_OK)
    {
        Error_Handler();
    }
    /* Enable Alarm A */
    sAlarm.AlarmTime.Hours              = 0x0;
    sAlarm.AlarmTime.Minutes            = 0x0;
    sAlarm.AlarmTime.Seconds            = 0x0;
    sAlarm.AlarmTime.SubSeconds         = 0x0;
    sAlarm.AlarmTime.DayLightSaving     = RTC_DAYLIGHTSAVING_NONE;
    sAlarm.AlarmTime.StoreOperation     = RTC_STOREOPERATION_RESET;
    sAlarm.AlarmMask                    = RTC_ALARMMASK_NONE;
    sAlarm.AlarmSubSecondMask           = RTC_ALARMSUBSECONDMASK_ALL;
    sAlarm.AlarmDateWeekDaySel          = RTC_ALARMDATEWEEKDAYSEL_DATE;
    sAlarm.AlarmDateWeekDay             = 0x1;
    sAlarm.Alarm                        = RTC_ALARM_A;
    if (HAL_RTC_SetAlarm_IT(&hrtc, &sAlarm, RTC_FORMAT_BCD) != HAL_OK)
    {
        Error_Handler();
    }
    /* USER CODE BEGIN RTC_Init 2 */
    /* USER CODE END RTC_Init 2 */
}
/**
  * @brief  USART2 Initialization Function
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{
    /* USER CODE BEGIN USART2_Init 0 */
    /* USER CODE END USART2_Init 0 */
    /* USER CODE BEGIN USART2_Init 1 */
    /* USER CODE END USART2_Init 1 */
    huart2.Instance                    = USART2;
    huart2.Init.BaudRate               = 115200;
    huart2.Init.WordLength             = UART_WORDLENGTH_8B;
    huart2.Init.StopBits               = UART_STOPBITS_1;
    huart2.Init.Parity                 = UART_PARITY_NONE;
    huart2.Init.Mode                   = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl              = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling           = UART_OVERSAMPLING_16;
    huart2.Init.OneBitSampling         = UART_ONE_BIT_SAMPLE_DISABLE;
    huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
    if (HAL_UART_Init(&huart2) != HAL_OK)
    {
        Error_Handler();
    }
    /* USER CODE BEGIN USART2_Init 2 */
    /* USER CODE END USART2_Init 2 */
}
/**
  * @brief  GPIO Initialization Function
  * @retval None
  */
static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    /* USER CODE BEGIN MX_GPIO_Init_1 */
    /* USER CODE END MX_GPIO_Init_1 */
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOH_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);
    /* B1 (Blue button) — falling edge interrupt */
    GPIO_InitStruct.Pin  = B1_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);
    /* LD2 (Green LED) — push-pull output */
    GPIO_InitStruct.Pin   = LD2_Pin;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LD2_GPIO_Port, &GPIO_InitStruct);
    /* USER CODE BEGIN MX_GPIO_Init_2 */
    /* USER CODE END MX_GPIO_Init_2 */
}
/* USER CODE BEGIN 4 */
/* USER CODE END 4 */
/**
  * @brief  Error Handler
  * @retval None
  */
void Error_Handler(void)
{
    /* USER CODE BEGIN Error_Handler_Debug */
    __disable_irq();
    while (1) { /* intentional infinite loop */ }
    /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the source file name and line number where an
  *         assert_param error occurred.
  * @param  file : pointer to the source file name
  * @param  line : assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
    /* USER CODE BEGIN 6 */
    /* User can add their own implementation to report the file name and line
       number, e.g.: printf("Wrong parameters value: file %s on line %d\r\n",
       file, line) */
    /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
