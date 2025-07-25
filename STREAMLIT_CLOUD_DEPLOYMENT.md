# Streamlit Cloud Deployment Guide

This guide will help you deploy Chat-Gidens to Streamlit Cloud (streamlit.io) successfully.

## 🚀 Quick Deployment Steps

### 1. Prepare Your Repository

Ensure your repository has the following structure:
```
Chat-Gidens/
├── app.py                      # Main application file
├── requirements.txt            # Dependencies (cloud-optimized)
├── .streamlit/
│   └── config.toml            # Streamlit configuration
├── utils/                      # Utility modules
│   ├── __init__.py
│   ├── pdf_processor.py
│   └── calendar_utils.py
├── .env.example               # Example environment variables
└── README.md                  # Documentation
```

### 2. Set Up Environment Variables on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub repository
3. In the app settings, add these secrets:

```toml
# Add these in Streamlit Cloud's "Secrets" section
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

### 3. Configure Google OAuth for Cloud Deployment

**Important**: Update your Google OAuth redirect URIs to include your Streamlit Cloud URL:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to "APIs & Services" > "Credentials"
3. Edit your OAuth 2.0 Client ID
4. Add these authorized redirect URIs:
   - `https://your-app-name-your-username.streamlit.app/`
   - `https://your-app-name-your-username.streamlit.app/_stcore/authorize`
   - `https://your-app-name-your-username.streamlit.app/streamlit_oauth_callback`

**Replace `your-app-name-your-username` with your actual Streamlit Cloud app URL.**

### 4. Deploy to Streamlit Cloud

1. **Push your code to GitHub**
   ```bash
   git add .
   git commit -m "Prepare for Streamlit Cloud deployment"
   git push origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Set main file path: `app.py`
   - Click "Deploy!"

## 🔧 Streamlit Cloud Specific Configurations

### Environment Variables vs Secrets

Streamlit Cloud uses a different system for environment variables:

**❌ Don't use `.env` files** - they won't work on Streamlit Cloud
**✅ Use Streamlit Secrets** - add them in the app settings

### File System Limitations

Streamlit Cloud has a read-only file system except for `/tmp`:

- **✅ Use `/tmp` for temporary files**
- **❌ Don't write to other directories**
- **✅ Use in-memory storage when possible**

### Memory and CPU Limits

Streamlit Cloud has resource limits:
- **Memory**: ~1GB RAM
- **CPU**: Limited processing power
- **Storage**: Read-only file system

## 🛠️ Troubleshooting Common Issues

### Issue: "Module not found" errors
**Solution**: Ensure all dependencies are in `requirements.txt`

### Issue: Google OAuth not working
**Solution**: 
1. Check redirect URIs in Google Cloud Console
2. Verify secrets are set correctly in Streamlit Cloud
3. Use HTTPS URLs only

### Issue: App crashes on startup
**Solution**:
1. Check the logs in Streamlit Cloud dashboard
2. Ensure all imports are available in `requirements.txt`
3. Test locally first with `streamlit run app.py`

### Issue: PDF processing fails
**Solution**:
1. Ensure PyPDF2 is in requirements.txt
2. Check file size limits (recommend < 10MB per file)
3. Use in-memory processing

### Issue: Vector database errors
**Solution**:
1. ChromaDB is configured for in-memory storage
2. No persistent storage on Streamlit Cloud
3. Data will be lost between sessions

## 📋 Pre-Deployment Checklist

- [ ] All dependencies in `requirements.txt`
- [ ] No `.env` files in repository
- [ ] Google OAuth redirect URIs updated
- [ ] Streamlit secrets configured
- [ ] App tested locally
- [ ] No hardcoded file paths
- [ ] All imports working
- [ ] Memory usage optimized

## 🔒 Security Considerations

### API Keys
- ✅ Store in Streamlit secrets
- ❌ Never commit to repository
- ✅ Use environment-specific keys

### OAuth Configuration
- ✅ Use HTTPS redirect URIs only
- ✅ Configure proper scopes
- ✅ Set appropriate expiration times

### Data Privacy
- ✅ No sensitive data in logs
- ✅ Temporary file cleanup
- ✅ Secure session handling

## 📊 Monitoring and Maintenance

### Logs
- Check Streamlit Cloud dashboard for logs
- Monitor for errors and performance issues
- Set up alerts for critical failures

### Updates
- Regularly update dependencies
- Monitor for security patches
- Test updates locally before deploying

### Performance
- Monitor memory usage
- Optimize for cloud constraints
- Use caching where appropriate

## 🆘 Getting Help

If you encounter issues:

1. **Check Streamlit Cloud logs** in the dashboard
2. **Test locally** with `streamlit run app.py`
3. **Verify secrets** are set correctly
4. **Check Google OAuth** configuration
5. **Review this guide** for common solutions

## 📞 Support Resources

- [Streamlit Cloud Documentation](https://docs.streamlit.io/streamlit-community-cloud)
- [Streamlit Community Forum](https://discuss.streamlit.io/)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [LangChain Documentation](https://python.langchain.com/)

---

**Note**: This deployment guide is specifically optimized for Streamlit Cloud. For other hosting platforms, refer to their respective documentation. 