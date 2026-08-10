import json
import os
import requests
from requests.auth import HTTPBasicAuth

# ==================== CONFIGURATION ====================
# The script safely pulls your clean, matched names from the cloud runner
ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
API_KEY = os.getenv("INTERVALS_API_KEY")
OUTPUT_FILE = "data.json"
# =======================================================

def fetch_activities():
    """Fetches the list of all activities from Intervals.icu."""
    print("Fetching activity list...")
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities"
    
    # Intervals.icu requires 'oldest' and 'newest' date limits (YYYY-MM-DD)
    # 2010-01-01 ensures we fetch your entire historical timeline
    # 2030-01-01 covers all dates up to the future
    params = {
        "oldest": "2010-01-01",
        "newest": "2030-01-01"
    }
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code} - {response.text}")
    return response.json()


def fetch_gps_stream(activity_id):
    """Fetches latitude/longitude coordinate arrays for a specific activity."""
    # Double-check that there is a strict forward slash after intervals.icu/
    url = f"https://intervals.icu/api/v1/athlete/{ATHLETE_ID}/activities/{activity_id}/streams"
    
    response = requests.get(url, params={"types": "lat,lng"}, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        return None
    data = response.json()
    if "lat" in data and "lng" in data:
        return list(zip(data["lat"], data["lng"]))
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials. Check your GitHub Secrets setup!")
        return

    try:
        # Load existing data from cache if it exists
        existing_data = {}
        if os.path.exists(OUTPUT_FILE):
            try:
                with open(OUTPUT_FILE, "r") as f:
                    old_list = json.load(f)
                    # Convert list to a dictionary lookup for blazing fast ID checking
                    existing_data = {str(item["id"]): item for item in old_list}
                print(f"Loaded {len(existing_data)} existing activities from cache.")
            except Exception:
                print("Cache file unreadable or empty. Starting fresh.")

        activities = fetch_activities()
        map_data = []
        print(f"Found {len(activities)} activities. Extracting GPS paths...")
        
        for idx, act in enumerate(activities):
            act_id = act.get("id")
            act_type = act.get("type")
            
            if act.get("indoor") or not act.get("distance"):
                continue
                
            # If it's a brand new activity, download its GPS coordinates
            print(f"✨ Found NEW activity! Downloading stream for {act_type} (ID: {act_id})...")
            coordinates = fetch_gps_stream(act_id)
            new_downloads_count += 1
            
            if coordinates and len(coordinates) > 1:
                map_data.append({
                    "id": act_id,
                    "type": act_type,
                    "coordinates": coordinates
                })
                
        # Save the combined historical + new dataset
        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nSync complete! Total tracks on map: {len(map_data)}. (Downloaded {new_downloads_count} new paths tonight).")
        
    except Exception as e:
        print(f"\nError running script: {e}")

if __name__ == "__main__":
    main()
