import time
from google import genai

def get_gemini_response(api_key, model_id, prompt):
    """
    Generic Gemini response generator.
    """
    for attempt in range(3):
        try:
            client = genai.Client(api_key=api_key)
            res = client.models.generate_content(model=model_id, contents=prompt)
            return res.text
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                time.sleep((attempt + 1) * 3)
                continue
            return f"API_ERROR: {str(e)}"
    return "RATE_LIMIT_EXCEEDED"
