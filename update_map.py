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
    # The URL pattern uses your specific athlete ID number
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params = {"oldest": "2010-01-01", "newest": "2020-01-01"}
    
    # CORRECT AUTH: The basic authentication username is strictly the string literal 'API_KEY'
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code} - {response.text}")
    return response.json()

def fetch_gps_stream(activity_id):
    """Fetches latitude/longitude coordinate arrays using the correct stream endpoint."""
    # CORRECT URL: Must be singular 'activity' followed by '.json' extension
    url = f"https://intervals.icu/api/v1/activity/{activity_id}/streams.json"
    params = {"types": "lat,lng"}
    
    # CORRECT AUTH: The basic authentication username is strictly the string literal 'API_KEY'
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    
    if response.status_code == 429:
        print("⚠️ Hitting rate limits! Saving current progress and backing off...")
        return "RATE_LIMIT"
    if response.status_code != 200:
        return None
        
    try:
        data = response.json()
        # Intervals returns streams as keys inside a dictionary object
        if isinstance(data, dict) and "lat" in data and "lng" in data:
            return list(zip(data["lat"], data["lng"]))
    except Exception:
        return None
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials. Verify your GitHub Secrets names!")
        return

    # Load existing progress (cache layer)
    existing_data = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                existing_data = {str(item["id"]): item for item in json.load(f) if "id" in item}
            print(f"Loaded {len(existing_data)} tracks from cache.")
        except Exception:
            pass

    try:
        activities = fetch_activities()
        map_data = []
        new_downloads = 0
        
        print(f"Syncing entries against {len(activities)} activities...")
        
        for idx, act in enumerate(activities):
            act_id = str(act.get("id"))
            act_type = act.get("type", "Other")
            act_name = act.get("name", f"Activity {act_id}")
            
            act_date = act.get("start_date_local", "")
            act_year = act_date.split("-")[0] if act_date else "Unknown"

            if act_id in existing_data:
                item = existing_data[act_id]
                item["name"] = act_name
                item["year"] = act_year
                map_data.append(item)
                continue
                
            if new_downloads >= 90: 
                print("Stopping loop for this run to keep API usage safe. Appending remaining cache files...")
                for remaining_act in activities[idx:]:
                    rem_id = str(remaining_act.get("id"))
                    if rem_id in existing_data:
                        map_data.append(existing_data[rem_id])
                break

            print(f"[{idx+1}/{len(activities)}] Processing: {act_name} ({act_year})")
            coordinates = fetch_gps_stream(act_id)
            
            if coordinates == "RATE_LIMIT":
                for remaining_act in activities[idx:]:
                    rem_id = str(remaining_act.get("id"))
                    if rem_id in existing_data:
                        map_data.append(existing_data[rem_id])
                break
                
            if coordinates:
                new_downloads += 1
                map_data.append({
                    "id": act_id,
                    "type": act_type,
                    "name": act_name,
                    "year": act_year,
                    "coordinates": coordinates
                })
                time.sleep(0.4) # Add 400ms delay to strictly respect API bounds

        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nBatch saved! Total tracks currently stored: {len(map_data)}.")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
