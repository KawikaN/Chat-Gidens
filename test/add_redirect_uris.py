#!/usr/bin/env python3
"""
Script to help add the necessary redirect URI to OAuth client
"""

import webbrowser
import json
import os

def add_redirect_uris():
    """Help user add the necessary redirect URI to OAuth client."""
    
    print("🔧 Adding Redirect URI to OAuth Client")
    print("=" * 50)
    
    # Check current credentials
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found!")
        return
    
    try:
        with open('credentials.json', 'r') as f:
            cred_data = json.load(f)
        
        if 'web' not in cred_data:
            print("❌ This is not a web OAuth client!")
            return
            
        client_id = cred_data['web']['client_id']
        print(f"✅ Found web OAuth client: {client_id}")
        
    except Exception as e:
        print(f"❌ Error reading credentials.json: {e}")
        return
    
    print("\n🔧 To fix the redirect_uri_mismatch error:")
    print("1. Opening Google Cloud Console...")
    webbrowser.open("https://console.cloud.google.com/")
    input("Press Enter when you're in Google Cloud Console...")
    
    print("\n2. Navigate to your OAuth client:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Find your OAuth 2.0 Client ID")
    print(f"   - Look for client ID: {client_id[:20]}...")
    print("   - Click 'Edit' (pencil icon)")
    input("Press Enter when you're editing the OAuth client...")
    
    print("\n3. Add this redirect URI:")
    print("   - Scroll down to 'Authorized redirect URIs'")
    print("   - Click 'Add URI' and add:")
    print("     • http://localhost:8080")
    print("   - Click 'Save'")
    input("Press Enter when you've added the redirect URI and saved...")
    
    print("\n4. Test the fix:")
    print("   - Wait 2-3 minutes for changes to apply")
    print("   - Run: python test_oauth_flow.py")
    print("   - Or run: streamlit run app.py")
    
    print("\n✅ Redirect URI added!")
    print("   This should fix the 'redirect_uri_mismatch' error.")
    print("   The OAuth flow will now use port 8080 for the callback.")

if __name__ == "__main__":
    add_redirect_uris() 