import os
import datetime
import json
import telebot
import pytz
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler

# --- 1. CONFIGURATION ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
MY_CHAT_ID = os.environ.get('MY_CHAT_ID')  # Required for proactive nudges
IST = pytz.timezone('Asia/Kolkata')

bot = telebot.TeleBot(TOKEN)
gemini = genai.Client(api_key=GEMINI_KEY)

# Local DB for Weight/Calories
DB_FILE = "health_db.json"

def get_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"weight": {}, "calories": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

# --- 2. GARMIN & AI HELPERS ---
def init_garmin():
    try:
        api = Garmin()
        api.login("./garmin_tokens")
        return api
    except: return None

def fetch_steps():
    api = init_garmin()
    if api:
        today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
        stats = api.get_user_summary(today)
        return stats.get('totalSteps') or stats.get('steps') or 0
    return "Offline"

# --- 3. PROACTIVE AGENT TASKS ---
def daily_report():
    db = get_db()
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
    
    steps = fetch_steps()
    cals = db["calories"].get(today, 0)
    weight = db["weight"].get(today, "Not recorded")
    
    prompt = (
        f"Generate a daily fitness report. Today's Data: "
        f"Steps: {steps}, Calories Consumed: {cals}, Weight: {weight}kg. "
        "Review the performance and give 1 tip for tomorrow. Keep it short and elite."
    )
    
    response = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    bot.send_message(MY_CHAT_ID, f"📊 *DAILY FINISH LINE*\n\n{response.text}", parse_mode="Markdown")

def morning_nudge():
    bot.send_message(MY_CHAT_ID, "☀️ Good morning! Weight check-in time. Reply with your weight in kg.")

def water_nudge():
    bot.send_message(MY_CHAT_ID, "💧 Water Break! Stay hydrated to keep that metabolism high.")

# --- 4. SCHEDULER SETUP ---
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(morning_nudge, 'cron', hour=8, minute=0)   # 8:00 AM
scheduler.add_job(water_nudge, 'interval', hours=3)          # Every 3 hours
scheduler.add_job(daily_report, 'cron', hour=21, minute=0)  # 9:00 PM
scheduler.start()

# --- 5. INTERACTIVE HANDLERS ---
@bot.message_handler(func=lambda m: True)
def handle_agent_input(message):
    text = message.text.lower()
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
    db = get_db()

    # LOG WEIGHT (e.g., "75kg" or "my weight is 74")
    if "kg" in text or "weight" in text:
        prompt = f"Extract only the number from: {text}. Reply with just the number."
        val = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt).text.strip()
        db["weight"][today] = val
        save_db(db)
        bot.reply_to(message, f"⚖️ Weight locked in: {val}kg.")

    # LOG FOOD (e.g., "I ate 2 chapatis")
    elif any(word in text for word in ["ate", "breakfast", "lunch", "dinner", "snack"]):
        prompt = f"User ate: {text}. Estimate total calories. Reply with ONLY the integer number."
        cals_est = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt).text.strip()
        
        current_cals = db["calories"].get(today, 0)
        db["calories"][today] = int(current_cals) + int(cals_est)
        save_db(db)
        bot.reply_to(message, f"🍎 ~{cals_est} kcal added. Total today: {db['calories'][today]} kcal.")

    # CHECK STEPS ON DEMAND
    elif "steps" in text:
        steps = fetch_steps()
        bot.reply_to(message, f"👟 Current steps: {steps}")

# --- 6. FLASK HEALTH CHECK ---
app = Flask('')
@app.route('/')
def home(): return "Agent Active"

def run_flask(): app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.delete_webhook(drop_pending_updates=True)
    bot.infinity_polling()