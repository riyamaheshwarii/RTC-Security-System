#ifndef RTC_H
#define RTC_H

#include "main.h"

typedef struct
{
    int enableHour;
    int enableMinute;
    int enableSecond;

    int disableHour;
    int disableMinute;
    int disableSecond;

    int active;   /* 1 = alarm currently active, 0 = inactive */
} AlarmConfig_t;

void RTC_SetCurrentTime(int hours, int minutes, int seconds);
void RTC_GetCurrentTime(RTC_TimeTypeDef *gTime, RTC_DateTypeDef *gDate);
int  RTC_CheckAlarmEnable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm);
int  RTC_CheckAlarmDisable(const RTC_TimeTypeDef *gTime, AlarmConfig_t *alarm);

#endif /* RTC_H */
