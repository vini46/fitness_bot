import os
import datetime
import json
import telebot
import pytz
import logging
import re
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- 0. LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURATION ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
MY_CHAT_ID = os.environ.get('MY_CHAT_ID')
IST = pytz.timezone('Asia/Kolkata')

bot = telebot.TeleBot(TOKEN)
client = genai.Client(api_key=GEMINI_KEY)
DB_FILE = "health_db.json"
MODEL_ID = "gemini-2.0-flash"

# --- 2. GARMIN SESSION (FOLDER BASED) ---
def init_garmin():
    token_dir = "./garmin_tokens"
    if not os.path.exists(token_dir):
        logger.error(f"❌ Garmin tokens folder missing at {token_dir}")
        return None
    try:
        api = Garmin()
        api.login(token_dir)
        logger.info("✅ Garmin session initialized.")
        return api
    except Exception as e:
        logger.error(f"❌ Garmin login failed: {e}")
        return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

# --- 3. DATABASE HELPERS ---
def get_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"weight": {}, "calories": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"DB Save Error: {e}")

# --- 4. DATA FETCHING ---
def fetch_workout_details():
    api = init_garmin()
    if not api: return "Garmin connection offline."
    
    today = get_today_str()
    try:
        activities = api.get_activities_by_date(today, today)
        if not activities: return "No workouts found for today yet."

        report = ""
        for act in activities:
            name = act.get('activityName', 'Activity')
            type_key = act.get('activityType', {}).get('typeKey', 'unknown')
            cals = act.get('calories', 0)
            duration = round(act.get('duration', 0) / 60, 1)
            
            report += f"🏃 *{name}* ({type_key.replace('_', ' ').title()})\n"
            report += f"⏱ {duration} min | 🔥 {cals} kcal\n"

            if type_key == 'strength_training':
                try:
                    sets = api.get_activity_exercise_sets(act.get('activityId'))
                    for s in sets.get('exerciseSets', []):
                        ex = s.get('exerciseName', 'Unknown')
                        reps = s.get('repetitionCount', 0)
                        wt = round(s.get('weight', 0)/1000, 1)
                        report += f"  • {ex}: {reps} reps @ {wt}kg\n"
                except: pass
            report += "---\n"
        return report
    except Exception as e:
        logger.error(f"Fetch Error: {e}")
        return "Error pulling Garmin data."

# --- 5. PROACTIVE TASKS ---
def morning_nudge():
    if MY_CHAT_ID:
        bot.send_message(MY_CHAT_ID, "☀️ *Morning Check-in:* Time to log your weight today!")

def water_nudge():
    if MY_CHAT_ID:
        bot.send_message(MY_CHAT_ID, "💧 *Hydration:* Stay sharp, drink some water.")

def daily_report_9pm():
    if not MY_CHAT_ID: return
    db = get_db()
    today = get_today_str()
    api = init_garmin()
    steps = 0
    if api:
        stats = api.get_user_summary(today)
        steps = stats.get('totalSteps') or stats.get('steps') or 0
    
    cals = db["calories"].get(today, 0)
    weight = db["weight"].get(today, "Not recorded")
    workouts = fetch_workout_details()

    prompt = (f"Analyze today's stats for an elite athlete. Steps:{steps}, Cals Consumed:{cals}, "
              f"Weight:{weight}kg. Workouts:{workouts}. Give a brutal but smart coaching summary.")
    
    try:
        analysis = client.models.generate_content(model=MODEL_ID, contents=prompt).text
        bot.send_message(MY_CHAT_ID, f"📊 *DAILY SUMMARY*\n\n{analysis}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Report Generation Error: {e}")

# --- 6. SCHEDULER ---
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(morning_nudge, 'cron', hour=8, minute=0)
scheduler.add_job(water_nudge, 'interval', hours=3)
scheduler.add_job(daily_report_9pm, 'cron', hour=21, minute=0)
scheduler.start()

# --- 7. HANDLERS ---
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    text = message.text.lower()
    db = get_db()
    today = get_today_str()
    logger.info(f"Processing input: {text}")

    # TRIGGER: Workout Info
    if any(w in text for w in ["workout", "exercise", "activity", "training"]):
        bot.send_chat_action(message.chat.id, 'typing')
        bot.reply_to(message, fetch_workout_details(), parse_mode="Markdown")

    # TRIGGER: Weight Logging
    elif "kg" in text or "weight" in text:
        try:
            res = client.models.generate_content(model=MODEL_ID, contents=f"Extract weight number from '{text}'. Just the number.").text
            val = "".join(re.findall(r"[-+]?\d*\.\d+|\d+", res)) # Extracts floats/ints
            db["weight"][today] = val
            save_db(db)
            bot.reply_to(message, f"⚖️ Weight: {val}kg.")
        except: bot.reply_to(message, "Failed to parse weight.")

    # TRIGGER: Food Logging
    elif any(w in text for w in ["ate", "lunch", "dinner", "snack", "scoops", "had"]):
        bot.send_chat_action(message.chat.id, 'typing')
        prompt = f"Estimate total calories for: '{text}'. Reply with ONLY the integer number."
        try:
            res = client.models.generate_content(model=MODEL_ID, contents=prompt).text
            # ROBUST CLEANER: Extract only the digits
            cals_only = "".join(filter(str.isdigit, res))
            if cals_only:
                cals_val = int(cals_only)
                db["calories"][today] = db["calories"].get(today, 0) + cals_val
                save_db(db)
                bot.reply_to(message, f"🍎 Added ~{cals_val} kcal.\nTotal Today: {db['calories'][today]} kcal.")
            else:
                bot.reply_to(message, "Could not estimate calories. Be more specific?")
        except Exception as e:
            logger.error(f"Food AI Error: {e}")
            bot.reply_to(message, "Error logging calories.")

    # FALLBACK: Coach Chat
    else:
        try:
            res = client.models.generate_content(model=MODEL_ID, contents=f"Short coach reply to: {text}")
            bot.reply_to(message, res.text)
        except: pass

# --- 8. RUN ---
app = Flask('')
@app.route('/')
def home(): return "Agent Active"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
    bot.remove_webhook()
    bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is polling...")
    bot.infinity_polling()