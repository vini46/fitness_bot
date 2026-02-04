import os
import datetime
import json
import telebot
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# --- 1. SETUP & DATABASE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
MY_CHAT_ID = os.environ.get('MY_CHAT_ID') # NEW: Get this from @userinfobot in Telegram
IST = pytz.timezone('Asia/Kolkata')

bot = telebot.TeleBot(TOKEN)
gemini = genai.Client(api_key=GEMINI_KEY)

# Simple JSON DB to store weight and calories
DB_FILE = "health_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {"weight": {}, "calories": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# --- 2. PROACTIVE TASKS (The "Agent" part) ---
def send_nudge(text):
    if MY_CHAT_ID:
        bot.send_message(MY_CHAT_ID, text)

def morning_checkin():
    send_nudge("☀️ Good morning! Step on the scale and tell me your weight today.")

def water_reminder():
    send_nudge("💧 Hydration check! Drink a glass of water now.")

def workout_reminder():
    send_nudge("🏋️ Time for your workout! Did you close your rings yet?")

# Setup Scheduler
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(morning_checkin, 'cron', hour=8, minute=0)  # 8 AM IST
scheduler.add_job(water_reminder, 'interval', hours=2)       # Every 2 hours
scheduler.add_job(workout_reminder, 'cron', hour=18, minute=0) # 6 PM IST
scheduler.start()

# --- 3. GARMIN & AI HELPERS ---
def get_steps():
    # ... (Same logic as before to fetch totalSteps)
    pass

# --- 4. MESSAGE HANDLER (Intelligent Tracking) ---
@bot.message_handler(func=lambda m: True)
def agent_logic(message):
    user_text = message.text.lower()
    db = load_db()
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')

    # Detect Weight Entry
    if any(x in user_text for x in ["kg", "weight"]):
        # Extract number using Gemini
        prompt = f"The user said '{message.text}'. Extract the weight as a number only. Reply with JUST the number."
        weight = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt).text.strip()
        db["weight"][today] = weight
        save_db(db)
        bot.reply_to(message, f"✅ Logged weight: {weight}kg. Keep it up!")

    # Detect Food Entry
    elif any(x in user_text for x in ["ate", "lunch", "dinner", "breakfast", "snack"]):
        prompt = f"The user ate: {message.text}. Estimate total calories. Reply with ONLY the number."
        cals = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt).text.strip()
        
        day_cals = db["calories"].get(today, 0)
        db["calories"][today] = int(day_cals) + int(cals)
        save_db(db)
        
        bot.reply_to(message, f"🍴 Logged ~{cals} kcal. Total today: {db['calories'][today]} kcal.")

    # Generic AI Chat
    else:
        prompt = f"You are a fitness coach. User says: {message.text}. Give a helpful reply."
        response = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        bot.reply_to(message, response.text)

# --- 5. RUN SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Agent is Active"

def run(): app.run(host='0.0.0.0', port=8080)
Thread(target=run).start()
bot.infinity_polling()