#!/usr/bin/env python3
"""
Script to check OAuth status and wait for changes to propagate
"""

import time
import os
from calendar_integration import calendar_integration

def check_oauth_status():
    """Check OAuth status and wait for changes to propagate."""
    
    print("🔍 Checking OAuth Status...")
    print("=" * 50)
    
    # Check if credentials exist
    if not os.path.exists('credentials.json'):
        print("❌ credentials.json not found!")
        return
    
    print("✅ credentials.json found")
    
    # Check current status
    has_access, status = calendar_integration.check_google_calendar_access()
    print(f"Current status: {has_access} - {status}")
    
    if has_access:
        print("🎉 OAuth is working! You can now add events to Google Calendar.")
        return
    
    if "authentication required" in status.lower():
        print("\n⏳ Waiting for OAuth changes to propagate...")
        print("This can take 2-3 minutes after updating redirect URIs in Google Cloud Console.")
        
        # Try OAuth flow with retries
        for attempt in range(3):
            print(f"\n🔄 Attempt {attempt + 1}/3: Trying OAuth flow...")
            try:
                success, message = calendar_integration.initiate_oauth_flow()
                if success:
                    print("✅ OAuth successful!")
                    print("🎉 You can now add events to Google Calendar.")
                    return
                else:
                    print(f"❌ OAuth failed: {message}")
                    if "redirect_uri_mismatch" in message.lower():
                        print("\n⏳ Waiting 60 seconds for changes to propagate...")
                        time.sleep(60)
                    else:
                        print("❌ OAuth configuration issue. Please check the error message above.")
                        return
            except Exception as e:
                print(f"❌ OAuth error: {e}")
                if attempt < 2:
                    print("⏳ Waiting 30 seconds before retry...")
                    time.sleep(30)
        
        print("\n❌ OAuth failed after 3 attempts.")
        print("Please check your OAuth configuration or try creating desktop credentials.")
        
    else:
        print(f"❌ OAuth issue: {status}")
        print("Please check your credentials.json file and OAuth configuration.")

if __name__ == "__main__":
    check_oauth_status() 