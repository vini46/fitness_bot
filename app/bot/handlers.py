import re
import logging
from app.bot.bot_instance import bot
from app.bot.tasks import run_report_for_user
from app.database import get_user_data, sync_to_supabase, get_weight_history
from app.services.garmin import fetch_workout_details, get_today_str
from app.services.gemini import get_gemini_response

logger = logging.getLogger(__name__)

def sanitize_markdown(text):
    """Remove or escape characters that break Telegram Markdown parsing."""
    if not text: return ""
    # Gemini often uses single * which breaks things. Let's convert them to - or ensure they match.
    # For now, simplest is to replace _ which is very problematic in Markdown V1
    return text.replace("_", "\\_").replace("[", "\\[").replace("]", "\\]")

def safe_reply(message, text, parse_mode="Markdown"):
    """Try to send with Markdown, fallback to plain text if it fails."""
    sanitized = sanitize_markdown(text)
    try:
        bot.reply_to(message, sanitized, parse_mode=parse_mode)
    except Exception as e:
        logger.error(f"Markdown failed: {e}. Falling back to plain text.")
        bot.reply_to(message, text.replace("*", "").replace("_", ""))

def register_handlers():
    @bot.message_handler(commands=['set_key'])
    def set_key(message):
        key = message.text.replace('/set_key', '').strip()
        sync_to_supabase(message.chat.id, get_today_str(), {"gemini_key": key})
        bot.reply_to(message, "✅ Key saved!")

    @bot.message_handler(commands=['report'])
    def manual_report(message):
        bot.send_chat_action(message.chat.id, 'typing')
        parts = message.text.split()
        mode = "evening" # default
        if len(parts) > 1:
            arg = parts[1].lower()
            if arg in ["morning", "kickoff", "9am"]:
                mode = "morning"
        
        run_report_for_user(message.chat.id, mode=mode)

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
        elif "weight" in text and any(w in text for w in ["progress", "history", "trend", "looking"]):
            # Historical Weight Analysis
            history = get_weight_history(tg_id)
            if not history:
                bot.reply_to(message, "I don't have any weight logs for you yet! Log your weight by saying something like '75kg'.")
                return
            
            history_str = "\n".join([f"{row['log_date']}: {row['weight']}kg" for row in history])
            prompt = (f"Review this weight history and provide a thoughtful coaching analysis on progress and trends. "
                      f"Keep it encouraging and concise:\n\n{history_str}")
            
            analysis = get_gemini_response(tg_id, prompt)
            safe_reply(message, f"⚖️ *Weight Progress Analysis*\n\n{analysis}")
        elif ("kg" in text or "weight" in text) and any(c.isdigit() for c in text):
            res = get_gemini_response(tg_id, f"Extract only the numeric weight from: '{text}'. Output only the number.")
            match = re.search(r"[-+]?\d*\.?\d+", res)
            val = match.group(0) if match else None
            if val:
                sync_to_supabase(tg_id, today, {"weight": val})
                bot.reply_to(message, f"⚖️ {val}kg logged.")
            else:
                # Fallback to chat if extraction fails
                safe_reply(message, get_gemini_response(tg_id, f"Coach reply: {text}"))
        elif any(w in text for w in ["ate", "had", "lunch", "dinner"]) and any(c.isdigit() for c in text):
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
                # Fallback to chat if extraction fails
                safe_reply(message, get_gemini_response(tg_id, f"Coach reply: {text}"))
        else:
            safe_reply(message, get_gemini_response(tg_id, f"Coach reply: {text}"))
