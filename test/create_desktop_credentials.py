#!/usr/bin/env python3
"""
Script to help create desktop OAuth credentials
"""

import webbrowser
import os

def create_desktop_credentials():
    """Guide user through creating desktop OAuth credentials."""
    
    print("🖥️  Desktop OAuth Credentials Setup")
    print("=" * 50)
    print("This will help you create the correct OAuth credentials for local development.")
    print()
    
    # Step 1: Open Google Cloud Console
    print("1. Opening Google Cloud Console...")
    webbrowser.open("https://console.cloud.google.com/")
    input("Press Enter when you're in Google Cloud Console...")
    
    # Step 2: Navigate to credentials
    print("\n2. Navigate to OAuth credentials:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click 'Create Credentials' > 'OAuth 2.0 Client IDs'")
    input("Press Enter when you're ready to create credentials...")
    
    # Step 3: Create desktop application
    print("\n3. Create Desktop Application credentials:")
    print("   - Choose 'Desktop application' (NOT Web application)")
    print("   - Name: 'Hawaii Business Assistant'")
    print("   - Click 'Create'")
    input("Press Enter when you've created the credentials...")
    
    # Step 4: Download credentials
    print("\n4. Download the credentials:")
    print("   - Click the download button (⬇️) next to your new OAuth client")
    print("   - Save the JSON file")
    input("Press Enter when you've downloaded the file...")
    
    # Step 5: Setup instructions
    print("\n5. Setup the credentials file:")
    print("   - Rename the downloaded file to 'credentials.json'")
    print("   - Move it to your project root directory")
    print("   - Replace the existing credentials.json file")
    
    # Check if credentials.json exists
    if os.path.exists('credentials.json'):
        print("\n⚠️  Warning: credentials.json already exists!")
        print("   You should replace it with the new desktop credentials.")
        print("   The current file is for a web application.")
    
    # Step 6: Clean up
    print("\n6. Clean up old tokens:")
    if os.path.exists('token.pickle'):
        print("   - Delete token.pickle file (if it exists)")
        print("   - This will force re-authentication")
    
    print("\n7. Test the new credentials:")
    print("   - Run: python test_oauth_flow.py")
    print("   - Or run: streamlit run app.py")
    
    print("\n✅ Desktop credentials setup complete!")
    print("   Desktop applications don't need redirect URI configuration,")
    print("   so you shouldn't get the redirect_uri_mismatch error anymore.")

if __name__ == "__main__":
    create_desktop_credentials() 