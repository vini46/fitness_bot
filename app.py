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
    # Koyeb pings 8080. If this server doesn't respond, Koyeb restarts the bot.
    app.run(host='0.0.0.0', port=8080)

# Start health check in background
Thread(target=run_health_server, daemon=True).start()

# --- 2. SETUP & ENVIRONMENT VARIABLES ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
GARMIN_EMAIL = os.environ.get('GARMIN_EMAIL')
GARMIN_PASSWORD = os.environ.get('GARMIN_PASSWORD')

# Safety check to prevent NoneType crashes
if not all([TOKEN, GEMINI_KEY]):
    raise ValueError("Missing critical Environment Variables in Koyeb settings!")

bot = telebot.TeleBot(TOKEN)
gemini = genai.Client(api_key=GEMINI_KEY)

# --- 3. GARMIN SESSION HANDLING ---
def init_garmin():
    token_dir = "./garmin_tokens"
    
    try:
        if os.path.exists(token_dir):
            print("Found saved Garmin tokens! Bypassing MFA...")
            api = Garmin()
            api.login(token_dir) # This loads your local session files
        else:
            print("No tokens found. Falling back to credentials...")
            api = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
            api.login()
        return api
    except Exception as e:
        print(f"Garmin Error: {e}")
        return None

garmin = init_garmin()

# --- 4. BOT HANDLERS ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text.lower()
    
    # Trigger Garmin Stats
    if any(word in user_input for word in ["garmin", "stats", "steps"]):
        if not garmin:
            bot.reply_to(message, "⚠️ Garmin connection is offline. Check logs.")
            return
            
        try:
            today = datetime.date.today().isoformat()
            stats = garmin.get_user_summary(today)
            steps = stats.get('steps', 0)
            
            # Use Gemini 2.5-Flash for better coach-like responses
            prompt = f"The user has {steps} steps today. Write a motivating coach-like response."
            response = gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            bot.reply_to(message, response.text)
        except Exception as e:
            bot.reply_to(message, f"Error fetching data: {str(e)}")
            
    else:
        # Standard AI Logging
        try:
            prompt = f"User says: {message.text}. Log this as a diet/workout entry and give feedback."
            response = gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            bot.reply_to(message, response.text)
        except Exception as e:
            bot.reply_to(message, "The AI is a bit busy. Try again in a second!")

# --- 5. START POLLING ---
if __name__ == "__main__":
    print("Clearing old webhooks...")
    bot.delete_webhook(drop_pending_updates=True)
    print("Bot is now listening for messages on Telegram!")
    bot.infinity_polling()