import os
import telebot
from garminconnect import Garmin
from google import genai

# Setup
TOKEN = os.environ.get('TELEGRAM_TOKEN')
bot = telebot.TeleBot(TOKEN)
KEY = os.environ.get('GEMINI_KEY')
gemini = genai.Client(api_key=KEY)
EMAIL = os.environ.get('GARMIN_EMAIL')
PASSWORD = os.environ.get('GARMIN_PASSWORD')
garmin = Garmin(EMAIL, PASSWORD)
garmin.login()

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_input = message.text
    
    if "garmin" in user_input.lower() or "stats" in user_input.lower():
        # Fetch data from Garmin
        stats = garmin.get_user_summary(datetime.date.today().isoformat())
        steps = stats['dailyStepGoal']
        
        # Let Gemini format the response nicely
        response = gemini.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"The user has {steps} steps today. Write a motivating coach-like response."
        )
        bot.reply_to(message, response.text)
    else:
        # Standard diet/workout logging via Gemini
        response = gemini.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"User says: {user_input}. Log this as a diet/workout entry and give feedback."
        )
        bot.reply_to(message, response.text)

bot.infinity_polling()