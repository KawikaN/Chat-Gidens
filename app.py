import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS, Chroma
from langchain.memory import ConversationSummaryBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from htmlTemplates import bot_template, user_template, css
from events import search_ticketmaster_events
# Enhanced event management imports
from enhanced_events import EnhancedEventManager, enhanced_search_events, format_events_for_chat, unified_event_search, ISLAND_CITY_MAP
from enhanced_topic_search import EnhancedEventConversationFlow, integrate_enhanced_events_with_existing_flow
# Calendar integration imports
from calendarTest import (
    get_credentials,
    check_google_calendar_access,
    initiate_oauth_flow,
    add_event_to_google_calendar,
    add_events_to_calendar,
    test_calendar_integration,
    parse_event_string
)
import datetime
import json
import os
import pickle
import webbrowser
import requests
from langchain.schema import AIMessage, HumanMessage
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from langchain.schema.retriever import BaseRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.schema import Document
from typing import List, Callable, Dict
import shutil
import chromadb
import re
import difflib

# Cache calendar access status to prevent multiple API calls
# @st.cache_data(ttl=30)  # DISABLED - causes issues with calendar API
def cached_check_google_calendar_access():
    """Cached version of calendar access check to prevent multiple API calls."""
    return check_google_calendar_access()

def get_calendar_status_for_sidebar():
    """Get calendar status specifically for sidebar display, with longer caching."""
    # Use session state to cache status for the entire session unless explicitly cleared
    if 'sidebar_calendar_status' not in st.session_state or st.session_state.get('force_calendar_status_refresh', False):
        try:
            has_access, message = check_google_calendar_access()
            st.session_state.sidebar_calendar_status = (has_access, message)
            st.session_state.force_calendar_status_refresh = False
        except Exception as e:
            st.session_state.sidebar_calendar_status = (False, f"Error checking status: {str(e)}")
    
    return st.session_state.sidebar_calendar_status

def filter_events_to_add(query: str, all_event_summaries: List[str], all_event_details: List[dict]) -> List[dict] or None:
    """
    Parses a user's query to determine which events to add to the calendar.
    Uses LLM understanding as the primary method for interpreting user requests.

    Args:
        query: The user's request string.
        all_event_summaries: The list of event summary strings shown to the user.
        all_event_details: The list of detailed event dictionaries.

    Returns:
        A list of specific event detail dictionaries to be added.
        Returns an empty list if specific events are requested but none match.
        Returns None if the query is ambiguous and needs clarification.
        Returns "QUESTION" if the user is asking a question about the events.
    """
    query_lower = query.lower()
    
    # Only handle the most obvious cases directly, let LLM handle everything else
    
    # Case 1: Very simple confirmations that need clarification
    if query_lower.strip() in ["yes", "yep", "ok", "sure", "please"]:
        return None  # Signal for clarification since this is ambiguous

    # Case 2: Clear cancellation patterns
    if any(pattern in query_lower for pattern in ["cancel", "never mind", "don't add", "no thanks", "none"]):
        return []

    # For everything else, use the LLM to understand the user's intent
    try:
        # Create a context-aware prompt for the LLM
        event_list_context = "\n".join([f"{i+1}. {summary}" for i, summary in enumerate(all_event_summaries)])
        
        llm_prompt = f"""You are helping a user select events to add to their calendar. The user has been shown this list of events:

{event_list_context}

The user just said: "{query}"

Your task is to determine what the user wants to do. Respond with ONLY one of these exact formats:

1. If they want specific events by number: "EVENTS:[1,3,5]" (list the numbers)
2. If they want all events: "ALL_EVENTS"
3. If they want events by name/artist and you can identify them: "EVENTS:[numbers]" (convert to numbers)
4. If they're asking a question or need clarification: "QUESTION:[their question/concern]"
5. If they want to cancel/don't want to add any: "CANCEL"

Examples:
- "Add the first two cirque du soleil events" → Look for Cirque du Soleil events and return their numbers like "EVENTS:[2,4]"
- "Can I get more details about the first event?" → "QUESTION:Can I get more details about the first event?"
- "Add the Jake Shimabukuro ones" → Look for Jake Shimabukuro events and return their numbers
- "What time is the concert?" → "QUESTION:What time is the concert?"
- "Add events 1 and 3" → "EVENTS:[1,3]"
- "I want all of them" → "ALL_EVENTS"
- "Never mind" → "CANCEL"

Important: Pay close attention to what the user actually asked for. If they mention specific artist names or event types, find those exact events in the list, not similar-sounding ones.

Respond with the appropriate format:"""

        # Get LLM interpretation
        from langchain.chat_models import ChatOpenAI
        llm = ChatOpenAI(temperature=0)  # Low temperature for consistent classification
        
        llm_response = llm.predict(llm_prompt).strip()
        
        # Parse LLM response
        if llm_response.startswith("EVENTS:["):
            # Extract event numbers
            numbers_str = llm_response[8:-1]  # Remove "EVENTS:[" and "]"
            try:
                indices = [int(x.strip()) - 1 for x in numbers_str.split(",")]
                events_to_add_details = []
                for i in indices:
                    if 0 <= i < len(all_event_details):
                        events_to_add_details.append(all_event_details[i])
                return events_to_add_details
            except:
                return None  # Invalid format, ask for clarification
                
        elif llm_response == "ALL_EVENTS":
            return all_event_details

        elif llm_response.startswith("QUESTION:[") or llm_response == "CANCEL":
            # User has a question or wants to cancel - let the main conversation handle this
            return "QUESTION"  # Special return value to indicate this should go to the main LLM
            
        else:
            # Unexpected LLM response format, ask for clarification
            return None
            
    except Exception as e:
        # If LLM fails, fall back to asking for clarification
        print(f"LLM classification failed: {e}")
        return None

# --- Manual Event Creator ---
class ManualEventCreator:
    """Manages the conversation flow for manually creating calendar events."""

    def __init__(self):
        if 'manual_event_state' not in st.session_state:
            st.session_state.manual_event_state = {
                "creating_event": False,
                "event_data": {},
                "awaiting_field": None,
                "original_query": None,
            }

    @property
    def state(self):
        return st.session_state.manual_event_state

    def is_manual_event_query(self, query: str) -> bool:
        """Check if a query is asking to create a manual event."""
        query_lower = query.lower()
        
        # Keywords that indicate manual event creation
        create_keywords = [
            "create event", "add event", "make event", "schedule event",
            "create appointment", "add appointment", "schedule appointment",
            "add to calendar", "put in calendar", "create calendar event",
            "schedule meeting", "book appointment", "set reminder",
            "add an event", "create an event", "make an event",
            "schedule an event", "book an event", "plan an event"
        ]
        
        # Check for exact matches first (highest priority)
        if any(keyword in query_lower for keyword in create_keywords):
            return True
        
        # Check for patterns with creation verbs followed by event-related words
        creation_verbs = ["create", "add", "make", "schedule", "book", "plan", "set"]
        event_words = ["event", "appointment", "meeting", "reminder", "calendar"]
        
        # Split query into words
        words = query_lower.split()
        
        # Look for creation verb + event word pattern
        for i, word in enumerate(words):
            if word in creation_verbs:
                # Check if an event word appears within next few words
                for j in range(i+1, min(i+4, len(words))):
                    if words[j] in event_words:
                        return True
        
        # Check for patterns like "schedule X on Y" or "add X to my calendar" 
        # where X could be any event name
        if any(verb in query_lower for verb in creation_verbs):
            if any(phrase in query_lower for phrase in ["on", "for", "at", "calendar", "tomorrow", "today", "next"]):
                return True
             
        return False

    def start_manual_event_creation(self, query: str):
        """Initiate the manual event creation flow."""
        self.state['creating_event'] = True
        self.state['original_query'] = query
        self.state['event_data'] = {}
        
        # Try to extract information from the initial query
        extracted_data = self._extract_event_info_from_query(query)
        self.state['event_data'].update(extracted_data)
        
        # Determine what information we still need
        missing_required = self._get_missing_required_fields()
        
        if missing_required:
            # Ask for the first missing required field
            return self._prompt_for_field(missing_required[0])
        else:
            # We have all required info, ask for optional details or confirm
            return self._offer_optional_details_or_confirm()

    def _extract_event_info_from_query(self, query: str) -> dict:
        """Extract event information from the user's query using LLM."""
        try:
            from langchain.chat_models import ChatOpenAI
            llm = ChatOpenAI(temperature=0)
            
            extraction_prompt = f"""Extract event information from this user request: "{query}"

Extract the following information if present:
- name: Event title/name
- date: Date in YYYY-MM-DD format (if relative like "tomorrow", convert to actual date)
- time: Time in HH:MM format (24-hour)
- description: Any additional details

Current date for reference: {datetime.datetime.now().strftime("%Y-%m-%d")}

Respond ONLY with a JSON object containing the extracted information. If information is not present, omit that field.
Example: {{"name": "Meeting with John", "date": "2024-01-15", "time": "14:30", "description": "Discuss project updates"}}

If you cannot extract any clear information, respond with: {{}}"""

            response = llm.predict(extraction_prompt).strip()
            
            # Try to parse JSON response
            import json
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {}
                
        except Exception as e:
            print(f"Error extracting event info: {e}")
            return {}

    def _get_missing_required_fields(self) -> list:
        """Get list of required fields that are missing."""
        required_fields = ['name', 'date']
        missing = []
        
        for field in required_fields:
            if field not in self.state['event_data'] or not self.state['event_data'][field]:
                missing.append(field)
                
        return missing

    def _prompt_for_field(self, field: str) -> str:
        """Generate a prompt asking for a specific field."""
        self.state['awaiting_field'] = field
        
        prompts = {
            'name': "What would you like to call this event? Please provide a name or title for your event.",
            'date': "What date is this event? Please provide the date (you can say 'tomorrow', 'next Friday', or a specific date like 'January 15th' or '2024-01-15').",
            'time': "What time is this event? Please provide the time (like '2:30 PM' or '14:30'). If you don't specify, I'll default to 7:00 PM.",
            'description': "Would you like to add any additional details or description for this event?"
        }
        
        return prompts.get(field, f"Please provide the {field} for this event.")

    def _offer_optional_details_or_confirm(self) -> str:
        """Offer to add optional details or confirm the event creation."""
        event_summary = self._format_event_summary()
        
        if 'time' not in self.state['event_data']:
            return f"Great! I have the essential information for your event:\n\n{event_summary}\n\nWhat time should this event be? (If you don't specify, I'll default to 7:00 PM)"
        elif 'description' not in self.state['event_data']:
            return f"Perfect! Here's your event:\n\n{event_summary}\n\nWould you like to add any additional details or description? Or should I go ahead and add this to your calendar as is?"
        else:
            return f"Here's your complete event:\n\n{event_summary}\n\nShould I add this to your calendar? Or would you like to modify anything?"

    def _format_event_summary(self) -> str:
        """Format the current event data into a readable summary."""
        data = self.state['event_data']
        summary_parts = []
        
        if 'name' in data:
            summary_parts.append(f"📅 **Event:** {data['name']}")
        if 'date' in data:
            summary_parts.append(f"📆 **Date:** {data['date']}")
        if 'time' in data:
            summary_parts.append(f"🕒 **Time:** {data['time']}")
        if 'description' in data:
            summary_parts.append(f"📝 **Details:** {data['description']}")
            
        return "\n".join(summary_parts)

    def handle_user_response(self, response: str):
        """Handle the user's response during event creation."""
        if not self.state['creating_event']:
            return None
        
        awaiting_field = self.state.get('awaiting_field')
        response_lower = response.lower().strip()
        
        # Prevent restarting event creation if already in progress
        # If user repeats a creation command, treat as confirmation
        creation_keywords = [
            "create event", "add event", "make event", "schedule event",
            "create appointment", "add appointment", "schedule appointment",
            "add to calendar", "put in calendar", "create calendar event",
            "schedule meeting", "book appointment", "set reminder",
            "add an event", "create an event", "make an event",
            "schedule an event", "book an event", "plan an event"
        ]
        if any(kw in response_lower for kw in creation_keywords):
            # If we're already creating, treat as confirmation
            return self._create_calendar_event()
        
        if awaiting_field:
            # User is providing information for a specific field
            if awaiting_field == 'date':
                parsed_date = self._parse_date_input(response)
                if parsed_date:
                    self.state['event_data']['date'] = parsed_date
                    self.state['awaiting_field'] = None
                else:
                    return "I couldn't understand that date. Please try again with a format like 'tomorrow', 'January 15th', or '2024-01-15'."
            elif awaiting_field == 'time':
                parsed_time = self._parse_time_input(response)
                if parsed_time:
                    self.state['event_data']['time'] = parsed_time
                    self.state['awaiting_field'] = None
                else:
                    return "I couldn't understand that time. Please try again with a format like '2:30 PM' or '14:30'."
            else:
                # For name and description, take the response as-is
                self.state['event_data'][awaiting_field] = response.strip()
                self.state['awaiting_field'] = None
            
            # Check if we need more required fields
            missing_required = self._get_missing_required_fields()
            if missing_required:
                return self._prompt_for_field(missing_required[0])
            else:
                return self._offer_optional_details_or_confirm()
        else:
            # User is either providing optional details or confirming
            # Check if user wants to confirm/proceed
            if any(word in response_lower for word in ['yes', 'add it', 'create it', 'go ahead', 'confirm', 'looks good', 'perfect']):
                return self._create_calendar_event()
            # Check if user wants to modify something
            elif any(word in response_lower for word in ['change', 'modify', 'edit', 'update', 'different']):
                return "What would you like to change? You can say things like 'change the time to 3 PM' or 'update the name to...'."
            # Check if user is declining optional details
            elif any(word in response_lower for word in ['no', 'skip', 'without', "don't need", 'just add it']):
                return self._create_calendar_event()
            # Otherwise, treat as additional details or modification
            else:
                return self._handle_modification_or_details(response)

    def _parse_date_input(self, date_input: str) -> str:
        """Parse various date input formats into YYYY-MM-DD."""
        try:
            from langchain.chat_models import ChatOpenAI
            llm = ChatOpenAI(temperature=0)
            
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            
            parse_prompt = f"""Convert this date input to YYYY-MM-DD format: "{date_input}"

Current date: {current_date}
Current day of week: {datetime.datetime.now().strftime("%A")}

Examples:
- "tomorrow" → {(datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")}
- "next Friday" → (calculate next Friday's date)
- "January 15th" → "2024-01-15" (use current year if not specified)
- "2024-01-15" → "2024-01-15"

Respond ONLY with the date in YYYY-MM-DD format or "INVALID" if the input cannot be parsed."""

            response = llm.predict(parse_prompt).strip()
            
            if response != "INVALID" and len(response) == 10 and response.count('-') == 2:
                return response
            else:
                return None
                
        except Exception as e:
            print(f"Error parsing date: {e}")
            return None

    def _parse_time_input(self, time_input: str) -> str:
        """Parse various time input formats into HH:MM format."""
        try:
            from langchain.chat_models import ChatOpenAI
            llm = ChatOpenAI(temperature=0)
            
            parse_prompt = f"""Convert this time input to 24-hour HH:MM format: "{time_input}"

Examples:
- "2:30 PM" → "14:30"
- "2:30pm" → "14:30"
- "14:30" → "14:30"
- "2 PM" → "14:00"
- "morning" → "09:00"
- "afternoon" → "14:00"
- "evening" → "19:00"

Respond ONLY with the time in HH:MM format or "INVALID" if the input cannot be parsed."""

            response = llm.predict(parse_prompt).strip()
            
            if response != "INVALID" and len(response) == 5 and response.count(':') == 1:
                return response
            else:
                return None
                
        except Exception as e:
            print(f"Error parsing time: {e}")
            return None

    def _handle_modification_or_details(self, response: str) -> str:
        """Handle modifications to existing event data or additional details."""
        response_lower = response.lower()
        
        # Check if this is a modification request
        if any(word in response_lower for word in ['change', 'time to', 'date to', 'name to', 'call it']):
            # Try to extract what they want to change using LLM
            try:
                from langchain.chat_models import ChatOpenAI
                llm = ChatOpenAI(temperature=0)
                
                current_data = self.state['event_data']
                
                modification_prompt = f"""The user wants to modify their event. Current event data: {current_data}

User said: "{response}"

What do they want to change? Respond with JSON containing the field(s) they want to update.

Examples:
- "change the time to 3 PM" → {{"time": "15:00"}}
- "update the name to Doctor Appointment" → {{"name": "Doctor Appointment"}}
- "change date to tomorrow" → {{"date": "2024-01-16"}} (calculate actual date)

Current date for reference: {datetime.datetime.now().strftime("%Y-%m-%d")}

Respond ONLY with valid JSON or {{}} if no clear modification is requested."""

                mod_response = llm.predict(modification_prompt).strip()
                
                import json
                modifications = json.loads(mod_response)
                
                if modifications:
                    self.state['event_data'].update(modifications)
                    return f"Updated! Here's your event now:\n\n{self._format_event_summary()}\n\nShould I add this to your calendar?"
                    
            except Exception as e:
                print(f"Error processing modification: {e}")
        
        # If not a modification, treat as additional description
        if 'description' not in self.state['event_data']:
            self.state['event_data']['description'] = response.strip()
        else:
            self.state['event_data']['description'] += f" {response.strip()}"
            
        return f"Added those details! Here's your complete event:\n\n{self._format_event_summary()}\n\nShould I add this to your calendar?"

    def _create_calendar_event(self) -> str:
        """Create the calendar event with the collected information."""
        try:
            event_data = self.state['event_data'].copy()
            
            # Ensure we have required fields
            if 'name' not in event_data or 'date' not in event_data:
                return "❌ Missing required information. Please provide at least an event name and date."
            
            # Set default time if not provided
            if 'time' not in event_data:
                event_data['time'] = "19:00"  # 7 PM default
            
            # Parse date and time into datetime objects
            event_date = event_data['date']
            event_time = event_data['time']
            
            try:
                event_datetime = datetime.datetime.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")
            except ValueError:
                return "❌ Error parsing date/time. Please check the format and try again."
            
            # Create end time (1 hour later by default)
            end_datetime = event_datetime + datetime.timedelta(hours=1)
            
            # Prepare the event for Google Calendar
            calendar_event = {
                'summary': event_data['name'],
                'description': event_data.get('description', f"Event created via Hawaii Business Assistant"),
                'start': {
                    'dateTime': event_datetime.isoformat(),
                    'timeZone': 'Pacific/Honolulu',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Pacific/Honolulu',
                },
            }
            
            # Store the event for calendar addition (using existing calendar logic)
            st.session_state['manual_event_to_add'] = calendar_event
            
            # Reset the manual event state
            self.reset()
            
            return f"✅ Perfect! I've prepared your event '{event_data['name']}' for {event_date} at {event_time}. Adding it to your calendar now..."
            
        except Exception as e:
            return f"❌ Error creating event: {str(e)}"

    def reset(self):
        """Reset the manual event creation state."""
        st.session_state.manual_event_state = {
            "creating_event": False,
            "event_data": {},
            "awaiting_field": None,
            "original_query": None,
        }

# --- Event Search Manager ---
class EventSearchManager:
    """Manages the conversation flow for searching events."""

    def __init__(self):
        if 'event_search_state' not in st.session_state:
            st.session_state.event_search_state = {
                "awaiting_city": False,
                "city": None,
                "start_date": None,
                "end_date": None,
                "original_query": None,
            }

    @property
    def state(self):
        return st.session_state.event_search_state

    def is_event_query(self, query: str) -> bool:
        """Check if a query is asking for events, with typo tolerance."""
        # First check if this is a manual event creation request - if so, it's NOT an event search
        manual_event_creator = ManualEventCreator()
        if manual_event_creator.is_manual_event_query(query):
            return False
        
        # Keywords for fuzzy matching (single words are better for this)
        event_keywords = [
            "event", "concert", "show", "game", "find", "music",
            "gig", "festival", "performance", "activities", "happening"
        ]
        # Keywords for exact matching (good for multi-word phrases)
        multi_word_keywords = [
            "find events", "live music", "things to do", "what's on", "what's happening"
        ]

        query_lower = query.lower()

        # Avoid triggering for calendar-add follow-ups if events have been found.
        if 'last_found_events' in st.session_state and st.session_state.last_found_events:
            if any(word in query_lower for word in ["add", "put", "schedule", "calendar", "yes", "yep", "ok"]):
                return False

        # 1. Check for exact multi-word keyword matches (fast and reliable)
        if any(kw in query_lower for kw in multi_word_keywords):
            return True

        # 2. Check for fuzzy matches on single words for typo tolerance
        # But exclude queries that clearly contain creation/scheduling intent
        creation_indicators = ["create", "add", "make", "schedule", "book", "plan"]
        if any(indicator in query_lower for indicator in creation_indicators):
            return False

        query_words = re.findall(r'\b\w+\b', query_lower)  # Split into words, handles punctuation
        for word in query_words:
            # If any word in the query is a close match to our keywords, trigger the search.
            # A cutoff of 0.8 handles small typos like 'vents' -> 'events'.
            if difflib.get_close_matches(word, event_keywords, n=1, cutoff=0.8):
                return True

        return False

    def start_event_search(self, query: str):
        """Initiate the event search flow."""
        # When starting a new search, clear any previously found events from the context.
        if 'last_found_events' in st.session_state:
            del st.session_state['last_found_events']
        if 'last_found_events_details' in st.session_state:
            del st.session_state['last_found_events_details']
            
        self.state['awaiting_city'] = True
        self.state['original_query'] = query
        return "Aloha! To find events for you, I need to know where you're interested in. Could you please tell me the island/city you're interested in?"

    def handle_city_response(self, city: str):
        """Handle the user's response providing a city."""
        self.state['city'] = city.strip()
        self.state['awaiting_city'] = False
        return self.state['original_query'] # Return original query to proceed

    def get_search_params(self):
        """Get parameters for the event search API call."""
        if not self.state['city']:
            return None

        # Default to the next month if no dates are specified
        start_date = self.state.get('start_date') or datetime.datetime.now()
        end_date = self.state.get('end_date') or (start_date + datetime.timedelta(days=30))

        return {
            "city": self.state['city'],
            "start_date": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_date": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def reset(self):
        """Reset the event search state."""
        st.session_state.event_search_state = {
            "awaiting_city": False,
            "city": None,
            "start_date": None,
            "end_date": None,
            "original_query": None,
        }

# --- Caching for External APIs ---
@st.cache_data(ttl=600) # Cache for 10 minutes
def cached_search_ticketmaster_events(query, city, start_date, end_date):
    print("HERE1", query, city, start_date, end_date)
    """Cached wrapper for the event search function to prevent repeated API calls."""
    return search_ticketmaster_events("", city, start_date, end_date)


@st.cache_data
def get_stored_pdfs():
    """
    Returns a sorted list of PDF files in the storage directory.
    Caches the result to avoid repeated filesystem access.
    """
    if not os.path.exists(PDF_STORAGE_PATH):
        return []
    return sorted([f for f in os.listdir(PDF_STORAGE_PATH) if f.endswith('.pdf')])


# --- Data Store Constants ---
PDF_STORAGE_PATH = "data_store/pdfs/"
VECTOR_STORE_PATH = "data_store/chroma_db/"
CHROMA_COLLECTION_NAME = "pdf_collection"
METADATA_FILE = "data_store/metadata.json"


def initialize_data_store():
    """Create necessary directories if they don't exist."""
    os.makedirs(PDF_STORAGE_PATH, exist_ok=True)
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)


def load_metadata() -> Dict[str, List[str]]:
    """Load the metadata file that maps PDF names to vector IDs."""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_metadata(metadata: Dict[str, List[str]]):
    """Save the metadata file."""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=4)


@st.cache_resource
def get_vector_store():
    """
    Initialize a persistent ChromaDB vector store.
    Caches the ChromaDB client for the Streamlit session.
    """
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    
    # Initialize LangChain's Chroma vector store wrapper
    vector_store = Chroma(
        client=client,
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=OpenAIEmbeddings(),
    )
    return vector_store

def add_pdfs_to_store(pdf_files):
    """Process uploaded PDFs and add them to the persistent ChromaDB store."""
    if not pdf_files:
        return

    vector_store = get_vector_store()

    with st.spinner("Processing and adding PDFs to the knowledge base..."):
        for pdf_file in pdf_files:
            pdf_name = pdf_file.name
            
            # Check if this PDF already exists
            existing_docs = vector_store.get(where={"source": pdf_name})
            if existing_docs and existing_docs['ids']:
                st.warning(f"'{pdf_name}' already exists in the data store. Skipping.")
                continue

            # Save the PDF to the designated storage path
            pdf_path = os.path.join(PDF_STORAGE_PATH, pdf_name)
            with open(pdf_path, "wb") as f:
                f.write(pdf_file.getbuffer())

            # Process the PDF
            raw_text = get_pdf_text(pdf_path)
            if not raw_text:
                st.warning(f"Could not extract text from '{pdf_name}'. Skipping.")
                continue
            
            # Get text chunks and add the PDF name to metadata
            text_chunks = get_chunk_text(raw_text, pdf_name)
            
            # Add to vector store
            try:
                vector_store.add_documents(documents=text_chunks)
                st.success(f"Successfully added '{pdf_name}' to the data store.")
            except Exception as e:
                st.error(f"Error adding '{pdf_name}' to the vector store: {e}")
    
    # No need to clear cache or rerun here, changes are live
    get_stored_pdfs.clear()
    st.rerun() # Rerun to update the sidebar UI

def remove_pdf_from_store(pdf_name: str):
    """Remove a PDF and its associated vectors from the ChromaDB store."""
    if not pdf_name:
        return

    vector_store = get_vector_store()
    
    # Find the document IDs associated with the PDF file
    existing_docs = vector_store.get(where={"source": pdf_name})
    doc_ids_to_remove = existing_docs.get('ids')

    if not doc_ids_to_remove:
        st.warning(f"No documents found for '{pdf_name}' to remove.")
        return
        
    try:
        # Remove the documents from ChromaDB
        vector_store.delete(ids=doc_ids_to_remove)
        
        # Remove the original PDF file from storage
        pdf_path = os.path.join(PDF_STORAGE_PATH, pdf_name)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            
        st.success(f"Successfully removed '{pdf_name}' and its {len(doc_ids_to_remove)} document chunks.")
    except Exception as e:
        st.error(f"Error removing '{pdf_name}': {e}")
    
    get_stored_pdfs.clear()
    st.rerun() # Rerun to update the sidebar UI

# Custom Retriever for injecting event data
class EventInjectingRetriever(BaseRetriever):
    """A custom retriever that injects real-time event information into the context."""
    vectorstore_retriever: BaseRetriever
    event_list: List[str] = [] # Summary list for display
    event_details: List[Dict] = [] # Detailed list for context

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        """Overrides the default method to add event context when needed."""
        # First, get the relevant documents from the underlying vector store.
        docs = self.vectorstore_retriever.get_relevant_documents(query, callbacks=run_manager.get_child())

        # Next, check if we have events to inject
        if self.event_list:
            # Store the found events in session state for later use in calendar confirmation
            st.session_state.last_found_events = self.event_list
            st.session_state.last_found_events_details = self.event_details

            # Format the detailed event information for the LLM context.
            # This gives the LLM the necessary data to answer follow-up questions.
            event_context_str = "\n".join([
                f"- Event: {details.get('name', 'N/A')}\n"
                f"  Date: {details.get('date', 'N/A')}\n"
                f"  Venue: {details.get('venue', 'N/A')}\n"
                f"  Description: {details.get('description', 'No description available.')}"
                for details in self.event_details
            ])
            
            event_doc = Document(page_content=f"\n\nHere are the real-time events you asked for:\n---\n{event_context_str}\n---")
            
            # Prepend the event document to the context for the LLM.
            docs.insert(0, event_doc)
        
        return docs

def parse_event_string(event_string):
    """Parse the event string into a dictionary."""
    try:
        event_parts = event_string.split(';')
        event_data = {
            'summary': event_parts[0],
            'description': event_parts[1],
            'start': {
                'dateTime': event_parts[2],
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': event_parts[3],
                'timeZone': 'UTC',
            },
        }
        return event_data
    except Exception:
        return None

def streamlit_oauth_flow():
    """Streamlit-compatible wrapper for OAuth flow with UI feedback."""
    if not os.path.exists('credentials.json'):
        st.error("Authentication error: `credentials.json` not found.")
        return False, "Authentication error: `credentials.json` not found."
    
    try:
        # Show Streamlit UI messages
        st.info("🔓 Starting Google Calendar authentication...")
        st.info("📝 A browser window will open. Please complete the sign-in process.")
        
        # Call the actual OAuth flow from calendarTest
        success, message = initiate_oauth_flow()
        
        if success:
            st.session_state['auth_success'] = True
            st.success("✅ Authentication successful! You may now proceed.")
        else:
            st.error(f"❌ Authentication failed: {message}")
            
        return success, message
        
    except Exception as e:
        st.error(f"❌ Authentication flow failed: {e}")
        return False, f"The authentication flow failed: {e}"

def streamlit_clear_authentication():
    """Streamlit-compatible wrapper for clearing authentication."""
    try:
        # Clear the token file directly since clear_authentication doesn't exist
        if os.path.exists('token.json'):
            os.remove('token.json')
        # Clear any Streamlit session-related auth flags if they exist
        st.session_state.pop('google_auth_creds', None)
        st.session_state.pop('auth_success', None)
        # Clear the sidebar calendar status to force refresh
        st.session_state.pop('sidebar_calendar_status', None)
        st.session_state.force_calendar_status_refresh = True
        st.success("Authentication cleared. You will be asked to grant access again.")
    except Exception as e:
        st.error(f"Error clearing authentication: {str(e)}")

def clear_cached_status():
    """Clear any cached status, such as the credentials cache."""
    # Force refresh of sidebar calendar status
    if 'sidebar_calendar_status' in st.session_state:
        st.session_state.pop('sidebar_calendar_status')
    st.session_state.force_calendar_status_refresh = True

def get_pdf_text(pdf_path):
    """Extracts text from a single PDF file."""
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    except Exception as e:
        st.error(f"Error reading {os.path.basename(pdf_path)}: {e}")
    return text


def get_chunk_text(text, pdf_name):
    """Splits text into chunks and adds source metadata."""
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len
    )
    # Use create_documents to include metadata easily
    chunks = text_splitter.create_documents([text], metadatas=[{"source": pdf_name}])
    return chunks

@st.cache_resource
def get_conversation_chain(_vector_store):
    
    # OpenAI Model
    llm = ChatOpenAI()

    # Custom prompt template
    template = """You are a helpful AI assistant that answers questions based on the provided context. 
    Use the following pieces of context to answer the question at the end.
    If you don't know the answer, just say that you don't know, don't try to make up an answer.
    
    If the user is asking a follow-up question about events that have already been found and are listed in the "Real-time Events" context, then use that context to answer their questions.
    Present the events as a numbered list to make it easier for the user to select them.
    After presenting the events, please ask the user if they would like to have them added to their calendar.
    If you are presenting events, let them know that the search was for the next month by default and that they can ask to search for events in a different city or over a different time period.

    - Warm Welcome:
    - Begin with a warm, friendly greeting using "Aloha." Inquire about the user's well-being with genuine empathy.
    - If the user asks a question in the first message make sure to answer it as normal following your greeting.
    - Do not ask how you can help if the user asks a question. Instead focus on answering the question and providing relevant context/information.
    - Emotional Sensitivity:
    - If the user expresses negative emotions, gently ask open-ended questions to understand their concerns.
    - If the user expresses positive emotions, celebrate with them and share their enthusiasm.
    - Personalized Assistance:
    - After understanding the user's emotional state, offer assistance with their Hawaii-based business.
    - Inquire about the location of their business within Hawaii to provide more contextually relevant support.
    - Gather all relevant information by asking questions that will help you to give a careful and crafted answer.
    - If there are multiple answers make sure to ask questions to only provide the most relevant to them. (ex: do not give them answers that do not apply to their district or island)
    - Do not present information as completely true for everyone or all use cases(again, ensure you ask questions to make sure it applies to their case)
    - If your answer has criteria for it to apply to their use case make sure to ask for information that ensures they fit or could possibly fit the criteria. If you ask a question and their answers suggest they do not fit the criteria do not present it as true to them. If there are no answers that fit them then you may present other answers with the added context of how it mgiht not apply to them.
    - Knowledge Grounding:
    - Do not repeat yourself or rephrase your response again immediately after giving a response. Wait for the user to ask for clarity and then rephrase to help them.
    - Active Listening and Confirmation:
    - Summarize the user's request in your own words to confirm understanding.
    - If necessary, ask clarifying questions to ensure you fully grasp their needs.
    - Solution-Oriented Approach:
    - Leverage your AI capabilities to offer relevant solutions, advice, and resources.
    - When the conversation ends and the topic changes, reference previous conversation to remain helpful
    - If the query falls outside the scope of the data store or your expertise, be transparent and offer alternative avenues for assistance.
    - When providing a list, format as bullet points
    - After answering a question with relevant information, ask the user if they need more assistance.
    - Empathetic Closing:
    - Express gratitude for their business and offer well wishes for their continued success.
    - End the conversation with a friendly closing, such as "A hui hou" (until we meet again) or "Mahalo for allowing me to assist you."
    - Personality: Develop a friendly and approachable persona, akin to a knowledgeable and caring friend.
    - Efficiency: Strive to provide prompt and efficient assistance while maintaining empathy and accuracy.
    - Cultural Sensitivity: Be mindful of Hawaiian culture and values, using appropriate language and demonstrating respect.
    - Provide a truly helpful, accurate, and empathetic experience for users, make them feel like they are talking to a trusted friend who is deeply invested in their success.
    - Do not use quotations unless referencing an acutal quote from a person.
    - Keep the conversation going until the user says "I don't need anymore help" or something similar.
    - Ask one question at a time so that the user doesn't get confused or overwhelmed by asking multiple follow-up questions.
    - Whenever you refer to your "data store" make sure to use the word "data source"

    Context: {context}
    
    Chat History: {chat_history}
    Human: {question}
    Assistant:"""


    QA_CHAIN_PROMPT = PromptTemplate(
        input_variables=["context", "chat_history", "question"],
        template=template
    )

    memory = ConversationSummaryBufferMemory(
        llm=llm, 
        max_token_limit=1000, 
        memory_key='chat_history', 
        return_messages=True
    )

    # Create the custom retriever
    vector_store_retriever = _vector_store.as_retriever()
    event_retriever = EventInjectingRetriever(
        vectorstore_retriever=vector_store_retriever
    )

    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm = llm,
        retriever = event_retriever,
        memory = memory,
        combine_docs_chain_kwargs={"prompt": QA_CHAIN_PROMPT}
    )

    return conversation_chain

def convert_newlines_to_html(text):
    """Convert newlines to HTML line breaks for proper display"""
    return text.replace('\n', '<br>')

def add_manual_event_to_calendar(calendar_event):
    """Add a manually created event to Google Calendar using the existing subprocess approach."""
    try:
        # Use the same subprocess approach as the other calendar events
        events_data = [calendar_event]  # Wrap in list for consistency
        
        # Create a temporary script to run the calendar operation
        import tempfile
        import subprocess
        import sys
        import json
        
        script_content = f'''
import sys
import os
import datetime
import json

# Add current directory to path for imports
current_dir = os.getcwd()
sys.path.insert(0, current_dir)

# Import only what we need to avoid dependency issues
try:
    from calendarTest import check_google_calendar_access, initiate_oauth_flow, add_event_to_google_calendar
except ImportError as e:
    print(f"RESULT:IMPORT_FAILED:Could not import calendar functions: {{e}}")
    sys.exit(1)

def main():
    print("=== MANUAL EVENT CALENDAR OPERATION ===")
    
    # Event data (passed from main app)
    events_data = {json.dumps(events_data, indent=4)}
    
    # Quick access check
    print("Checking calendar access...")
    try:
        has_access, status = check_google_calendar_access()
        print(f"Access: {{has_access}} - {{status}}")
    except Exception as e:
        print(f"RESULT:ACCESS_CHECK_FAILED:{{str(e)}}")
        return
    
    # If no access, try OAuth once
    if not has_access:
        print("No access, initiating OAuth...")
        try:
            success, message = initiate_oauth_flow()
            print(f"OAuth result: {{success}} - {{message}}")
            if not success:
                print(f"RESULT:OAUTH_FAILED:{{message}}")
                return
        except Exception as e:
            print(f"RESULT:OAUTH_ERROR:{{str(e)}}")
            return
        
        # Check access again
        try:
            has_access, status = check_google_calendar_access()
            print(f"Post-OAuth access: {{has_access}} - {{status}}")
        except Exception as e:
            print(f"RESULT:POST_OAUTH_CHECK_FAILED:{{str(e)}}")
            return
    
    # If we still don't have access, fail
    if not has_access:
        print(f"RESULT:ACCESS_FAILED:{{status}}")
        return
    
    # Add the event
    event_data = events_data[0]
    print(f"Adding manual event: {{event_data['summary']}}...")
    try:
        success, message = add_event_to_google_calendar(event_data)
        print(f"Manual event result: {{success}} - {{message}}")
        
        if success:
            print(f"RESULT:SUCCESS:{{message}}")
        else:
            print(f"RESULT:FAILED:{{message}}")
    except Exception as e:
        print(f"RESULT:CALENDAR_ERROR:{{str(e)}}")

if __name__ == '__main__':
    main()
'''
        
        # Write the script to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_content)
            temp_script_path = f.name
        
        try:
            # Run the script in a subprocess
            result = subprocess.run(
                [sys.executable, temp_script_path], 
                capture_output=True, 
                text=True, 
                timeout=60,
                cwd=os.getcwd()
            )
            
            # Parse the result from the script output
            output_lines = result.stdout.strip().split('\n')
            result_line = None
            for line in output_lines:
                if line.startswith('RESULT:'):
                    result_line = line
                    break
            
            if result_line:
                parts = result_line.split(':', 2)
                if len(parts) >= 3:
                    result_type = parts[1]
                    result_message = parts[2]
                    
                    if result_type == 'SUCCESS':
                        return f"✅ Successfully added '{calendar_event['summary']}' to your Google Calendar!"
                    elif result_type == 'IMPORT_FAILED':
                        return f"❌ Calendar setup issue: {result_message}. Please check your calendar integration."
                    elif result_type in ['ACCESS_CHECK_FAILED', 'OAUTH_ERROR', 'POST_OAUTH_CHECK_FAILED', 'CALENDAR_ERROR']:
                        return f"❌ Calendar error: {result_message}. Try the '🧪 Test Calendar Integration' button in the sidebar."
                    else:
                        return f"❌ Failed to add event: {result_message}"
                else:
                    return f"❌ Unexpected result format: {result_line}"
            else:
                if result.returncode == 0:
                    return f"✅ Event '{calendar_event['summary']}' was added to your calendar!"
                else:
                    return f"❌ Calendar operation failed. Error: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            return "❌ Calendar operation timed out. Please try again."
        except Exception as e:
            return f"❌ Error running calendar operation: {str(e)}"
        
        finally:
            # Clean up the temporary script
            try:
                os.unlink(temp_script_path)
            except:
                pass
                
    except Exception as e:
        return f"❌ Error creating calendar event: {str(e)}"

def add_events_to_calendar_subprocess(events_to_add):
    """Add multiple events to calendar using subprocess approach."""
    try:
        # Prepare all events data for the subprocess
        events_data = []
        for event in events_to_add:
            # Parse the event date properly
            event_date_str = event.get('date', '')
            try:
                if event_date_str:
                    date_parts = event_date_str.strip().split()
                    if len(date_parts) >= 1:
                        date_part = date_parts[0]  # YYYY-MM-DD
                        time_part = date_parts[1] if len(date_parts) > 1 else "19:00"  # Default to 7 PM
                        
                        if time_part.upper().endswith(('AM', 'PM')):
                            # 12-hour format like "07:00 PM"
                            event_datetime = datetime.datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %I:%M %p")
                        else:
                            # 24-hour format like "19:00"  
                            event_datetime = datetime.datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
                    else:
                        # Just date, default time
                        event_datetime = datetime.datetime.strptime(date_part, "%Y-%m-%d").replace(hour=19, minute=0)
                else:
                    # No date info, default to tomorrow
                    event_datetime = datetime.datetime.now() + datetime.timedelta(days=1)
                    event_datetime = event_datetime.replace(hour=19, minute=0, second=0, microsecond=0)
            except (ValueError, IndexError):
                # Fallback to tomorrow if parsing fails
                event_datetime = datetime.datetime.now() + datetime.timedelta(days=1)
                event_datetime = event_datetime.replace(hour=19, minute=0, second=0, microsecond=0)
            
            # Create end time (2 hours later)
            end_datetime = event_datetime + datetime.timedelta(hours=2)
            
            # Create comprehensive event data
            event_data = {
                'summary': event.get('name', 'Event'),
                'location': event.get('venue', 'TBD'),
                'description': f"""Event Details:
• Event: {event.get('name', 'N/A')}
• Artist/Performer: {event.get('artist', 'N/A')}
• Venue: {event.get('venue', 'N/A')}
• Description: {event.get('description', 'No additional information provided.')}

Added via Hawaii Business Assistant""",
                'start': {
                    'dateTime': event_datetime.isoformat(),
                    'timeZone': 'Pacific/Honolulu',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Pacific/Honolulu',
                },
            }
            events_data.append(event_data)
        
        # Create the temporary script content for multiple events
        import tempfile
        import subprocess
        import sys
        import json
        
        script_content = f'''
import sys
import os
import datetime
import json
sys.path.append(os.getcwd())

from calendarTest import check_google_calendar_access, initiate_oauth_flow, add_event_to_google_calendar

def main():
    print("=== ISOLATED CALENDAR OPERATION ===")
    print(f"Processing {{len({events_data})}} event(s)...")
    
    # Events data (passed from main app)
    events_data = {json.dumps(events_data, indent=4)}
    
    # Quick access check
    print("Checking calendar access...")
    has_access, status = check_google_calendar_access()
    print(f"Access: {{has_access}} - {{status}}")
    
    # If no access, try OAuth once
    if not has_access:
        print("No access, initiating OAuth...")
        success, message = initiate_oauth_flow()
        print(f"OAuth result: {{success}} - {{message}}")
        if not success:
            print(f"RESULT:OAUTH_FAILED:{{message}}")
            return
        
        # Check access again
        has_access, status = check_google_calendar_access()
        print(f"Post-OAuth access: {{has_access}} - {{status}}")
    
    # If we still don't have access, fail
    if not has_access:
        print(f"RESULT:ACCESS_FAILED:{{status}}")
        return
    
    # Add all events
    success_count = 0
    failed_count = 0
    event_links = []
    error_messages = []
    
    for i, event_data in enumerate(events_data):
        print(f"Adding event {{i+1}}/{{len(events_data)}}: {{event_data['summary']}}...")
        success, message = add_event_to_google_calendar(event_data)
        print(f"Event {{i+1}} result: {{success}} - {{message}}")
        
        if success:
            success_count += 1
            # Extract the event link if present
            if "Event created: https" in message:
                event_links.append(message.replace("Event created: ", ""))
            else:
                event_links.append(message)
        else:
            failed_count += 1
            error_messages.append(f"{{event_data['summary']}}: {{message}}")
    
    # Generate final result
    if success_count > 0 and failed_count == 0:
        result_msg = f"Successfully added {{success_count}} event(s) to your calendar!"
        if event_links:
            result_msg += " Links: " + " | ".join(event_links[:3])  # Limit to first 3 links
        print(f"RESULT:SUCCESS:{{result_msg}}")
    elif success_count > 0 and failed_count > 0:
        result_msg = f"Added {{success_count}} event(s), but {{failed_count}} failed. Errors: {{'; '.join(error_messages[:2])}}"
        print(f"RESULT:PARTIAL:{{result_msg}}")
    else:
        result_msg = f"Failed to add all events. Errors: {{'; '.join(error_messages[:3])}}"
        print(f"RESULT:FAILED:{{result_msg}}")

if __name__ == '__main__':
    main()
'''
        
        # Write the script to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_content)
            temp_script_path = f.name
        
        try:
            # Run the script in a subprocess with a reasonable timeout
            result = subprocess.run(
                [sys.executable, temp_script_path], 
                capture_output=True, 
                text=True, 
                timeout=60,  # 60 second timeout
                cwd=os.getcwd()
            )
            
            # Parse the result from the script output
            output_lines = result.stdout.strip().split('\n')
            result_line = None
            for line in output_lines:
                if line.startswith('RESULT:'):
                    result_line = line
                    break
            
            if result_line:
                parts = result_line.split(':', 2)
                if len(parts) >= 3:
                    result_type = parts[1]
                    result_message = parts[2]
                    
                    if result_type == 'SUCCESS':
                        if len(events_to_add) == 1:
                            return f"✅ Successfully added '{events_to_add[0].get('name', 'the event')}' to your Google Calendar! {result_message}"
                        else:
                            return f"✅ {result_message}"
                    elif result_type == 'PARTIAL':
                        return f"⚠️ {result_message}"
                    elif result_type == 'OAUTH_FAILED':
                        return f"❌ Could not connect to Google Calendar: {result_message}. Please try the manual test button in the sidebar first."
                    elif result_type == 'ACCESS_FAILED':
                        return f"❌ Could not establish calendar connection: {result_message}. Please use the '🧪 Test Calendar Integration' button in the sidebar first."
                    else:
                        return f"❌ Failed to add event(s): {result_message}"
                else:
                    return f"❌ Unexpected result format: {result_line}"
            else:
                if result.returncode == 0:
                    if len(events_to_add) == 1:
                        return f"✅ Calendar operation completed, but couldn't parse result. Check your Google Calendar for '{events_to_add[0].get('name', 'the event')}'."
                    else:
                        return f"✅ Calendar operation completed, but couldn't parse result. Check your Google Calendar for the {len(events_to_add)} event(s) you requested."
                else:
                    return f"❌ Calendar operation failed with return code {result.returncode}. Error: {result.stderr}"
        
        except subprocess.TimeoutExpired:
            return "❌ Calendar operation timed out after 60 seconds. Please try again or use the manual test button."
        except Exception as e:
            return f"❌ Error running calendar operation: {str(e)}"
        
        finally:
            # Clean up the temporary script
            try:
                os.unlink(temp_script_path)
            except:
                pass
                
    except Exception as e:
        return f"❌ Error preparing calendar events: {str(e)}"

# Add to the top of the file (after imports)
EVENT_SEARCH_STEPS = [
    'awaiting_greeting',
    'awaiting_location',
    'awaiting_event_type',
    'ready_to_search'
]

def handle_user_input(question):
    # 1. Initialize conversation chain if it doesn't exist
    if "conversation_chain" not in st.session_state or st.session_state.conversation_chain is None:
        initialize_conversation()
    
    # 2. Add user's message to chat history
    st.session_state.chat_history.append(HumanMessage(content=question))

    # --- IMPROVED: Distinguish between add-to-calendar and Q&A requests, and track last referenced event ---
    if st.session_state.get('last_found_events') and st.session_state.get('last_found_events_details'):
        add_intent_words = [
            'add', 'put', 'schedule', 'calendar', 'create', 'book', 'plan', 'insert', 'save', 'set', 'place', 'include'
        ]
        lower_q = question.lower().strip()
        from enhanced_topic_search import EnhancedEventConversationFlow
        all_event_summaries = st.session_state['last_found_events']
        all_event_details = st.session_state['last_found_events_details']
        import re
        event_number_match = re.search(r'(?:event\s*#?|#)(\d+)', lower_q)
        event_index = None
        if event_number_match:
            event_index = int(event_number_match.group(1)) - 1
            if 0 <= event_index < len(all_event_details):
                st.session_state['last_referenced_event_index'] = event_index
        elif 'this event' in lower_q or 'that event' in lower_q:
            event_index = st.session_state.get('last_referenced_event_index')
        elif re.fullmatch(r'\d+', lower_q):
            event_index = int(lower_q) - 1
            if 0 <= event_index < len(all_event_details):
                st.session_state['last_referenced_event_index'] = event_index

        if any(word in lower_q for word in add_intent_words):
            # If user refers to 'this event', 'that event', or just a number, use last referenced event
            if (('this event' in lower_q or 'that event' in lower_q or re.fullmatch(r'\d+', lower_q))
                and st.session_state.get('last_referenced_event_index') is not None):
                idx = st.session_state['last_referenced_event_index']
                add_result = [all_event_details[idx]]
            else:
                add_result = filter_events_to_add(question, all_event_summaries, all_event_details)
            if isinstance(add_result, list):
                if not add_result:
                    st.session_state.chat_history.append(AIMessage(content="I couldn't find any events matching your request to add. Please specify which event(s) you'd like to add to your calendar."))
                    return
                # --- Deduplicate events by name, date, and location ---
                seen = set()
                unique_events = []
                for event in add_result:
                    key = (event.get('name', '').strip().lower(), event.get('date', '').strip(), event.get('location', '').strip().lower())
                    if key not in seen:
                        seen.add(key)
                        unique_events.append(event)
                from app import add_events_to_calendar_subprocess
                result_msg = add_events_to_calendar_subprocess(unique_events)
                # --- Post-process result message for accurate count ---
                import re
                link_matches = re.findall(r'https://www\.google\.com/calendar/event\?eid=[^\s|]+', result_msg)
                n_links = len(link_matches)
                n_events = len(unique_events)
                # If only one event, show single message
                if n_events == 1:
                    msg = f"✅ Successfully added '{unique_events[0].get('name', 'the event')}' to your Google Calendar!"
                    if n_links:
                        msg += f" Link: {link_matches[0]}"
                else:
                    msg = f"✅ Successfully added {n_events} unique event(s) to your calendar!"
                    if n_links:
                        msg += " Links: " + " | ".join(link_matches[:3])
                st.session_state.chat_history.append(AIMessage(content=msg))
                return
            elif add_result is None:
                st.session_state.chat_history.append(AIMessage(content="Could you clarify which event(s) you'd like to add to your calendar? You can specify by number, name, or say 'all events'."))
                return
            elif add_result == "QUESTION":
                flow = EnhancedEventConversationFlow()
                answer = flow.answer_event_question(question)
                st.session_state.chat_history.append(AIMessage(content=answer))
                return
        else:
            if event_index is not None and 0 <= event_index < len(all_event_details):
                st.session_state['last_referenced_event_index'] = event_index
            flow = EnhancedEventConversationFlow()
            answer = flow.answer_event_question(question)
            st.session_state.chat_history.append(AIMessage(content=answer))
            return

    # --- If the user asks to see the event list again, print it from session ---
    lower_q = question.lower().strip()
    show_list_phrases = [
        'show the list again', 'repeat the events', 'show events again', 'show me the events again',
        'repeat the list', 'repeat events', 'show events', 'show the events', 'list the events',
        'print the events', 'print the list', 'show me the list', 'show me events', 'show last events',
        'show previous events', 'show last list', 'show previous list', 'can you provide me the list again',
        'can you show me the list again', 'can you show the events again', 'can you repeat the events',
        'can you repeat the list', 'can you print the events', 'can you print the list', 'can you list the events'
    ]
    if any(phrase in lower_q for phrase in show_list_phrases):
        from enhanced_topic_search import EnhancedEventConversationFlow
        flow = EnhancedEventConversationFlow()
        event_list_str = flow.get_last_event_list()
        st.session_state.chat_history.append(AIMessage(content=event_list_str))
        return

    # --- Q&A about events before any step-based event search flow ---
    from enhanced_topic_search import EnhancedEventConversationFlow
    if st.session_state.get('last_found_events') and st.session_state.get('last_found_events_details'):
        is_new_search = False
        # Check for new search intent (island/city names, 'find', 'search', etc.)
        for island in ISLAND_CITY_MAP.keys():
            if island in lower_q:
                is_new_search = True
        if any(word in lower_q for word in ['find', 'search', 'show events', 'look for', 'see events', 'get events', 'list events', 'what events', 'which events', 'events in', 'calendar', 'add event', 'create event', 'schedule event']):
            is_new_search = True
        if not is_new_search:
            # Route to event Q&A
            flow = EnhancedEventConversationFlow()
            answer = flow.answer_event_question(question)
            st.session_state.chat_history.append(AIMessage(content=answer))
            return

    # --- Step-by-step event search flow ---
    if 'event_search_step' not in st.session_state:
        st.session_state.event_search_step = EVENT_SEARCH_STEPS[0]
        st.session_state.event_search_context = {}
    
    # Check if user is changing time frame during the conversation
    time_frame_change = _detect_time_frame_change(question)
    if time_frame_change and st.session_state.event_search_step != 'awaiting_greeting':
        # Update time frame and continue with current step
        st.session_state.event_search_context['time_frame'] = time_frame_change
        st.session_state.chat_history.append(AIMessage(content=f"Got it! I'll search for events {time_frame_change}. Now, which island or city would you like to search for events in?"))
        st.session_state.event_search_step = 'awaiting_location'
        return
    
    # Step 1: Greet and explain default time period
    if st.session_state.event_search_step == 'awaiting_greeting':
        st.session_state.event_search_step = 'awaiting_location'
        st.session_state.event_search_context['time_frame'] = 'for the next month'
        st.session_state.chat_history.append(AIMessage(content="Aloha! I'll search for events happening in Hawaii for the next month by default. If you'd like to search for a different time period, just let me know!"))
        st.session_state.chat_history.append(AIMessage(content="Which island or city would you like to search for events in?"))
        return
    
    # Step 2: Ask for island/city
    if st.session_state.event_search_step == 'awaiting_location':
        # Check if user is actually providing a location or changing time frame
        if _detect_time_frame_change(question):
            time_frame = _detect_time_frame_change(question)
            st.session_state.event_search_context['time_frame'] = time_frame
            st.session_state.chat_history.append(AIMessage(content=f"Got it! I'll search for events {time_frame}. Which island or city would you like to search for events in?"))
            return
        else:
            st.session_state.event_search_context['location'] = question.strip()
            st.session_state.event_search_step = 'awaiting_event_type'
            st.session_state.chat_history.append(AIMessage(content="Are you interested in a specific type of event (like music, food, business, etc.), or would you like to see all events? You can say 'all events' to see everything."))
            return
    
    # Step 3: Ask for event type or all events
    if st.session_state.event_search_step == 'awaiting_event_type':
        # Check if user is changing time frame instead of providing event type
        if _detect_time_frame_change(question):
            time_frame = _detect_time_frame_change(question)
            st.session_state.event_search_context['time_frame'] = time_frame
            st.session_state.chat_history.append(AIMessage(content=f"Got it! I'll search for events {time_frame}. Are you interested in a specific type of event (like music, food, business, etc.), or would you like to see all events? You can say 'all events' to see everything."))
            return
        else:
            event_type = question.strip().lower()
            st.session_state.event_search_context['event_type'] = event_type
            st.session_state.event_search_step = 'ready_to_search'
    
    # Step 4: Perform the search
    if st.session_state.event_search_step == 'ready_to_search':
        location = st.session_state.event_search_context.get('location', '')
        event_type = st.session_state.event_search_context.get('event_type', '')
        time_frame = st.session_state.event_search_context.get('time_frame', 'for the next month')
        is_island = location.lower() in ISLAND_CITY_MAP
        # If user said 'all events', search with no topic filter
        query = '' if event_type in ['all', 'all events', 'everything', 'any'] else event_type
        # --- Add date range for event search ---
        from datetime import datetime, timedelta
        # Default: next 30 days
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        # If time_frame is in context, try to parse it (future improvement)
        summaries, details = unified_event_search(query, location, is_island, start_date, end_date)
        st.session_state.last_found_events = summaries
        st.session_state.last_found_events_details = details
        response_parts = []
        if summaries:
            response_parts.append(f"Aloha! Here are the upcoming events in {location.title()} {time_frame}:")
            for i, summary in enumerate(summaries):
                response_parts.append(f"{i+1}. {summary}")
            response_parts.append("\nWould you like me to add any of these to your calendar?")
        else:
            response_parts.append(f"I couldn't find any events in {location.title()} {time_frame}. Would you like to try a different location or see uncertain events?")
        st.session_state.chat_history.append(AIMessage(content="\n".join(response_parts)))
        # Reset the step for next search, but allow Q&A on these events
        st.session_state.event_search_step = EVENT_SEARCH_STEPS[0]
        st.session_state.event_search_context = {}
        return

def _detect_time_frame_change(question: str) -> str or None:
    """Detect if the user is requesting a time frame change."""
    question_lower = question.lower()
    
    # Common time frame patterns
    time_patterns = {
        r'(\d+)\s*month': lambda m: f"for the next {m.group(1)} month{'s' if int(m.group(1)) > 1 else ''}",
        r'(\d+)\s*week': lambda m: f"for the next {m.group(1)} week{'s' if int(m.group(1)) > 1 else ''}",
        r'(\d+)\s*day': lambda m: f"for the next {m.group(1)} day{'s' if int(m.group(1)) > 1 else ''}",
        r'next\s*(\d+)\s*month': lambda m: f"for the next {m.group(1)} month{'s' if int(m.group(1)) > 1 else ''}",
        r'next\s*(\d+)\s*week': lambda m: f"for the next {m.group(1)} week{'s' if int(m.group(1)) > 1 else ''}",
        r'next\s*(\d+)\s*day': lambda m: f"for the next {m.group(1)} day{'s' if int(m.group(1)) > 1 else ''}",
        r'this\s*month': "for this month",
        r'this\s*week': "for this week",
        r'next\s*month': "for the next month",
        r'next\s*week': "for the next week",
        r'this\s*year': "for this year",
        r'next\s*year': "for next year"
    }
    
    import re
    for pattern, replacement in time_patterns.items():
        match = re.search(pattern, question_lower)
        if match:
            if callable(replacement):
                return replacement(match)
            else:
                return replacement
    
    return None

def initialize_conversation():
    """Initialize the conversation chain and store it in session state."""
    vector_store = get_vector_store()
    st.session_state.conversation_chain = get_conversation_chain(vector_store)

    # Sync conversation memory with chat history if it exists
    if st.session_state.chat_history:
        st.session_state.conversation_chain.memory.chat_memory.messages = st.session_state.chat_history.copy()


def clear_chat():
    """Clear chat history and reset all conversational state."""
    st.session_state.chat_history = []
    st.session_state.initial_greeting_shown = False
    
    # Clear the conversation memory in the chain
    if "conversation_chain" in st.session_state and st.session_state.conversation_chain:
        st.session_state.conversation_chain.memory.clear()
    
    st.rerun()

def main():
    # --- Temp Directory Fix for Tiktoken ---
    # In some environments, the default temporary directory is not writable,
    # causing an error with the tiktoken library used by LangChain.
    # This sets a local cache directory for tiktoken to resolve the issue.
    tiktoken_cache_dir = os.path.join(os.getcwd(), "tiktoken_cache")
    os.makedirs(tiktoken_cache_dir, exist_ok=True)
    os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
    # --- End of Fix ---

    load_dotenv()
    st.set_page_config(
        page_title='Chat with Your own PDFs', 
        page_icon=':books:',
        layout='wide',
        initial_sidebar_state='expanded'
    )

    # Initialize data store directories
    initialize_data_store()

    # Force dark mode
    st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117 !important;
        color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.write(css, unsafe_allow_html=True)

    # Initialize chat history before conversation
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Initialize calendar operation tracking
    if "calendar_operation_in_progress" not in st.session_state:
        st.session_state.calendar_operation_in_progress = False

    # Initialize conversation chain if not already done
    if "conversation_chain" not in st.session_state or st.session_state.conversation_chain is None:
        initialize_conversation()

    # Add initial greeting if no chat history exists
    if "initial_greeting_shown" not in st.session_state:
        st.session_state.initial_greeting_shown = False
    
    if "show_connect_button" not in st.session_state:
        st.session_state.show_connect_button = False
    
    if not st.session_state.initial_greeting_shown:
        initial_message = "Aloha! I'm here to help you with your Hawaii-based business questions. How are you doing today? I'd love to assist you with any information you need about your business in Hawaii.\n\nI can also help you with events in two ways:\n1. **Find events**: Ask me to find events happening in Hawaii and I'll search for you\n2. **Create events**: Ask me to create or schedule an event and I'll help you add it to your calendar with all the details\n\nJust let me know what you need!"
        
        # Add the initial greeting to chat history as a bot message
        st.session_state.chat_history.append(AIMessage(content=initial_message))
        st.session_state.initial_greeting_shown = True
    
    st.header('Chat with Your own PDFs :books:')
    
    # Create a container for the text input with custom styling
    input_container = st.container()
    with input_container:
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([6, 1])
            with col1:
                user_input = st.text_area(
                    "Ask anything to your PDF:",
                    height=100,  # Fixed height
                    max_chars=2000,  # Limit characters
                    placeholder="Type your question here...",
                    label_visibility="collapsed"
                )
            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                submit_button = st.form_submit_button("Send", type="primary", use_container_width=True)
            
            if submit_button and user_input and user_input.strip():
                handle_user_input(user_input.strip())
    
    # Display chat history
    if st.session_state.chat_history:
        for i, message in enumerate(reversed(st.session_state.chat_history)):
            if isinstance(message, HumanMessage):
                st.write(user_template.replace("{{MSG}}", message.content), unsafe_allow_html=True)
            elif isinstance(message, AIMessage):
                # Convert newlines to HTML line breaks for bot messages
                formatted_message = convert_newlines_to_html(message.content)
                st.write(bot_template.replace("{{MSG}}", formatted_message), unsafe_allow_html=True)

    # Trigger the authentication flow if requested by the app logic
    if st.session_state.get('trigger_auth_flow'):
        del st.session_state['trigger_auth_flow']  # Consume the flag immediately
        # The run_auth_flow function is removed, so this block is effectively removed.
        # The manual auth flow is now handled directly in the sidebar.
        st.rerun()

    with st.sidebar:
        st.subheader("Upload your Documents Here: ")
        pdf_files = st.file_uploader("Choose your PDF Files and Press OK", type=['pdf'], accept_multiple_files=True)

        if pdf_files:
            add_pdfs_to_store(pdf_files)

        st.subheader("Manage Knowledge Base")
        
        with st.expander("Remove Uploaded PDFs"):
            stored_pdfs = get_stored_pdfs()

            if not stored_pdfs:
                st.info("No PDFs have been added yet.")
            else:
                # Pagination for the PDF list
                page_size = 10
                if 'pdf_page' not in st.session_state:
                    st.session_state.pdf_page = 0

                num_pages = (len(stored_pdfs) - 1) // page_size + 1
                # Prevent page number from being out of bounds after deletion
                if st.session_state.pdf_page >= num_pages:
                    st.session_state.pdf_page = num_pages - 1
                
                start_index = st.session_state.pdf_page * page_size
                end_index = start_index + page_size
                
                # Navigation buttons
                nav_cols = st.columns([1, 2, 1])
                with nav_cols[0]:
                    if st.button("⬅️ Previous", disabled=(st.session_state.pdf_page == 0), use_container_width=True):
                        st.session_state.pdf_page -= 1
                        st.rerun()
                with nav_cols[1]:
                    st.write(f"Page {st.session_state.pdf_page + 1} of {num_pages}")
                with nav_cols[2]:
                    if st.button("Next ➡️", disabled=(st.session_state.pdf_page >= num_pages - 1), use_container_width=True):
                        st.session_state.pdf_page += 1
                        st.rerun()
                
                st.write("---") # Separator

                # Display the current page of PDFs
                for pdf_name in stored_pdfs[start_index:end_index]:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"📄 {pdf_name}")
                    with col2:
                        if st.button("🗑️", key=f"del_{pdf_name}", help=f"Remove {pdf_name}"):
                            with st.spinner(f"Removing '{pdf_name}'..."):
                                remove_pdf_from_store(pdf_name)

        if st.button("Clear Chat"):
            clear_chat()
        
        # Calendar Integration Settings
        st.subheader("📅 Calendar Integration")
        
        # Add refresh button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Refresh Status", help="Check current Google Calendar access status"):
                # Force a fresh status check
                st.session_state.force_calendar_status_refresh = True
                st.rerun()
        
        # Add test browser button
        if st.button("🧪 Test Browser Open", help="Test if browser opening works"):
            st.write("🧪 **DEBUG**: Testing browser opening...")
            try:
                webbrowser.open("https://www.google.com")
                st.success("✅ Browser opened successfully!")
            except Exception as e:
                st.error(f"❌ Browser opening failed: {e}")
        
        # Add test credentials button
        if st.button("🔑 Test Credentials", help="Test if credentials.json is valid"):
            st.write("🔑 **DEBUG**: Testing credentials.json...")
            try:
                import json
                with open('credentials.json', 'r') as f:
                    cred_data = json.load(f)
                
                if 'web' in cred_data:
                    st.success("✅ Web OAuth credentials found!")
                    st.write(f"Client ID: {cred_data['web']['client_id'][:20]}...")
                elif 'installed' in cred_data:
                    st.success("✅ Desktop OAuth credentials found!")
                    st.write(f"Client ID: {cred_data['installed']['client_id'][:20]}...")
                else:
                    st.error("❌ Invalid credentials.json format")
                    
            except FileNotFoundError:
                st.error("❌ credentials.json not found")
            except Exception as e:
                st.error(f"❌ Error reading credentials: {e}")
        
        # Add clear authentication button
        if st.button("🗑️ Clear Authentication", help="Force clear all saved authentication"):
            streamlit_clear_authentication()
            st.rerun()
        
        # Add regenerate credentials button
        if st.button("🔧 Regenerate Credentials", help="Regenerate credentials.json from environment variables"):
            st.write("🔧 **DEBUG**: Regenerating credentials.json from environment variables...")
            # Simple replacement for generate_credentials_from_env
            try:
                st.info("This feature would regenerate credentials.json from environment variables, but it's not implemented yet.")
                success = False
            except Exception:
                success = False
                
            if success:
                st.success("✅ credentials.json regenerated successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to regenerate credentials.json. Check your environment variables or Streamlit secrets.")
        
        # Add test calendar integration button
        if st.button("🧪 Test Calendar Integration", help="Add a test event to your Google Calendar to verify it's working"):
            st.write("🧪 **DEBUG**: Running EXACT calendarTest.py main function...")
            
            # Import and run the EXACT same code as calendarTest.py main section
            import subprocess
            import sys
            
            try:
                # Run calendarTest.py directly as a subprocess to avoid any Streamlit interference
                result = subprocess.run([sys.executable, 'calendarTest.py'], 
                                      capture_output=True, text=True, timeout=30)
                
                st.write("**STDOUT Output:**")
                if result.stdout:
                    st.code(result.stdout)
                else:
                    st.write("(No stdout output)")
                
                if result.stderr:
                    st.write("**STDERR Output:**")
                    st.code(result.stderr)
                
                st.write(f"**Return Code:** {result.returncode}")
                
                if result.returncode == 0:
                    st.success("✅ CalendarTest.py executed successfully!")
                else:
                    st.error(f"❌ CalendarTest.py failed with return code {result.returncode}")
                    
            except subprocess.TimeoutExpired:
                st.error("❌ CalendarTest.py timed out after 30 seconds")
            except Exception as e:
                st.error(f"❌ Error running calendarTest.py: {str(e)}")
                
            # Also run the functions directly for comparison
            st.write("---")
            st.write("**Direct Function Calls (for comparison):**")
            
            try:
                # Direct import and execution - EXACT same as calendarTest.py
                from calendarTest import check_google_calendar_access, initiate_oauth_flow, test_calendar_integration
                
                # Check Google Calendar access
                has_access, status = check_google_calendar_access()
                st.write(f"Direct access check: {has_access} - {status}")
                
                if has_access:
                    # Test adding an event
                    test_result = test_calendar_integration()
                    st.write(f"Direct test result: {test_result}")
                else:
                    st.write("Direct test skipped - no access")
                    
            except Exception as e:
                st.error(f"Direct function error: {str(e)}")
        
        # Add a direct execution button (fastest method)
        if st.button("⚡ Direct Calendar Test", help="Run calendar test with zero Streamlit overhead"):
            st.write("⚡ **DIRECT EXECUTION**: Running calendarTest.py logic with zero overhead...")
            
            # Execute the EXACT main logic from calendarTest.py
            import time
            start_time = time.time()
            
            try:
                # Import the functions
                from calendarTest import check_google_calendar_access, initiate_oauth_flow, test_calendar_integration
                
                print("=== DIRECT CALENDAR TEST ===")
                # Check Google Calendar access
                has_access, status = check_google_calendar_access()
                print(f"Access: {has_access} - {status}")
                
                if not has_access:
                    print(f"Access Error: {status}")
                    print("Initiating OAuth flow...")
                    success, message = initiate_oauth_flow()
                    if success:
                        print(message)
                    else:
                        print(f"OAuth Error: {message}")
                
                # Test adding an event
                test_result = test_calendar_integration()
                print(test_result)
                
                end_time = time.time()
                execution_time = end_time - start_time
                
                st.success(f"✅ Direct execution completed in {execution_time:.2f} seconds!")
                st.write("Check the terminal/console for output (printed directly, not through Streamlit)")
                
            except Exception as e:
                st.error(f"❌ Direct execution error: {str(e)}")
                import traceback
                print(f"Error: {e}")
                traceback.print_exc()
        
        # Check Google Calendar access status (cached for session)
        has_access, message = get_calendar_status_for_sidebar()
        if has_access:
            st.success("✅ Google Calendar is connected!")
            st.info("You can now add events directly to your calendar from the chat.")
        else:
            # If an action is pending, make the message more prominent.
            if st.session_state.get('pending_calendar_add'):
                st.warning(f"🔐 Action Required: {message}")
            else:
                st.warning(f"🔐 Google Calendar not connected: {message}")
            
            st.info("💡 **Pro tip**: Connect your calendar so events can be added instantly when you need them!")
            
            # Show additional help
            with st.expander("🔧 Need help with OAuth?"):
                st.markdown("""
                **If you're getting redirect_uri_mismatch errors:**
                1. Wait 2-3 minutes for Google Cloud changes to apply
                2. Or run: `python quick_fix_web_client.py` for guided setup
                3. Or run: `python create_desktop_credentials.py` for new desktop credentials
                """)
        
        # --- NEW: Debugging Section ---
        with st.expander("🔍 Debug Info"):
            st.write("**Authentication Status:**")
            
            # Check for credentials.json
            creds_exist = os.path.exists('credentials.json')
            st.write(f"- `credentials.json` found: {'✅' if creds_exist else '❌'}")

            # Check for token.json
            token_exist = os.path.exists('token.json')
            st.write(f"- `token.json` found: {'✅' if token_exist else '❌'}")
            
            # Button to test credential loading
            if st.button("🔬 Test Credential Loading"):
                with st.spinner("Testing credentials..."):
                    creds = get_credentials()
                    if creds and creds.valid:
                        st.success("✅ Credentials loaded and are valid.")
                    elif creds:
                        st.warning("⚠️ Credentials loaded but are not valid (likely expired). Refresh might be needed.")
                    else:
                        st.error("❌ Failed to load credentials. `token.json` might be missing, corrupt, or revoked.")

        # Show fallback information
        st.info("💡 **Fallback**: If Google Calendar is unavailable, events will be saved as downloadable iCal files.")
        
        # Download iCal file if available
        if "ical_file_path" in st.session_state and st.session_state.ical_file_path:
            try:
                with open(st.session_state.ical_file_path, 'r') as f:
                    ical_content = f.read()
                
                st.download_button(
                    label="📥 Download Events (.ics)",
                    data=ical_content,
                    file_name="hawaii_events.ics",
                    mime="text/calendar",
                    help="Download the events file to import into your calendar"
                )
            except FileNotFoundError:
                st.warning("iCal file not found. Events may have been cleared.")
                if "ical_file_path" in st.session_state:
                    del st.session_state.ical_file_path

if __name__ == '__main__':
    main()

