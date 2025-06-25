#!/bin/bash

# Quick start script for Python 3.13 users
# This script helps you get Chat-Gidens running on Python 3.13

echo "🚀 Quick start for Python 3.13 users"
echo "====================================="

# Check Python version
python_version=$(python3 --version 2>&1 | grep -o '3\.13')
if [[ "$python_version" != "3.13" ]]; then
    echo "⚠️  Warning: This script is designed for Python 3.13"
    echo "   Current Python version: $(python3 --version)"
    echo "   Continue anyway? (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing Python 3.13 compatible dependencies..."

# Install core dependencies without problematic packages
pip install streamlit python-dotenv langchain langchain-openai langchain-community openai PyPDF2 chromadb google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client requests aiohttp numpy pandas scikit-learn tqdm rich Pygments markdown-it-py mdurl watchdog

echo "✅ Core dependencies installed successfully!"

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    echo "📝 Setting up environment file..."
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        echo "✅ Created .env file from .env.example"
        echo "⚠️  Please edit .env file with your actual API keys"
    else
        echo "❌ .env.example not found. Please create .env file manually"
    fi
else
    echo "✅ .env file already exists"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run: streamlit run app.py"
echo ""
echo "Note: Some advanced text processing features are disabled for Python 3.13 compatibility"
echo "The core PDF chat and Google Calendar features will work normally." 