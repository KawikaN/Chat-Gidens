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

### 3. Automatic Generation

The application will automatically:
- Generate `credentials.json` from environment variables when needed
- Regenerate credentials if the file is missing
- Handle OAuth flow securely

## 🛠️ Manual Commands

### Generate credentials.json manually:
```bash
python generate_credentials.py
```

### Regenerate from environment variables:
```bash
python -c "from calendar_integration import generate_credentials_from_env; generate_credentials_from_env()"
```

## 🔧 App Features

The application includes several security features:

- **🔧 Regenerate Credentials**: Button to regenerate `credentials.json` from `.env`
- **🗑️ Clear Authentication**: Button to clear saved authentication tokens
- **🔑 Test Credentials**: Button to verify credentials are valid
- **🧪 Test Browser**: Button to test browser opening functionality

## 🚨 Security Notes

- **Never commit `.env` or `credentials.json`** to version control
- **Keep your `.env` file secure** and don't share it
- **Rotate credentials regularly** for production use
- **Use different credentials** for development and production

## 🔄 Migration from Hardcoded Credentials

If you previously had hardcoded credentials:

1. Move your credentials to `.env` file
2. Delete the old `credentials.json` file
3. The app will automatically generate a new one from environment variables
4. Test the OAuth flow to ensure it works

## ✅ Verification

To verify the setup is working:

1. Check that `.env` contains your credentials
2. Click "🔧 Regenerate Credentials" in the app
3. Click "🔑 Test Credentials" to verify
4. Try the OAuth flow to ensure it works 