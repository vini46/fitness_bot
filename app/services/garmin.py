import os
import datetime
from garminconnect import Garmin
from app.config import IST, GARMIN_TOKEN_DIR

def init_garmin():
    if not os.path.exists(GARMIN_TOKEN_DIR): return None
    try:
        api = Garmin()
        api.login(GARMIN_TOKEN_DIR)
        return api
    except: return None

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

def fetch_workout_details():
    api = init_garmin()
    if not api: return "No Garmin data link."
    today = get_today_str()
    try:
        # Get Steps
        summary = api.get_user_summary(today)
        steps = summary.get('totalSteps', 0)
        step_str = f"👣 Steps: {steps}\n"
        
        # Get Workouts
        activities = api.get_activities_by_date(today, today)
        if not activities: 
            return step_str + "No workouts logged today."
        
        report = step_str + "Workouts:\n"
        for act in activities:
            name = act.get('activityName', 'Activity')
            cals = act.get('calories', 0)
            duration = round(act.get('duration', 0) / 60, 1)
            report += f"- {name}: {duration}m | {cals}kcal\n"
        return report
    except: return "Garmin sync error."
