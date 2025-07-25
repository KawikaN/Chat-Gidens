# Chat-Gidens: Google Calendar Integration Assistant

A powerful chatbot application that integrates with Google Calendar for enhanced productivity and event management.

## Features

- **Google Calendar Integration**: View, create, and manage calendar events
- **Advanced Chat Interface**: Interactive chat with AI assistance
- **Secure OAuth Authentication**: Secure Google Calendar access

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd Chat-Gidens
```

### 2. Create and activate a virtual environment (recommended)
```bash
# Using venv (Python 3.3+)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Upgrade pip and install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your API keys (see below for details)
```

### 5. Run the application
```bash
streamlit run app.py
```

---

## Prerequisites

- Python 3.8 or higher (Python 3.13 supported with limitations)
- Google Cloud Platform account
- OpenAI API key
- Ticketmaster Developer account (for event search)

---

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

---

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Calendar API"
   - Click "Enable"
4. Go to "APIs & Services" > "Credentials"
5. Click "Create Credentials" > "OAuth 2.0 Client ID"
6. Choose "Web application" as the application type
7. Add authorized redirect URIs:
   - For local development: `http://localhost:8501/`
   - Additional URIs: `/_stcore/authorize` and `/streamlit_oauth_callback`
8. Click "Create" and copy your credentials
9. Add the following to your `.env` file:
   ```env
   GOOGLE_CLIENT_ID="your_google_client_id_here"
   GOOGLE_PROJECT_ID="your_project_id_here"
   GOOGLE_AUTH_URI="https://accounts.google.com/o/oauth2/auth"
   GOOGLE_TOKEN_URI="https://oauth2.googleapis.com/token"
   GOOGLE_AUTH_PROVIDER_X509_CERT_URL="https://www.googleapis.com/oauth2/v1/certs"
   GOOGLE_CLIENT_SECRET="your_google_client_secret_here"
   ```

---

## Usage

1. **Start the application**
   ```bash
   streamlit run app.py
   ```
2. **Access the application**
   - Local: Open your browser and go to `http://localhost:8501`
3. **Chat with AI Assistant**
   - Type your questions in the chat interface
   - The AI will help you with calendar management, event planning, and searching for live events via Ticketmaster
   - Ask questions about your schedule, request help creating events, or search for local activities

---

## System-Specific Installation Tips

### macOS (Apple Silicon M1/M2)
```bash
# Install Rosetta 2 if needed
softwareupdate --install-rosetta
# Use conda for better compatibility (optional)
conda install -c conda-forge faiss-cpu
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Windows
```bash
# Install Visual C++ Build Tools if needed
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
# Use pre-built wheels when possible
pip install --only-binary=all torch
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install build-essential python3-dev
pip install -r requirements.txt
```

---

## Verification

After installation, verify everything works:

1. **Test core functionality**:
   ```bash
   python -c "import streamlit, langchain, openai; print('✅ Core packages imported successfully')"
   ```
2. **Test Google OAuth**:
   ```bash
   python -c "from calendarTest import get_credentials; print('✅ Google OAuth setup working')"
   ```
3. **Run the app**:
   ```bash
   streamlit run app.py
   ```

---

## Requirements Summary

### Core Requirements
- Python 3.8+
- streamlit
- langchain
- openai
- chromadb (cloud-compatible)
- google-auth packages

### Optional (Local development only)
- torch (for ML models)
- transformers (for text processing)
- **Note**: These are NOT compatible with Streamlit Cloud

---

## Troubleshooting

### Python 3.13 Issues
- Package compatibility: Some advanced features may not be available
- Missing system dependencies: Run `./install_system_deps.sh`

### OAuth Issues
- Ensure your redirect URIs are correctly configured in Google Cloud Console
- Check that all environment variables are properly set
- Clear browser cache and cookies if authentication fails
- Try using incognito mode for testing

### API Issues
- Verify your OpenAI API key is valid and has sufficient credits
- Check your internet connection
- Ensure all required packages are installed

### General Installation Issues
- **sentencepiece/torch/faiss-cpu install fails**: Try pre-built wheels, use conda, or see system-specific tips above
- **App crashes on startup**: Check Streamlit logs, ensure all packages in `requirements.txt` are installed
- **Memory errors**: Optimize for resource limits, avoid large files

---

## Updating

To update the application:
```bash
# Update dependencies
pip install -r requirements.txt --upgrade
# Pull latest code
git pull origin main
```

---

## Common Pitfalls

- Always use a virtual environment (do not install globally)
- Do not mix package managers (use either pip or conda, not both)
- Ensure you're using Python 3.8+
- Always upgrade pip before installing requirements
- Read error messages carefully; most errors have specific solutions
- Optional packages may not work on Streamlit Cloud 