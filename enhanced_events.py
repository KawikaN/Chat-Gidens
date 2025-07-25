import requests
import os
import json
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta
import streamlit as st
from langchain.chat_models import ChatOpenAI
import re


class EnhancedEventManager:
    """Enhanced event management system with topic filtering, research capabilities, and user tracking."""
    
    def __init__(self):
        self.event_storage_file = "data_store/event_database.json"
        self.user_preferences_file = "data_store/user_event_preferences.json"
        self.uncertain_events_file = "data_store/uncertain_events.json"
        self.event_suggestions_file = "data_store/event_research_suggestions.json"
        self._ensure_files_exist()
    
    def _ensure_files_exist(self):
        """Create necessary data files if they don't exist."""
        os.makedirs("data_store", exist_ok=True)
        
        for file_path in [self.event_storage_file, self.user_preferences_file, 
                         self.uncertain_events_file, self.event_suggestions_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump({}, f)
    
    def add_event_to_database(self, event_data: Dict, source: str = "manual"):
        """Add an event to the persistent event database."""
        try:
            with open(self.event_storage_file, 'r') as f:
                events = json.load(f)
            
            # Generate a unique event ID
            event_id = f"{event_data.get('name', 'unknown')}_{event_data.get('date', 'unknown')}_{source}"
            event_id = event_id.replace(" ", "_").replace("/", "_")
            
            # Add metadata
            event_data['id'] = event_id
            event_data['source'] = source
            event_data['added_date'] = datetime.now().isoformat()
            
            events[event_id] = event_data
            
            with open(self.event_storage_file, 'w') as f:
                json.dump(events, f, indent=2)
                
            return True, event_id
        except Exception as e:
            return False, str(e)
    
    def search_events_by_topic(self, topics: List[str], location: Optional[str] = None) -> Tuple[List[str], List[Dict]]:
        """Search for events by specific topics/categories."""
        try:
            with open(self.event_storage_file, 'r') as f:
                all_events = json.load(f)
            
            if not topics:
                return self._format_all_events(all_events, location)
            
            # Filter events by topics using LLM understanding
            filtered_events = self._filter_events_by_topics(all_events, topics, location)
            
            # Convert to display format
            summaries = []
            details = []
            
            for event_id, event in filtered_events.items():
                summary = self._format_event_summary(event)
                summaries.append(summary)
                details.append(event)
            
            return summaries, details
            
        except Exception as e:
            st.error(f"Error searching events by topic: {e}")
            return [], []
    
    def _filter_events_by_topics(self, events: Dict, topics: List[str], location: Optional[str]) -> Dict:
        """Use LLM to filter events by topics."""
        try:
            llm = ChatOpenAI(temperature=0)
            
            # Create event context for LLM
            event_context = []
            for event_id, event in events.items():
                event_summary = f"ID: {event_id}\nName: {event.get('name', 'N/A')}\nDescription: {event.get('description', 'N/A')}\nCategories: {event.get('categories', [])}"
                event_context.append(event_summary)
            
            topics_str = ", ".join(topics)
            location_filter = f"Location filter: {location}" if location else "No location filter"
            
            filter_prompt = f"""You are filtering events based on user-requested topics. 

Topics requested: {topics_str}
{location_filter}

Events to filter:
{chr(10).join(event_context)}

Return ONLY a JSON list of event IDs that match the requested topics. Consider:
- Direct topic matches (music → concerts, festivals)
- Related categories (food → food trucks, cooking classes)
- Event descriptions and content
- If location is specified, only include events in that location

Example response: ["event1_id", "event2_id", "event3_id"]

If no events match, return: []"""

            response = llm.predict(filter_prompt).strip()
            
            # Parse LLM response
            import json
            try:
                matching_ids = json.loads(response)
                return {event_id: events[event_id] for event_id in matching_ids if event_id in events}
            except json.JSONDecodeError:
                # Fallback to keyword matching
                return self._fallback_topic_filter(events, topics, location)
                
        except Exception as e:
            print(f"LLM filtering failed: {e}")
            return self._fallback_topic_filter(events, topics, location)
    
    def _fallback_topic_filter(self, events: Dict, topics: List[str], location: Optional[str]) -> Dict:
        """Fallback keyword-based filtering if LLM fails."""
        filtered = {}
        topics_lower = [topic.lower() for topic in topics]
        
        for event_id, event in events.items():
            # Check location if specified - use same flexible matching as _format_all_events
            if location:
                location_lower = location.lower()
                venue_lower = event.get('venue', '').lower()
                
                # For Hawaii locations, be more flexible with matching
                hawaii_areas = {
                    'honolulu': ['honolulu', 'waikiki', 'downtown', 'chinatown', 'kapiolani', 'diamond head'],
                    'oahu': ['honolulu', 'waikiki', 'north shore', 'pearl harbor', 'kaneohe', 'kailua', 'hawaii'],
                    'hawaii': ['hawaii', 'honolulu', 'waikiki', 'north shore', 'oahu', 'maui', 'big island'],
                    'north shore': ['north shore', 'haleiwa', 'sunset beach', 'pipeline'],
                    'waikiki': ['waikiki', 'honolulu']
                }
                
                # Check if location matches venue directly
                location_matches = location_lower in venue_lower
                
                # Check for Hawaii-specific area matching
                if not location_matches and location_lower in hawaii_areas:
                    for area in hawaii_areas[location_lower]:
                        if area in venue_lower:
                            location_matches = True
                            break
                
                # If location is specified but doesn't match, skip this event
                if not location_matches:
                    continue
                
            # Check if any topic matches event content
            event_text = f"{event.get('name', '')} {event.get('description', '')} {' '.join(event.get('categories', []))}".lower()
            
            if any(topic in event_text for topic in topics_lower):
                filtered[event_id] = event
        
        return filtered
    
    def _format_all_events(self, events: Dict, location: Optional[str]) -> Tuple[List[str], List[Dict]]:
        """Format all events for display."""
        summaries = []
        details = []
        
        for event_id, event in events.items():
            # Apply location filter if specified - but be more flexible for Hawaii
            if location:
                location_lower = location.lower()
                venue_lower = event.get('venue', '').lower()
                
                # For Hawaii locations, be more flexible with matching
                hawaii_areas = {
                    'honolulu': ['honolulu', 'waikiki', 'downtown', 'chinatown', 'kapiolani', 'diamond head'],
                    'oahu': ['honolulu', 'waikiki', 'north shore', 'pearl harbor', 'kaneohe', 'kailua', 'hawaii'],
                    'hawaii': ['hawaii', 'honolulu', 'waikiki', 'north shore', 'oahu', 'maui', 'big island'],
                    'north shore': ['north shore', 'haleiwa', 'sunset beach', 'pipeline'],
                    'waikiki': ['waikiki', 'honolulu']
                }
                
                # Check if location matches venue directly
                location_matches = location_lower in venue_lower
                
                # Check for Hawaii-specific area matching
                if not location_matches and location_lower in hawaii_areas:
                    for area in hawaii_areas[location_lower]:
                        if area in venue_lower:
                            location_matches = True
                            break
                
                # If location is specified but doesn't match, skip this event
                if not location_matches:
                    continue
                
            summary = self._format_event_summary(event)
            summaries.append(summary)
            details.append(event)
        
        return summaries, details
    
    def _format_event_summary(self, event: Dict) -> str:
        """Format a single event for clean display."""
        name = event.get('name', 'Unknown Event')
        date = event.get('date', 'TBD')
        venue = event.get('venue', 'TBD')
        
        # Clean date format
        if date and date != 'TBD':
            try:
                if 'T' in date:
                    date_obj = datetime.fromisoformat(date.replace('Z', ''))
                    date = date_obj.strftime('%Y-%m-%d')
                elif ' ' in date:
                    date = date.split()[0]  # Take just the date part
            except:
                pass  # Keep original date if parsing fails
        
        return f"{name} - {date} at {venue}"
    
    def research_event_details(self, event: Dict) -> Dict:
        """Research additional details about an event using web search."""
        try:
            # Extract key information for research
            event_name = event.get('name', '')
            venue = event.get('venue', '')
            date = event.get('date', '')
            
            # Construct search query
            search_query = f"{event_name} {venue} {date} event details"
            
            # Perform web search (this function needs to be implemented)
            research_results = search_web_for_event_info(search_query)
            
            if research_results:
                # Use LLM to extract relevant information
                enhanced_info = self._extract_relevant_event_info(event, research_results)
                
                # Add research findings to suggestions file
                self._add_research_suggestion(event, enhanced_info)
                
                return enhanced_info
            
            return event
            
        except Exception as e:
            print(f"Error researching event {event.get('name', 'Unknown')}: {e}")
            return event
    
    def _extract_relevant_event_info(self, original_event: Dict, research_results: str) -> Dict:
        """Use LLM to extract relevant information from web search results."""
        try:
            llm = ChatOpenAI(temperature=0)
            
            extraction_prompt = f"""Extract relevant event information from the web search results to enhance the original event data.

Original Event:
Name: {original_event.get('name', 'N/A')}
Date: {original_event.get('date', 'N/A')}
Venue: {original_event.get('venue', 'N/A')}
Description: {original_event.get('description', 'N/A')}

Web Search Results:
{research_results}

Extract and return ONLY new/additional information as JSON:
{{
    "enhanced_description": "detailed description if found",
    "ticket_price": "price range if mentioned",
    "event_type": "category/type of event",
    "duration": "event duration if mentioned",
    "age_restrictions": "any age limits",
    "additional_details": "any other relevant information"
}}

Only include fields where you found actual information. Return {{}} if no useful information found."""

            response = llm.predict(extraction_prompt).strip()
            
            try:
                enhanced_info = json.loads(response)
                # Merge with original event data
                result = original_event.copy()
                result.update(enhanced_info)
                return result
            except json.JSONDecodeError:
                return original_event
                
        except Exception as e:
            print(f"Error extracting event info: {e}")
            return original_event
    
    def _add_research_suggestion(self, event: Dict, enhanced_info: Dict):
        """Add research findings to suggestions file for review."""
        try:
            with open(self.event_suggestions_file, 'r') as f:
                suggestions = json.load(f)
            
            event_id = event.get('id', f"unknown_{datetime.now().timestamp()}")
            
            suggestion = {
                "original_event": event,
                "enhanced_info": enhanced_info,
                "research_date": datetime.now().isoformat(),
                "status": "pending_review"
            }
            
            suggestions[event_id] = suggestion
            
            with open(self.event_suggestions_file, 'w') as f:
                json.dump(suggestions, f, indent=2)
                
        except Exception as e:
            print(f"Error adding research suggestion: {e}")
    
    def add_uncertain_event(self, event: Dict, reason: str = "unclear_context"):
        """Add an event to the uncertain events list for user review."""
        try:
            with open(self.uncertain_events_file, 'r') as f:
                uncertain = json.load(f)
            
            event_id = f"uncertain_{datetime.now().timestamp()}"
            
            uncertain_entry = {
                "event": event,
                "reason": reason,
                "added_date": datetime.now().isoformat(),
                "status": "pending_review"
            }
            
            uncertain[event_id] = uncertain_entry
            
            with open(self.uncertain_events_file, 'w') as f:
                json.dump(uncertain, f, indent=2)
                
            return event_id
            
        except Exception as e:
            print(f"Error adding uncertain event: {e}")
            return None
    
    def get_uncertain_events(self) -> List[Dict]:
        """Get list of events the system is uncertain about."""
        try:
            with open(self.uncertain_events_file, 'r') as f:
                uncertain = json.load(f)
            
            return [entry for entry in uncertain.values() if entry.get('status') == 'pending_review']
            
        except Exception as e:
            print(f"Error getting uncertain events: {e}")
            return []
    
    def track_user_event_interest(self, event: Dict, user_action: str = "added"):
        """Track which events the user is interested in."""
        try:
            with open(self.user_preferences_file, 'r') as f:
                preferences = json.load(f)
            
            if 'interested_events' not in preferences:
                preferences['interested_events'] = []
            
            event_record = {
                "event": event,
                "action": user_action,
                "timestamp": datetime.now().isoformat()
            }
            
            preferences['interested_events'].append(event_record)
            
            with open(self.user_preferences_file, 'w') as f:
                json.dump(preferences, f, indent=2)
                
        except Exception as e:
            print(f"Error tracking user interest: {e}")
    
    def get_user_event_preferences(self) -> Dict:
        """Get user's event preferences and history."""
        try:
            with open(self.user_preferences_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error getting user preferences: {e}")
            return {}
    
    def suggest_similar_events(self, event: Dict) -> List[Dict]:
        """Suggest similar events based on user's past interests."""
        try:
            preferences = self.get_user_event_preferences()
            interested_events = preferences.get('interested_events', [])
            
            if not interested_events:
                return []
            
            # Use LLM to find similar events
            llm = ChatOpenAI(temperature=0)
            
            # Get all events from database
            with open(self.event_storage_file, 'r') as f:
                all_events = json.load(f)
            
            # Create context of user's interests
            user_interests = [item['event'] for item in interested_events[-10:]]  # Last 10 interests
            
            similarity_prompt = f"""Based on the user's past event interests, suggest similar events from the database.

User's Past Interests:
{json.dumps(user_interests, indent=2)}

Current Event:
{json.dumps(event, indent=2)}

Available Events Database:
{json.dumps(list(all_events.values()), indent=2)}

Return a JSON list of event IDs that are similar to the user's interests and the current event. Consider:
- Event type/category
- Venue type
- Artist/performer style
- Event theme

Maximum 5 suggestions. Return [] if no similar events found."""

            response = llm.predict(similarity_prompt).strip()
            
            try:
                similar_ids = json.loads(response)
                return [all_events[event_id] for event_id in similar_ids if event_id in all_events]
            except json.JSONDecodeError:
                return []
                
        except Exception as e:
            print(f"Error suggesting similar events: {e}")
            return []


def search_web_for_event_info(query: str) -> Optional[str]:
    """Search the web for additional event information."""
    try:
        # This will be implemented using web search tools
        # For now, we'll use a simple approach or return None
        # You can later integrate with SerpAPI, Google Custom Search, etc.
        
        # Placeholder implementation - in production, you would use:
        # from your_web_search_module import web_search
        # return web_search(query)
        
        return None
    except Exception as e:
        print(f"Error searching web for event info: {e}")
        return None


# Integration functions for existing system
def enhanced_search_events(query: str, city: str, topics: List[str] = None, 
                          start_date: str = None, end_date: str = None) -> Tuple[List[str], List[Dict]]:
    """Enhanced event search that combines Ticketmaster API with local database."""
    manager = EnhancedEventManager()
    
    # First, search local database for topic-specific events
    if topics:
        local_summaries, local_details = manager.search_events_by_topic(topics, city)
    else:
        local_summaries, local_details = manager.search_events_by_topic([], city)
    
    print(f"Local database found: {len(local_summaries)} events")
    
    # Then search Ticketmaster API for current events
    tm_summaries, tm_details = [], []
    try:
        from events import search_ticketmaster_events
        
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        if not end_date:
            end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        print(f"Searching Ticketmaster with query='{query}', city='{city}'")
        tm_summaries, tm_details = search_ticketmaster_events(query, city, start_date, end_date)
        
        # Check if Ticketmaster returned an error message
        if tm_summaries and len(tm_summaries) == 1 and "API key" in tm_summaries[0]:
            print(f"Ticketmaster API issue: {tm_summaries[0]}")
            tm_summaries, tm_details = [], []  # Clear error message
        elif tm_summaries and len(tm_summaries) == 1 and "No Ticketmaster events found" in tm_summaries[0]:
            print("No Ticketmaster events found for the search criteria")
            tm_summaries, tm_details = [], []  # Clear "no events" message
        else:
            print(f"Ticketmaster found: {len(tm_summaries)} events")
        
        # Ensure we have valid lists
        if not isinstance(tm_summaries, list):
            tm_summaries = []
        if not isinstance(tm_details, list):
            tm_details = []
            
        # Make sure summaries and details lists are the same length
        min_length = min(len(tm_summaries), len(tm_details))
        if min_length < len(tm_summaries) or min_length < len(tm_details):
            print(f"Aligning Ticketmaster results: {len(tm_summaries)} summaries, {len(tm_details)} details -> {min_length}")
            tm_summaries = tm_summaries[:min_length]
            tm_details = tm_details[:min_length]
        
    except Exception as e:
        print(f"Error searching Ticketmaster: {e}")
        tm_summaries, tm_details = [], []
    
    # Combine results, prioritizing local database events
    print(f"Combining: {len(local_summaries)} local + {len(tm_summaries)} Ticketmaster events")
    all_summaries = local_summaries + tm_summaries
    all_details = local_details + tm_details
    
    # Ensure lists are aligned
    if len(all_summaries) != len(all_details):
        min_length = min(len(all_summaries), len(all_details))
        print(f"Final alignment: {len(all_summaries)} summaries, {len(all_details)} details -> {min_length}")
        all_summaries = all_summaries[:min_length]
        all_details = all_details[:min_length]
    
    # Remove duplicates and limit results
    seen_names = set()
    unique_summaries = []
    unique_details = []
    
    for i in range(len(all_summaries)):
        if i < len(all_details):  # Double-check bounds
            event_name = all_details[i].get('name', '').lower()
            if event_name not in seen_names:
                seen_names.add(event_name)
                unique_summaries.append(all_summaries[i])
                unique_details.append(all_details[i])
    
    print(f"Final result: {len(unique_summaries)} unique events")
    return unique_summaries[:15], unique_details[:15]  # Limit to 15 events


def format_events_for_chat(summaries: List[str], details: List[Dict]) -> str:
    """Format events in a clean, non-cluttered way for chat display."""
    if not summaries:
        return "No events found matching your criteria."
    
    # Group events by type/category for better organization
    event_groups = {}
    
    for i, (summary, detail) in enumerate(zip(summaries, details)):
        # Determine event type from various sources
        event_type = None
        
        # First, try to get from categories (local events)
        if detail.get('categories'):
            category = detail['categories'][0]  # Take first category
            if category == 'music':
                event_type = 'Music & Entertainment'
            elif category == 'food':
                event_type = 'Food & Culinary'
            elif category == 'business':
                event_type = 'Business & Networking'
            elif category == 'cultural':
                event_type = 'Cultural Events'
            elif category == 'arts':
                event_type = 'Arts & Crafts'
            else:
                event_type = category.title()
        
        # If no category, try to detect from Ticketmaster data
        elif detail.get('artist') or 'concert' in summary.lower() or 'music' in summary.lower():
            event_type = 'Music & Entertainment'
        elif 'festival' in summary.lower() and ('food' in summary.lower() or 'culinary' in summary.lower()):
            event_type = 'Food & Culinary'
        elif 'business' in summary.lower() or 'networking' in summary.lower():
            event_type = 'Business & Networking'
        elif 'cultural' in summary.lower() or 'traditional' in summary.lower():
            event_type = 'Cultural Events'
        elif 'sports' in summary.lower() or 'game' in summary.lower():
            event_type = 'Sports & Recreation'
        
        # Default fallback
        if not event_type:
            # Check if it's a Ticketmaster event (has artist field)
            if detail.get('artist'):
                event_type = 'Live Events (Ticketmaster)'
            else:
                event_type = 'General Events'
        
        if event_type not in event_groups:
            event_groups[event_type] = []
        event_groups[event_type].append(f"{i+1}. {summary}")
    
    # Format output with better organization
    formatted_output = []
    
    if len(event_groups) == 1:
        # Single category - simple list
        formatted_output.extend(list(event_groups.values())[0])
    else:
        # Multiple categories - grouped display with local events first
        # Sort to prioritize local event categories
        category_priority = {
            'Food & Culinary': 1,
            'Business & Networking': 2,
            'Cultural Events': 3,
            'Arts & Crafts': 4,
            'Music & Entertainment': 5,
            'Live Events (Ticketmaster)': 6,
            'Sports & Recreation': 7,
            'General Events': 8
        }
        
        sorted_categories = sorted(event_groups.keys(), 
                                 key=lambda x: category_priority.get(x, 9))
        
        for category in sorted_categories:
            events = event_groups[category]
            formatted_output.append(f"\n**{category}:**")
            formatted_output.extend(events)
    
    return "\n".join(formatted_output) 


def parse_evt_txt(file_path: str = "evt.txt") -> list:
    """Parse evt.txt and return a list of event dicts with name, date, location."""
    events = []
    print(f"[DEBUG] Starting to parse {file_path}")
    
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    print(f"[DEBUG] Read {len(lines)} lines from {file_path}")
    
    # Debug: Show first few lines to understand the format
    print(f"[DEBUG] First 10 lines:")
    for i in range(min(10, len(lines))):
        print(f"[DEBUG] Line {i}: '{lines[i].strip()}'")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Debug: Show what line we're processing
        if line and not line.startswith("#") and not line.startswith("---"):
            print(f"[DEBUG] Processing line {i}: '{line[:50]}...'")
        
        # Skip empty lines, comments (single #), and section separators
        if not line or line.startswith("# ") or line.startswith("---"):
            if line.startswith("# "):
                print(f"[DEBUG] Skipping comment/header: '{line[:30]}...'")
            i += 1
            continue
        
        # Detect event headers (### or ####) - these are NOT comments, they are event names!
        if line.startswith("### ") or line.startswith("#### "):
            event_name = line.replace("### ", "").replace("#### ", "").strip()
            print(f"[DEBUG] Found event header: '{event_name}'")
            
            # Look ahead for event details
            event_data = {"name": event_name, "date": None, "location": None, "venue": None}
            
            j = i + 1
            while j < len(lines) and j < i + 20:  # Look ahead up to 20 lines
                next_line = lines[j].strip()
                
                # Stop at next event header or major section
                if next_line.startswith("### ") or next_line.startswith("#### ") or next_line.startswith("## "):
                    print(f"[DEBUG] Stopping at next header: '{next_line[:30]}...'")
                    break
                
                # Parse date
                if next_line.startswith("**Date:**"):
                    date_value = next_line.replace("**Date:**", "").strip()
                    event_data["date"] = date_value
                    print(f"[DEBUG] Found date: {date_value}")
                
                # Parse location
                elif next_line.startswith("**Location:**"):
                    location_value = next_line.replace("**Location:**", "").strip()
                    event_data["location"] = location_value
                    print(f"[DEBUG] Found location: {location_value}")
                
                # Parse venue
                elif next_line.startswith("**Venue:**"):
                    venue_value = next_line.replace("**Venue:**", "").strip()
                    event_data["venue"] = venue_value
                    print(f"[DEBUG] Found venue: {venue_value}")
                
                # Parse upcoming dates (for recurring events)
                elif next_line.startswith("**Upcoming Dates:**") or next_line.startswith("**Dates:**"):
                    dates_value = next_line.replace("**Upcoming Dates:**", "").replace("**Dates:**", "").strip()
                    print(f"[DEBUG] Found recurring dates: {dates_value}")
                    
                    # Create individual events for each date
                    if dates_value:
                        date_parts = [d.strip() for d in dates_value.split("|")]
                        for date_part in date_parts:
                            if date_part.strip():
                                # Parse the date part (e.g., "August 3, 10, 17, 24, 31")
                                date_matches = re.findall(r'([A-Za-z]+)\s+(\d+)', date_part)
                                for month, day in date_matches:
                                    year = "2025"  # Default year
                                    full_date = f"{month} {day}, {year}"
                                    
                                    # Create individual event entry
                                    individual_event = {
                                        "name": event_name,
                                        "date": full_date,
                                        "location": event_data.get("location"),
                                        "venue": event_data.get("venue")
                                    }
                                    events.append(individual_event)
                                    print(f"[DEBUG] Created recurring event: {event_name} - {full_date}")
                    
                    # Don't add the main event since we created individual ones
                    break
                
                # Parse bullet point dates (for some events)
                elif next_line.startswith("- ") and ("2025" in next_line or "2026" in next_line):
                    # Extract date from bullet point
                    date_match = re.search(r'([A-Za-z]+ \d+,? \d{4})', next_line)
                    if date_match:
                        date_value = date_match.group(1)
                        individual_event = {
                            "name": event_name,
                            "date": date_value,
                            "location": event_data.get("location"),
                            "venue": event_data.get("venue")
                        }
                        events.append(individual_event)
                        print(f"[DEBUG] Created bullet point event: {event_name} - {date_value}")
                
                j += 1
            
            # If we didn't create recurring events, add the main event
            if event_data.get("date") and not any(e["name"] == event_name and e["date"] != event_data["date"] for e in events):
                events.append(event_data)
                print(f"[DEBUG] Added single event: {event_name} - {event_data.get('date')}")
        
        i += 1
    
    # Debug: Print all parsed events
    print(f"[DEBUG] Total events parsed: {len(events)}")
    for e in events:
        print(f"[DEBUG] Final event: name='{e.get('name')}', location='{e.get('location')}', date='{e.get('date')}', venue='{e.get('venue')}'")
    
    # Filter out events without a name or date
    filtered_events = [e for e in events if e.get("name") and e.get("date")]
    print(f"[DEBUG] Filtered events (with name and date): {len(filtered_events)}")
    
    return filtered_events

ISLAND_CITY_MAP = {
    "oahu": [
        "Honolulu", "Kailua", "Pearl City", "Waipahu", "Kaneohe", "Mililani", "Ewa Beach", "Aiea", "Kapolei", "Wahiawa", "Haleiwa", "Laie", "Hauula", "Waimanalo", "Makaha", "Waialua", "Waianae", "Schofield Barracks"
    ],
    "maui": [
        "Kahului", "Lahaina", "Kihei", "Wailuku", "Pukalani", "Makawao", "Paia", "Hana", "Kula", "Napili-Honokowai", "Maalaea"
    ],
    "big island": [
        "Hilo", "Kailua-Kona", "Waimea", "Kealakekua", "Pahoa", "Volcano", "Hawi", "Honokaa", "Keaau", "Kamuela", "Ocean View", "Mountain View", "Papaikou", "Pepeekeo"
    ],
    "kauai": [
        "Lihue", "Kapaa", "Hanalei", "Koloa", "Princeville", "Waimea", "Kalaheo", "Hanapepe", "Kekaha", "Wailua"
    ],
}

def get_island_city_list_str():
    """Return a user-friendly string listing all major cities/towns for each island."""
    lines = ["Here's how I match events to islands and cities:"]
    for island, cities in ISLAND_CITY_MAP.items():
        lines.append(f"- {island.title()}: {', '.join(cities)}")
    return '\n'.join(lines)

def get_evt_txt_events(location: str, is_island: bool = False) -> list:
    print(f"[DEBUG] get_evt_txt_events called with location='{location}', is_island={is_island}")
    events = parse_evt_txt()
    print(f"[DEBUG] parse_evt_txt returned {len(events)} total events")
    location = location.lower()
    print(f"[DEBUG] Looking for events matching location: '{location}'")
    if is_island and location in ISLAND_CITY_MAP:
        cities = ISLAND_CITY_MAP[location]
        print(f"[DEBUG] Island search - checking cities: {cities}")
        matching_events = []
        for e in events:
            if e.get("location"):
                event_location = e["location"].lower()
                event_name = e.get("name", "").lower()
                for city in cities:
                    city_l = city.lower()
                    if city_l in event_location or city_l in event_name:
                        matching_events.append(e)
                        break
        print(f"[DEBUG] Island search found {len(matching_events)} matching events")
        return matching_events
    else:
        print(f"[DEBUG] City search - looking for '{location}' in event locations")
        matching_events = []
        for e in events:
            if e.get("location"):
                event_location = e["location"].lower()
                event_name = e.get("name", "").lower()
                if location in event_location or location in event_name:
                    matching_events.append(e)
        print(f"[DEBUG] City search found {len(matching_events)} matching events")
        return matching_events

def format_unified_event(event: dict) -> str:
    """Format an event dict as 'Name - Date at Location'."""
    name = event.get("name", "Unknown Event")
    date = event.get("date", "TBD")
    location = event.get("location", "TBD")
    return f"{name} - {date} at {location}" 

def filter_evt_txt_events_by_topic(events: list, topic: str) -> list:
    """Filter evt.txt events by topic/type using LLM semantic matching."""
    if not topic or topic in ['all', 'all events', 'everything', 'any']:
        return events
    try:
        from langchain.chat_models import ChatOpenAI
        llm = ChatOpenAI(temperature=0)
        # Prepare prompt for LLM
        event_context = "\n".join([
            f"Event: {e.get('name', '')}\nDescription: {e.get('description', '') if e.get('description') else ''}\nLocation: {e.get('location', '')}\nDate: {e.get('date', '')}"
            for e in events
        ])
        filter_prompt = f"""You are filtering a list of events for a user who is interested in events related to '{topic}'.

Here are the events:
{event_context}

Return ONLY a JSON list of the indexes (0-based) of the events that match the topic '{topic}'.
If none match, return []."""
        response = llm.predict(filter_prompt).strip()
        import json
        try:
            matching_indexes = json.loads(response)
            return [events[i] for i in matching_indexes if 0 <= i < len(events)]
        except json.JSONDecodeError:
            return []
    except Exception as e:
        print(f"[DEBUG] LLM topic filtering failed: {e}")
        return []

# Update unified_event_search to use topic filtering for evt.txt events

def unified_event_search(query: str, location: str, is_island: bool = False, start_date: str = None, end_date: str = None) -> Tuple[List[str], List[Dict]]:
    """Combine evt.txt and Ticketmaster events for a city or island, return unified formatted results. Includes debug logging."""
    from datetime import datetime
    import re
    # 1. Get evt.txt events
    evt_events = get_evt_txt_events(location, is_island)
    # Filter by topic/type if needed
    filtered_evt_events = filter_evt_txt_events_by_topic(evt_events, query)
    # --- DATE FILTERING FOR EVT.TXT EVENTS ---
    def parse_event_date(date_str):
        # Try to parse common date formats, fallback to None
        if not date_str:
            return None
        try:
            # Try 'Month Day, Year' (e.g., 'August 3, 2025')
            return datetime.strptime(date_str, '%B %d, %Y')
        except Exception:
            pass
        try:
            # Try 'Month Day Year' (e.g., 'August 3 2025')
            return datetime.strptime(date_str, '%B %d %Y')
        except Exception:
            pass
        try:
            # Try 'YYYY-MM-DD'
            return datetime.strptime(date_str, '%Y-%m-%d')
        except Exception:
            pass
        # Try to extract date from string using regex
        match = re.search(r'([A-Za-z]+) (\d{1,2}), (\d{4})', date_str)
        if match:
            try:
                return datetime.strptime(match.group(0), '%B %d, %Y')
            except Exception:
                pass
        return None
    # Default date range: next 30 days
    now = datetime.now()
    if not start_date:
        start_date_dt = now
    else:
        try:
            start_date_dt = datetime.strptime(start_date[:10], '%Y-%m-%d')
        except Exception:
            start_date_dt = now
    if not end_date:
        end_date_dt = now.replace(hour=23, minute=59, second=59) + timedelta(days=30)
    else:
        try:
            end_date_dt = datetime.strptime(end_date[:10], '%Y-%m-%d')
        except Exception:
            end_date_dt = now.replace(hour=23, minute=59, second=59) + timedelta(days=30)
    # Filter events by date
    filtered_evt_events = [e for e in filtered_evt_events if parse_event_date(e.get('date')) and start_date_dt <= parse_event_date(e.get('date')) <= end_date_dt]
    print(f"[DEBUG] evt.txt events for location '{location}' (is_island={is_island}): {len(filtered_evt_events)} after topic/date filter '{query}'")
    for e in filtered_evt_events:
        print(f"[DEBUG] evt.txt event: {e}")
    evt_summaries = [format_unified_event(e) for e in filtered_evt_events]
    evt_details = filtered_evt_events

    # 2. Get Ticketmaster events (logic unchanged)
    from events import search_ticketmaster_events
    tm_summaries, tm_details = [], []
    if is_island and location.lower() in ISLAND_CITY_MAP:
        for city in ISLAND_CITY_MAP[location.lower()]:
            s, d = search_ticketmaster_events(query, city, start_date, end_date)
            print(f"[DEBUG] Ticketmaster events for city '{city}': {len(s)} found")
            for detail in d:
                print(f"[DEBUG] Ticketmaster event: {detail}")
            tm_summaries.extend(s)
            tm_details.extend(d)
    else:
        tm_summaries, tm_details = search_ticketmaster_events(query, location, start_date, end_date)
        print(f"[DEBUG] Ticketmaster events for location '{location}': {len(tm_summaries)} found")
        for detail in tm_details:
            print(f"[DEBUG] Ticketmaster event: {detail}")

    def format_tm_event(detail):
        name = detail.get("name", "Unknown Event")
        date = detail.get("date", "TBD")
        venue = detail.get("venue", "TBD")
        return f"{name} - {date} at {venue}"
    tm_summaries_fmt = [format_tm_event(d) for d in tm_details]

    all_summaries = evt_summaries + tm_summaries_fmt
    all_details = evt_details + tm_details
    seen = set()
    unique_summaries = []
    unique_details = []
    for s, d in zip(all_summaries, all_details):
        key = s.lower()
        if key not in seen:
            seen.add(key)
            unique_summaries.append(s)
            unique_details.append(d)
    print(f"[DEBUG] Unified event list: {len(unique_summaries)} unique events returned")
    return unique_summaries, unique_details 