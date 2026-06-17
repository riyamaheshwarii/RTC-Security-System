/* rtc.c */
/* Includes ------------------------------------------------------------------*/
#include "rtc.h"
/* External handle declared in generated / MX code --------------------------*/
extern RTC_HandleTypeDef hrtc;
/* -------------------------------------------------------------------------- */
/*                           Public Functions                                  */
/* -------------------------------------------------------------------------- */
/**
 * @brief  Sets the RTC time and a fixed default date (Mon 01-Jan-2024).
 * @param  hours   : Hour   value (0-23)
 * @param  minutes : Minute value (0-59)
 * @param  seconds : Second value (0-59)
 * @retval None
 */
void RTC_SetCurrentTime(int hours, int minutes, int seconds)
{
    RTC_TimeTypeDef sTime = {0};
    RTC_DateTypeDef sDate = {0};
    /* ----- Set Time ----- */
    sTime.Hours   = (uint8_t)hours;
    sTime.Minutes = (uint8_t)minutes;
    sTime.Seconds = (uint8_t)seconds;
    HAL_RTC_SetTime(&hrtc, &sTime, RTC_FORMAT_BIN);
    /* ----- Set a default date (required by HAL) ----- */
    sDate.WeekDay = RTC_WEEKDAY_MONDAY;
    sDate.Month   = RTC_MONTH_JANUARY;
    sDate.Date    = 1;
    sDate.Year    = 24;   /* 2024 */
    HAL_RTC_SetDate(&hrtc, &sDate, RTC_FORMAT_BIN);
}
/**
 * @brief  Reads the current time from the RTC peripheral.
 *         NOTE: HAL requires that GetDate() is always called after GetTime()
 *               to unlock the shadow registers.
 * @param  gTime : Pointer to an RTC_TimeTypeDef structure to fill.
 * @param  gDate : Pointer to an RTC_DateTypeDef structure to fill.
 * @retval None
 */
void RTC_GetCurrentTime(RTC_TimeTypeDef *gTime, RTC_DateTypeDef *gDate)
{
    HAL_RTC_GetTime(&hrtc, gTime, RTC_FORMAT_BIN);
    HAL_RTC_GetDate(&hrtc, gDate, RTC_FORMAT_BIN);
}
/**
 * @brief  Checks whether the current RTC time matches the alarm-enable time.
 *         Sets alarm->active = 1 if matched.
 * @param  gTime : Current time from the RTC.
 * @param  alarm : Pointer to the AlarmConfig_t to update.
 * @retval 1 if the alarm was just enabled, 0 otherwise.
 */
int RTC_CheckAlarmEnable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm)
{
    if (gTime->Hours   == (uint32_t)alarm->enableHour   &&
        gTime->Minutes == (uint32_t)alarm->enableMinute &&
        gTime->Seconds == (uint32_t)alarm->enableSecond)
    {
        alarm->active = 1;
        return 1;
    }
    return 0;
}
/**
 * @brief  Checks whether the current RTC time matches the alarm-disable time.
 *         Sets alarm->active = 0 if matched.
 * @param  gTime : Current time from the RTC.
 * @param  alarm : Pointer to the AlarmConfig_t to update.
 * @retval 1 if the alarm was just disabled, 0 otherwise.
 */
int RTC_CheckAlarmDisable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm)
{
    if (gTime->Hours   == (uint32_t)alarm->disableHour   &&
        gTime->Minutes == (uint32_t)alarm->disableMinute &&
        gTime->Seconds == (uint32_t)alarm->disableSecond)
    {
        alarm->active = 0;
        return 1;
    }
    return 0;
}
