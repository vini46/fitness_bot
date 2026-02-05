import logging
from flask import Flask
from threading import Thread
from app.config import PORT
from app.bot.bot_instance import bot
from app.bot.handlers import register_handlers
from app.scheduler import start_scheduler

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = Flask('')

@app.route('/')
def home(): 
    return "Fitness Bot Active"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    # Register handlers
    register_handlers()
    
    # Start Scheduler
    start_scheduler()
    
    # Run Flask in a background thread
    Thread(target=run_flask, daemon=True).start()
    
    # Start Bot Polling
    logging.info("Starting bot infinity polling...")
    bot.infinity_polling()
