#!/usr/bin/env python3
"""
Test script to verify OAuth flow works correctly
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from calendar_integration import GoogleCalendarIntegration

def test_oauth_flow():
    """Test the OAuth flow."""
    
    print("🧪 Testing OAuth Flow")
    print("=" * 30)
    
    # Initialize calendar integration
    calendar = GoogleCalendarIntegration()
    
    print("1. Checking current access status...")
    has_access = calendar.has_google_calendar_access()
    print(f"   Current access: {'✅ Yes' if has_access else '❌ No'}")
    
    if has_access:
        print("\n✅ OAuth is already working!")
        print("   You can now use 'AdD_CaL' in the chat to add events.")
        return
    
    print("\n2. Testing OAuth flow...")
    print("   This will open your browser for authentication.")
    print("   Please complete the sign-in process.")
    
    try:
        success = calendar.initiate_oauth_flow()
        if success:
            print("\n✅ OAuth flow completed successfully!")
            print("   You can now use 'AdD_CaL' in the chat to add events.")
        else:
            print("\n❌ OAuth flow failed.")
            print("   Please check the error messages above.")
            
    except Exception as e:
        print(f"\n❌ Error during OAuth flow: {e}")
        print("   Please check your credentials.json and redirect URIs.")

if __name__ == "__main__":
    test_oauth_flow() 