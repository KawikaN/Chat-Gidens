# Chat-Gidens: Multi-PDF Chatbot with Google Calendar Integration

A powerful chatbot application that can process multiple PDF documents and integrate with Google Calendar for enhanced productivity.

## Features

- **Multi-PDF Processing**: Upload and chat with multiple PDF documents simultaneously
- **Google Calendar Integration**: View, create, and manage calendar events
- **Advanced Chat Interface**: Interactive chat with document context
- **Secure OAuth Authentication**: Secure Google Calendar access
- **Modern UI**: Clean and responsive interface built with Streamlit
- **Cloud Ready**: Optimized for deployment on Streamlit Cloud

## Prerequisites

- Python 3.8 or higher (Python 3.13 supported with limitations)
- Google Cloud Platform account
- OpenAI API key
- Hugging Face API token (optional)

## Quick Start

### 🚀 Deploy to Streamlit Cloud (Recommended)

The easiest way to get started is to deploy directly to Streamlit Cloud:

1. **Fork this repository** to your GitHub account
2. **Go to [share.streamlit.io](https://share.streamlit.io)**
3. **Connect your GitHub account**
4. **Deploy the app** by selecting this repository
5. **Configure secrets** (see deployment guide below)

📖 **Detailed deployment guide**: [STREAMLIT_CLOUD_DEPLOYMENT.md](STREAMLIT_CLOUD_DEPLOYMENT.md)

### 🖥️ Local Installation

#### Standard Installation (Python 3.8-3.12)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Chat-Gidens
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your credentials:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `HUGGINGFACEHUB_API_TOKEN`: Your Hugging Face token (optional)
   - Google OAuth credentials (see setup below)

#### Python 3.13 Installation

If you're using Python 3.13, some packages may not have pre-built wheels. Use the Python 3.13 specific requirements:

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Chat-Gidens
   ```

2. **Install system dependencies** (if needed)
   ```bash
   # On Linux (Ubuntu/Debian)
   sudo apt-get update && sudo apt-get install -y build-essential python3-dev pkg-config cmake
   
   # Or run the automated script
   ./install_system_deps.sh
   ```

3. **Install Python 3.13 compatible dependencies**
   ```bash
   pip install -r requirements-python313.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

**Note**: Python 3.13 installation excludes some advanced text processing packages (`sentencepiece`, `sentence-transformers`, `torch`) due to compatibility issues. The core functionality will work, but with reduced text processing capabilities.

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

## Usage

1. **Start the application**
   ```bash
   streamlit run app.py
   ```

2. **Access the application**
   - **Local**: Open your browser and go to `http://localhost:8501`
   - **Cloud**: Your app will be available at your Streamlit Cloud URL

3. **Upload PDFs**
   - Use the file uploader to select PDF documents
   - Multiple PDFs can be uploaded simultaneously
   - The system will process and index the documents

4. **Chat with documents**
   - Type your questions in the chat interface
   - The AI will respond based on the content of your uploaded PDFs
   - You can ask questions about specific documents or general queries

5. **Google Calendar Integration**
   - Click "Connect Google Calendar" to authenticate
   - View your upcoming events
   - Create new calendar events
   - Manage your schedule directly from the chat interface

## Security Features

- **Environment Variables**: All sensitive credentials are stored in environment variables
- **OAuth 2.0**: Secure Google Calendar authentication
- **Session Management**: Proper session handling for user authentication
- **Input Validation**: Secure handling of user inputs
- **Cloud Security**: Optimized for secure cloud deployment

## Troubleshooting

### Streamlit Cloud Issues
- **App not deploying**: Check `requirements.txt` for compatibility
- **OAuth not working**: Verify redirect URIs include your cloud URL
- **Secrets not loading**: Ensure secrets are configured in Streamlit Cloud dashboard
- **Memory errors**: Optimize for cloud resource limits

### Python 3.13 Issues
- **sentencepiece build failure**: Use `requirements-python313.txt` instead
- **Missing system dependencies**: Run `./install_system_deps.sh`
- **Package compatibility**: Some advanced features may not be available

### OAuth Issues
- Ensure your redirect URIs are correctly configured in Google Cloud Console
- Check that all environment variables are properly set
- Clear browser cache and cookies if authentication fails
- Try using incognito mode for testing

### PDF Processing Issues
- Ensure PDFs are not password-protected
- Check that PDFs contain readable text (not just images)
- Verify file size is reasonable (< 50MB recommended, < 10MB for cloud)

### API Issues
- Verify your OpenAI API key is valid and has sufficient credits
- Check your internet connection
- Ensure all required packages are installed

## Development

### Project Structure
```
Chat-Gidens/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Standard Python dependencies (cloud-optimized)
├── requirements-python313.txt  # Python 3.13 compatible dependencies
├── install_system_deps.sh     # System dependencies installer
├── .streamlit/
│   └── config.toml            # Streamlit configuration for cloud
├── .env.example               # Example environment variables
├── README.md                  # This file
├── STREAMLIT_CLOUD_DEPLOYMENT.md  # Cloud deployment guide
└── utils/                     # Utility functions
    ├── __init__.py
    ├── pdf_processor.py       # PDF processing utilities
    └── calendar_utils.py      # Google Calendar utilities
```

### Adding New Features
1. Create new utility functions in the `utils/` directory
2. Update the main application in `app.py`
3. Add any new dependencies to `requirements.txt`
4. Update this README with new features
5. Test both locally and on Streamlit Cloud

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (locally and on Streamlit Cloud)
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you encounter any issues or have questions:
1. Check the troubleshooting section above
2. Review the [Streamlit Cloud Deployment Guide](STREAMLIT_CLOUD_DEPLOYMENT.md)
3. Review the Google Cloud Console documentation
4. Open an issue on the repository 