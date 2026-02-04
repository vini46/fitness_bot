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
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"weight": {}, "calories": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

# --- 2. GARMIN DATA HELPERS ---
def init_garmin():
    try:
        api = Garmin()
        api.login("./garmin_tokens")
        return api
    except: return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

def fetch_workout_details():
    api = init_garmin()
    if not api: return "Garmin connection is currently offline."
    
    today = get_today_str()
    activities = api.get_activities_by_date(today, today)
    
    if not activities:
        return "No workouts found for today yet. Get moving!"

    report = ""
    for act in activities:
        name = act.get('activityName', 'Activity')
        type_key = act.get('activityType', {}).get('typeKey', 'unknown')
        cals = act.get('calories', 0)
        duration = round(act.get('duration', 0) / 60, 1)
        
        report += f"🏃 *{name}* ({type_key.replace('_', ' ').title()})\n"
        report += f"⏱ {duration} min | 🔥 {cals} kcal\n"

        # Strength Training Deep Dive
        if type_key == 'strength_training':
            try:
                activity_id = act.get('activityId')
                sets = api.get_activity_exercise_sets(activity_id)
                for s in sets.get('exerciseSets', []):
                    ex_name = s.get('exerciseName', 'Unknown')
                    reps = s.get('repetitionCount', 0)
                    weight = round(s.get('weight', 0) / 1000, 1)
                    report += f"  • {ex_name}: {reps} reps @ {weight}kg\n"
            except: pass
        report += "---\n"
    return report

# --- 3. PROACTIVE AGENT TASKS ---
def morning_nudge():
    bot.send_message(MY_CHAT_ID, "☀️ *Morning Check-in:* Step on the scale and tell me your weight (e.g., 75kg).")

def water_nudge():
    bot.send_message(MY_CHAT_ID, "💧 *Hydration Alert:* Drink a glass of water now to stay on track!")

def daily_report_9pm():
    db = get_db()
    today = get_today_str()
    
    # Get Final Stats
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

# --- 4. SCHEDULER ---
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(morning_nudge, 'cron', hour=8, minute=0)
scheduler.add_job(water_nudge, 'interval', hours=3)
scheduler.add_job(daily_report_9pm, 'cron', hour=21, minute=0)
scheduler.start()

# --- 5. INTERACTIVE HANDLERS ---
@bot.message_handler(func=lambda m: True)
def handle_input(message):
    text = message.text.lower()
    db = get_db()
    today = get_today_str()

    # DETECT: Workout Inquiry
    if any(w in text for w in ["workout", "exercise", "activity", "training"]):
        bot.send_chat_action(message.chat.id, 'typing')
        bot.reply_to(message, f"🏋️ *Today's Sessions:*\n\n{fetch_workout_details()}", parse_mode="Markdown")

    # DETECT: Weight Entry
    elif "kg" in text or "weight" in text:
        prompt = f"Extract number from '{text}'. Reply with only the number."
        val = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt).text.strip()
        db["weight"][today] = val
        save_db(db)
        bot.reply_to(message, f"⚖️ Weight recorded: {val}kg.")

    # DETECT: Food Entry
    elif any(w in text for w in ["ate", "lunch", "dinner", "breakfast", "snack"]):
        prompt = f"Estimate calories for: '{text}'. Reply with ONLY the integer."
        cals_est = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt).text.strip()
        try:
            current = db["calories"].get(today, 0)
            db["calories"][today] = current + int(cals_est)
            save_db(db)
            bot.reply_to(message, f"🍎 Logged ~{cals_est} kcal. Total today: {db['calories'][today]} kcal.")
        except: bot.reply_to(message, "I couldn't calculate those calories. Try again?")

    # DEFAULT: Coaching Chat
    else:
        prompt = f"You are a high-performance fitness coach. User says: {text}. Give a short, smart reply."
        res = gemini.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        bot.reply_to(message, res.text)

# --- 6. RUN ---
app = Flask('')
@app.route('/')
def home(): return "Agent Active"
Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

if __name__ == "__main__":
    bot.delete_webhook(drop_pending_updates=True)
    bot.infinity_polling()