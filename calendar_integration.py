import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import json
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Google Calendar API setup
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP server to handle OAuth callback"""
    
    def __init__(self, *args, auth_code_queue=None, **kwargs):
        self.auth_code_queue = auth_code_queue
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle OAuth callback"""
        try:
            # Parse the callback URL
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            # Check if this is an OAuth callback
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                print(f"✅ Received OAuth authorization code")
                
                # Send success response to browser
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                success_html = """
                <html>
                <head><title>Authentication Successful</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                    <div style="background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px);">
                        <h2 style="color: #4CAF50; margin-bottom: 20px;">✅ Authentication Successful!</h2>
                        <p style="font-size: 18px; margin-bottom: 15px;">Your Google Calendar is now connected!</p>
                        <p style="font-size: 16px; margin-bottom: 25px;">Redirecting you back to your chatbot...</p>
                        <div style="margin-top: 20px;">
                            <button onclick="window.close()" style="background: #4CAF50; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; cursor: pointer; transition: background 0.3s;" onmouseover="this.style.background='#45a049'" onmouseout="this.style.background='#4CAF50'">
                                Close Window
                            </button>
                        </div>
                    </div>
                    <script>
                        // Try to redirect to Streamlit app first
                        try {
                            // Attempt to redirect to common Streamlit ports
                            const streamlitUrls = [
                                'http://localhost:8501',
                                'http://localhost:8502', 
                                'http://localhost:8503',
                                'http://127.0.0.1:8501',
                                'http://127.0.0.1:8502',
                                'http://127.0.0.1:8503'
                            ];
                            
                            // Try each URL
                            for (let url of streamlitUrls) {
                                try {
                                    window.open(url, '_self');
                                    break;
                                } catch (e) {
                                    console.log('Could not redirect to:', url);
                                }
                            }
                        } catch (e) {
                            console.log('Redirect failed, will auto-close');
                        }
                        
                        // Auto-close after 3 seconds as fallback
                        setTimeout(function() {
                            window.close();
                        }, 3000);
                        
                        // Also close on any click
                        document.addEventListener('click', function() {
                            window.close();
                        });
                    </script>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
                
                # Put the auth code in the queue for the main thread
                if self.auth_code_queue:
                    self.auth_code_queue.put(auth_code)
                    
            else:
                # Handle error or other requests
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                error_html = """
                <html>
                <head><title>Authentication Error</title></head>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white;">
                    <div style="background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px);">
                        <h2 style="color: #ff4757; margin-bottom: 20px;">❌ Authentication Error</h2>
                        <p style="font-size: 16px; margin-bottom: 25px;">There was an issue with the authentication process.</p>
                        <p style="font-size: 14px; margin-bottom: 20px;">Please try again or contact support if the problem persists.</p>
                        <div style="margin-top: 20px;">
                            <button onclick="window.close()" style="background: #ff4757; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; cursor: pointer;">
                                Close Window
                            </button>
                        </div>
                    </div>
                    <script>
                        setTimeout(function() {
                            window.close();
                        }, 5000);
                    </script>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
                
        except Exception as e:
            print(f"❌ OAuth callback error: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error_html = """
            <html>
            <head><title>Server Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); color: white;">
                <div style="background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px);">
                    <h2 style="color: #ff4757; margin-bottom: 20px;">❌ Server Error</h2>
                    <p style="font-size: 16px; margin-bottom: 25px;">An unexpected error occurred during authentication.</p>
                    <p style="font-size: 14px; margin-bottom: 20px;">Please try again or contact support.</p>
                    <div style="margin-top: 20px;">
                        <button onclick="window.close()" style="background: #ff4757; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-size: 16px; cursor: pointer;">
                            Close Window
                        </button>
                    </div>
                </div>
                <script>
                    setTimeout(function() {
                        window.close();
                    }, 5000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())

class CalendarIntegration:
    """
    Calendar integration class to handle adding events to various calendar services.
    
    USER DATA REQUIREMENTS:
    - For Google Calendar: 
      * Create a project in Google Cloud Console
      * Enable Google Calendar API
      * Create OAuth 2.0 credentials
      * Download credentials.json file
      * Place credentials.json in the project root
    - For Outlook/Office365:
      * Microsoft Graph API credentials
      * Client ID and Client Secret
    - For iCal export:
      * No credentials needed, generates .ics file
    """
    
    def __init__(self):
        self.google_service = None
        self.outlook_credentials = None
        self.auth_status = "not_checked"  # not_checked, authorized, unauthorized, needs_setup
        
    def check_google_calendar_access(self) -> Tuple[bool, str]:
        """
        Check if we have access to Google Calendar.
        
        Returns:
            Tuple of (has_access, status_message)
        """
        try:
            # Check if credentials file exists
            if not os.path.exists('credentials.json'):
                return False, "Google Calendar setup required. Please follow the setup guide to download credentials.json"
            
            # Check if we have valid tokens
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
                
                if creds and creds.valid:
                    # Test the connection with timeout
                    try:
                        import signal
                        
                        def timeout_handler(signum, frame):
                            raise TimeoutError("Connection timed out")
                        
                        # Set a 10-second timeout for the API call
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(10)
                        
                        try:
                            service = build('calendar', 'v3', credentials=creds)
                            # Try to access calendar to verify permissions
                            calendar_info = service.calendars().get(calendarId='primary').execute()
                            self.google_service = service
                            self.auth_status = "authorized"
                            signal.alarm(0)  # Cancel the alarm
                            
                            # Get user info to verify it's the right account
                            user_info = service.calendars().get(calendarId='primary').execute()
                            print(f"✅ DEBUG: Connected to calendar for account: {user_info.get('id', 'unknown')}")
                            
                            return True, "✅ Google Calendar access confirmed"
                        except TimeoutError:
                            signal.alarm(0)  # Cancel the alarm
                            return False, "⏰ Google Calendar connection timed out"
                        except Exception as e:
                            signal.alarm(0)  # Cancel the alarm
                            if "invalid_grant" in str(e) or "token_expired" in str(e):
                                return False, "🔄 Google Calendar token expired. Please re-authenticate."
                            else:
                                return False, f"❌ Google Calendar access error: {str(e)}"
                    except Exception as e:
                        # Fallback for systems without signal support (like Windows)
                        try:
                            service = build('calendar', 'v3', credentials=creds)
                            # Try to access calendar to verify permissions
                            calendar_info = service.calendars().get(calendarId='primary').execute()
                            self.google_service = service
                            self.auth_status = "authorized"
                            
                            # Get user info to verify it's the right account
                            user_info = service.calendars().get(calendarId='primary').execute()
                            print(f"✅ DEBUG: Connected to calendar for account: {user_info.get('id', 'unknown')}")
                            
                            return True, "✅ Google Calendar access confirmed"
                        except Exception as e:
                            if "invalid_grant" in str(e) or "token_expired" in str(e):
                                return False, "🔄 Google Calendar token expired. Please re-authenticate."
                            else:
                                return False, f"❌ Google Calendar access error: {str(e)}"
                elif creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open('token.pickle', 'wb') as token:
                            pickle.dump(creds, token)
                        service = build('calendar', 'v3', credentials=creds)
                        self.google_service = service
                        self.auth_status = "authorized"
                        return True, "✅ Google Calendar access restored"
                    except Exception as e:
                        return False, "🔄 Google Calendar token refresh failed. Please re-authenticate."
                else:
                    return False, "🔐 Google Calendar authentication required"
            else:
                return False, "🔐 Google Calendar authentication required"
                
        except Exception as e:
            return False, f"❌ Google Calendar setup error: {str(e)}"
    
    def setup_google_calendar(self, credentials_path: str = "credentials.json") -> Tuple[bool, str]:
        """
        Setup Google Calendar integration with user-friendly messaging.
        Uses a callback approach that works with Streamlit.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            if not os.path.exists(credentials_path):
                return False, (
                    "📋 Google Calendar setup required!\n\n"
                    "To use Google Calendar integration:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a project and enable Google Calendar API\n"
                    "3. Create OAuth 2.0 credentials (Desktop application)\n"
                    "4. Download the JSON file and rename it to 'credentials.json'\n"
                    "5. Place it in your project root directory\n\n"
                    "See CALENDAR_SETUP.md for detailed instructions."
                )
            
            print("🔐 Checking existing credentials...")
            creds = None
            # The file token.pickle stores the user's access and refresh tokens
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            # If there are no (valid) credentials available, let the user log in
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        print("🔄 Refreshing expired token...")
                        creds.refresh(Request())
                    except Exception:
                        # Refresh failed, need new authentication
                        print("❌ Token refresh failed, need new authentication")
                        creds = None
                
                if not creds:
                    print("🔐 No valid credentials found, starting OAuth flow...")
                    # Load credentials and determine client type
                    with open(credentials_path, 'r') as f:
                        cred_data = json.load(f)
                    
                    # Check if it's web or desktop client
                    if 'web' in cred_data:
                        # Web client - use callback approach
                        client_config = cred_data['web']
                        print("🌐 Using web OAuth client with callback...")
                        
                        # Use a simple callback server approach
                        success, message = self._handle_web_oauth_flow(cred_data)
                        if not success:
                            return False, message
                        
                        # The OAuth flow should have created the credentials
                        if os.path.exists('token.pickle'):
                            with open('token.pickle', 'rb') as token:
                                creds = pickle.load(token)
                        else:
                            return False, "OAuth flow completed but no credentials were saved"
                            
                    elif 'installed' in cred_data:
                        # Desktop client
                        print("🖥️ Using desktop OAuth client...")
                        print("🔐 Opening browser for OAuth authentication...")
                        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                        creds = flow.run_local_server(port=0)
                        print("✅ OAuth authentication completed!")
                    else:
                        return False, "❌ Invalid credentials.json format. Please download OAuth 2.0 credentials for Desktop application."
                
                # Save the credentials for the next run
                print("💾 Saving authentication credentials...")
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            print("🔗 Building Google Calendar service...")
            self.google_service = build('calendar', 'v3', credentials=creds)
            self.auth_status = "authorized"
            print("✅ Google Calendar setup completed successfully!")
            return True, "✅ Google Calendar successfully connected!"
            
        except Exception as e:
            print(f"❌ Google Calendar setup failed: {str(e)}")
            self.auth_status = "unauthorized"
            return False, f"❌ Google Calendar setup failed: {str(e)}"
    
    def _handle_web_oauth_flow(self, cred_data: dict) -> Tuple[bool, str]:
        """
        Handle web OAuth flow with callback to Streamlit app.
        
        Args:
            cred_data: The credentials data from credentials.json
            
        Returns:
            Tuple of (success, message)
        """
        try:
            import queue
            auth_code_queue = queue.Queue()
            
            # Start a simple callback server on a different port
            callback_port = 8080
            server = None
            
            try:
                # Create a custom handler class with the queue
                class CustomOAuthHandler(OAuthCallbackHandler):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, auth_code_queue=auth_code_queue, **kwargs)
                
                # Start the callback server
                server = HTTPServer(('localhost', callback_port), CustomOAuthHandler)
                server_thread = threading.Thread(target=server.serve_forever)
                server_thread.daemon = True
                server_thread.start()
                
                print(f"🔐 OAuth callback server started on port {callback_port}")
                
                # Create the OAuth flow
                flow = InstalledAppFlow.from_client_config(
                    cred_data, 
                    SCOPES,
                    redirect_uri=f'http://localhost:{callback_port}'
                )
                
                # Get the authorization URL
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                print("🔐 Opening browser for OAuth authentication...")
                print(f"   Authorization URL: {auth_url}")
                
                # Open the browser
                webbrowser.open(auth_url)
                
                # Wait for the authorization code (with timeout)
                print("⏳ Waiting for OAuth callback...")
                try:
                    auth_code = auth_code_queue.get(timeout=300)  # 5 minute timeout
                    
                    # Exchange the authorization code for credentials
                    flow.fetch_token(code=auth_code)
                    creds = flow.credentials
                    
                    # Save the credentials
                    with open('token.pickle', 'wb') as token:
                        pickle.dump(creds, token)
                    
                    print("✅ OAuth flow completed successfully!")
                    return True, "OAuth authentication successful"
                    
                except queue.Empty:
                    return False, "OAuth timeout - no response received within 5 minutes"
                    
            finally:
                # Clean up the server
                if server:
                    server.shutdown()
                    server.server_close()
                    
        except Exception as e:
            print(f"❌ Web OAuth flow error: {e}")
            return False, f"OAuth flow error: {str(e)}"
    
    def clear_cached_status(self):
        """Clear cached authentication status to force a fresh check"""
        self.auth_status = "not_checked"
        self.google_service = None
    
    def force_clear_authentication(self):
        """Force clear all saved authentication to ensure fresh OAuth"""
        print("🔐 DEBUG: Force clearing all authentication...")
        self.auth_status = "not_checked"
        self.google_service = None
        
        # Remove saved token file
        if os.path.exists('token.pickle'):
            try:
                os.remove('token.pickle')
                print("✅ DEBUG: Removed token.pickle file")
            except Exception as e:
                print(f"❌ DEBUG: Error removing token.pickle: {e}")
        
        # Clear any other cached data
        try:
            import tempfile
            import glob
            # Clear any cached credentials in temp directories
            for temp_dir in [tempfile.gettempdir(), os.path.expanduser('~/.cache')]:
                if os.path.exists(temp_dir):
                    for file in glob.glob(os.path.join(temp_dir, '*google*')):
                        try:
                            os.remove(file)
                            print(f"✅ DEBUG: Removed cached file: {file}")
                        except:
                            pass
        except Exception as e:
            print(f"❌ DEBUG: Error clearing cache: {e}")
        
        print("✅ DEBUG: Authentication cleared successfully")
    
    def get_google_auth_prompt(self) -> str:
        """
        Get a user-friendly prompt for Google Calendar authentication.
        
        Returns:
            String with authentication instructions
        """
        has_access, status = self.check_google_calendar_access()
        
        if has_access:
            return "✅ Google Calendar is ready to use!"
        
        if "setup required" in status.lower():
            return (
                "🔧 **Google Calendar Setup Required**\n\n"
                "To add events to your Google Calendar:\n\n"
                "1. **Download credentials**: Go to [Google Cloud Console](https://console.cloud.google.com/)\n"
                "2. **Create project**: Create a new project or select existing\n"
                "3. **Enable API**: Go to APIs & Services > Library > Search 'Google Calendar API' > Enable\n"
                "4. **Create credentials**: Go to APIs & Services > Credentials > Create Credentials > OAuth 2.0 Client IDs\n"
                "5. **Download file**: Choose 'Desktop application', download JSON file\n"
                "6. **Rename file**: Rename to 'credentials.json' and place in project root\n\n"
                "Once you have credentials.json, try adding events again!"
            )
        
        if "authentication required" in status.lower():
            return (
                "🔐 **Google Calendar Authentication Required**\n\n"
                "Click the button below to grant calendar access:\n\n"
                "This will open your browser to sign in with Google and grant calendar permissions."
            )
        
        return f"❌ **Google Calendar Issue**: {status}"
    
    def add_event_to_google_calendar(self, event_data: Dict) -> bool:
        """
        Add event to Google Calendar.
        
        Args:
            event_data: Dictionary containing event information
                - name: Event name
                - start_date: Start date (YYYY-MM-DD format)
                - start_time: Start time (HH:MM format, optional)
                - venue: Venue name
                - description: Event description (optional)
        """
        if not self.google_service:
            print("Google Calendar not set up. Please run setup_google_calendar() first.")
            return False
        
        try:
            # Parse date and time
            start_date = event_data.get('start_date', '')
            start_time = event_data.get('start_time', '00:00')
            
            # Create datetime object
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = start_datetime + timedelta(hours=2)  # Default 2-hour duration
            
            event = {
                'summary': event_data.get('name', 'Event'),
                'location': event_data.get('venue', ''),
                'description': event_data.get('description', ''),
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Pacific/Honolulu',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Pacific/Honolulu',
                },
            }
            
            event = self.google_service.events().insert(calendarId='primary', body=event).execute()
            print(f"Event created: {event.get('htmlLink')}")
            return True
            
        except Exception as e:
            print(f"Error adding event to Google Calendar: {e}")
            return False
    
    def create_ical_file(self, events: List[Dict], filename: str = "events.ics") -> str:
        """
        Create an iCal file for events that can be imported into any calendar.
        
        Args:
            events: List of event dictionaries
            filename: Output filename for the .ics file
        
        Returns:
            Path to the created .ics file
        """
        try:
            ical_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Hawaii Business Assistant//Calendar Events//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
"""
            
            for i, event_data in enumerate(events):
                # Parse event data
                event_name = event_data.get('name', 'Event')
                start_date = event_data.get('start_date', '')
                start_time = event_data.get('start_time', '00:00')
                venue = event_data.get('venue', '')
                description = event_data.get('description', '')
                
                # Create datetime
                start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                end_datetime = start_datetime + timedelta(hours=2)
                
                # Format for iCal
                start_str = start_datetime.strftime("%Y%m%dT%H%M%S")
                end_str = end_datetime.strftime("%Y%m%dT%H%M%S")
                
                ical_content += f"""BEGIN:VEVENT
UID:event_{i}_{start_str}@hawaiibusinessassistant.com
DTSTAMP:{datetime.now().strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start_str}
DTEND:{end_str}
SUMMARY:{event_name}
LOCATION:{venue}
DESCRIPTION:{description}
END:VEVENT
"""
            
            ical_content += "END:VCALENDAR"
            
            # Write to file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(ical_content)
            
            return os.path.abspath(filename)
            
        except Exception as e:
            print(f"Error creating iCal file: {e}")
            return ""
    
    def parse_event_string(self, event_string: str) -> Dict:
        """
        Parse event string from the format: "Event Name - YYYY-MM-DD at Venue"
        
        Args:
            event_string: Event string in the format returned by search_ticketmaster_events
        
        Returns:
            Dictionary with parsed event data
        """
        try:
            # Split by " - " to separate name from date/venue
            parts = event_string.split(" - ")
            if len(parts) < 2:
                return {}
            
            name = parts[0].strip()
            date_venue_part = parts[1].strip()
            
            # Split by " at " to separate date from venue
            date_venue_parts = date_venue_part.split(" at ")
            if len(date_venue_parts) < 2:
                return {}
            
            date_str = date_venue_parts[0].strip()
            venue = date_venue_parts[1].strip()
            
            # Parse date (assuming format YYYY-MM-DD)
            try:
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                return {
                    'name': name,
                    'start_date': date_str,
                    'start_time': '19:00',  # Default time
                    'venue': venue,
                    'description': f'Event: {name} at {venue}'
                }
            except ValueError:
                print(f"Could not parse date: {date_str}")
                return {}
                
        except Exception as e:
            print(f"Error parsing event string: {e}")
            return {}
    
    def add_events_to_calendar(self, event_strings: List[str], calendar_type: str = "ical") -> str:
        """
        Add multiple events to calendar.
        
        Args:
            event_strings: List of event strings from search_ticketmaster_events
            calendar_type: Type of calendar ("google", "outlook", "ical")
        
        Returns:
            Success message or error message
        """
        try:
            # Parse events
            events = []
            for event_string in event_strings:
                if event_string != "No Ticketmaster events found.":
                    event_data = self.parse_event_string(event_string)
                    if event_data:
                        events.append(event_data)
            
            if not events:
                return "No valid events found to add to calendar."
            
            # Add to calendar based on type
            if calendar_type.lower() == "google":
                if not self.google_service:
                    success, message = self.setup_google_calendar()
                    if not success:
                        return message
                
                success_count = 0
                for event in events:
                    if self.add_event_to_google_calendar(event):
                        success_count += 1
                
                return f"Successfully added {success_count} out of {len(events)} events to Google Calendar."
            
            elif calendar_type.lower() == "ical":
                filename = self.create_ical_file(events)
                if filename:
                    return f"Successfully created iCal file: {filename}. You can import this file into any calendar application."
                else:
                    return "Failed to create iCal file."
            
            else:
                return f"Unsupported calendar type: {calendar_type}. Supported types: google, ical"
                
        except Exception as e:
            return f"Error adding events to calendar: {e}"

    def get_calendar_status_summary(self) -> str:
        """
        Get a summary of the current calendar integration status.
        
        Returns:
            String with current status and next steps
        """
        has_access, status = self.check_google_calendar_access()
        
        if has_access:
            return "✅ **Google Calendar**: Connected and ready to use"
        
        if "setup required" in status.lower():
            return "🔧 **Google Calendar**: Setup required - download credentials.json"
        elif "authentication required" in status.lower():
            return "🔐 **Google Calendar**: Authentication required - click 'Grant Access'"
        elif "token expired" in status.lower():
            return "🔄 **Google Calendar**: Token expired - click 'Grant Access' to refresh"
        else:
            return f"❌ **Google Calendar**: {status}"

    def initiate_oauth_flow(self) -> Tuple[bool, str]:
        """
        Initiate the OAuth flow for Google Calendar access.
        This should be called when user clicks the "Grant Calendar Access" button.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            print("🔐 DEBUG: Starting initiate_oauth_flow...")
            
            # Force clear any existing authentication to ensure fresh OAuth
            self.force_clear_authentication()
            
            # Check if credentials file exists first
            if not os.path.exists('credentials.json'):
                print("❌ DEBUG: credentials.json not found")
                return False, (
                    "❌ **Credentials file not found**\n\n"
                    "Please download your Google Calendar credentials first:\n\n"
                    "1. Go to [Google Cloud Console](https://console.cloud.google.com/)\n"
                    "2. Create a project and enable Google Calendar API\n"
                    "3. Create OAuth 2.0 credentials (Desktop application)\n"
                    "4. Download the JSON file and rename it to 'credentials.json'\n"
                    "5. Place it in your project root directory\n\n"
                    "See CALENDAR_SETUP.md for detailed instructions."
                )
            
            print("✅ DEBUG: credentials.json found")
            print("🔐 Starting simplified OAuth flow...")
            
            # Load credentials
            with open('credentials.json', 'r') as f:
                cred_data = json.load(f)
            
            print(f"🔐 DEBUG: Credential type: {'web' if 'web' in cred_data else 'installed' if 'installed' in cred_data else 'unknown'}")
            
            # Check if it's web or desktop client
            if 'web' in cred_data:
                # Web client - use callback approach
                print("🌐 Using web OAuth client with callback...")
                success, message = self._handle_web_oauth_flow(cred_data)
                if success:
                    print("✅ OAuth flow completed successfully")
                    return True, (
                        "✅ **Google Calendar Connected Successfully!**\n\n"
                        "🎉 Your Google Calendar is now ready to use!\n\n"
                        "**What happens next:**\n"
                        "• The browser window should close automatically\n"
                        "• You can now add events to your Google Calendar\n"
                        "• Events will be automatically synced to your calendar\n\n"
                        "**If the browser window doesn't close:**\n"
                        "• Simply close it manually and return to the chatbot\n"
                        "• Your authentication is still valid\n\n"
                        "You're all set! 🚀"
                    )
                else:
                    print(f"❌ OAuth flow failed: {message}")
                    return False, message
                    
            elif 'installed' in cred_data:
                # Desktop client - direct browser opening
                print("🖥️ Using desktop OAuth client...")
                print("🔐 Opening browser for OAuth authentication...")
                
                try:
                    print("🔐 DEBUG: Creating InstalledAppFlow...")
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    print("🔐 DEBUG: InstalledAppFlow created successfully")
                    
                    print("🔐 DEBUG: About to call run_local_server...")
                    creds = flow.run_local_server(port=0)
                    print("🔐 DEBUG: run_local_server completed successfully")
                    
                    # Save the credentials
                    print("🔐 DEBUG: Saving credentials...")
                    with open('token.pickle', 'wb') as token:
                        pickle.dump(creds, token)
                    
                    # Build the service
                    print("🔐 DEBUG: Building Google Calendar service...")
                    self.google_service = build('calendar', 'v3', credentials=creds)
                    self.auth_status = "authorized"
                    
                    print("✅ OAuth authentication completed!")
                    return True, (
                        "✅ **Google Calendar Connected Successfully!**\n\n"
                        "🎉 Your Google Calendar is now ready to use!\n\n"
                        "**What happens next:**\n"
                        "• The browser window should close automatically\n"
                        "• You can now add events to your Google Calendar\n"
                        "• Events will be automatically synced to your calendar\n\n"
                        "**If the browser window doesn't close:**\n"
                        "• Simply close it manually and return to the chatbot\n"
                        "• Your authentication is still valid\n\n"
                        "You're all set! 🚀"
                    )
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f"❌ Desktop OAuth exception: {error_msg}")
                    print(f"❌ DEBUG: Exception type: {type(e)}")
                    import traceback
                    print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
                    if "redirect_uri_mismatch" in error_msg:
                        return False, (
                            "❌ **OAuth Configuration Error**\n\n"
                            "The redirect URI doesn't match your OAuth client configuration.\n\n"
                            "**Quick Fix:**\n"
                            "1. Go to Google Cloud Console > APIs & Services > Credentials\n"
                            "2. Edit your OAuth 2.0 Client ID\n"
                            "3. Add this redirect URI: http://localhost:8080\n"
                            "4. Save and try again\n\n"
                            "**Alternative:** Wait 2-3 minutes for Google Cloud changes to apply, then try again."
                        )
                    else:
                        return False, f"❌ **OAuth Error**: {error_msg}"
            else:
                print("❌ DEBUG: Invalid credentials.json format")
                return False, "❌ Invalid credentials.json format. Please download OAuth 2.0 credentials for Desktop application."
                
        except Exception as e:
            print(f"❌ OAuth flow failed: {str(e)}")
            import traceback
            print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
            return False, f"❌ OAuth flow failed: {str(e)}"

# Global instance
calendar_integration = CalendarIntegration() 