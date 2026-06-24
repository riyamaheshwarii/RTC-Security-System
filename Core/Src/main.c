/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : RTC Alarm + VL53L8CX Proximity + Buzzer (multi-session)
  ******************************************************************************
  */
/* USER CODE END Header */

#include "main.h"

/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <unistd.h>
#include "uart.h"
#include "rtc.h"
#include "platform.h"
#define VL53L8CX_NB_TARGET_PER_ZONE 1U
#include "vl53l8cx_api.h"
/* USER CODE END Includes */

/* USER CODE BEGIN PTD */
typedef enum {
    MENU_SET_CURRENT_TIME  = '1',
    MENU_SET_ENABLE_TIME   = '2',
    MENU_SET_DISABLE_TIME  = '3',
    MENU_START_MONITORING  = '4',
    MENU_VIEW_STATUS       = '5',
    MENU_AUTO_ARM          = '6',
} MenuOption_t;

typedef enum {
    STATE_IDLE,
    STATE_ALARM_ACTIVE,
    STATE_STOPPED,
} AlarmState_t;
/* USER CODE END PTD */

/* USER CODE BEGIN PD */
#define PROXIMITY_THRESHOLD_MM  300U
#define PWREN_PORT   GPIOA
#define PWREN_PIN    GPIO_PIN_7
#define LPN_PORT     GPIOA
#define LPN_PIN      GPIO_PIN_4
#define LED_PORT     GPIOA
#define LED_PIN      GPIO_PIN_5
/* USER CODE END PD */

#undef huart2
I2C_HandleTypeDef  hi2c1;
RTC_HandleTypeDef  hrtc;
UART_HandleTypeDef huart2;
TIM_HandleTypeDef  htim2;

void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_RTC_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM2_Init(void);

/* USER CODE BEGIN 0 */
int _write(int fd, char *ptr, int len)
{
    (void)fd;
    HAL_StatusTypeDef s = HAL_UART_Transmit(&huart2, (uint8_t *)ptr,
                                             (uint16_t)len, HAL_MAX_DELAY);
    return (s == HAL_OK) ? len : -1;
}

static void ReadTimeFromUART(const char *prompt, int *h, int *m, int *s)
{
    char buf[7];
    UART_SendString((char *)prompt);
    for (int i = 0; i < 6; i++) {
        buf[i] = UART_GetChar();
        HAL_UART_Transmit(&huart2, (uint8_t *)&buf[i], 1, HAL_MAX_DELAY);
    }
    buf[6] = '\0';
    *h = (buf[0]-'0')*10 + (buf[1]-'0');
    *m = (buf[2]-'0')*10 + (buf[3]-'0');
    *s = (buf[4]-'0')*10 + (buf[5]-'0');
}

static void PrintStatus(const AlarmConfig_t *alarm, int curH, int curM, int curS)
{
    printf("\r\n--- Config ---\r\n");
    printf("  Current : %02d:%02d:%02d\r\n", curH, curM, curS);
    printf("  Enable  : %02d:%02d:%02d\r\n",
           alarm->enableHour, alarm->enableMinute, alarm->enableSecond);
    printf("  Disable : %02d:%02d:%02d\r\n",
           alarm->disableHour, alarm->disableMinute, alarm->disableSecond);
    printf("--------------\r\n");
}

static void BuzzerOn(void)  { HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2); }
static void BuzzerOff(void) { HAL_TIM_PWM_Stop(&htim2,  TIM_CHANNEL_2); }
static void LedOn(void)     { HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);   }
static void LedOff(void)    { HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET); }

/*
 * Flush stale UART RX bytes AND clear any UART error flags that
 * accumulate when bytes arrive during monitoring (when nothing reads them).
 */
static void UART_FlushRX(void)
{
    uint8_t dummy;

    /* Wait 1 second so all bytes the GUI sent during monitoring arrive */
    HAL_Delay(1000);

    /* Clear overrun / noise / framing error flags BEFORE draining */
    __HAL_UART_CLEAR_OREFLAG(&huart2);
    __HAL_UART_CLEAR_NEFLAG(&huart2);
    __HAL_UART_CLEAR_FEFLAG(&huart2);

    /* Drain every byte from the RX buffer */
    while (HAL_UART_Receive(&huart2, &dummy, 1, 100) == HAL_OK) {}

    /* Clear flags again after drain — belt and braces */
    __HAL_UART_CLEAR_OREFLAG(&huart2);
    __HAL_UART_CLEAR_NEFLAG(&huart2);
    __HAL_UART_CLEAR_FEFLAG(&huart2);
}
/* USER CODE END 0 */

int main(void)
{
    HAL_Init();
    SystemClock_Config();
    MX_GPIO_Init();
    LedOn();

    MX_RTC_Init();
    MX_USART2_UART_Init();
    MX_I2C1_Init();
    MX_TIM2_Init();

    setvbuf(stdout, NULL, _IONBF, 0);

    /* Power up sensor */
    HAL_GPIO_WritePin(PWREN_PORT, PWREN_PIN, GPIO_PIN_SET);
    HAL_Delay(10);
    HAL_GPIO_WritePin(LPN_PORT, LPN_PIN, GPIO_PIN_SET);
    HAL_Delay(100);

    /* I2C scan */
    printf("\r\nScanning I2C bus...\r\n");
    int found = 0;
    for (uint8_t addr = 1; addr < 128; addr++) {
        if (HAL_I2C_IsDeviceReady(&hi2c1, (uint16_t)(addr<<1), 1, 10) == HAL_OK) {
            printf("  [FOUND] 0x%02X\r\n", addr);
            found++;
        }
    }
    printf("  Scan done. %d device(s) found.\r\n", found);

    /* ── VL53L8CX init ─────────────────────────────────────────────────────
     * IMPORTANT: We init and start ranging HERE, once, before the menu loop.
     * We NEVER call stop_ranging / start_ranging again. This avoids the sensor
     * hanging on the second call which was the root cause of the multi-session bug.
     * ─────────────────────────────────────────────────────────────────────── */
    static VL53L8CX_Configuration proxDev;
    static VL53L8CX_ResultsData   proxData;
    uint8_t proxReady = 0;
    proxDev.platform.address = VL53L8CX_DEFAULT_I2C_ADDRESS;

    printf("\r\nInitialising VL53L8CX...\r\n");
    if (vl53l8cx_init(&proxDev) != VL53L8CX_STATUS_OK) {
        printf("[ERROR] VL53L8CX init failed!\r\n");
        Error_Handler();
    }
    vl53l8cx_set_resolution(&proxDev, VL53L8CX_RESOLUTION_4X4);
    vl53l8cx_set_ranging_frequency_hz(&proxDev, 10);
    vl53l8cx_start_ranging(&proxDev);   /* <-- start ONCE, runs forever */
    printf("VL53L8CX OK! Threshold: %d mm\r\n", PROXIMITY_THRESHOLD_MM);

    AlarmConfig_t alarm = {0};
    int timeSet   = 0, enableSet = 0, disableSet = 0;
    int curH = 0, curM = 0, curS = 0;

    /* ══════════════════════════════════════════════════════════════════════
       OUTER LOOP  –  always returns here after monitoring stops
       ══════════════════════════════════════════════════════════════════════ */
    while (1)
    {


//        printf("\r\n=============================\r\n");
//        printf("    RTC ALARM SYSTEM SETUP   \r\n");
//        printf("=============================\r\n");
//        printf("  1. Set Current Time\r\n");
//        printf("  2. Set Alarm Enable Time\r\n");
//        printf("  3. Set Alarm Disable Time\r\n");
//        printf("  4. Start Monitoring\r\n");
//        printf("  5. View Config\r\n");
//        printf("  6. Auto Arm System\r\n");
//        printf("\r\nEnter choice: ");

        char choice = UART_GetChar();
        HAL_UART_Transmit(&huart2, (uint8_t *)&choice, 1, HAL_MAX_DELAY);
        printf("\r\n");

        switch ((MenuOption_t)choice)
        {
            case MENU_SET_CURRENT_TIME:
                ReadTimeFromUART("\r\nEnter Current Time (HHMMSS): ",
                                 &curH, &curM, &curS);
                printf("\r\nTime saved: %02d:%02d:%02d\r\n", curH, curM, curS);
                timeSet = 1;
                break;

            case MENU_SET_ENABLE_TIME:
                ReadTimeFromUART("\r\nEnter Enable Time (HHMMSS): ",
                                 &alarm.enableHour,
                                 &alarm.enableMinute,
                                 &alarm.enableSecond);
                printf("\r\nEnable Time: %02d:%02d:%02d\r\n",
                       alarm.enableHour, alarm.enableMinute, alarm.enableSecond);
                enableSet = 1;
                break;

            case MENU_SET_DISABLE_TIME:
                ReadTimeFromUART("\r\nEnter Disable Time (HHMMSS): ",
                                 &alarm.disableHour,
                                 &alarm.disableMinute,
                                 &alarm.disableSecond);
                printf("\r\nDisable Time: %02d:%02d:%02d\r\n",
                       alarm.disableHour, alarm.disableMinute, alarm.disableSecond);
                disableSet = 1;
                break;

            case MENU_AUTO_ARM:
                alarm.enableHour   = 22; alarm.enableMinute  = 0; alarm.enableSecond  = 0;
                alarm.disableHour  =  7; alarm.disableMinute = 0; alarm.disableSecond = 0;
                enableSet = 1; disableSet = 1;
                printf("\r\n[AUTO ARM] Enable: 22:00:00  Disable: 07:00:00\r\n");
                break;

            case MENU_VIEW_STATUS:
                PrintStatus(&alarm, curH, curM, curS);
                break;

            case MENU_START_MONITORING:
                if (!timeSet || (!enableSet && !disableSet)) {
                    printf("\r\n[ERROR] Set times first!\r\n");
                    break;
                }

                RTC_SetCurrentTime(curH, curM, curS);
                /* NOTE: Do NOT call vl53l8cx_start_ranging here.
                 * The sensor is already ranging from startup. */
                printf("\r\nRTC set. Starting...\r\n");
                printf("\r\n===== MONITORING STARTED =====\r\n");

                /* ── Inner monitoring loop ──────────────────────────────── */
                {
                    AlarmState_t state = STATE_IDLE;

                    while (state != STATE_STOPPED)
                    {
                        RTC_TimeTypeDef gTime;
                        RTC_DateTypeDef gDate;
                        RTC_GetCurrentTime(&gTime, &gDate);
                        printf("\r\nTime: %02d:%02d:%02d",
                               gTime.Hours, gTime.Minutes, gTime.Seconds);

                        switch (state)
                        {
                            case STATE_IDLE:
                                printf(" | IDLE");
                                if (RTC_CheckAlarmEnable(&gTime, &alarm)) {
                                    printf("\r\n>>> ALARM ENABLED <<<\r\n");
                                    state = STATE_ALARM_ACTIVE;
                                }
                                break;

                            case STATE_ALARM_ACTIVE:
                                printf(" | ALARM ACTIVE");
                                vl53l8cx_check_data_ready(&proxDev, &proxReady);
                                if (proxReady) {
                                    vl53l8cx_get_ranging_data(&proxDev, &proxData);
                                    int16_t dist   = proxData.distance_mm[0];
                                    uint8_t status = proxData.target_status[0];
                                    if (status == 5) {
                                        printf(" | %4d mm", dist);
                                        if (dist < PROXIMITY_THRESHOLD_MM) {
                                            printf(" | *** DETECTED! ***");
                                            LedOff();
                                            BuzzerOn();
                                        } else {
                                            printf(" | Clear");
                                            LedOn();
                                            BuzzerOff();
                                        }
                                    } else {
                                        printf(" | ---- mm");
                                        LedOff();
                                        BuzzerOff();
                                    }
                                }
                                if (RTC_CheckAlarmDisable(&gTime, &alarm)) {
                                    LedOff();
                                    BuzzerOff();
                                    printf("\r\n>>> ALARM DISABLED <<<\r\n");
                                    state = STATE_STOPPED;
                                }
                                break;

                            default:
                                break;
                        }
                        HAL_Delay(1000);
                    }
                }
                /* ── End inner loop ─────────────────────────────────────── */

                LedOff();
                BuzzerOff();
                /* NOTE: Do NOT call vl53l8cx_stop_ranging. Sensor stays active. */
                printf("\r\n===== MONITORING STOPPED =====\r\n");
                printf(">>> Flushing UART. Returning to menu in ~1 sec...\r\n");

                /* Clear stale bytes + UART error flags before re-entering menu */
                UART_FlushRX();

                break;   /* ← back to outer while(1) = menu */

            default:
                printf("\r\n[ERROR] Invalid choice. Enter 1-6.\r\n");
                break;
        }
    }
}

void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK) Error_Handler();
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
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) Error_Handler();

    RCC_ClkInitStruct.ClockType      = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                     | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource   = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider  = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4) != HAL_OK) Error_Handler();
}

static void MX_I2C1_Init(void)
{
    __HAL_RCC_GPIOB_CLK_ENABLE();
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin   = GPIO_PIN_8 | GPIO_PIN_9;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_OD;
    GPIO_InitStruct.Pull  = GPIO_PULLUP;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    for (int i = 0; i < 9; i++) {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_RESET); HAL_Delay(1);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_SET);   HAL_Delay(1);
    }
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, GPIO_PIN_RESET); HAL_Delay(1);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_8, GPIO_PIN_SET);   HAL_Delay(1);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, GPIO_PIN_SET);   HAL_Delay(10);

    __HAL_RCC_I2C1_CLK_ENABLE();
    hi2c1.Instance             = I2C1;
    hi2c1.Init.Timing          = 0x00F02B86;
    hi2c1.Init.OwnAddress1     = 0;
    hi2c1.Init.AddressingMode  = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c1.Init.OwnAddress2     = 0;
    hi2c1.Init.OwnAddress2Masks= I2C_OA2_NOMASK;
    hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c1.Init.NoStretchMode   = I2C_NOSTRETCH_DISABLE;
    if (HAL_I2C_Init(&hi2c1) != HAL_OK) Error_Handler();
    if (HAL_I2CEx_ConfigAnalogFilter(&hi2c1, I2C_ANALOGFILTER_ENABLE) != HAL_OK) Error_Handler();
    if (HAL_I2CEx_ConfigDigitalFilter(&hi2c1, 0) != HAL_OK) Error_Handler();

    GPIO_InitStruct.Pin       = GPIO_PIN_8 | GPIO_PIN_9;
    GPIO_InitStruct.Mode      = GPIO_MODE_AF_OD;
    GPIO_InitStruct.Pull      = GPIO_PULLUP;
    GPIO_InitStruct.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    GPIO_InitStruct.Alternate = GPIO_AF4_I2C1;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
}

static void MX_RTC_Init(void)
{
    RTC_TimeTypeDef  sTime  = {0};
    RTC_DateTypeDef  sDate  = {0};
    RTC_AlarmTypeDef sAlarm = {0};

    hrtc.Instance            = RTC;
    hrtc.Init.HourFormat     = RTC_HOURFORMAT_24;
    hrtc.Init.AsynchPrediv   = 127;
    hrtc.Init.SynchPrediv    = 255;
    hrtc.Init.OutPut         = RTC_OUTPUT_DISABLE;
    hrtc.Init.OutPutRemap    = RTC_OUTPUT_REMAP_NONE;
    hrtc.Init.OutPutPolarity = RTC_OUTPUT_POLARITY_HIGH;
    hrtc.Init.OutPutType     = RTC_OUTPUT_TYPE_OPENDRAIN;
    if (HAL_RTC_Init(&hrtc) != HAL_OK) Error_Handler();

    sTime.DayLightSaving = RTC_DAYLIGHTSAVING_NONE;
    sTime.StoreOperation = RTC_STOREOPERATION_RESET;
    if (HAL_RTC_SetTime(&hrtc, &sTime, RTC_FORMAT_BCD) != HAL_OK) Error_Handler();

    sDate.WeekDay = RTC_WEEKDAY_MONDAY;
    sDate.Month   = RTC_MONTH_JANUARY;
    sDate.Date    = 0x1;
    sDate.Year    = 0x0;
    if (HAL_RTC_SetDate(&hrtc, &sDate, RTC_FORMAT_BCD) != HAL_OK) Error_Handler();

    sAlarm.AlarmTime.DayLightSaving = RTC_DAYLIGHTSAVING_NONE;
    sAlarm.AlarmTime.StoreOperation = RTC_STOREOPERATION_RESET;
    sAlarm.AlarmMask           = RTC_ALARMMASK_NONE;
    sAlarm.AlarmSubSecondMask  = RTC_ALARMSUBSECONDMASK_ALL;
    sAlarm.AlarmDateWeekDaySel = RTC_ALARMDATEWEEKDAYSEL_DATE;
    sAlarm.AlarmDateWeekDay    = 0x1;
    sAlarm.Alarm               = RTC_ALARM_A;
    if (HAL_RTC_SetAlarm_IT(&hrtc, &sAlarm, RTC_FORMAT_BCD) != HAL_OK) Error_Handler();
}

static void MX_USART2_UART_Init(void)
{
    __HAL_RCC_USART2_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
    GPIO_InitStruct.Mode      = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Pull      = GPIO_NOPULL;
    GPIO_InitStruct.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    GPIO_InitStruct.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

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
    if (HAL_UART_Init(&huart2) != HAL_OK) Error_Handler();
}

static void MX_TIM2_Init(void)
{
    TIM_OC_InitTypeDef sConfigOC   = {0};
    GPIO_InitTypeDef   GPIO_InitStruct = {0};

    __HAL_RCC_TIM2_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitStruct.Pin       = GPIO_PIN_3;
    GPIO_InitStruct.Mode      = GPIO_MODE_AF_PP;
    GPIO_InitStruct.Pull      = GPIO_NOPULL;
    GPIO_InitStruct.Speed     = GPIO_SPEED_FREQ_LOW;
    GPIO_InitStruct.Alternate = GPIO_AF1_TIM2;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    htim2.Instance               = TIM2;
    htim2.Init.Prescaler         = 79;
    htim2.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim2.Init.Period            = 356;
    htim2.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    if (HAL_TIM_PWM_Init(&htim2) != HAL_OK) Error_Handler();

    TIM_OC_InitTypeDef sOC = {0};
    sOC.OCMode     = TIM_OCMODE_PWM1;
    sOC.Pulse      = 178;
    sOC.OCPolarity = TIM_OCPOLARITY_HIGH;
    sOC.OCFastMode = TIM_OCFAST_DISABLE;
    if (HAL_TIM_PWM_ConfigChannel(&htim2, &sOC, TIM_CHANNEL_2) != HAL_OK) Error_Handler();
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOH_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4 | GPIO_PIN_5 | GPIO_PIN_7, GPIO_PIN_RESET);

    GPIO_InitStruct.Pin  = GPIO_PIN_13;
    GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

    GPIO_InitStruct.Pin   = GPIO_PIN_4 | GPIO_PIN_5 | GPIO_PIN_7;
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

void Error_Handler(void)
{
    __disable_irq();
    while (1) { }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {}
#endif
