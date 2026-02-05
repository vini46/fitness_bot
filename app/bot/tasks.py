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

    workouts = fetch_workout_details(tg_id)
    cals = user_data.get('calories_consumed', 0)
    weight = user_data.get('weight', "Not recorded")

    prompt = (f"Analyze: Cals Consumed:{cals}, Weight:{weight}kg, {workouts}. "
              "Give a smart coaching summary. DO NOT use underscores (_) and use minimal bolding.")
    
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
    logger.info("Starting scheduled morning reminder job.")
    all_users = get_unique_users()
    for user_id in all_users:
        try:
            time.sleep(random.uniform(2, 5))
            bot.send_message(user_id, "☀️ Good morning! Don't forget to log your weight today. Just type something like '85kg' or 'My weight is 85'.")
        except Exception as e:
            logger.error(f"Error in morning reminder for {user_id}: {e}")

def water_reminder():
    logger.info("Starting scheduled water reminder job.")
    all_users = get_unique_users()
    if not all_users:
        logger.warning("No users found for water reminder.")
    for user_id in all_users:
        try:
            time.sleep(random.uniform(2, 5))
            bot.send_message(user_id, "💧 Stay hydrated! Time for a glass of water.")
            logger.info(f"Water reminder sent to {user_id}")
        except Exception as e:
            logger.error(f"Error sending water reminder to {user_id}: {e}")

def workout_nudge():
    logger.info("Starting scheduled workout nudge job.")
    from app.services.garmin import get_garmin_client
    all_users = get_unique_users()
    
    today = get_today_str()
    for user_id in all_users:
        try:
            time.sleep(random.uniform(2, 5))
            api = get_garmin_client(user_id)
            if not api: continue
            
            activities = api.get_activities_by_date(today, today)
            if not activities:
                bot.send_message(user_id, "💪 Don't forget to move today! A quick walk or a short workout makes a big difference. You've got this!")
                logger.info(f"Workout nudge sent to {user_id}")
        except Exception as e:
            logger.error(f"Error in workout nudge for {user_id}: {e}")
