import os
import telebot
import datetime
from garminconnect import Garmin
from google import genai
from flask import Flask
from threading import Thread

# 1. KOYEB HEALTH CHECK SERVER
# This keeps the service "Green" on Koyeb
app = Flask('')

@app.route('/')
def home():
    return "Fitness Bot is running!"

def run_web_server():
    # Koyeb pings port 8080 by default
    app.run(host='0.0.0.0', port=8080)

# Start the web server in a background thread
Thread(target=run_web_server, daemon=True).start()

# 2. BOT SETUP
TOKEN = os.environ.get('TELEGRAM_TOKEN')
KEY = os.environ.get('GEMINI_KEY')
EMAIL = os.environ.get('GARMIN_EMAIL')
PASSWORD = os.environ.get('GARMIN_PASSWORD')

bot = telebot.TeleBot(TOKEN)
gemini = genai.Client(api_key=KEY)

# 3. GARMIN LOGIN (Note: This might trigger MFA)
print("Attempting to log into Garmin...")
try:
    garmin = Garmin(EMAIL, PASSWORD)
    garmin.login()
    print("Garmin login successful!")
except Exception as e:
    print(f"Garmin login failed: {e}")
    garmin = None

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text
    
    # Check if user wants Garmin stats
    if "garmin" in user_input.lower() or "stats" in user_input.lower():
        if not garmin:
            bot.reply_to(message, "I couldn't connect to Garmin. Check logs for MFA issues.")
            return
            
        try:
            today = datetime.date.today().isoformat()
            stats = garmin.get_user_summary(today)
            # Garmin returns a dictionary; keys might vary, 'steps' is common
            steps = stats.get('steps', 'unknown')
            
            response = gemini.models.generate_content(
                model="gemini-1.5-flash",
                contents=f"The user has {steps} steps today. Write a motivating coach-like response."
            )
            bot.reply_to(message, response.text)
        except Exception as e:
            bot.reply_to(message, f"Error fetching Garmin data: {e}")
            
    else:
        # Standard AI chat logic
        response = gemini.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"User says: {user_input}. Log this as a diet/workout entry and give feedback."
        )
        bot.reply_to(message, response.text)

print("Telegram bot is polling...")
bot.infinity_polling()