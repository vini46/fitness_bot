import os
import datetime
import json
import telebot
import pytz
import logging
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- 0. LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()] # Ensures logs go to Koyeb console
)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURATION ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
MY_CHAT_ID = os.environ.get('MY_CHAT_ID')
IST = pytz.timezone('Asia/Kolkata')

bot = telebot.TeleBot(TOKEN)
gemini = genai.Client(api_key=GEMINI_KEY)

DB_FILE = "health_db.json"

def get_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except Exception as e:
            logger.error(f"Error reading DB: {e}")
    return {"weight": {}, "calories": {}}

def save_db(data):
    try:
        with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
        logger.info("Database updated successfully.")
    except Exception as e:
        logger.error(f"Error saving DB: {e}")

# --- 2. GARMIN DATA HELPERS ---
def init_garmin():
    try:
        api = Garmin()
        api.login("./garmin_tokens")
        logger.info("Garmin session initialized from tokens.")
        return api
    except Exception as e:
        logger.error(f"Garmin login failed: {e}")
        return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

def fetch_workout_details():
    logger.info("Fetching workout details from Garmin...")
    api = init_garmin()
    if not api: return "Garmin connection is currently offline."
    
    today = get_today_str()
    activities = api.get_activities_by_date(today, today)
    
    if not activities:
        logger.info(f"No activities found for {today}")
        return "No workouts found for today yet. Get moving!"

    logger.info(f"Found {len(activities)} activities.")
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
                activity_id = act.get('activityId')
                sets = api.get_activity_exercise_sets(activity_id)
                for s in sets.get('exerciseSets', []):
                    ex_name = s.get('exerciseName', 'Unknown')
                    reps = s.get('repetitionCount', 0)
                    weight = round(s.get('weight', 0) / 1000, 1)
                    report += f"  • {ex_name}: {reps} reps @ {weight}kg\n"
            except Exception as e:
                logger.warning(f"Could not fetch strength sets: {e}")
        report += "---\n"
    return report

# --- 3. PROACTIVE AGENT TASKS ---
def morning_nudge():
    logger.info("Executing Morning Nudge...")
    bot.send_message(MY_CHAT_ID, "☀️ *Morning Check-in:* Step on the scale and tell me your weight (e.g., 75kg).")

def water_nudge():
    logger.info("Executing Water Nudge...")
    bot.send_message(MY_CHAT_ID, "💧 *Hydration Alert:* Drink a glass of water now!")

def daily_report_9pm():
    logger.info("Generating 9 PM Daily Report...")
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

    prompt = (
        f"Generate a daily elite fitness summary. Steps: {steps}. "
        f"Calories Eaten: {cals}. Weight: {weight}kg. Workouts: {workouts}. "
        "Analyze if the user met their goals and give 1 aggressive coaching tip for tomorrow."
    )
    
    analysis = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt).text
    bot.send_message(MY_CHAT_ID, f"📊 *DAILY SUMMARY (9 PM)*\n\n{analysis}", parse_mode="Markdown")
    logger.info("9 PM Report sent.")

# --- 4. SCHEDULER ---
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(morning_nudge, 'cron', hour=8, minute=0)
scheduler.add_job(water_nudge, 'interval', hours=3)
scheduler.add_job(daily_report_9pm, 'cron', hour=21, minute=0)
scheduler.start()
logger.info("Scheduler started for IST timezone.")

# --- 5. INTERACTIVE HANDLERS ---
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    text = message.text.lower()
    db = get_db()
    today = get_today_str()
    logger.info(f"Received message from {message.chat.id}: {text[:50]}...")

    if any(w in text for w in ["workout", "exercise", "activity", "training"]):
        bot.send_chat_action(message.chat.id, 'typing')
        bot.reply_to(message, f"🏋️ *Today's Sessions:*\n\n{fetch_workout_details()}", parse_mode="Markdown")

    elif "kg" in text or "weight" in text:
        logger.info("Processing weight entry...")
        prompt = f"Extract number from '{text}'. Reply with only the number."
        val = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt).text.strip()
        db["weight"][today] = val
        save_db(db)
        bot.reply_to(message, f"⚖️ Weight recorded: {val}kg.")

    elif any(w in text for w in ["ate", "lunch", "dinner", "breakfast", "snack"]):
        logger.info("Processing calorie entry...")
        prompt = f"Estimate calories for: '{text}'. Reply with ONLY the integer."
        cals_est = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt).text.strip()
        try:
            current = db["calories"].get(today, 0)
            db["calories"][today] = current + int(cals_est)
            save_db(db)
            bot.reply_to(message, f"🍎 Logged ~{cals_est} kcal. Total today: {db['calories'][today]} kcal.")
        except Exception as e:
            logger.error(f"Calorie calculation failed: {e}")
            bot.reply_to(message, "I couldn't calculate those calories. Try again?")

    else:
        logger.info("Falling back to Gemini coach chat.")
        prompt = f"You are a high-performance fitness coach. User says: {text}. Give a short, smart reply."
        res = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        bot.reply_to(message, res.text)

# --- 6. RUN ---
app = Flask('')
@app.route('/')
def home(): return "Agent Active"

def run_flask():
    logger.info("Flask health check server starting on port 8080...")
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted. Starting polling...")
    bot.infinity_polling()