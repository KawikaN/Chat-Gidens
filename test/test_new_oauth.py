#!/usr/bin/env python3
"""
Test script to verify the new OAuth flow with callback approach
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from calendar_integration import CalendarIntegration

def test_new_oauth_flow():
    """Test the new OAuth flow with callback approach."""
    
    print("🧪 Testing New OAuth Flow (Callback Approach)")
    print("=" * 50)
    
    # Initialize calendar integration
    calendar = CalendarIntegration()
    
    print("1. Checking current access status...")
    has_access, status = calendar.check_google_calendar_access()
    print(f"   Current access: {'✅ Yes' if has_access else '❌ No'}")
    print(f"   Status: {status}")
    
    if has_access:
        print("\n✅ OAuth is already working!")
        print("   You can now use 'AdD_CaL' in the chat to add events.")
        return
    
    print("\n2. Testing new OAuth flow...")
    print("   This will:")
    print("   - Start a callback server on port 8080")
    print("   - Open your browser for authentication")
    print("   - Handle the callback automatically")
    print("   - Return you to your Streamlit app")
    
    try:
        success, message = calendar.initiate_oauth_flow()
        if success:
            print("\n✅ OAuth flow completed successfully!")
            print("   You can now use 'AdD_CaL' in the chat to add events.")
        else:
            print(f"\n❌ OAuth flow failed: {message}")
            print("   Please check the error messages above.")
            
    except Exception as e:
        print(f"\n❌ Error during OAuth flow: {e}")
        print("   Please check your credentials.json and redirect URI.")

if __name__ == "__main__":
    test_new_oauth_flow() 