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
    # Universal slash included cleanly after intervals.icu/
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params = {"oldest": "2010-01-01", "newest": "2030-01-01"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code} - {response.text}")
    return response.json()

def fetch_gps_stream(activity_id):
    """Fetches coordinate paths using the correct streams endpoint string layout."""
    # FIXED URL: Clean trailing slash after intervals.icu/ and removed the .json extension
    url = f"https://intervals.icu/api/v1/activity/{activity_id}/streams"
    
    response = requests.get(url, params={"types": "latlng"}, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        return None
        
    try:
        streams = response.json()
        
        # Parse through the stream list blocks returned by the server
        if isinstance(streams, list):
            for stream in streams:
                if isinstance(stream, dict) and stream.get("type") == "latlng":
                    lats = stream.get("data", [])
                    lngs = stream.get("data2", [])
                    
                    if lats and lngs:
                        return list(zip(lats, lngs))
    except Exception:
        return None
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials. Verify your GitHub Secrets names!")
        return

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
                time.sleep(0.2)
            else:
                existing_ids.add(act_id)

        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nSuccess! Total tracks currently stored inside data.json: {len(map_data)}. New downloads added: {new_downloads}")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
