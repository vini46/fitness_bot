import os
import garth
from garminconnect import Garmin

# 1. Provide your credentials
email = "vinod.baradwaj@live.com"
password = "Batman@123"

# 2. Define where to save the tokens (a folder named 'garmin_tokens')
token_dir = "./garmin_tokens"

try:
    print(f"Attempting to log in as {email}...")
    api = Garmin(email, password)
    api.login()
    
    # 3. Use garth to save the session to the folder
    # This saves multiple .json files (oauth1, oauth2, etc.)
    api.garth.dump(token_dir)
    print(f"\n✅ SUCCESS! Tokens saved to: {token_dir}")
    print("Action: Upload this entire folder to your GitHub repository.")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")