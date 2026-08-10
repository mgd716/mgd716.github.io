import json
import os
import requests
from requests.auth import HTTPBasicAuth

# ==================== CONFIGURATION ====================
# Replace these with your actual credentials from your Intervals.icu Settings page
ATHLETE_ID = "YOUR_INTERVALS_ICU_ATHLETE_ID"
API_KEY = "YOUR_INTERVALS_ICU_API_KEY"
OUTPUT_FILE = "data.json"
# =======================================================

def fetch_activities():
    """Fetches the list of all activities from Intervals.icu."""
    print("Fetching activity list...")
    url = f"https://intervals.icu{ATHLETE_ID}/activities"
    
    # Intervals.icu uses basic auth: username is 'athlete', password is your API key
    response = requests.get(url, auth=HTTPBasicAuth('athlete', API_KEY))
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch activities: {response.status_code} - {response.text}")
        
    return response.json()

def fetch_gps_stream(activity_id):
    """Fetches the latitude and longitude stream arrays for a specific activity."""
    url = f"https://intervals.icu{ATHLETE_ID}/activities/{activity_id}/streams"
    params = {"types": "lat,lng"}
    
    response = requests.get(url, params=params, auth=HTTPBasicAuth('athlete', API_KEY))
    
    if response.status_code != 200:
        # Some workouts (like indoor gym or indoor cycling) won't have GPS data
        return None
        
    data = response.json()
    
    # Ensure both streams exist
    if "lat" in data and "lng" in data:
        # Combine [lat1, lat2...] and [lng1, lng2...] into [[lat1, lng1], [lat2, lng2]...]
        coordinates = list(zip(data["lat"], data["lng"]))
        return coordinates
    return None

def main():
    try:
        activities = fetch_activities()
        map_data = []
        
        print(f"Found {len(activities)} activities. Extracting GPS paths...")
        
        for idx, act in enumerate(activities):
            act_id = act.get("id")
            act_type = act.get("type") # e.g., 'Run', 'Ride'
            
            # Skip activities that are clearly indoor or don't have moving distance
            if act.get("indoor") or not act.get("distance"):
                continue
                
            print(f"[{idx+1}/{len(activities)}] Processing {act_type} (ID: {act_id})...")
            
            coordinates = fetch_gps_stream(act_id)
            
            if coordinates and len(coordinates) > 1:
                map_data.append({
                    "id": act_id,
                    "type": act_type,
                    "coordinates": coordinates
                })
                
        # Save to data.json
        with open(OUTPUT_FILE, "w") as f:
            json.dump(map_data, f, indent=2)
            
        print(f"\nSuccess! Successfully saved {len(map_data)} mapped activities to '{OUTPUT_FILE}'.")
        
    except Exception as e:
        print(f"\nError running script: {e}")

if __name__ == "__main__":
    main()
