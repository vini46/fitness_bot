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
    res = supabase.table("user_configs").select("*").eq("telegram_id", str(tg_id)).eq("log_date", date_str).execute()
    if res.data:
        return res.data[0]
    
    recent = supabase.table("user_configs").select("gemini_key").eq("telegram_id", str(tg_id)).order("log_date", desc=True).limit(1).execute()
    if recent.data:
        return {"gemini_key": recent.data[0]['gemini_key'], "calories_consumed": 0, "weight": None}
    return None

def sync_to_supabase(tg_id, date_str, updates):
    data = {"telegram_id": str(tg_id), "log_date": date_str, **updates}
    supabase.table("user_configs").upsert(data, on_conflict="telegram_id, log_date").execute()

# --- 3. DYNAMIC GEMINI CLIENT ---
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
            if "429" in str(e) or "ResourceExhausted" in str(e):
                time.sleep((attempt + 1) * 3)
                continue
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
    except: return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

def fetch_workout_details():
    api = init_garmin()
    if not api: return "No Garmin data link."
    today = get_today_str()
    try:
        activities = api.get_activities_by_date(today, today)
        if not activities: return "No workouts logged today."
        report = ""
        for act in activities:
            name = act.get('activityName', 'Activity')
            cals = act.get('calories', 0)
            duration = round(act.get('duration', 0) / 60, 1)
            report += f"{name}: {duration}m | {cals}kcal\n"
        return report
    except: return "Garmin sync error."

# --- 5. REPORT LOGIC WITH FORMATTING FIX ---
def run_report_for_user(tg_id):
    today = get_today_str()
    user_data = get_user_data(tg_id, today)
    if not user_data or not user_data.get('gemini_key'): return

    workouts = fetch_workout_details()
    cals = user_data.get('calories_consumed', 0)
    weight = user_data.get('weight', "Not recorded")

    # Added formatting instruction to prompt
    prompt = (f"Analyze: Cals Consumed:{cals}, Weight:{weight}kg, Workouts:{workouts}. "
              "Give a smart coaching summary. DO NOT use underscores (_) and use minimal bolding.")
    
    analysis = get_gemini_response(tg_id, prompt)
    
    if analysis == "RATE_LIMIT_EXCEEDED":
        bot.send_message(tg_id, "⏳ AI is busy. Try `/report` in a few minutes.")
        return

    # Clean the output to avoid Telegram Parser errors
    clean_analysis = analysis.replace("_", "-").replace("[", "(").replace("]", ")")

    try:
        # Attempt to send with Markdown
        bot.send_message(tg_id, f"📊 *HEALTH SUMMARY*\n\n{clean_analysis}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Markdown failed for {tg_id}: {e}. Sending plain text.")
        # Fallback safety: Send as plain text if Markdown fails
        bot.send_message(tg_id, f"📊 HEALTH SUMMARY\n\n{analysis}")

def multi_user_report_9pm():
    try:
        res = supabase.table("user_configs").select("telegram_id").execute()
        all_users = list(set([row['telegram_id'] for row in res.data]))
        for user_id in all_users:
            time.sleep(random.uniform(2, 5))
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
    sync_to_supabase(message.chat.id, get_today_str(), {"gemini_key": key})
    bot.reply_to(message, "✅ Key saved!")

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
        bot.reply_to(message, fetch_workout_details())
    elif "kg" in text or "weight" in text:
        res = get_gemini_response(tg_id, f"Extract number from {text}")
        val = "".join(re.findall(r"[-+]?\d*\.\d+|\d+", res))
        if val:
            sync_to_supabase(tg_id, today, {"weight": val})
            bot.reply_to(message, f"⚖️ {val}kg logged.")
    elif any(w in text for w in ["ate", "had", "lunch", "dinner"]):
        res = get_gemini_response(tg_id, f"Calories for {text}. Int only.")
        cals = "".join(filter(str.isdigit, res))
        if cals:
            user_data = get_user_data(tg_id, today)
            new_total = (user_data.get('calories_consumed') or 0) + int(cals)
            sync_to_supabase(tg_id, today, {"calories_consumed": new_total})
            bot.reply_to(message, f"🍎 Logged {cals} kcal. Total: {new_total}")
    else:
        bot.reply_to(message, get_gemini_response(tg_id, f"Coach reply: {text}"))

# --- 7. RUN ---
app = Flask('')
@app.route('/')
def home(): return "Agent Active"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
    bot.infinity_polling()