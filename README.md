# 🤖 Personal Coach Bot

![App Status](https://img.shields.io/website?url=https%3A%2F%2Fharsh-pansie-vbvini-1199210e.koyeb.app%2F&label=App%20Status)

An AI-powered health and fitness companion that lives in Telegram. It integrates with Garmin and MyFitnessPal to provide personalized coaching, health summaries, and proactive nudges.

---

## 🌟 Key Features

- **Twice-Daily Reports**:
    - **9 AM Kickoff**: Analyzes last night's sleep, current Body Battery, and suggests a movement goal for the day.
    - **9 PM Wind-down**: Summarizes achievements, analyze nutrition (MyFitnessPal), and suggests recovery strategies.
- **Device Integration**: Native syncing with **Garmin Connect** (Steps, Heart Rate, Body Battery, Stress, Sleep, Workouts) and **MyFitnessPal** (Nutrition/Macros).
- **Proactive Nudges**: Automated reminders for weight logging, water intake, and evening workout checks.
- **AI Brain**: Powered by **Gemini 2.0 Flash** for natural, encouraging, and context-aware health coaching.
- **Relational Database**: Scalable Supabase architecture with separate tables for user profiles, platform integrations, and daily metrics.

---

## 📱 User Guide: Start Coaching

Follow these steps to get your personal AI coach running in minutes:

1.  **Find the Bot**: Search for [@fitVinod_bot](https://t.me/fitVinod_bot) on Telegram and press **Start**.
2.  **Set your AI Key**: (Only if self-hosting) Send `/set_key your_api_key` to give the bot its "brain."
3.  **Link Garmin**: Send `/set_garmin your_email your_password`. 
    - *Tip: This syncs your steps, sleep, and MyFitnessPal nutrition data automatically.*
4.  **Log your Weight**: Simply type `85kg` or `My weight is 85.5` anytime. The bot will track your progress.
5.  **Log your Food**: Type `I had a 500 kcal lunch` to track calories manually if you don't use MyFitnessPal.
6.  **Ask Questions**: Ask the coach anything! e.g., *"Why is my body battery low?"* or *"How was my sleep last night?"*

### 🎮 Commands
- `/report`: Get an instant health summary (Morning or Evening).
- `/set_garmin`: Link your Garmin Connect account.
- `/set_key`: Configure your Gemini API key.

---

## 🏗 Architecture

- **Language**: Python 3.11+
- **Framework**: `pyTelegramBotAPI` (Telebot)
- **Database**: `Supabase` (PostgreSQL)
- **AI**: `Google Gemini SDK`
- **Scheduler**: `APScheduler`
- **Server**: `Flask` + `Waitress` (for health checks/deployment)
- **Infrastructure**: `Docker`

---

## 🚀 Getting Started (Developer Guide)

### 1. Prerequisites
- Python 3.11 or higher.
- A **Supabase** project (URL and Secret Key).
- A **Telegram Bot Token** (from @BotFather).
- A **Google Gemini API Key**.

### 2. Environment Variables
Create a `.env` file (or set these in your environment):
```env
TELEGRAM_TOKEN=your_telegram_bot_token
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key
GEMINI_KEY=your_gemini_api_key
PORT=8080
```

### 3. Installation
```bash
# Clone the repository
git clone https://github.com/vini46/fitness_bot.git
cd fitnessbot

# Install dependencies
pip install -r requirements.txt
```

### 4. Database Setup
1. Execute the SQL script found in `scripts/schema_migration.sql` in your Supabase SQL Editor.
2. If you have legacy data, use `scripts/migrate_v1_to_v2.py`.
3. Refer to [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) for detailed table definitions.

### 5. Running the Bot
```bash
python main.py
```

---

## 📁 Project Structure

```text
├── app/
│   ├── bot/
│   │   ├── handlers.py     # Telegram command and message handlers
│   │   ├── tasks.py        # Background reporting and reminder logic
│   │   └── bot_instance.py # Bot initialization
│   ├── services/
│   │   ├── garmin.py       # Garmin & MyFitnessPal integration service
│   │   └── gemini.py       # AI response generation service
│   ├── database.py         # Supabase CRUD operations
│   ├── scheduler.py        # Background job configurations
│   └── config.py           # Global constants and timezone setup
├── scripts/                # SQL migrations and data utilities
├── main.py                 # Entry point (Flask + Bot + Scheduler)
├── README.md               # You are here
└── DATABASE_SCHEMA.md      # Database relationship documentation
```

---

## 🤝 How to Contribute

We welcome contributions! To get started:

1.  **Fork the Repo**: Create your own branch for the feature or fix.
2.  **Follow the Pattern**: Use the **Adapter Pattern** for new health platforms (e.g., adding Apple Health or Google Fit).
3.  **Code Style**: 
    - Keep functions small and focused.
    - Wrap API calls in `try-except` blocks for resilience.
    - Use `safe_reply` in `handlers.py` to handle Telegram's message limits.
4.  **Verification**: 
    - Test commands manually via a test bot.
    - Verify database writes in the Supabase dashboard.
5.  **Submit a PR**: Provide a clear description of what changed and why.

---

## 📄 Documentation
- [Database Schema](./DATABASE_SCHEMA.md)
