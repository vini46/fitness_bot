import random
import time
import re
import datetime
import logging
from app.config import IST, MODEL_ID
from app.database import get_user_data, sync_to_supabase, supabase
from app.services.garmin import fetch_workout_details, get_today_str
from app.services.gemini import get_gemini_response
from app.bot.bot_instance import bot

logger = logging.getLogger(__name__)

def get_unique_users():
    try:
        res = supabase.table("user_configs").select("telegram_id").execute()
        unique_users = list(set([row['telegram_id'] for row in res.data]))
        logger.info(f"Fetched {len(unique_users)} unique users from {len(res.data)} total records.")
        return unique_users
    except Exception as e:
        logger.error(f"Error fetching unique users: {e}")
        return []

def run_report_for_user(tg_id):
    today = get_today_str()
    user_data = get_user_data(tg_id, today)
    if not user_data or not user_data.get('gemini_key'): return

    from app.services.garmin import fetch_workout_details, fetch_advanced_metrics
    workouts = fetch_workout_details(tg_id)
    advanced = fetch_advanced_metrics(tg_id)
    cals = user_data.get('calories_consumed', 0)
    weight = user_data.get('weight', "Not recorded")

    prompt = (f"Analyze: Cals Consumed:{cals}, Weight:{weight}kg, {workouts}. "
              f"Advanced Metrics: {advanced}. "
              "Give a smart coaching summary. Highlight recovery if Body Battery or Sleep is low. "
              "DO NOT use underscores (_) and use minimal bolding.")
    
    analysis = get_gemini_response(tg_id, prompt)
    
    if analysis == "RATE_LIMIT_EXCEEDED":
        bot.send_message(tg_id, "⏳ AI is busy. Try `/report` in a few minutes.")
        return

    clean_analysis = analysis.replace("_", "-").replace("[", "(").replace("]", ")")

    try:
        bot.send_message(tg_id, f"📊 *HEALTH SUMMARY*\n\n{clean_analysis}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Markdown failed for {tg_id}: {e}. Sending plain text.")
        bot.send_message(tg_id, f"📊 HEALTH SUMMARY\n\n{analysis}")

def multi_user_report_9pm():
    logger.info("Starting scheduled 9pm report job.")
    all_users = get_unique_users()
    for user_id in all_users:
        try:
            time.sleep(random.uniform(2, 5))
            run_report_for_user(user_id)
        except Exception as e:
            logger.error(f"Error in 9pm report for {user_id}: {e}")

def morning_reminder():
    logger.info("Starting morning reminder job.")
    all_users = get_unique_users()
    today = get_today_str()
    slot = "weight_8am"

    for user_id in all_users:
        try:
            user_data = get_user_data(user_id, today)
            notified = user_data.get('last_notified', {})

            if notified.get(slot) == today:
                continue

            time.sleep(random.uniform(2, 5))
            bot.send_message(user_id, "☀️ Good morning! Don't forget to log your weight today. Just type something like '85kg' or 'My weight is 85'.")
            
            notified[slot] = today
            sync_to_supabase(user_id, today, {"last_notified": notified})
        except Exception as e:
            logger.error(f"Error in morning reminder for {user_id}: {e}")

def water_reminder(specific_hr=None):
    logger.info(f"Starting water reminder check (hr={specific_hr}).")
    all_users = get_unique_users()
    if not all_users: return

    hr = specific_hr if specific_hr is not None else datetime.datetime.now(IST).hour
    today = get_today_str()
    slot = f"water_{hr}h"

    for user_id in all_users:
        try:
            user_data = get_user_data(user_id, today)
            notified = user_data.get('last_notified', {})
            
            if notified.get(slot) == today:
                continue

            time.sleep(random.uniform(0.5, 1.5))
            bot.send_message(user_id, "💧 Stay hydrated! Time for a glass of water.")
            
            notified[slot] = today
            sync_to_supabase(user_id, today, {"last_notified": notified})
            logger.info(f"Water reminder sent for {user_id} ({slot})")
        except Exception as e:
            logger.error(f"Error in water reminder ({slot}): {e}")

def workout_nudge():
    logger.info("Starting workout nudge job.")
    all_users = get_unique_users()
    today = get_today_str()
    slot = "workout_6pm"
    from app.services.garmin import get_garmin_client
    
    for user_id in all_users:
        try:
            user_data = get_user_data(user_id, today)
            notified = user_data.get('last_notified', {})

            if notified.get(slot) == today:
                continue

            time.sleep(random.uniform(0.5, 1.5))
            api = get_garmin_client(user_id)
            if not api: continue
            
            activities = api.get_activities_by_date(today, today)
            if not activities:
                bot.send_message(user_id, "💪 Don't forget to move today! A quick walk or a short workout makes a big difference. You've got this!")
                
                notified[slot] = today
                sync_to_supabase(user_id, today, {"last_notified": notified})
        except Exception as e:
            logger.error(f"Error in workout nudge for {user_id}: {e}")

def startup_catchup():
    """Run on startup to catch any reminders missed during downtime."""
    logger.info("Running robust startup catch-up check.")
    now = datetime.datetime.now(IST)
    hr = now.hour
    
    # 1. Catch 8 AM Morning Reminder if bot starts later
    if hr >= 8:
        morning_reminder()
        
    # 2. Catch all scheduled Water Reminders (9, 12, 15, 18, 21) that were missed
    water_slots = [9, 12, 15, 18, 21]
    for w_hr in water_slots:
        if hr >= w_hr:
            water_reminder(specific_hr=w_hr)
            
    # 3. Catch 6 PM Workout Nudge if bot starts later
    if hr >= 18:
        workout_nudge()
