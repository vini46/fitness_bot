import random
import time
import re
import datetime
import logging
from app.config import IST, MODEL_ID
from app.database import get_user_data, sync_to_supabase, supabase
from app.services.garmin import fetch_workout_details, get_today_str
from app.services.llm_factory import get_llm_response
from app.bot.bot_instance import bot

logger = logging.getLogger(__name__)

def get_unique_users():
    try:
        res = supabase.table("users").select("telegram_id").execute()
        unique_users = [row['telegram_id'] for row in res.data]
        logger.info(f"Fetched {len(unique_users)} users from the new users table.")
        return unique_users
    except Exception as e:
        logger.error(f"Error fetching unique users: {e}")
        return []

def run_report_for_user(tg_id, mode="evening"):
    today = get_today_str()
    user_data = get_user_data(tg_id, today)
    if not user_data: return
    # Check if they have at least one key for a supported provider
    has_any_key = any(user_data.get(f"{p}_key") for p in ["gemini", "openrouter"])
    if not has_any_key: return

    from app.services.garmin import fetch_workout_details, fetch_advanced_metrics
    workouts = fetch_workout_details(tg_id)
    advanced_str, advanced_data = fetch_advanced_metrics(tg_id)
    
    # Persist the advanced metrics to database
    if advanced_data:
        sync_to_supabase(tg_id, today, advanced_data)
        # Refresh user_data to get the newly synced calories/metrics
        user_data = get_user_data(tg_id, today)

    cals = user_data.get('calories_consumed', 0)
    weight = user_data.get('weight', "Not recorded")

    if mode == "morning":
        prompt = (f"Kickoff the day for the user. Context: Weight:{weight}kg, {advanced_str}, {workouts}. "
                  "Focus on sleep quality and recovery from last night. Suggest an activity goal for today. "
                  "Keep it high-energy and motivating. DO NOT use underscores (_) and use minimal bolding.")
    else:
        # Use a fallback note if manual calories are 0 but Garmin has data
        nutrition_context = f"Manual Calories Logged: {cals}"
        if cals == 0 and "MFP Nutrition" in advanced_str:
            nutrition_context = "User didn't log food manually, but MyFitnessPal data is available. Use that for analysis."
            
        prompt = (f"Winddown report. Today's stats: {nutrition_context}, Weight:{weight}kg, {workouts}. "
                  f"Recovery & Nutrition Metrics: {advanced_str}. "
                  "Summarize today's achievements. Analyze nutrition and macro balance if data is present. "
                  "If recovery (Body Battery/Sleep) is low, suggest early sleep. "
                  "Keep it reflective and encouraging. DO NOT use underscores (_) and use minimal bolding.")
    
    analysis = get_llm_response(tg_id, prompt)
    
    if analysis == "RATE_LIMIT_EXCEEDED":
        bot.send_message(tg_id, "⏳ AI is busy or rate limited. Try `/report` in a few minutes or switch models.")
        return

    clean_analysis = analysis.replace("_", "-").replace("[", "(").replace("]", ")")

    try:
        title = "🌅 *MORNING KICKOFF*" if mode == "morning" else "📊 *HEALTH SUMMARY*"
        bot.send_message(tg_id, f"{title}\n\n{clean_analysis}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Markdown failed for {tg_id}: {e}. Sending plain text.")
        title_plain = "🌅 MORNING KICKOFF" if mode == "morning" else "📊 HEALTH SUMMARY"
        bot.send_message(tg_id, f"{title_plain}\n\n{analysis}")

def multi_user_kickoff_9am():
    logger.info("Starting scheduled 9am kickoff job.")
    all_users = get_unique_users()
    for user_id in all_users:
        try:
            time.sleep(random.uniform(2, 5))
            run_report_for_user(user_id, mode="morning")
        except Exception as e:
            logger.error(f"Error in 9am kickoff for {user_id}: {e}")

def multi_user_report_9pm():
    logger.info("Starting scheduled 9pm report job.")
    all_users = get_unique_users()
    for user_id in all_users:
        try:
            time.sleep(random.uniform(2, 5))
            run_report_for_user(user_id, mode="evening")
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
    
    # 0. Catch 9 AM Kickoff
    if hr >= 9:
        multi_user_kickoff_9am()
        
    # 1. Catch 8 AM Morning Reminder
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
