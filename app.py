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
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_health_server, daemon=True).start()

# --- 2. SETUP ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
GEMINI_KEY = os.environ.get('GEMINI_KEY')
GARMIN_EMAIL = os.environ.get('GARMIN_EMAIL')
GARMIN_PASSWORD = os.environ.get('GARMIN_PASSWORD')

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
        print(f"Garmin Error: {e}")
        return None

garmin = init_garmin()

# --- 4. BOT HANDLERS ---

# NEW: Explicit Test Command (Must be ABOVE the catch-all)
@bot.message_handler(commands=['testgarmin'])
def test_garmin(message):
    if not garmin:
        bot.reply_to(message, "❌ Garmin is not initialized. Check Koyeb logs.")
        return
    try:
        # Fetching full name as a lightweight connectivity test
        name = garmin.get_full_name()
        bot.reply_to(message, f"✅ Garmin Connection Active!\nUser: {name}")
    except Exception as e:
        bot.reply_to(message, f"❌ Garmin Test Failed: {str(e)}")

# Existing Catch-All Handler
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text.lower()
    
    # 1. Check if user is asking for Garmin data
    if any(word in user_input for word in ["garmin", "stats", "steps", "activity"]):
        if not garmin:
            bot.reply_to(message, "⚠️ Garmin connection is offline.")
            return
            
        try:
            today = datetime.date.today().isoformat()
            stats = garmin.get_user_summary(today)
            steps = stats.get('steps', 0)
            
            prompt = f"The user has {steps} steps today. Write a short, high-energy coach response."
            response = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            bot.reply_to(message, response.text)
        except Exception as e:
            bot.reply_to(message, f"Error fetching stats: {str(e)}")
            
    # 2. Otherwise, treat as general AI chat
    else:
        try:
            prompt = f"User is tracking fitness. They said: {message.text}. Reply as a supportive coach."
            response = gemini.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            bot.reply_to(message, response.text)
        except Exception as e:
            bot.reply_to(message, "AI is resting. Try again in a moment!")

# --- 5. START ---
if __name__ == "__main__":
    bot.delete_webhook(drop_pending_updates=True)
    print("Bot is live!")
    bot.infinity_polling()