import os
import datetime
import tempfile
import json
import shutil
from garminconnect import Garmin
from app.config import IST

def get_garmin_client(tg_id):
    from app.database import supabase
    # Fetch from 'user_integrations' table
    res = (supabase.table("user_integrations")
           .select("session_data")
           .eq("user_id", str(tg_id))
           .eq("provider", "garmin")
           .eq("is_active", True)
           .execute())
    
    if not res.data:
        return None
    
    # Create a temp dir to load the session
    tmp_dir = tempfile.mkdtemp()
    try:
        session_data = res.data[0]['session_data']
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
    from app.database import supabase
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
        
        # Save to 'user_integrations'
        integration_row = {
            "user_id": str(tg_id),
            "provider": "garmin",
            "session_data": session_dict,
            "is_active": True
        }
        supabase.table("user_integrations").upsert(integration_row, on_conflict="user_id, provider").execute()
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
        return report
    except: return "Garmin sync error."

def fetch_advanced_metrics(tg_id):
    api = get_garmin_client(tg_id)
    if not api: return ""
    today = get_today_str()
    metrics = []
    try:
        # 1. Sleep Data
        sleep = api.get_sleep_data(today)
        if sleep and 'dailySleepDTO' in sleep:
            dto = sleep['dailySleepDTO']
            score = dto.get('sleepScore', 'N/A')
            hours = round(dto.get('sleepTimeSeconds', 0) / 3600, 1)
            metrics.append(f"💤 Sleep: {hours}h (Score: {score})")
            
        # 2. Body Battery
        bb = api.get_body_battery(today)
        if bb:
            current_bb = bb[-1].get('bodyBatteryValue', 'N/A') if bb else 'N/A'
            metrics.append(f"🔋 Body Battery: {current_bb}/100")
            
        # 3. Stress
        stress = api.get_stress_data(today)
        if stress and 'stressChartDTO' in stress:
            avg_stress = stress.get('avgStressLevel', 'N/A')
            metrics.append(f"🧘 Stress Level: {avg_stress}")
            
        # 4. Nutrition (MyFitnessPal Sync)
        summary = api.get_user_summary(today)
        mfp_cals = summary.get('caloriesConsumed', 0)
        if mfp_cals > 0:
            protein = summary.get('proteinGrams', 0)
            carbs = summary.get('carbsGrams', 0)
            fat = summary.get('fatGrams', 0)
            metrics.append(f"🍎 MFP Nutrition: {mfp_cals} kcal (P:{protein}g, C:{carbs}g, F:{fat}g)")
            
        return "\n".join(metrics)
    except Exception as e:
        print(f"Advanced metrics error: {e}")
        return ""
