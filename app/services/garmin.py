import os
import datetime
import tempfile
import json
import shutil
from garminconnect import Garmin
from app.config import IST

def get_garmin_client(tg_id):
    from app.database import get_user_data
    user_info = get_user_data(tg_id, get_today_str())
    if not user_info or not user_info.get('garmin_session'):
        return None
    
    # Create a temp dir to load the session
    tmp_dir = tempfile.mkdtemp()
    try:
        session_data = user_info['garmin_session']
        for filename, content in session_data.items():
            with open(os.path.join(tmp_dir, filename), 'w') as f:
                json.dump(content, f)
        
        api = Garmin()
        api.login(tmp_dir)
        return api
    except Exception as e:
        print(f"Garmin resume error for {tg_id}: {e}")
        return None
    finally:
        shutil.rmtree(tmp_dir)

def login_user_to_garmin(tg_id, email, password):
    from app.database import sync_to_supabase
    tmp_dir = tempfile.mkdtemp()
    try:
        api = Garmin(email, password)
        api.login()
        api.garth.dump(tmp_dir)
        
        # Read all files in tmp_dir and store them in a dict
        session_dict = {}
        for filename in os.listdir(tmp_dir):
            file_path = os.path.join(tmp_dir, filename)
            if os.path.isfile(file_path):
                with open(file_path, 'r') as f:
                    session_dict[filename] = json.load(f)
        
        sync_to_supabase(tg_id, get_today_str(), {"garmin_session": session_dict})
        return True
    except Exception as e:
        print(f"Garmin login error for {tg_id}: {e}")
        return False
    finally:
        shutil.rmtree(tmp_dir)

def get_today_str():
    return datetime.datetime.now(IST).strftime('%Y-%m-%d')

def fetch_workout_details(tg_id):
    api = get_garmin_client(tg_id)
    if not api: return "No Garmin data link. Use `/set_garmin email password` to link your account."
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
