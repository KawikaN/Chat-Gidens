#!/usr/bin/env python3
"""
Helper script to diagnose and fix OAuth configuration issues
"""

import json
import os

def check_oauth_config():
    """Check the OAuth configuration and provide fixes."""
    
    print("🔧 OAuth Configuration Checker")
    print("=" * 50)
    
    # Check if credentials.json exists
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found!")
        print("\n📋 To fix this:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Google Calendar API")
        print("3. Create OAuth 2.0 credentials")
        print("4. Download the JSON file and rename it to 'credentials.json'")
        print("5. Place it in your project root directory")
        return
    
    # Parse credentials.json
    try:
        with open('credentials.json', 'r') as f:
            cred_data = json.load(f)
    except json.JSONDecodeError:
        print("❌ Invalid JSON in credentials.json")
        return
    
    # Check client type
    if 'web' in cred_data:
        print("✅ Found web OAuth client")
        client_config = cred_data['web']
        
        print(f"   Client ID: {client_config.get('client_id', 'Not found')}")
        print(f"   Project ID: {client_config.get('project_id', 'Not found')}")
        
        # Check for redirect URIs
        if 'redirect_uris' in client_config:
            print(f"   Redirect URIs: {client_config['redirect_uris']}")
        else:
            print("   ⚠️  No redirect URIs configured")
        
        print("\n🔧 To fix redirect_uri_mismatch error:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Navigate to: APIs & Services > Credentials")
        print("3. Find your OAuth 2.0 Client ID and click 'Edit'")
        print("4. In the 'Authorized redirect URIs' section, add:")
        print("   - http://localhost:8080")
        print("   - http://localhost:8090")
        print("   - http://localhost:9000")
        print("   - http://localhost:9090")
        print("5. Click 'Save'")
        print("6. Try the OAuth flow again")
        
    elif 'installed' in cred_data:
        print("✅ Found desktop OAuth client")
        client_config = cred_data['installed']
        print(f"   Client ID: {client_config.get('client_id', 'Not found')}")
        print("   ✅ Desktop clients don't need redirect URI configuration")
        
    else:
        print("❌ Invalid credentials.json format")
        print("   Expected 'web' or 'installed' client configuration")
    
    # Check for token.pickle
    if os.path.exists('token.pickle'):
        print("\n✅ Found existing authentication token")
        print("   You may need to delete token.pickle if authentication fails")
    else:
        print("\nℹ️  No existing authentication token found")
        print("   This is normal for first-time setup")

def create_desktop_credentials_guide():
    """Provide guide for creating desktop credentials."""
    
    print("\n📋 Guide: Creating Desktop OAuth Credentials")
    print("=" * 50)
    print("1. Go to https://console.cloud.google.com/")
    print("2. Create a new project or select existing")
    print("3. Enable Google Calendar API:")
    print("   - Go to APIs & Services > Library")
    print("   - Search for 'Google Calendar API'")
    print("   - Click on it and press 'Enable'")
    print("4. Create OAuth 2.0 credentials:")
    print("   - Go to APIs & Services > Credentials")
    print("   - Click 'Create Credentials' > 'OAuth 2.0 Client IDs'")
    print("   - Choose 'Desktop application' (not Web application)")
    print("   - Give it a name (e.g., 'Hawaii Business Assistant')")
    print("   - Click 'Create'")
    print("5. Download the JSON file")
    print("6. Rename it to 'credentials.json'")
    print("7. Place it in your project root directory")
    print("8. Delete the old token.pickle file if it exists")
    print("9. Try the OAuth flow again")

if __name__ == "__main__":
    check_oauth_config()
    create_desktop_credentials_guide() 