import re
import logging
from app.bot.bot_instance import bot
from app.bot.tasks import run_report_for_user
from app.database import get_user_data, sync_to_supabase
from app.services.garmin import fetch_workout_details, get_today_str
from app.services.gemini import get_gemini_response

logger = logging.getLogger(__name__)

def register_handlers():
    @bot.message_handler(commands=['set_key'])
    def set_key(message):
        key = message.text.replace('/set_key', '').strip()
        sync_to_supabase(message.chat.id, get_today_str(), {"gemini_key": key})
        bot.reply_to(message, "✅ Key saved!")

    @bot.message_handler(commands=['report'])
    def manual_report(message):
        bot.send_chat_action(message.chat.id, 'typing')
        run_report_for_user(message.chat.id)

    @bot.message_handler(commands=['set_garmin'])
    def set_garmin(message):
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "Usage: `/set_garmin email password` \n\n⚠️ Please delete this message after sending to protect your password!", parse_mode="Markdown")
            return
        
        email, password = parts[1], parts[2]
        bot.send_message(message.chat.id, "⏳ Authenticating with Garmin... (this may take a minute)")
        
        from app.services.garmin import login_user_to_garmin
        if login_user_to_garmin(message.chat.id, email, password):
            bot.reply_to(message, "✅ Garmin linked successfully! You can now delete your credential message.")
        else:
            bot.reply_to(message, "❌ Garmin login failed. Please check your email/password.")

    @bot.message_handler(func=lambda m: True)
    def handle_input(message):
        tg_id = message.chat.id
        text = message.text.lower()
        today = get_today_str()

        if any(w in text for w in ["workout", "exercise", "activity", "steps", "step", "walk"]):
            bot.reply_to(message, fetch_workout_details(tg_id))
        elif "kg" in text or "weight" in text:
            res = get_gemini_response(tg_id, f"Extract only the numeric weight from: '{text}'. Output only the number.")
            match = re.search(r"[-+]?\d*\.?\d+", res)
            val = match.group(0) if match else None
            if val:
                sync_to_supabase(tg_id, today, {"weight": val})
                bot.reply_to(message, f"⚖️ {val}kg logged.")
        elif any(w in text for w in ["ate", "had", "lunch", "dinner"]):
            res = get_gemini_response(tg_id, f"Identify the total calories in: '{text}'. Output ONLY the number.")
            match = re.search(r"\d+", res)
            cals_val = int(match.group(0)) if match else None
            
            if cals_val is not None:
                if cals_val > 10000:
                    bot.reply_to(message, "⚠️ That seems like too many calories! Please check the entry or try again.")
                else:
                    user_data = get_user_data(tg_id, today)
                    new_total = (user_data.get('calories_consumed') or 0) + cals_val
                    sync_to_supabase(tg_id, today, {"calories_consumed": new_total})
                    bot.reply_to(message, f"🍎 Logged {cals_val} kcal. Total: {new_total}")
        else:
            bot.reply_to(message, get_gemini_response(tg_id, f"Coach reply: {text}"))
