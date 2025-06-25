# Installation Guide

This guide ensures smooth installation for all users, regardless of their system or experience level.

## 🚀 Quick Start (Recommended)

### 1. Clone the repository
```bash
git clone <repository-url>
cd Chat-Gidens
```

### 2. Create virtual environment
```bash
# Using venv (Python 3.3+)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install core dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
# See SECURE_SETUP.md for Google OAuth setup
```

### 5. Run the application
```bash
streamlit run app.py
```

## 🔧 Troubleshooting Common Issues

### Issue: sentencepiece installation fails
**Error**: `Failed building wheel for sentencepiece`

**Solution**: 
```bash
# Try pre-built wheels
pip install --only-binary=all sentencepiece

# Or install without sentencepiece (core functionality will still work)
pip install -r requirements.txt --no-deps
pip install sentencepiece --no-build-isolation
```

### Issue: torch installation fails
**Error**: `Could not build wheels for torch`

**Solution**:
```bash
# For CPU-only installation
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# For CUDA (if you have NVIDIA GPU)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Issue: faiss-cpu installation fails
**Error**: `Failed building wheel for faiss-cpu`

**Solution**:
```bash
# Try conda installation
conda install -c conda-forge faiss-cpu

# Or use alternative vector store
# Edit app.py to use ChromaDB instead of FAISS
```

### Issue: Google OAuth credentials not working
**Error**: `Credentials file not found`

**Solution**:
1. Follow the setup in `SECURE_SETUP.md`
2. Ensure `.env` file contains all required Google OAuth variables
3. Click "🔧 Regenerate Credentials" in the app

## 🛠️ Advanced Installation

### Install with optional features (Local Only)
```bash
# Install core requirements first
pip install -r requirements.txt

# Then install optional features (may require additional system dependencies)
# NOTE: These packages are NOT compatible with Streamlit Cloud
pip install -r requirements-optional-local-only.txt
```

### System-specific installations

#### macOS (Apple Silicon M1/M2)
```bash
# Install Rosetta 2 if needed
softwareupdate --install-rosetta

# Use conda for better compatibility
conda install -c conda-forge faiss-cpu
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

#### Windows
```bash
# Install Visual C++ Build Tools if needed
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Use pre-built wheels when possible
pip install --only-binary=all sentencepiece torch
```

#### Linux (Ubuntu/Debian)
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install build-essential python3-dev

# Install Python packages
pip install -r requirements.txt
```

## 🔍 Verification

After installation, verify everything works:

1. **Test core functionality**:
   ```bash
   python -c "import streamlit, langchain, openai; print('✅ Core packages imported successfully')"
   ```

2. **Test Google OAuth**:
   ```bash
   python -c "from calendar_integration import generate_credentials_from_env; print('✅ Google OAuth setup working')"
   ```

3. **Run the app**:
   ```bash
   streamlit run app.py
   ```

## 📋 Requirements Summary

### Core Requirements (Always needed)
- Python 3.8+
- streamlit
- langchain
- openai
- PyPDF2
- chromadb (cloud-compatible)
- google-auth packages

### Optional Requirements (Local development only)
- sentence-transformers (for better embeddings)
- torch (for ML models)
- transformers (for text processing)
- **Note**: These are NOT compatible with Streamlit Cloud

## 🆘 Getting Help

If you encounter issues:

1. **Check the troubleshooting section** above
2. **Verify your Python version**: `python --version`
3. **Check your pip version**: `pip --version`
4. **Try with a fresh virtual environment**
5. **Check system-specific requirements** for your OS

## 🔄 Updating

To update the application:

```bash
# Update dependencies
pip install -r requirements.txt --upgrade

# Update optional dependencies (local only)
pip install -r requirements-optional-local-only.txt --upgrade

# Pull latest code
git pull origin main
```

## 🚨 Common Pitfalls

- **Don't install globally**: Always use a virtual environment
- **Don't mix package managers**: Use either pip or conda, not both
- **Check Python version**: Ensure you're using Python 3.8+
- **Update pip**: Always upgrade pip before installing requirements
- **Read error messages**: Most errors have specific solutions
- **Streamlit Cloud limitations**: Optional packages won't work on cloud deployment 