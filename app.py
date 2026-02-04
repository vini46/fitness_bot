import os
import datetime
import telebot
import pytz
import logging
import re
import time
import random
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from supabase import create_client, Client

# --- 0. LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURATION ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
IST = pytz.timezone('Asia/Kolkata')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_ID = "gemini-2.0-flash"

# --- 2. SUPABASE HELPERS ---
def get_user_data(tg_id, date_str):
    """Fetches today's row. If missing, looks for the most recent gemini_key."""
    res = supabase.table("user_configs").select("*").eq("telegram_id", str(tg_id)).eq("log_date", date_str).execute()
    if res.data:
        return res.data[0]
    
    recent = supabase.table("user_configs").select("gemini_key").eq("telegram_id", str(tg_id)).order("log_date", desc=True).limit(1).execute()
    if recent.data:
        return {"gemini_key": recent.data[0]['gemini_key'], "calories_consumed": 0, "weight": None}
    return None

def sync_to_supabase(tg_id, date_str, updates):
    """Upserts data for specific user/date."""
    data = {"telegram_id": str(tg_id), "log_date": date_str, **updates}
    supabase.table("user_configs").upsert(data, on_conflict="telegram_id, log_date").execute()

# --- 3. GEMINI CLIENT WITH BACKOFF ---
def get_gemini_response(tg_id, prompt):
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
    user_info = get_user_data(tg_id, today)
    
    if not user_info or not user_info.get('gemini_key'):
        return "KEY_MISSING"

    for attempt in range(3):
        try:
            client = genai.Client(api_key=user_info['gemini_key'])
            res = client.models.generate_content(model=MODEL_ID, contents=prompt)
            return res.text
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "ResourceExhausted" in err_msg:
                wait_time = (attempt + 1) * 3 
                logger.warning(f"Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Gemini Error: {e}")
                return "API_ERROR"
    
    return "RATE_LIMIT_EXCEEDED"

# --- 4. GARMIN ---
def init_garmin():
    token_dir = "./garmin_tokens"
    if not os.path.exists(token_dir): return None
    try:
        api = Garmin()
        api.login(token_dir)
        return api
    except Exception as e:
        logger.error(f"Garmin login failed: {e}")
        return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

def fetch_workout_details():
    api = init_garmin()
    if not api: return "Garmin connection offline."
    today = get_today_str()
    try:
        activities = api.get_activities_by_date(today, today)
        if not activities: return "No workouts found."
        report = ""
        for act in activities:
            name = act.get('activityName', 'Activity')
            cals = act.get('calories', 0)
            duration = round(act.get('duration', 0) / 60, 1)
            report += f"🏃 *{name}*\n⏱ {duration} min | 🔥 {cals} kcal\n---\n"
        return report
    except: return "Error pulling Garmin data."

# --- 5. SCHEDULER LOGIC ---
def run_report_for_user(tg_id):
    """Core logic to generate and send a report."""
    today = get_today_str()
    user_data = get_user_data(tg_id, today)
    if not user_data or not user_data.get('gemini_key'): return

    workouts = fetch_workout_details()
    cals = user_data.get('calories_consumed', 0)
    weight = user_data.get('weight', "Not recorded")

    prompt = (f"Analyze today's stats: Cals Consumed:{cals}, Weight:{weight}kg. "
              f"Workouts:{workouts}. Give a brutal but smart coaching summary.")
    
    analysis = get_gemini_response(tg_id, prompt)
    
    if analysis == "RATE_LIMIT_EXCEEDED":
        bot.send_message(tg_id, "⏳ AI is busy. Please try `/report` again in a few minutes.")
    elif analysis not in ["KEY_MISSING", "API_ERROR"]:
        bot.send_message(tg_id, f"📊 *HEALTH SUMMARY*\n\n{analysis}", parse_mode="Markdown")

def multi_user_report_9pm():
    try:
        res = supabase.table("user_configs").select("telegram_id").execute()
        all_users = list(set([row['telegram_id'] for row in res.data]))
        for user_id in all_users:
            time.sleep(random.uniform(2, 5)) # Safety delay
            run_report_for_user(user_id)
    except Exception as e:
        logger.error(f"Scheduler error: {e}")

# --- 6. HANDLERS ---
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(multi_user_report_9pm, 'cron', hour=21, minute=0)
scheduler.start()

@bot.message_handler(commands=['set_key'])
def set_key(message):
    key = message.text.replace('/set_key', '').strip()
    if not key:
        bot.reply_to(message, "Usage: `/set_key AIza...`")
        return
    sync_to_supabase(message.chat.id, get_today_str(), {"gemini_key": key})
    bot.reply_to(message, "✅ Key saved and ID registered!")

@bot.message_handler(commands=['report'])
def manual_report(message):
    bot.send_chat_action(message.chat.id, 'typing')
    run_report_for_user(message.chat.id)

@bot.message_handler(func=lambda m: True)
def handle_input(message):
    tg_id = message.chat.id
    text = message.text.lower()
    today = get_today_str()

    if any(w in text for w in ["workout", "exercise", "activity"]):
        bot.reply_to(message, fetch_workout_details(), parse_mode="Markdown")

    elif "kg" in text or "weight" in text:
        res = get_gemini_response(tg_id, f"Extract weight number from '{text}'. Just number.")
        val = "".join(re.findall(r"[-+]?\d*\.\d+|\d+", res))
        if val:
            sync_to_supabase(tg_id, today, {"weight": val})
            bot.reply_to(message, f"⚖️ Weight: {val}kg logged.")

    elif any(w in text for w in ["ate", "lunch", "dinner", "snack", "had"]):
        res = get_gemini_response(tg_id, f"Estimate calories for: '{text}'. Integer only.")
        cals_only = "".join(filter(str.isdigit, res))
        if cals_only:
            user_data = get_user_data(tg_id, today)
            new_total = (user_data.get('calories_consumed') or 0) + int(cals_only)
            sync_to_supabase(tg_id, today, {"calories_consumed": new_total})
            bot.reply_to(message, f"🍎 Added ~{cals_only} kcal. Total: {new_total}")
    else:
        res = get_gemini_response(tg_id, f"Short coach reply to: {text}")
        bot.reply_to(message, res)

# --- 7. RUN ---
app = Flask('')
@app.route('/')
def home(): return "Multi-User Agent Active"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
    bot.infinity_polling()