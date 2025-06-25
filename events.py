import requests
from datetime import datetime




def search_events(event_type: str):
    token = "ItAuqTG7g3M1FhHu"
    params = {
        "q": event_type,
        "location.address": "Honolulu",
        "start_date.range_start": "2025-06-20T00:00:00Z",
        "start_date.range_end": "2025-07-31T23:59:59Z",
        "expand": "venue"
    }
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get("https://www.eventbriteapi.com/v3/events/search/", params=params, headers=headers)
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        print(response.text)
        return []
    events = response.json().get("events", [])
    if not events:
        print(f"No events found for '{event_type}'.")
    else:
        for e in events:
            print(f"{e['name']['text']} — {e['start']['local']} at {e.get('venue', {}).get('address', {}).get('localized_address_display', 'Unknown')}")
    return list, events


def search_ticketmaster_events(event_type: str):
    list = []
    api_key = "t1olQhHOzw8OSkI6CkPUpiu7INqmsbke"
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": api_key,
        "keyword": event_type,
        "city": "Honolulu",
        "startDateTime": "2025-06-23T00:00:00Z",
        "endDateTime": "2025-07-10T23:59:59Z",
        "size": 20
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Ticketmaster Error: Received status code {response.status_code}")
        print(response.text)
        return []
    data = response.json()
    events = data.get("_embedded", {}).get("events", [])
    if not events:
        print(f"No Ticketmaster events found for '{event_type}'.")
        list.append("No Ticketmaster events found.")
    else:
        for e in events:
            name = e.get('name', 'Unknown')
            start = e.get('dates', {}).get('start', {}).get('localDate', 'Unknown')
            venue = e.get('_embedded', {}).get('venues', [{}])[0].get('name', 'Unknown')
            list.append(name + " - " + start + " at " + venue)
            # print(f"{name} — {start} at {venue}")
    return list, events

# Example usage:
# result = search_events("")
# print(f"Returned {len(result)} events.")

# print('\n')

## Example usage for Ticketmaster:
# tm_result = search_ticketmaster_events("")
# print(f"Ticketmaster returned {len(tm_result)} events.")

# print('\n')

# import requests

# response = requests.get('https://ipinfo.io/json')
# data = response.json()

# loc = data['loc']  # e.g., "37.3860,-122.0838"
# latitude, longitude = map(float, loc.split(','))

def search_Allevents_events(latitude, longitude, radius):
    list = []
    api_key = "t1olQhHOzw8OSkI6CkPUpiu7INqmsbke"
    url = "https://api.allevents.in/events/geo/?latitude={latitude}&longitude={longitude}&radius={radius}[&page][&category]"
    params = {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius
            # page,
            # category
            }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        print(response.text)
        return []
    data = response.json()
    events = data.get("_embedded", {}).get("events", [])
    if not events:
        pass
        # print(f"No AllEvents event found for '{category}'.")

    else:
        for e in events:
            name = e.get('name', 'Unknown')
            start = e.get('dates', {}).get('start', {}).get('localDate', 'Unknown')
            venue = e.get('_embedded', {}).get('venues', [{}])[0].get('name', 'Unknown')
            list.append(name + " - " + start + " at " + venue)
            print(f"{name} — {start} at {venue}")
    return list, events

# latitude = 40.7
# longitude = 74.0
# search_Allevents_events(latitude, longitude, 100)
# for i in search_ticketmaster_events("")[0]:
#     print(i)
# print(search_ticketmaster_events("")[0])
# event_message = "\n".join(search_ticketmaster_events("")[0])
# print(event_message[0])