import os
import datetime
import telebot
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread

# --- 1. KOYEB HEALTH CHECK SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Fitness Bot is running and healthy!"

def run_health_server():
    # Koyeb requires a response on port 8080 to keep the service 'Healthy'
    app.run(host='0.0.0.0', port=8080)

# Start health check in background
Thread(target=run_health_server, daemon=True).start()

# --- 2. SETUP & ENVIRONMENT VARIABLES ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
GARMIN_EMAIL = os.environ.get('GARMIN_EMAIL')
GARMIN_PASSWORD = os.environ.get('GARMIN_PASSWORD')

if not all([TOKEN, GEMINI_KEY]):
    raise ValueError("Missing critical Environment Variables (TOKEN or GEMINI_KEY)!")

bot = telebot.TeleBot(TOKEN)
gemini = genai.Client(api_key=GEMINI_KEY)

# --- 3. GARMIN SESSION HANDLING ---
def init_garmin():
    token_dir = "./garmin_tokens"
    try:
        if os.path.exists(token_dir):
            print("Found saved Garmin tokens! Bypassing MFA...")
            api = Garmin()
            api.login(token_dir)
        else:
            print("No tokens found. Falling back to credentials...")
            api = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            api.login()
        return api
    except Exception as e:
        print(f"Garmin Initialization Error: {e}")
        return None

garmin_api = init_garmin()

# --- 4. BOT HANDLERS ---

@bot.message_handler(commands=['testgarmin'])
def test_garmin(message):
    if not garmin_api:
        bot.reply_to(message, "❌ Garmin is not initialized. Check logs.")
        return
    try:
        name = garmin_api.get_full_name()
        bot.reply_to(message, f"✅ Connection Active!\nUser: {name}")
    except Exception as e:
        bot.reply_to(message, f"❌ Test Failed: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text.lower()
    
    # Trigger Garmin Stats (Checks for keywords)
    if any(word in user_input for word in ["garmin", "stats", "steps", "activity"]):
        if not garmin_api:
            bot.reply_to(message, "⚠️ Garmin connection is offline.")
            return
            
        try:
            # TIMEZONE FIX: Koyeb uses UTC. We adjust to IST (UTC+5.5)
            # This ensures 'today' matches your local date.
            now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            today_str = now_ist.strftime('%Y-%m-%d')
            
            stats = garmin_api.get_user_summary(today_str)
            
            # THE FIX: Priority check for 'totalSteps' which we found in your debug
            steps = stats.get('totalSteps') or stats.get('steps') or 0
            goal = stats.get('dailyStepGoal', 10000)
            
            prompt = (
                f"The user has {steps} steps today out of a goal of {goal}. "
                "Write a very short, punchy, motivating response as a fitness coach."
            )
            
            # Using 1.5-flash for stability and high quota
            response = gemini.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt
            )
            bot.reply_to(message, response.text)
            
        except Exception as e:
            bot.reply_to(message, f"Error fetching stats: {str(e)}")
            
    else:
        # Standard AI Logging/Chat
        try:
            prompt = f"User says: {message.text}. Reply as a supportive fitness coach."
            response = gemini.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt
            )
            bot.reply_to(message, response.text)
        except Exception as e:
            if "429" in str(e):
                bot.reply_to(message, "🚀 Slow down! I'm catching my breath. Try again in a minute.")
            else:
                bot.reply_to(message, "I'm a bit distracted. Try again?")

# --- 5. START POLLING ---
if __name__ == "__main__":
    # Clear any old connections before starting
    bot.delete_webhook(drop_pending_updates=True)
    print("Bot is live and listening...")
    bot.infinity_polling()