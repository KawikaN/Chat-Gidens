# Chat-Gidens: Google Calendar Integration Assistant

A powerful chatbot application that integrates with Google Calendar for enhanced productivity and event management.

## Features

- **Google Calendar Integration**: View, create, and manage calendar events
- **Advanced Chat Interface**: Interactive chat with AI assistance
- **Secure OAuth Authentication**: Secure Google Calendar access


## Prerequisites

- Python 3.8 or higher (Python 3.13 supported with limitations)
- Google Cloud Platform account
- OpenAI API key
- Ticketmaster Developer account (for event search)

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your credentials:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - Google OAuth credentials (see setup below)

#### Python 3.13 Installation

If you're using Python 3.13, some packages may not have pre-built wheels. Use the Python 3.13 specific requirements:

 **Install Python 3.13 compatible dependencies**
   ```bash
   pip install -r requirements-python313.txt
   ```

## Google OAuth Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

### Step 2: Create OAuth Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client ID"
3. Choose "Web application" as the application type
4. Add authorized redirect URIs:
   - **For local development**: `http://localhost:8501/`
   - **For Streamlit Cloud**: `https://your-app-name-your-username.streamlit.app/`
   - **Additional URIs**: `/_stcore/authorize` and `/streamlit_oauth_callback`
5. Click "Create"
6. Download the JSON file or copy the credentials

### Step 3: Configure Environment Variables

Add the following to your `.env` file (local) or Streamlit secrets (cloud):

```env
GOOGLE_CLIENT_ID="your_client_id_here"
GOOGLE_PROJECT_ID="your_project_id_here"
GOOGLE_AUTH_URI="https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI="https://oauth2.googleapis.com/token"
GOOGLE_AUTH_PROVIDER_X509_CERT_URL="https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_CLIENT_SECRET="your_client_secret_here"
```

## Ticketmaster API Setup

This app integrates with the Ticketmaster Discovery API to allow users to search for live events and activities. To enable this feature:

1. Go to [Ticketmaster Developer Portal](https://developer.ticketmaster.com/)
2. Sign up for a free account and create an application
3. Copy your API key
4. Add the following to your `.env` file:
   ```env
   TICKETMASTER_API_KEY="your_ticketmaster_api_key_here"
   ```

The app will use this key to fetch event data from Ticketmaster. If the key is missing or invalid, event search features will not work.

## Usage

1. **Start the application**
   ```bash
   streamlit run app.py
   ```

2. **Access the application**
   - **Local**: Open your browser and go to `http://localhost:8501`

3. **Chat with AI Assistant**
   - Type your questions in the chat interface
   - The AI will help you with calendar management, event planning, and searching for live events via Ticketmaster
   - Ask questions about your schedule, request help creating events, or search for local activities

## Troubleshooting

### Python 3.13 Issues
- **Package compatibility**: Some advanced features may not be available
- **Missing system dependencies**: Run `./install_system_deps.sh`

### OAuth Issues
- Ensure your redirect URIs are correctly configured in Google Cloud Console
- Check that all environment variables are properly set
- Clear browser cache and cookies if authentication fails
- Try using incognito mode for testing

### API Issues
- Verify your OpenAI API key is valid and has sufficient credits
- Check your internet connection
- Ensure all required packages are installed 