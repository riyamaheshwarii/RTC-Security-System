/* rtc.h */
#ifndef RTC_H
#define RTC_H
/* Includes ------------------------------------------------------------------*/
#include "main.h"
/* -------------------------------------------------------------------------- */
/*                         Exported Types / Structs                            */
/* -------------------------------------------------------------------------- */
/**
 * @brief  Holds all alarm configuration (enable / disable times and state).
 */
typedef struct
{
    int enableHour;
    int enableMinute;
    int enableSecond;
    int disableHour;
    int disableMinute;
    int disableSecond;
    int active;      /**< 1 = alarm is currently active, 0 = inactive */
} AlarmConfig_t;
/* -------------------------------------------------------------------------- */
/*                        Exported Function Prototypes                         */
/* -------------------------------------------------------------------------- */
/**
 * @brief  Sets the RTC time using binary-format values.
 * @param  hours   : Hour   value (0-23)
 * @param  minutes : Minute value (0-59)
 * @param  seconds : Second value (0-59)
 * @retval None
 */
void RTC_SetCurrentTime(int hours, int minutes, int seconds);
/**
 * @brief  Reads the current time from the RTC peripheral.
 * @param  gTime : Pointer to an RTC_TimeTypeDef structure to fill.
 * @param  gDate : Pointer to an RTC_DateTypeDef structure to fill.
 *                 (Must be read even if unused — required by the HAL.)
 * @retval None
 */
void RTC_GetCurrentTime(RTC_TimeTypeDef *gTime, RTC_DateTypeDef *gDate);
/**
 * @brief  Checks whether the current RTC time matches the alarm-enable time.
 * @param  gTime  : Current time from the RTC.
 * @param  alarm  : Pointer to the AlarmConfig_t to update.
 * @retval 1 if just enabled, 0 otherwise.
 */
int RTC_CheckAlarmEnable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm);
/**
 * @brief  Checks whether the current RTC time matches the alarm-disable time.
 * @param  gTime  : Current time from the RTC.
 * @param  alarm  : Pointer to the AlarmConfig_t to update.
 * @retval 1 if just disabled, 0 otherwise.
 */
int RTC_CheckAlarmDisable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm);
#endif /* RTC_H */
