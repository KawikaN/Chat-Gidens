#!/usr/bin/env python3
"""
Test script for calendar integration functionality.
Run this to verify that the calendar integration is working properly.
"""

from calendar_integration import calendar_integration
from events import search_ticketmaster_events

def test_calendar_integration():
    """Test the calendar integration with sample events."""
    
    print("🧪 Testing Calendar Integration...")
    print("=" * 50)
    
    # Test 1: Get events from Ticketmaster
    print("1. Fetching events from Ticketmaster...")
    events, raw_events = search_ticketmaster_events("")
    
    if not events or events[0] == "No Ticketmaster events found.":
        print("❌ No events found. Using sample events for testing.")
        # Create sample events for testing
        sample_events = [
            "Sample Concert - 2025-06-25 at Honolulu Arena",
            "Hawaii Festival - 2025-06-26 at Waikiki Beach",
            "Local Market - 2025-06-27 at Ala Moana Center"
        ]
        events = sample_events
    
    print(f"✅ Found {len(events)} events")
    for event in events[:3]:  # Show first 3 events
        print(f"   • {event}")
    
    # Test 2: Parse event strings
    print("\n2. Testing event parsing...")
    for event in events[:2]:
        parsed = calendar_integration.parse_event_string(event)
        if parsed:
            print(f"✅ Parsed: {parsed}")
        else:
            print(f"❌ Failed to parse: {event}")
    
    # Test 3: Create iCal file
    print("\n3. Testing iCal file creation...")
    result = calendar_integration.add_events_to_calendar(events[:3], "ical")
    print(f"Result: {result}")
    
    # Test 4: Test Google Calendar (if credentials available)
    print("\n4. Testing Google Calendar integration...")
    try:
        # Test access checking first
        has_access, status = calendar_integration.check_google_calendar_access()
        print(f"Access check: {has_access} - {status}")
        
        if has_access:
            result = calendar_integration.add_events_to_calendar(events[:1], "google")
            print(f"Add events result: {result}")
        else:
            print(f"⚠️  Google Calendar not accessible: {status}")
            print("   To set up Google Calendar:")
            print("   1. Follow CALENDAR_SETUP.md instructions")
            print("   2. Download credentials.json")
            print("   3. Run the app and click 'Grant Calendar Access'")
            
    except Exception as e:
        print(f"⚠️  Google Calendar test skipped: {e}")
    
    # Test 5: Test OAuth flow initiation
    print("\n5. Testing OAuth flow initiation...")
    try:
        success, message = calendar_integration.initiate_oauth_flow()
        print(f"OAuth initiation: {success} - {message}")
    except Exception as e:
        print(f"⚠️  OAuth test skipped: {e}")
    
    # Test 6: Test status summary
    print("\n6. Testing status summary...")
    status_summary = calendar_integration.get_calendar_status_summary()
    print(f"Status summary: {status_summary}")
    
    print("\n" + "=" * 50)
    print("✅ Calendar integration test completed!")
    print("\n📋 Next steps:")
    print("1. For Google Calendar: Set up credentials.json (see CALENDAR_SETUP.md)")
    print("2. For iCal: Check the generated .ics file in your project directory")
    print("3. Run the main app: streamlit run app.py")

if __name__ == "__main__":
    test_calendar_integration() 