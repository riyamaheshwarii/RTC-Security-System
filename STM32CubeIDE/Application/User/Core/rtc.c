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

// Helper function to check if the current time is within the active alarm window
static int IsInAlarmWindow(const RTC_TimeTypeDef *time, AlarmConfig_t *alarm)
{
    uint32_t currentSec = toTotalSeconds((int)time->Hours, (int)time->Minutes, (int)time->Seconds);
    uint32_t enableSec  = toTotalSeconds(alarm->enableHour, alarm->enableMinute, alarm->enableSecond);
    uint32_t disableSec = toTotalSeconds(alarm->disableHour, alarm->disableMinute, alarm->disableSecond);

    if (enableSec > disableSec) {
        // The schedule crosses midnight (e.g., 22:00 to 07:00)
        return (currentSec >= enableSec || currentSec < disableSec);
    } else {
        // The schedule is on the same day (e.g., 09:00 to 17:00)
        return (currentSec >= enableSec && currentSec < disableSec);
    }
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
    // If the current time enters the active window, enable the alarm
    if (IsInAlarmWindow(gTime, alarm))
    {
        alarm->active = 1;
        return 1;
    }
    return 0;
}

int RTC_CheckAlarmDisable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm)
{
    // If the current time is NO LONGER in the active window, disable the alarm
    if (!IsInAlarmWindow(gTime, alarm))
    {
        alarm->active = 0;
        return 1;
    }
    return 0;
}
