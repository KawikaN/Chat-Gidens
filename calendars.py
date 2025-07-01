from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime

# If modifying these scopes, delete the file token.json
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    # OAuth flow
    creds = None
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=8080)

    # Save token for future use
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

    # Connect to the Calendar API
    service = build('calendar', 'v3', credentials=creds)

    # Create a sample event
    event = {
        'summary': 'Sample Event',
        'location': 'Honolulu, HI',
        'description': 'Testing calendar API.',
        'start': {
            'dateTime': '2025-06-26T10:00:00-10:00',
            'timeZone': 'Pacific/Honolulu',
        },
        'end': {
            'dateTime': '2025-06-26T11:00:00-10:00',
            'timeZone': 'Pacific/Honolulu',
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")

if __name__ == '__main__':
    main()
