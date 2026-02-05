import time
import datetime
from google import genai
from app.config import MODEL_ID, IST
from app.database import get_user_data

def get_gemini_response(tg_id, prompt):
    today = datetime.datetime.now(IST).strftime('%Y-%m-%d')
    user_info = get_user_data(tg_id, today)
    
    if not user_info or not user_info.get('gemini_key'):
        return "KEY_MISSING"

    for attempt in range(3):
        try:
            client = genai.Client(api_key=user_info['gemini_key'])
            res = client.models.generate_content(model=MODEL_ID, contents=prompt)
            return res.text
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                time.sleep((attempt + 1) * 3)
                continue
            return "API_ERROR"
    return "RATE_LIMIT_EXCEEDED"
