import pickle
import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.exceptions import RefreshError

# Calendar integration constants and functions
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_credentials():
    """Get valid Google Calendar credentials, handling token refresh and corruption."""
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except ValueError:
            os.remove('token.json')
            return None
        except Exception as e:
            print(f"Error loading token.json: {e}")
            return None # Token file is corrupt.

    # If there are no credentials or they are invalid, attempt to refresh them.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                os.remove('token.json')
                print(f"Error refreshing token: {e}")
                return None
        else:
            return None

    return creds

def check_google_calendar_access():
    """Check if we have access to Google Calendar."""
    creds = get_credentials()
    if not creds:
        return False, "Authentication required"
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        service.calendars().get(calendarId='primary').execute()
        return True, "Access granted"
    except Exception as e:
        return False, f"Access error: {str(e)}"

def initiate_oauth_flow():
    """Initiate OAuth flow to authenticate the user."""
    if not os.path.exists('credentials.json'):
        return False, "Authentication error: `credentials.json` not found."
    
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8085, prompt='consent')

    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    return True, "Authentication successful!"

def add_event_to_google_calendar(event_data):
    """Add a single event to Google Calendar."""
    creds = get_credentials()
    if not creds:
        return False, "Authentication required."

    try:
        service = build('calendar', 'v3', credentials=creds)
        event = service.events().insert(calendarId='primary', body=event_data).execute()
        return True, f"Event created: {event.get('htmlLink')}"
    except Exception as e:
        if 'invalid_grant' in str(e) or 'invalid_credentials' in str(e):
            print("Authentication error during API call. Deleting token to force re-auth.")
            if os.path.exists('token.json'):
                os.remove('token.json')
        return False, f"Failed to add event: {str(e)}"

def parse_event_string(event_string):
    """Parse the event string into a dictionary."""
    try:
        event_parts = event_string.split(';')
        event_data = {
            'summary': event_parts[0],
            'description': event_parts[1],
            'start': {
                'dateTime': event_parts[2],
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': event_parts[3],
                'timeZone': 'UTC',
            },
        }
        return event_data
    except Exception:
        return None

def add_events_to_calendar(events, calendar_type="google"):
    """Add events to calendar (Google Calendar or iCal file)."""
    if calendar_type == "google":
        success_count = 0
        failed_count = 0
        results = []
        for event_string in events:
            event_data = parse_event_string(event_string)
            if event_data:
                success, message = add_event_to_google_calendar(event_data)
                if success:
                    success_count += 1
                    results.append(f"✅ {event_data['summary']}")
                else:
                    failed_count += 1
                    results.append(f"❌ {message}")
        
        result_message = f"{success_count} event(s) added successfully, {failed_count} failed."
        return result_message, results

def test_calendar_integration():
    """Test the Google Calendar integration."""
    test_event = {
        'summary': 'Test Event',
        'location': 'Online',
        'description': 'This is a test event.',
        'start': {
            'dateTime': (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat(),
            'timeZone': 'UTC',
        },
    }

    success, message = add_event_to_google_calendar(test_event)
    if success:
        return f"✅ **Test successful!** {message}"
    else:
        return f"❌ **Test failed:** {message}"

# Main logic to handle Google Calendar OAuth and event creation
if __name__ == '__main__':
    # Check Google Calendar access
    has_access, status = check_google_calendar_access()
    if not has_access:
        print(f"Access Error: {status}")
        print("Initiating OAuth flow...")
        success, message = initiate_oauth_flow()
        if success:
            print(message)
        else:
            print(f"OAuth Error: {message}")
    
    # Test adding an event
    test_result = test_calendar_integration()
    print(test_result)
