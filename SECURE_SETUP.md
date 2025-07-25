# Secure Google OAuth Setup

This application now uses environment variables to securely store Google OAuth credentials instead of hardcoding them in the source code.

## 🔐 Security Features

- **Environment Variables**: All sensitive credentials are stored in `.env` file
- **Auto-Generation**: `credentials.json` is automatically generated from environment variables
- **Git Protection**: `credentials.json` and `.env` are excluded from version control
- **No Hardcoded Secrets**: No sensitive data in source code

## 📋 Setup Instructions

### 1. Environment Variables Setup

Add your Google OAuth credentials to the `.env` file:

```env
# Google OAuth Credentials
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_PROJECT_ID=your_project_id_here
GOOGLE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
GOOGLE_CLIENT_SECRET=your_client_secret_here
```

### 2. Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable Google Calendar API
4. Go to APIs & Services > Credentials
5. Create OAuth 2.0 Client ID (Web application)
6. Copy the credentials to your `.env` file

### 3.  `credentials.json` 
### 🛠️ Manual Commands

### Generate credentials.json manually:
```bash
python generate_credentials.py
```

### Regenerate from environment variables:
```bash
python -c "from calendar_integration import generate_credentials_from_env; generate_credentials_from_env()"
```

## ✅ Verification

To verify the setup is working:

1. Check that `.env` contains your credentials
2. Click "🔧 Regenerate Credentials" in the app
3. Click "🔑 Test Credentials" to verify
4. Try the OAuth flow to ensure it works 