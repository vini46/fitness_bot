import os
import datetime
import telebot
import pytz
import logging
import re
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
MY_CHAT_ID = os.environ.get('MY_CHAT_ID') # Still used for your specific nudges
IST = pytz.timezone('Asia/Kolkata')

bot = telebot.TeleBot(TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
MODEL_ID = "gemini-2.0-flash"

# --- 2. SUPABASE HELPERS ---
def get_user_data(tg_id, date_str):
    """Fetches today's row. If missing, looks for the most recent gemini_key."""
    # Try today first
    res = supabase.table("user_configs").select("*").eq("telegram_id", str(tg_id)).eq("log_date", date_str).execute()
    if res.data:
        return res.data[0]
    
    # Otherwise, get the most recent row just to grab the API Key
    recent = supabase.table("user_configs").select("gemini_key").eq("telegram_id", str(tg_id)).order("log_date", desc=True).limit(1).execute()
    if recent.data:
        return {"gemini_key": recent.data[0]['gemini_key'], "calories_consumed": 0, "weight": None}
    return None

def sync_to_supabase(tg_id, date_str, updates):
    """Upserts data for the user on the specific date."""
    data = {"telegram_id": str(tg_id), "log_date": date_str, **updates}
    supabase.table("user_configs").upsert(data, on_conflict="telegram_id, log_date").execute()

# --- 3. DYNAMIC GEMINI CLIENT ---
def get_gemini_response(tg_id, prompt):
    """Initializes a client using the user's specific key from DB."""
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
    user_info = get_user_data(tg_id, today)
    
    if not user_info or not user_info.get('gemini_key'):
        return "KEY_MISSING"

    try:
        # Create dynamic client
        client = genai.Client(api_key=user_info['gemini_key'])
        res = client.models.generate_content(model=MODEL_ID, contents=prompt)
        return res.text
    except Exception as e:
        logger.error(f"Gemini Error for {tg_id}: {e}")
        return "API_ERROR"

# --- 4. GARMIN SESSION ---
def init_garmin():
    token_dir = "./garmin_tokens"
    if not os.path.exists(token_dir):
        return None
    try:
        api = Garmin()
        api.login(token_dir)
        return api
    except Exception as e:
        logger.error(f"Garmin login failed: {e}")
        return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

# --- 5. WORKOUT FETCHING ---
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
            cals = act.get('calories', 0)
            duration = round(act.get('duration', 0) / 60, 1)
            report += f"🏃 *{name}*\n⏱ {duration} min | 🔥 {cals} kcal\n---\n"
        return report
    except: return "Error pulling Garmin data."

# --- 6. PROACTIVE TASKS ---
def daily_report_9pm():
    if not MY_CHAT_ID: return
    today = get_today_str()
    user_data = get_user_data(MY_CHAT_ID, today)
    if not user_data: return
    
    workouts = fetch_workout_details()
    cals = user_data.get('calories_consumed', 0)
    weight = user_data.get('weight', "Not recorded")

    prompt = (f"Analyze today's stats: Cals Consumed:{cals}, Weight:{weight}kg. "
              f"Workouts:{workouts}. Give a brutal but smart coaching summary.")
    
    analysis = get_gemini_response(MY_CHAT_ID, prompt)
    if analysis not in ["KEY_MISSING", "API_ERROR"]:
        bot.send_message(MY_CHAT_ID, f"📊 *DAILY SUMMARY*\n\n{analysis}", parse_mode="Markdown")

# --- 7. SCHEDULER ---
scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(daily_report_9pm, 'cron', hour=21, minute=0)
scheduler.start()

# --- 8. HANDLERS ---
@bot.message_handler(commands=['set_key'])
def set_key(message):
    key = message.text.replace('/set_key', '').strip()
    if not key:
        bot.reply_to(message, "Usage: `/set_key AIzaSy...`")
        return
    today = get_today_str()
    sync_to_supabase(message.chat.id, today, {"gemini_key": key})
    bot.reply_to(message, "✅ Gemini API Key saved!")

@bot.message_handler(func=lambda m: True)
def handle_input(message):
    tg_id = message.chat.id
    text = message.text.lower()
    today = get_today_str()
    logger.info(f"Input from {tg_id}: {text}")

    # TRIGGER: Workout Info
    if any(w in text for w in ["workout", "exercise", "activity"]):
        bot.send_chat_action(tg_id, 'typing')
        bot.reply_to(message, fetch_workout_details(), parse_mode="Markdown")

    # TRIGGER: Weight Logging
    elif "kg" in text or "weight" in text:
        bot.send_chat_action(tg_id, 'typing')
        res = get_gemini_response(tg_id, f"Extract weight number from '{text}'. Just the number.")
        
        if res == "KEY_MISSING":
            bot.reply_to(message, "Please set your Gemini Key first using `/set_key YOUR_KEY`.")
            return

        val = "".join(re.findall(r"[-+]?\d*\.\d+|\d+", res))
        if val:
            sync_to_supabase(tg_id, today, {"weight": val})
            bot.reply_to(message, f"⚖️ Weight: {val}kg logged to cloud.")

    # TRIGGER: Food Logging
    elif any(w in text for w in ["ate", "lunch", "dinner", "snack", "had"]):
        bot.send_chat_action(tg_id, 'typing')
        res = get_gemini_response(tg_id, f"Estimate total calories for: '{text}'. Reply with ONLY the integer.")
        
        if res == "KEY_MISSING":
            bot.reply_to(message, "Please set your Gemini Key first using `/set_key YOUR_KEY`.")
            return

        cals_only = "".join(filter(str.isdigit, res))
        if cals_only:
            cals_val = int(cals_only)
            user_data = get_user_data(tg_id, today)
            new_total = (user_data.get('calories_consumed') or 0) + cals_val
            sync_to_supabase(tg_id, today, {"calories_consumed": new_total})
            bot.reply_to(message, f"🍎 Added ~{cals_val} kcal.\nTotal Today: {new_total} kcal.")

    # FALLBACK: Coach Chat
    else:
        res = get_gemini_response(tg_id, f"Short coach reply to: {text}")
        if res == "KEY_MISSING":
            bot.reply_to(message, "Welcome! Set your Gemini Key to start chatting: `/set_key YOUR_KEY`.")
        elif res == "API_ERROR":
            bot.reply_to(message, "There was an error with your API key.")
        else:
            bot.reply_to(message, res)

# --- 9. RUN ---
app = Flask('')
@app.route('/')
def home(): return "Supabase Agent Active"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
    bot.remove_webhook()
    bot.delete_webhook(drop_pending_updates=True)
    bot.infinity_polling()