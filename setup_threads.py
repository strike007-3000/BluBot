import requests
from dotenv import load_dotenv

load_dotenv()

# --- STEP 1: CONFIGURATION ---
# Get these from https://developers.facebook.com/
APP_ID = input("Enter your Threads App ID: ")
APP_SECRET = input("Enter your Threads App Secret: ")
REDIRECT_URI = "https://localhost/" # Must match what you set in the App Dashboard

print(f"\n1. Go to this URL in your browser:\n")
print(f"https://www.threads.net/oauth/authorize?client_id={APP_ID}&redirect_uri={REDIRECT_URI}&scope=threads_basic,threads_content_publish&response_type=code")
print("\n2. Authorize the app and you will be redirected to a URL like https://localhost/?code=YOUR_CODE_HERE")
print("3. Copy the string after 'code=' and paste it below.")

code = input("\nEnter the 'code' from the URL: ").strip()

if not code:
    print("Error: No code provided.")
    exit()

# --- STEP 2: EXCHANGE CODE FOR SHORT-LIVED TOKEN ---
print("\nExchanging code for short-lived token...")
url = "https://graph.threads.net/oauth/access_token"
payload = {
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
    "code": code
}

try:
    response = requests.post(url, data=payload)
    response.raise_for_status()
    data = response.json()
    short_token = data.get("access_token")
    user_id = data.get("user_id")
    
    print(f"Success! User ID: {user_id}")
    
    # --- STEP 3: EXCHANGE FOR LONG-LIVED TOKEN (60 DAYS) ---
    print("Exchanging for long-lived access token...")
    ll_url = "https://graph.threads.net/access_token"
    ll_params = {
        "grant_type": "th_exchange_token",
        "client_secret": APP_SECRET,
        "access_token": short_token
    }
    
    ll_response = requests.get(ll_url, params=ll_params)
    ll_response.raise_for_status()
    ll_data = ll_response.json()
    long_token = ll_data.get("access_token")
    
    print("\n" + "="*50)
    print("🎉 CONGRATULATIONS! 🎉")
    print("="*50)
    print(f"Your Threads Long-Lived Access Token is:\n\n{long_token}\n")
    print("Copy this token and add it to your GitHub Secrets as 'THREADS_ACCESS_TOKEN'.")
    print("Also, add your User ID to GitHub Secrets as 'THREADS_USER_ID' if prompted by the bot.")
    print("="*50)

except Exception as e:
    print(f"\nError: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response: {e.response.text}")
