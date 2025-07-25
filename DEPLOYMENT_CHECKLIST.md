# Streamlit Cloud Deployment Checklist

Use this checklist to ensure your Chat-Gidens app deploys successfully on Streamlit Cloud.

## ✅ Pre-Deployment Checklist

### Repository Setup
- [ ] Repository is on GitHub
- [ ] `app.py` exists in the root directory
- [ ] `requirements.txt` exists and is cloud-compatible
- [ ] No `.env` files in the repository (they're in `.gitignore`)
- [ ] `.streamlit/config.toml` exists for cloud configuration

### Requirements File
- [ ] `requirements.txt` contains only cloud-compatible packages
- [ ] No `sentencepiece`, `torch`, `faiss-cpu`, or `sentence-transformers`
- [ ] Uses `chromadb` instead of `faiss-cpu`
- [ ] All core dependencies are included

### Code Compatibility
- [ ] No hardcoded file paths (use relative paths or `/tmp`)
- [ ] No `.env` file reading (use `st.secrets` instead)
- [ ] All imports are available in `requirements.txt`
- [ ] No system-specific dependencies

### Google OAuth Setup
- [ ] Google Cloud project created
- [ ] Google Calendar API enabled
- [ ] OAuth 2.0 credentials created
- [ ] Redirect URIs include your Streamlit Cloud URL:
  - `https://your-app-name-your-username.streamlit.app/`
  - `https://your-app-name-your-username.streamlit.app/_stcore/authorize`
  - `https://your-app-name-your-username.streamlit.app/streamlit_oauth_callback`

## 🚀 Deployment Steps

### 1. Push to GitHub
```bash
git add .
git commit -m "Prepare for Streamlit Cloud deployment"
git push origin main
```

### 2. Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click "New app"
4. Select your repository
5. Set main file path: `app.py`
6. Click "Deploy!"

### 3. Configure Secrets
In your app settings, add these secrets:

```toml
[secrets]
OPENAI_API_KEY = "your_openai_api_key_here"
# Google OAuth Credentials
GOOGLE_CLIENT_ID = "your_google_client_id_here"
GOOGLE_PROJECT_ID = "your_google_project_id_here"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_PROVIDER_X509_CERT_URL = "https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_CLIENT_SECRET = "your_google_client_secret_here"
```