import requests
import time
import logging
from app.config import OPENROUTER_BASE_URL

logger = logging.getLogger(__name__)

def get_openrouter_response(api_key, model_id, prompt):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/vini46/fitness_bot", # Optional, for OpenRouter rankings
        "X-Title": "Fitness Bot"
    }
    
    data = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    for attempt in range(3):
        try:
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            elif response.status_code == 429:
                logger.warning(f"OpenRouter 429 - Attempt {attempt + 1}")
                time.sleep((attempt + 1) * 3)
                continue
            else:
                logger.error(f"OpenRouter API Error: {response.status_code} - {response.text}")
                return "API_ERROR"
        except Exception as e:
            logger.error(f"OpenRouter Exception: {e}")
            time.sleep((attempt + 1) * 2)
            
    return "RATE_LIMIT_EXCEEDED"
