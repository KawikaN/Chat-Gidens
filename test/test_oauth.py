#!/usr/bin/env python3
"""
Test script to verify OAuth flow with existing credentials.json
"""

from calendar_integration import calendar_integration
import json

def test_credentials():
    """Test the credentials.json file and OAuth flow."""
    
    print("🔍 Testing Google Calendar OAuth Setup...")
    print("=" * 50)
    
    # Test 1: Check if credentials.json exists and is valid
    print("1. Checking credentials.json...")
    try:
        with open('credentials.json', 'r') as f:
            cred_data = json.load(f)
        
        if 'web' in cred_data:
            print("✅ Found web OAuth client credentials")
            client_id = cred_data['web']['client_id']
            project_id = cred_data['web']['project_id']
            print(f"   Client ID: {client_id}")
            print(f"   Project ID: {project_id}")
        elif 'installed' in cred_data:
            print("✅ Found desktop OAuth client credentials")
            client_id = cred_data['installed']['client_id']
            print(f"   Client ID: {client_id}")
        else:
            print("❌ Invalid credentials.json format")
            return
            
    except FileNotFoundError:
        print("❌ credentials.json not found")
        return
    except json.JSONDecodeError:
        print("❌ Invalid JSON in credentials.json")
        return
    
    # Test 2: Check current access status
    print("\n2. Checking current access status...")
    has_access, status = calendar_integration.check_google_calendar_access()
    print(f"   Has access: {has_access}")
    print(f"   Status: {status}")
    
    # Test 3: Test OAuth flow initiation
    print("\n3. Testing OAuth flow initiation...")
    if not has_access:
        print("   Initiating OAuth flow...")
        success, message = calendar_integration.initiate_oauth_flow()
        print(f"   Success: {success}")
        print(f"   Message: {message}")
        
        if success:
            # Test 4: Verify access after OAuth
            print("\n4. Verifying access after OAuth...")
            has_access, status = calendar_integration.check_google_calendar_access()
            print(f"   Has access: {has_access}")
            print(f"   Status: {status}")
    else:
        print("   ✅ Already have access, no OAuth needed")
    
    # Test 5: Test adding a sample event
    print("\n5. Testing event addition...")
    if has_access:
        sample_event = {
            'name': 'Test Event',
            'start_date': '2025-06-25',
            'start_time': '19:00',
            'venue': 'Test Venue',
            'description': 'This is a test event'
        }
        
        success = calendar_integration.add_event_to_google_calendar(sample_event)
        if success:
            print("   ✅ Successfully added test event to Google Calendar")
        else:
            print("   ❌ Failed to add test event")
    else:
        print("   ⚠️  Cannot test event addition - no access")
    
    print("\n" + "=" * 50)
    print("✅ OAuth test completed!")
    
    if has_access:
        print("\n🎉 Google Calendar is ready to use!")
        print("   You can now run the main app and add events to your calendar.")
    else:
        print("\n📋 Next steps:")
        print("   1. Make sure you have the correct credentials.json file")
        print("   2. Run this test again to complete OAuth")
        print("   3. Or run the main app and use the 'Grant Calendar Access' button")

if __name__ == "__main__":
    test_credentials() 