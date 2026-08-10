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
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    params = {"oldest": "2010-01-01", "newest": "2030-01-01"}
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code}")
    return response.json()

def fetch_gps_stream(activity_id):
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities/{activity_id}/streams"
    response = requests.get(url, params={"types": "lat,lng"}, auth=HTTPBasicAuth('API_KEY', API_KEY))
    
    if response.status_code == 429:
        print("⚠️ Hitting rate limits! Saving current progress and backing off...")
        return "RATE_LIMIT"
    if response.status_code != 200:
        return None
        
    data = response.json()
    if "lat" in data and "lng" in data:
        return list(zip(data["lat"], data["lng"]))
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials.")
        return

    # Load existing progress (cache)
    existing_data = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                existing_data = {str(item["id"]): item for item in json.load(f)}
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
            
            # FIXED: Added [0] to extract just the 4-digit year string (e.g., '2024')
            act_date = act.get("start_date_local", "")
            act_year = act_date.split("-")[0] if act_date else "Unknown"

            # Re-use existing cache item if it's already completely downloaded
            if act_id in existing_data:
                item = existing_data[act_id]
                item["name"] = act_name
                item["year"] = act_year
                map_data.append(item)
                continue
                
            # Rate limit buffer checkpoint (downloads ~90 tracks per workflow trigger execution)
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
                time.sleep(0.3) # Short safety pause

        # Save all results safely 
        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nBatch saved! Total tracks currently stored: {len(map_data)}.")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
