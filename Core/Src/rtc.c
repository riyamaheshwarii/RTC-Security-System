/* rtc.c */
#include "rtc.h"

extern RTC_HandleTypeDef hrtc;

/* -------------------------------------------------------------------------- */
/*                          Private Helper                                     */
/* -------------------------------------------------------------------------- */

static uint32_t toTotalSeconds(int h, int m, int s)
{
    return (uint32_t)(h * 3600 + m * 60 + s);
}

/* -------------------------------------------------------------------------- */
/*                          Public Functions                                    */
/* -------------------------------------------------------------------------- */

void RTC_SetCurrentTime(int hours, int minutes, int seconds)
{
    RTC_TimeTypeDef sTime = {0};
    RTC_DateTypeDef sDate = {0};

    sTime.Hours   = (uint8_t)hours;
    sTime.Minutes = (uint8_t)minutes;
    sTime.Seconds = (uint8_t)seconds;
    HAL_RTC_SetTime(&hrtc, &sTime, RTC_FORMAT_BIN);

    sDate.WeekDay = RTC_WEEKDAY_MONDAY;
    sDate.Month   = RTC_MONTH_JANUARY;
    sDate.Date    = 1;
    sDate.Year    = 24;
    HAL_RTC_SetDate(&hrtc, &sDate, RTC_FORMAT_BIN);
}

void RTC_GetCurrentTime(RTC_TimeTypeDef *gTime, RTC_DateTypeDef *gDate)
{
    HAL_RTC_GetTime(&hrtc, gTime, RTC_FORMAT_BIN);
    HAL_RTC_GetDate(&hrtc, gDate, RTC_FORMAT_BIN);  /* mandatory unlock */
}

int RTC_CheckAlarmEnable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm)
{
    uint32_t current = toTotalSeconds((int)gTime->Hours,
                                      (int)gTime->Minutes,
                                      (int)gTime->Seconds);

    uint32_t target  = toTotalSeconds(alarm->enableHour,
                                      alarm->enableMinute,
                                      alarm->enableSecond);

    if (current >= target)   /* >= catches missed exact seconds */
    {
        alarm->active = 1;
        return 1;
    }
    return 0;
}

int RTC_CheckAlarmDisable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm)
{
    uint32_t current = toTotalSeconds((int)gTime->Hours,
                                      (int)gTime->Minutes,
                                      (int)gTime->Seconds);

    uint32_t target  = toTotalSeconds(alarm->disableHour,
                                      alarm->disableMinute,
                                      alarm->disableSecond);

    if (current >= target)   /* >= catches missed exact seconds */
    {
        alarm->active = 0;
        return 1;
    }
    return 0;
}
