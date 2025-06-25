#!/bin/bash

# Deployment preparation script for Streamlit Cloud
# This script helps prepare your repository for deployment

echo "🚀 Preparing Chat-Gidens for Streamlit Cloud deployment"
echo "======================================================"

# Check if we're in a git repository
if [[ ! -d ".git" ]]; then
    echo "❌ Error: Not in a git repository"
    echo "Please run this script from the root of your Chat-Gidens repository"
    exit 1
fi

# Check if .env file exists and warn about it
if [[ -f ".env" ]]; then
    echo "⚠️  Warning: .env file found"
    echo "   Remember: .env files don't work on Streamlit Cloud"
    echo "   You'll need to configure secrets in the Streamlit Cloud dashboard"
    echo ""
fi

# Check if requirements.txt exists
if [[ ! -f "requirements.txt" ]]; then
    echo "❌ Error: requirements.txt not found"
    echo "Please ensure you have a requirements.txt file"
    exit 1
fi

# Check if app.py exists
if [[ ! -f "app.py" ]]; then
    echo "❌ Error: app.py not found"
    echo "Please ensure you have an app.py file"
    exit 1
fi

# Check if .streamlit/config.toml exists
if [[ ! -f ".streamlit/config.toml" ]]; then
    echo "⚠️  Warning: .streamlit/config.toml not found"
    echo "   Creating basic Streamlit configuration..."
    mkdir -p .streamlit
    cat > .streamlit/config.toml << EOF
[global]
# Streamlit Cloud configuration

[server]
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
EOF
    echo "✅ Created .streamlit/config.toml"
fi

echo ""
echo "📋 Pre-deployment checklist:"
echo ""

# Check for common issues
issues_found=false

# Check for problematic packages in requirements.txt
if grep -q "sentencepiece\|torch\|faiss-cpu" requirements.txt; then
    echo "❌ requirements.txt contains packages that may cause issues on Streamlit Cloud:"
    grep -E "sentencepiece|torch|faiss-cpu" requirements.txt
    echo "   Consider using requirements-python313.txt instead"
    issues_found=true
fi

# Check for hardcoded file paths
if grep -r "\.env\|/home\|/Users" app.py utils/ 2>/dev/null; then
    echo "❌ Found hardcoded file paths that may not work on Streamlit Cloud"
    issues_found=true
fi

# Check for missing imports
echo "🔍 Checking for potential import issues..."
python3 -c "
import sys
try:
    import streamlit
    print('✅ streamlit')
except ImportError:
    print('❌ streamlit not found')

try:
    import langchain
    print('✅ langchain')
except ImportError:
    print('❌ langchain not found')

try:
    import openai
    print('✅ openai')
except ImportError:
    print('❌ openai not found')

try:
    import PyPDF2
    print('✅ PyPDF2')
except ImportError:
    print('❌ PyPDF2 not found')

try:
    import chromadb
    print('✅ chromadb')
except ImportError:
    print('❌ chromadb not found')
" 2>/dev/null

echo ""
echo "📝 Next steps for deployment:"
echo ""

if [[ "$issues_found" == true ]]; then
    echo "⚠️  Issues found. Please fix them before deploying:"
    echo "   1. Review the issues above"
    echo "   2. Update requirements.txt if needed"
    echo "   3. Fix any hardcoded paths"
    echo ""
fi

echo "🚀 To deploy to Streamlit Cloud:"
echo "   1. Push your code to GitHub:"
echo "      git add ."
echo "      git commit -m 'Prepare for Streamlit Cloud deployment'"
echo "      git push origin main"
echo ""
echo "   2. Go to https://share.streamlit.io"
echo "   3. Connect your GitHub account"
echo "   4. Create a new app and select this repository"
echo "   5. Set main file path to: app.py"
echo "   6. Configure secrets in the app settings"
echo ""
echo "📖 For detailed instructions, see: STREAMLIT_CLOUD_DEPLOYMENT.md"
echo ""
echo "🔧 Required secrets to configure in Streamlit Cloud:"
echo "   - OPENAI_API_KEY"
echo "   - GOOGLE_CLIENT_ID"
echo "   - GOOGLE_CLIENT_SECRET"
echo "   - GOOGLE_PROJECT_ID"
echo "   - GOOGLE_AUTH_URI"
echo "   - GOOGLE_TOKEN_URI"
echo "   - GOOGLE_AUTH_PROVIDER_X509_CERT_URL"
echo ""
echo "✅ Repository preparation complete!" 