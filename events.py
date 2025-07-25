import requests
import os
from typing import List, Tuple, Dict
from datetime import datetime, timedelta

def search_ticketmaster_events(query: str, city: str, start_date: str, end_date: str) -> Tuple[List[str], List[Dict]]:
    """
    Searches for events using the Ticketmaster Discovery API.

    Args:
        query: A keyword to search for (e.g., "concerts", "sports").
        city: The city to search for events in.
        start_date: The start date for the event search in ISO 8601 format.
        end_date: The end date for the event search in ISO 8601 format.

    Returns:
        A tuple containing:
        - A list of formatted event summary strings for user display.
        - A list of detailed event dictionaries for the LLM context.
    """
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if not api_key:
        return ["Ticketmaster API key is not set. Please configure it in your environment variables."], []

    base_url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": api_key,
        "keyword": query,
        "city": city,
        "startDateTime": start_date,
        "endDateTime": end_date,
        "sort": "date,asc",
        "size": 10  # Limit to 10 events for concise output
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        if "_embedded" not in data or not data["_embedded"]["events"]:
            return ["No Ticketmaster events found."], []

        events = data["_embedded"]["events"]
        
        summaries = []
        details_list = []

        for event in events:
            name = event.get("name", "No Name")
            
            # --- Date and Time Formatting ---
            date_info = event.get("dates", {}).get("start", {})
            local_date = date_info.get("localDate")
            local_time = date_info.get("localTime")
            
            date_str = ""
            if local_date:
                try:
                    # Format date as YYYY-MM-DD
                    date_obj = datetime.strptime(local_date, "%Y-%m-%d")
                    date_str = date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    date_str = local_date # Fallback to original string

            time_str = ""
            if local_time:
                try:
                    # Format time as HH:MM AM/PM
                    time_obj = datetime.strptime(local_time, "%H:%M:%S")
                    time_str = time_obj.strftime("%I:%M %p")
                except ValueError:
                    time_str = local_time # Fallback to original string

            # --- Venue Information ---
            venue_info = event.get("_embedded", {}).get("venues", [{}])[0]
            venue_name = venue_info.get("name", "No Venue")

            # --- Description / Additional Info ---
            description = event.get("info") or event.get("pleaseNote") or "No additional information provided."
            
            # Create a user-friendly summary string
            if time_str:
                summary_str = f"{name} - {date_str} at {time_str} at {venue_name}"
            else:
                summary_str = f"{name} - {date_str} at {venue_name}"
            summaries.append(summary_str)
            
            # Create a detailed dictionary for the LLM
            details_list.append({
                "name": name,
                "date": f"{date_str} {time_str}".strip(),
                "venue": venue_name,
                "description": description,
                "artist": ", ".join([att.get("name") for att in event.get("_embedded", {}).get("attractions", []) if att.get("name")]),
            })

        return summaries, details_list

    except requests.exceptions.RequestException as e:
        return [f"An error occurred while fetching events: {e}"], []
    except Exception as e:
        return [f"An unexpected error occurred: {e}"], []

if __name__ == '__main__':
    # Example usage for testing
    # To run this, you need to set the TICKETMASTER_API_KEY environment variable
    # export TICKETMASTER_API_KEY='your_key_here'
    
    test_query = "concert"
    test_city = "Honolulu"
    # Search for events in the next 30 days
    now = datetime.now()
    start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Searching for '{test_query}' in '{test_city}' from {start} to {end}")
    
    event_summaries, event_details = search_ticketmaster_events(test_query, test_city, start, end)
    
    if event_summaries:
        print("\n--- Event Summaries ---")
        for i, summary in enumerate(event_summaries):
            print(f"{i+1}. {summary}")

    if event_details:
        print("\n--- Event Details (for LLM) ---")
        for i, detail in enumerate(event_details):
            print(f"\nEvent {i+1}:")
            print(f"  Name: {detail.get('name')}")
            print(f"  Date: {detail.get('date')}")
            print(f"  Venue: {detail.get('venue')}")
            print(f"  Artist(s): {detail.get('artist')}")
            print(f"  Description: {detail.get('description')}") 