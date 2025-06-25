#!/usr/bin/env python3
"""
Quick fix script for web OAuth client redirect URI issues
"""

import webbrowser
import json
import os

def quick_fix_web_client():
    """Quick fix for web OAuth client redirect URI issues."""
    
    print("🔧 Quick Fix for Web OAuth Client")
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
    
    print("\n3. Add redirect URIs:")
    print("   - Scroll down to 'Authorized redirect URIs'")
    print("   - Click 'Add URI' for each of these:")
    print("     • http://localhost:8080")
    print("     • http://localhost:8090")
    print("     • http://localhost:9000")
    print("     • http://localhost:9090")
    print("   - Click 'Save'")
    input("Press Enter when you've added the redirect URIs and saved...")
    
    print("\n4. Test the fix:")
    print("   - Run: python test_oauth_flow.py")
    print("   - Or run: streamlit run app.py")
    
    print("\n✅ Web OAuth client should now work!")
    print("   The redirect_uri_mismatch error should be resolved.")

if __name__ == "__main__":
    quick_fix_web_client() 