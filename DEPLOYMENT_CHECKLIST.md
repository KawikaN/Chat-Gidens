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
HUGGINGFACEHUB_API_TOKEN = "your_huggingface_token_here"

# Google OAuth Credentials
GOOGLE_CLIENT_ID = "your_google_client_id_here"
GOOGLE_PROJECT_ID = "your_google_project_id_here"
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_PROVIDER_X509_CERT_URL = "https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_CLIENT_SECRET = "your_google_client_secret_here"
```

## 🔍 Post-Deployment Verification

### App Functionality
- [ ] App loads without errors
- [ ] PDF upload works
- [ ] Chat interface responds
- [ ] Google Calendar OAuth works
- [ ] No console errors in browser

### Performance
- [ ] App starts within reasonable time
- [ ] No memory errors
- [ ] File uploads work (under 10MB)
- [ ] Chat responses are timely

## 🛠️ Troubleshooting

### Common Issues and Solutions

#### "Module not found" errors
- **Cause**: Missing dependency in `requirements.txt`
- **Solution**: Add missing package to `requirements.txt`

#### Google OAuth not working
- **Cause**: Incorrect redirect URIs or missing secrets
- **Solution**: 
  1. Update redirect URIs in Google Cloud Console
  2. Verify all secrets are set in Streamlit Cloud

#### App crashes on startup
- **Cause**: Incompatible packages or missing dependencies
- **Solution**: 
  1. Check Streamlit Cloud logs
  2. Ensure all packages in `requirements.txt` are cloud-compatible

#### Memory errors
- **Cause**: Large files or inefficient processing
- **Solution**: 
  1. Limit file sizes to < 10MB
  2. Use in-memory processing
  3. Implement caching

## 📊 Monitoring

### Check Logs
- Monitor Streamlit Cloud dashboard for errors
- Check browser console for client-side issues
- Review Google Cloud Console for OAuth issues

### Performance Metrics
- App startup time
- Memory usage
- Response times
- Error rates

## 🔄 Updates and Maintenance

### Regular Tasks
- [ ] Update dependencies monthly
- [ ] Monitor for security patches
- [ ] Test locally before deploying updates
- [ ] Backup configuration and secrets

### Version Control
- [ ] Tag releases
- [ ] Document changes
- [ ] Test in staging environment
- [ ] Rollback plan ready

## 🆘 Emergency Procedures

### If App is Down
1. Check Streamlit Cloud status page
2. Review recent deployment logs
3. Verify secrets are still valid
4. Test locally to isolate issue

### If OAuth is Broken
1. Check Google Cloud Console for credential status
2. Verify redirect URIs are correct
3. Regenerate credentials if needed
4. Update secrets in Streamlit Cloud

### If Dependencies are Outdated
1. Update `requirements.txt` locally
2. Test thoroughly
3. Deploy with new requirements
4. Monitor for compatibility issues

---

**Remember**: Streamlit Cloud has limitations. Always test locally first and keep optional packages separate for local development only. 