#!/bin/bash

# System dependencies installation script for Chat-Gidens
# This script installs the necessary system packages for building Python packages

echo "🔧 Installing system dependencies for Chat-Gidens..."

# Detect the operating system
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        echo "📦 Installing dependencies for Debian/Ubuntu..."
        sudo apt-get update
        sudo apt-get install -y \
            build-essential \
            python3-dev \
            pkg-config \
            cmake \
            git \
            curl \
            wget
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL/Fedora
        echo "📦 Installing dependencies for CentOS/RHEL/Fedora..."
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y \
            python3-devel \
            pkgconfig \
            cmake \
            git \
            curl \
            wget
    elif command -v dnf &> /dev/null; then
        # Fedora (newer versions)
        echo "📦 Installing dependencies for Fedora..."
        sudo dnf groupinstall -y "Development Tools"
        sudo dnf install -y \
            python3-devel \
            pkgconfig \
            cmake \
            git \
            curl \
            wget
    else
        echo "❌ Unsupported Linux distribution. Please install manually:"
        echo "   - build-essential (or equivalent)"
        echo "   - python3-dev"
        echo "   - pkg-config"
        echo "   - cmake"
        echo "   - git"
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "🍎 Installing dependencies for macOS..."
    if command -v brew &> /dev/null; then
        brew install \
            pkg-config \
            cmake \
            git
    else
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        echo "   Then run: brew install pkg-config cmake git"
    fi
else
    echo "❌ Unsupported operating system: $OSTYPE"
    echo "Please install the following manually:"
    echo "   - pkg-config"
    echo "   - cmake"
    echo "   - git"
    echo "   - build tools for your system"
fi

echo "✅ System dependencies installation complete!"
echo ""
echo "Next steps:"
echo "1. Activate your virtual environment"
echo "2. Run: pip install -r requirements.txt"
echo "3. (Optional - Local Only) Run: pip install -r requirements-optional-local-only.txt"
echo "   Note: Optional packages are NOT compatible with Streamlit Cloud" 