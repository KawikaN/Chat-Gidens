# Calendar Integration Setup Guide

This guide will help you set up calendar integration for the Hawaii Business Assistant chatbot to add events to your calendar.

## Overview

The calendar integration supports multiple calendar services:
- **Google Calendar** (requires setup)
- **iCal Export** (no setup required, generates .ics files)

## Option 1: Google Calendar Integration (Recommended)

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click on it and press "Enable"

### Step 2: Create OAuth 2.0 Credentials

**Important**: Choose the correct application type!

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. **Choose "Desktop application"** (recommended) or "Web application"
4. Give it a name (e.g., "Hawaii Business Assistant")
5. Click "Create"
6. Download the JSON file and rename it to `credentials.json`
7. Place `credentials.json` in the root directory of your project

### Step 3: First Time Authentication

When you first run the application and try to add events to Google Calendar:
1. A browser window will open
2. Sign in with your Google account
3. Grant permission to access your calendar
4. The application will save the authentication token for future use

## Troubleshooting OAuth Issues

### Error: "redirect_uri_mismatch"

If you see this error, it means your OAuth client is configured for different redirect URIs than what the application is using.

**For Web Application clients:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to: APIs & Services > Credentials
3. Find your OAuth 2.0 Client ID and click "Edit"
4. In the "Authorized redirect URIs" section, add:
   - `http://localhost:8080`
   - `http://localhost:8090`
   - `http://localhost:9000`
   - `http://localhost:9090`
5. Click "Save"
6. Try the OAuth flow again

**For Desktop Application clients:**
- This error shouldn't occur with desktop clients
- If it does, try deleting `token.pickle` and re-authenticating

### Quick Fix Script

Run the diagnostic script to check your configuration:
```bash
python fix_oauth_config.py
```

This will:
- Check your credentials.json file
- Identify the client type (web vs desktop)
- Provide specific instructions for fixing issues
- Guide you through creating new credentials if needed

## Option 2: iCal Export (No Setup Required)

The iCal export feature works out of the box and generates `.ics` files that can be imported into:
- Google Calendar
- Apple Calendar
- Outlook
- Any calendar application that supports iCal format

## How It Works

1. When the chatbot finds events and you agree to add them to your calendar
2. The system will **always try Google Calendar OAuth first**
3. If OAuth succeeds, events are added directly to your Google Calendar
4. If OAuth fails, events are automatically saved as downloadable iCal files
5. No user choice needed - automatic fallback

## File Structure

```
your-project/
├── app.py
├── calendar_integration.py
├── events.py
├── credentials.json          # Google Calendar credentials (if using Google)
├── token.pickle             # Google auth token (auto-generated)
├── events.ics               # iCal file (auto-generated when using iCal)
├── fix_oauth_config.py      # OAuth diagnostic script
└── CALENDAR_SETUP.md        # This file
```

## Troubleshooting

### Google Calendar Issues

1. **"credentials.json not found"**
   - Make sure you downloaded the credentials file from Google Cloud Console
   - Ensure it's named exactly `credentials.json`
   - Place it in the project root directory

2. **"redirect_uri_mismatch" error**
   - Run `python fix_oauth_config.py` for specific instructions
   - Add the required redirect URIs to your OAuth client
   - Or create new desktop application credentials

3. **Authentication errors**
   - Delete `token.pickle` file and try again
   - Make sure you're using the correct Google account
   - Check that the Google Calendar API is enabled

4. **Permission denied**
   - Ensure you granted calendar access during authentication
   - Check that your Google account has calendar permissions

### iCal Issues

1. **File not created**
   - Check that the application has write permissions in the directory
   - Ensure events are being found and parsed correctly

2. **Import issues**
   - Verify the .ics file is not corrupted
   - Try importing into a different calendar application

## Security Notes

- Keep your `credentials.json` file secure and don't share it
- The `token.pickle` file contains your authentication tokens
- Consider adding these files to your `.gitignore` if using version control

## Example Usage

Once set up, the calendar integration works automatically:

1. Ask the chatbot about events: "What events are happening in Hawaii?"
2. The chatbot will search for events and display them
3. When asked if you want to add events to your calendar, say "Yes"
4. The system will automatically try Google Calendar OAuth first
5. If OAuth succeeds, events are added to your Google Calendar
6. If OAuth fails, events are saved as downloadable iCal files

## Support

If you encounter issues:
1. Run `python fix_oauth_config.py` to diagnose OAuth issues
2. Check the console output for error messages
3. Verify your setup follows this guide
4. Ensure all dependencies are installed: `pip install -r requirements.txt` 