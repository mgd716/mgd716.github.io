import json
import os
import requests
import time
import glob # <--- New import needed to find multiple files
from requests.auth import HTTPBasicAuth

# ==================== CONFIGURATION ====================
ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
API_KEY = os.getenv("INTERVALS_API_KEY")
OUTPUT_FILE = "data.json"
# =======================================================

def fetch_activities():
    """Fetches the list of all activities from Intervals.icu."""
    # Strictly structured base domain with a trailing slash
    base_url = "https://intervals.icu/"
    endpoint = f"api/v1/athlete/{ATHLETE_ID}/activities"
    url = base_url + endpoint
    
    params = {"oldest": "2010-01-01", "newest": "2030-01-01"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities list: {response.status_code} - {response.text}")
    return response.json()

def fetch_gps_stream(activity_id):
    """Fetches time-series data using the official activities streams endpoint format."""
    # Hardcoded base path to guarantee slashes never get dropped or misplaced
    base_url = "https://intervals.icu/"
    endpoint = f"api/v1/activity/{activity_id}/streams.json"
    url = base_url + endpoint
    
    params = {"types": "latlng"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('API_KEY', API_KEY))
    if response.status_code != 200:
        return None
        
    try:
        streams = response.json()
        
        # Parse through the data stream list blocks returned by the server
        if isinstance(streams, list):
            for stream in streams:
                if isinstance(stream, dict) and stream.get("type") == "latlng":
                    lats = stream.get("data", [])
                    lngs = stream.get("data2", []) # Longitudes live inside data2
                    
                    if lats and lngs:
                        # Round to 5 decimal places and keep only every 4th point [::4]
                        return [[round(lat, 5), round(lng, 5)] for lat, lng in zip(lats, lngs)][::4]
    except Exception:
        return None
    return None

def main():
    if not ATHLETE_ID or not API_KEY:
        print("Error: Missing credentials. Check your GitHub Secrets names!")
        return

    # 1. Load cache from ALL existing year files
    years_data = {}
    existing_ids = set()
    
    for file in glob.glob("data_*.json"):
        try:
            with open(file, "r") as f:
                data = json.load(f)
                year_key = file.split("_")[1].split(".")[0]
                years_data[year_key] = data
                for item in data:
                    if "id" in item:
                        existing_ids.add(str(item["id"]))
            print(f"Loaded {len(data)} tracks from {file}.")
        except Exception:
            pass

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
                
            print(f"[{idx+1}/{len(activities)}] Fetching stream for: {act_name} ({act_year})")
            coordinates = fetch_gps_stream(act_id)
            
            if coordinates:
                new_downloads += 1
                if act_year not in years_data:
                    years_data[act_year] = []
                    
                years_data[act_year].append({
                    "id": act_id,
                    "type": act_type,
                    "name": act_name,
                    "year": act_year,
                    "coordinates": coordinates
                })
                time.sleep(0.2) 
            else:
                existing_ids.add(act_id)

        # 2. Save each year as its own compressed file
        years_list = list(years_data.keys())
        for year, data in years_data.items():
            with open(f"data_{year}.json", "w") as f:
                json.dump(data, f, separators=(',', ':'))
                
        # 3. Save a metadata file so the frontend knows what years exist
        with open("years.json", "w") as f:
            json.dump(years_list, f)
            
        print(f"\nSuccess! Saved {len(years_list)} year files. New downloads: {new_downloads}")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
