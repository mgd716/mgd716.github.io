import json
import os
import requests
import time
from requests.auth import HTTPBasicAuth

# ==================== CONFIGURATION ====================
ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
API_KEY = os.getenv("INTERVALS_API_KEY")
OUTPUT_FILE = "data.json"
# =======================================================

def fetch_activities():
    """Fetches the list of all activities from Intervals.icu."""
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params = {"oldest": "2010-01-01", "newest": "2020-01-01"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code} - {response.text}")
    return response.json()

def fetch_gps_stream(activity_id):
    """Fetches latitude/longitude coordinate arrays using the verified latlng stream key."""
    # The official endpoint to retrieve stream data as JSON
    url = f"https://intervals.icu/api/v1/activity/{activity_id}/streams.json"
    
    # Pass 'latlng' to grab the combined positional path array
    params = {"types": "latlng"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        return None
        
    try:
        data = response.json()
        # Intervals returns streams as list objects inside a dictionary container
        # If 'latlng' is found, it will look like: [[lat1, lng1], [lat2, lng2]...]
        if isinstance(data, dict) and "latlng" in data:
            return data["latlng"]
    except Exception:
        return None
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials. Verify your GitHub Secrets names!")
        return

    # 1. Load existing data if it exists
    map_data = []
    existing_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                map_data = json.load(f)
                if not isinstance(map_data, list):
                    map_data = []
                existing_ids = {str(item["id"]) for item in map_data if "id" in item}
            print(f"Loaded {len(map_data)} tracks from cache.")
        except Exception:
            print("Cache unreadable. Starting fresh.")
            map_data = []

    try:
        activities = fetch_activities()
        print(f"Syncing feed against {len(activities)} total activities...")
        
        new_downloads = 0
        
        for idx, act in enumerate(activities):
            act_id = str(act.get("id"))
            act_type = act.get("type", "Other")
            act_name = act.get("name", f"Activity {act_id}")
            
            act_date = act.get("start_date_local", "")
            act_year = act_date.split("-")[0] if act_date else "Unknown"

            # SMART SKIP: If we already have this ID saved in our array, completely skip it!
            if act_id in existing_ids:
                continue
                
            print(f"[{idx+1}/{len(activities)}] Downloading NEW stream: {act_name} ({act_year})")
            coordinates = fetch_gps_stream(act_id)
            
            if coordinates:
                new_downloads += 1
                map_data.append({
                    "id": act_id,
                    "type": act_type,
                    "name": act_name,
                    "year": act_year,
                    "coordinates": coordinates
                })
                # Subtle break interval to prevent server spamming
                time.sleep(0.1)
                
        # 2. Save the compiled results directly back to your file
        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nSuccess! Total tracks currently stored inside your file: {len(map_data)}. New downloads added: {new_downloads}")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
