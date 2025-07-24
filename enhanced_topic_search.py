from typing import List, Dict, Optional, Tuple
import streamlit as st
from langchain.chat_models import ChatOpenAI
from enhanced_events import EnhancedEventManager, enhanced_search_events, format_events_for_chat, unified_event_search, ISLAND_CITY_MAP
import json


class TopicBasedEventSearch:
    """Handles intelligent topic-based event searches and user interaction."""
    
    def __init__(self):
        self.manager = EnhancedEventManager()
        
    def detect_topic_request(self, query: str) -> Optional[List[str]]:
        """Detect if user is asking for events related to specific topics."""
        try:
            llm = ChatOpenAI(temperature=0)
            
            detection_prompt = f"""Analyze this user query to determine if they're asking for events related to specific topics or categories.

User query: "{query}"

If the user is asking for events related to specific topics, extract those topics. Consider:
- Music/concert requests: "jazz concerts", "classical music", "rock shows"
- Food events: "food festivals", "cooking classes", "wine tasting"
- Arts/culture: "art exhibitions", "theater shows", "cultural events"
- Sports: "basketball games", "football matches", "sports events"
- Business/networking: "business events", "networking", "conferences"
- Educational: "workshops", "seminars", "lectures"
- Family/kids: "family events", "kids activities", "children shows"

Return ONLY a JSON list of topics if found, or null if this is not a topic-based event request.

Examples:
- "Find me some jazz concerts" → ["jazz", "music", "concerts"]
- "Any food festivals happening?" → ["food", "festivals"]
- "Show me business networking events" → ["business", "networking"]
- "What events are in Honolulu?" → null (location-based, not topic-based)
- "Add event 1 to my calendar" → null (not a search request)

Response:"""

            response = llm.predict(detection_prompt).strip()
            
            try:
                topics = json.loads(response)
                return topics if topics else None
            except json.JSONDecodeError:
                return None
                
        except Exception as e:
            print(f"Error detecting topics: {e}")
            return None
    
    def search_with_topics(self, query: str, topics: List[str], city: str = None) -> Tuple[List[str], List[Dict], bool]:
        """Search for events with specific topics and return results with uncertainty flag."""
        try:
            # Use enhanced search with topics
            summaries, details = enhanced_search_events(
                query=query,
                city=city or "Honolulu",  # Default to Honolulu
                topics=topics
            )
            
            # Check if we have uncertain events to show
            uncertain_events = self.manager.get_uncertain_events()
            has_uncertain = len(uncertain_events) > 0
            
            return summaries, details, has_uncertain
            
        except Exception as e:
            print(f"Error in topic search: {e}")
            return [], [], False
    
    def offer_uncertain_events(self) -> str:
        """Create a message offering to show uncertain events."""
        uncertain_events = self.manager.get_uncertain_events()
        
        if not uncertain_events:
            return ""
        
        count = len(uncertain_events)
        return f"\n\nI also have {count} event(s) that I'm not completely sure about based on their titles and descriptions. Would you like me to show you these events so you can decide if they interest you?"
    
    def show_uncertain_events(self) -> str:
        """Format and show uncertain events to the user."""
        uncertain_events = self.manager.get_uncertain_events()
        
        if not uncertain_events:
            return "No uncertain events to show."
        
        formatted_events = []
        formatted_events.append("**Events I'm uncertain about:**")
        formatted_events.append("*(These events had unclear descriptions or titles)*\n")
        
        for i, uncertain_entry in enumerate(uncertain_events):
            event = uncertain_entry['event']
            reason = uncertain_entry['reason']
            
            name = event.get('name', 'Unknown Event')
            date = event.get('date', 'TBD')
            venue = event.get('venue', 'TBD')
            description = event.get('description', 'No description available')
            
            formatted_events.append(f"{i+1}. **{name}**")
            formatted_events.append(f"   📅 Date: {date}")
            formatted_events.append(f"   📍 Venue: {venue}")
            formatted_events.append(f"   📝 Description: {description}")
            formatted_events.append(f"   ❓ Reason for uncertainty: {reason}")
            formatted_events.append("")
        
        formatted_events.append("Let me know if any of these interest you!")
        
        return "\n".join(formatted_events)
    
    def handle_user_topic_selection(self, user_response: str, available_topics: List[str]) -> List[str]:
        """Handle user's response when asked about topic preferences."""
        try:
            llm = ChatOpenAI(temperature=0)
            
            selection_prompt = f"""The user was asked about their event topic preferences and responded: "{user_response}"

Available topics detected from their original query: {available_topics}

Determine which specific topics they want to focus on. Return ONLY a JSON list of selected topics.

Examples:
- "Just music events please" → ["music", "concerts"]
- "Food and business events" → ["food", "business"]
- "All of them" → {available_topics}
- "Just the jazz stuff" → ["jazz", "music"]
- "None, show me everything" → []

Response:"""

            response = llm.predict(selection_prompt).strip()
            
            try:
                selected_topics = json.loads(response)
                return selected_topics if selected_topics else []
            except json.JSONDecodeError:
                return available_topics  # Default to all detected topics
                
        except Exception as e:
            print(f"Error handling topic selection: {e}")
            return available_topics


class EnhancedEventConversationFlow:
    """Manages the enhanced conversation flow for event searches with topic filtering."""
    
    def __init__(self):
        self.topic_search = TopicBasedEventSearch()
        self.manager = EnhancedEventManager()
        
        # Initialize state if not exists
        if 'enhanced_event_state' not in st.session_state:
            st.session_state.enhanced_event_state = {
                'awaiting_topic_selection': False,
                'detected_topics': [],
                'original_query': '',
                'city': None,
                'showing_uncertain': False
            }
    
    def process_event_query(self, query: str, city: str = None) -> str:
        """Process an event search query with enhanced topic detection and unified event search."""
        # Detect topics in the query
        detected_topics = self.topic_search.detect_topic_request(query)
        
        # If the user provided a location (city or island), use unified_event_search
        if city:
            is_island = city.lower() in ISLAND_CITY_MAP
            summaries, details = unified_event_search(query, city, is_island)
            st.session_state.last_found_events = summaries
            st.session_state.last_found_events_details = details
            response_parts = []
            if summaries:
                response_parts.append(f"Aloha! Here are the upcoming events in {city.title()}:")
                for i, summary in enumerate(summaries):
                    response_parts.append(f"{i+1}. {summary}")
                response_parts.append("\nWould you like me to add any of these to your calendar?")
            else:
                response_parts.append(f"I couldn't find any events in {city.title()} for the next month. Would you like to try a different location or see uncertain events?")
            return "\n".join(response_parts)
        
        # If multiple topics detected, ask user to narrow down or see all events
        if detected_topics and len(detected_topics) > 2:
            st.session_state.enhanced_event_state.update({
                'awaiting_topic_selection': True,
                'detected_topics': detected_topics,
                'original_query': query,
                'city': city
            })
            topics_str = ", ".join(detected_topics)
            return (
                f"I detected you're interested in events related to: {topics_str}. "
                "Would you like me to show events for all these topics, or would you prefer to focus on specific ones? "
                "If you don't want to choose a type, just say 'show me all events' and I'll list everything available in your area."
            )
        
        # Otherwise, fallback to the old topic-based search (for non-location queries)
        summaries, details, has_uncertain = self.topic_search.search_with_topics(
            query, detected_topics or [], city
        )
        st.session_state.last_found_events = summaries
        st.session_state.last_found_events_details = details
        response_parts = []
        if summaries:
            if detected_topics:
                response_parts.append(f"Aloha! I found these events for you:")
            else:
                response_parts.append(f"Aloha! Here are all the events I have available:")
            response_parts.append(format_events_for_chat(summaries, details))
            response_parts.append("\nWould you like me to add any of these to your calendar?")
            uncertain_offer = self.topic_search.offer_uncertain_events()
            if uncertain_offer:
                response_parts.append(uncertain_offer)
        else:
            if detected_topics:
                response_parts.append("I couldn't find any events matching your criteria in our database.")
            else:
                response_parts.append("I don't have any events in our database for that location.")
            uncertain_offer = self.topic_search.offer_uncertain_events()
            if uncertain_offer:
                response_parts.append(uncertain_offer)
            else:
                response_parts.append("I can search for events in a different city or time period if you'd like.")
        return "\n".join(response_parts)
    
    def handle_topic_selection_response(self, response: str) -> str:
        """Handle user's response to topic selection."""
        state = st.session_state.enhanced_event_state
        
        if not state['awaiting_topic_selection']:
            return "I'm not currently waiting for topic selection."
        
        # Process the user's topic selection
        selected_topics = self.topic_search.handle_user_topic_selection(
            response, state['detected_topics']
        )
        
        # Search with selected topics
        summaries, details, has_uncertain = self.topic_search.search_with_topics(
            state['original_query'], selected_topics, state['city']
        )
        
        # Store results
        st.session_state.last_found_events = summaries
        st.session_state.last_found_events_details = details
        
        # Reset state
        st.session_state.enhanced_event_state['awaiting_topic_selection'] = False
        
        # Format response
        if summaries:
            response_parts = [
                f"Great! Here are the events for your selected topics:",
                format_events_for_chat(summaries, details),
                "\nWould you like me to add any of these to your calendar?"
            ]
            
            # Offer uncertain events
            uncertain_offer = self.topic_search.offer_uncertain_events()
            if uncertain_offer:
                response_parts.append(uncertain_offer)
                
            return "\n".join(response_parts)
        else:
            return "I couldn't find any events matching your selected topics. Would you like to try different topics or see uncertain events?"
    
    def handle_uncertain_events_request(self, response: str) -> Optional[str]:
        """Handle user's request to see uncertain events."""
        response_lower = response.lower().strip()
        
        # Check if user wants to see uncertain events
        # More comprehensive detection patterns
        if any(phrase in response_lower for phrase in [
            "show uncertain", "show the uncertain", "see uncertain", "see the uncertain",
            "show those events", "show them", "yes show", "yes, show", "sure show", "sure, show",
            "yes please", "show me those", "let me see", "i want to see", "yes i would like",
            "yes i'd like", "sure let me see", "okay show", "ok show", "display them",
            "show me them", "let's see them", "i'd like to see them", "yes show me"
        ]):
            st.session_state.enhanced_event_state['showing_uncertain'] = True
            return self.topic_search.show_uncertain_events()
        
        # Also check for simple confirmations when uncertain events were just offered
        if response_lower in ["yes", "yep", "sure", "ok", "okay", "please", "show", "show me"]:
            # Check if uncertain events were recently offered (within last 2 conversation turns)
            if hasattr(st.session_state, 'chat_history') and len(st.session_state.chat_history) >= 2:
                # Check the last bot message for uncertain event offer
                last_bot_message = None
                for msg in reversed(st.session_state.chat_history):
                    if hasattr(msg, 'content') and isinstance(msg.content, str):
                        if "not completely sure about" in msg.content or "uncertain" in msg.content:
                            last_bot_message = msg.content
                            break
                
                if last_bot_message and "would you like me to show you these events" in last_bot_message.lower():
                    st.session_state.enhanced_event_state['showing_uncertain'] = True
                    return self.topic_search.show_uncertain_events()
        
        return None
    
    def track_event_addition(self, events: List[Dict]):
        """Track when user adds events to their calendar."""
        for event in events:
            self.manager.track_user_event_interest(event, "added_to_calendar")
    
    def is_topic_selection_pending(self) -> bool:
        """Check if we're waiting for topic selection."""
        return st.session_state.enhanced_event_state.get('awaiting_topic_selection', False)


def integrate_enhanced_events_with_existing_flow():
    """Integration function to be called from main app.py"""
    flow = EnhancedEventConversationFlow()
    
    # This will be called from the main conversation handler
    return flow 