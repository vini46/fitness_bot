from apscheduler.schedulers.background import BackgroundScheduler
from app.config import IST
from app.bot.tasks import (
    multi_user_report_9pm, 
    morning_reminder, 
    water_reminder, 
    workout_nudge
)

def start_scheduler():
    scheduler = BackgroundScheduler(timezone=IST)
    scheduler.add_job(multi_user_report_9pm, 'cron', hour=21, minute=0)
    scheduler.add_job(morning_reminder, 'cron', hour=8, minute=0)
    scheduler.add_job(water_reminder, 'cron', hour='9,12,15,18,21', minute=0)
    scheduler.add_job(workout_nudge, 'cron', hour=18, minute=0)
    scheduler.start()
    return scheduler
