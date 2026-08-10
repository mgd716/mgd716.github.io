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
    url = f"https://intervals.icu{ATHLETE_ID}/activities"
    params = {"oldest": "2010-01-01", "newest": "2030-01-01"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code} - {response.text}")
    return response.json()

def fetch_gps_stream(activity_id):
    """Fetches and parses the unique Intervals.icu latlng stream arrays."""
    url = f"https://intervals.icu{activity_id}/streams.json"
    
    response = requests.get(url, params={"types": "latlng"}, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        return None
        
    try:
        streams = response.json()
        
        # Intervals.icu returns streams as a LIST of stream blocks
        if isinstance(streams, list):
            for stream in streams:
                # Find the target dictionary block labeled 'latlng'
                if stream.get("type") == "latlng":
                    lats = stream.get("data", [])
                    lngs = stream.get("data2", []) # Longitudes are packed inside data2
                    
                    if lats and lngs:
                        # Combine lats and lngs into [[lat1, lng1], [lat2, lng2]...]
                        return list(zip(lats, lngs))
    except Exception as e:
        print(f"  └─ Parsing error for activity {activity_id}: {e}")
        return None
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials. Verify your GitHub Secrets names!")
        return

    # Load existing cached progress to avoid re-downloading
    map_data = []
    existing_ids = set()
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                map_data = json.load(f)
                if not isinstance(map_data, list):
                    map_data = []
                existing_ids = {str(item["id"]) for item in map_data if "id" in item}
            print(f"Loaded {len(map_data)} existing tracks from file.")
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

            # Skip if we already have this specific activity track mapped out
            if act_id in existing_ids:
                continue
                
            print(f"[{idx+1}/{len(activities)}] Processing NEW stream: {act_name} ({act_year})")
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
                # Prevent spamming the API too fast
                time.sleep(0.2)
            else:
                # If an activity has no GPS data (stationary trainer, indoor gym, etc.)
                # we track its ID as empty so we don't query it again on the next run
                existing_ids.add(act_id) 

        # Save the combined historical + new dataset
        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nSuccess! Total tracks stored inside data.json: {len(map_data)}. Newly added: {new_downloads}")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
