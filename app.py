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
        return "Aloha! To find events for you, I need to know which city you're interested in. Could you please tell me the city?"

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

def handle_user_input(question):
    # 1. Initialize conversation chain if it doesn't exist
    if "conversation_chain" not in st.session_state or st.session_state.conversation_chain is None:
        initialize_conversation()
        
    # 2. Add user's message to chat history
    st.session_state.chat_history.append(HumanMessage(content=question))

    event_search_manager = EventSearchManager()
    is_follow_up_about_events = 'last_found_events' in st.session_state and st.session_state.last_found_events

    # 3. Handle the multi-turn event search flow
    # Check if this is a response to the "what city?" prompt
    if event_search_manager.state['awaiting_city']:
        original_query = event_search_manager.handle_city_response(question)
        
        # We now have the city, so we can proceed to fetch events.
        # The user's message (the city name) has been added to the history.
        # Now, we'll fetch events and then let the chain formulate the response.
        question = original_query  # Restore the original query to continue the search

    # If it's an event query but we don't have a city, ask for it and stop.
    # Do not trigger a new search if the user is asking a follow-up question about events we just found.
    if (event_search_manager.is_event_query(question) or event_search_manager.state['original_query']) and not event_search_manager.state['city'] and not is_follow_up_about_events:
        response_text = event_search_manager.start_event_search(question)
        st.session_state.chat_history.append(AIMessage(content=response_text))
        return  # Exit to display the "what city?" prompt

    # 4. Perform the event search if we have the necessary parameters
    event_params = event_search_manager.get_search_params()
    if event_params:
        with st.spinner(f"Finding events in {event_params['city']}..."):
            try:
                original_query = event_search_manager.state['original_query'] or question
                summaries, details = cached_search_ticketmaster_events(original_query, **event_params)

                # --- DIRECT RESPONSE LOGIC ---
                # Instead of passing back to the LLM, directly formulate the response.
                st.session_state.last_found_events = summaries
                st.session_state.last_found_events_details = details
                # Also populate the retriever for any true follow-up questions.
                st.session_state.conversation_chain.retriever.event_list = summaries
                st.session_state.conversation_chain.retriever.event_details = details

                if summaries and "No Ticketmaster events found" not in summaries[0]:
                    response_parts = [f"Aloha! I found these events for you in {event_params['city']}:"]
                    for i, summary in enumerate(summaries):
                        response_parts.append(f"{i+1}. {summary}")
                    
                    response_parts.append("\nWould you like me to add any of these to your calendar?")
                    response_parts.append("I can also search for events in a different city or over a different time period if you'd like.")
                    response_message = "\n".join(response_parts)
                else:
                    response_message = f"I'm sorry, I couldn't find any events in {event_params['city']} for the next month. Is there another city or time frame you're interested in?"

                st.session_state.chat_history.append(AIMessage(content=response_message))

            except Exception as e:
                st.error(f"An error occurred while fetching events: {e}")
                response_message = "I'm sorry, but I ran into an error while trying to find events. Please try again later."
                st.session_state.chat_history.append(AIMessage(content=response_message))
                st.session_state.conversation_chain.retriever.event_list = []
                st.session_state.conversation_chain.retriever.event_details = []
            finally:
                event_search_manager.reset()
                return # IMPORTANT: Exit to display the event list and prevent falling through to the LLM.
    else:
        # If not an event query, ensure the event list in the retriever is empty
        st.session_state.conversation_chain.retriever.event_list = []
        st.session_state.conversation_chain.retriever.event_details = []

    # 5. Check if the user is asking to add events to the calendar.
    # This logic is designed to be robust and prevent the LLM from hallucinating
    # confirmations by reliably intercepting calendar-related commands.
    user_wants_to_add_events = False
    if 'last_found_events' in st.session_state and st.session_state.last_found_events:
        question_lower = question.lower().strip()
        
        # Define keywords that strongly indicate a command to add events.
        action_keywords = ["add", "put", "schedule", "yes", "yep", "ok", "sure", "please"]
        
        # Define question words to avoid false positives on questions.
        question_words = ["what", "which", "who", "when", "where", "how", "why", "is", "are", "can", "do", "will", "should"]

        is_a_question = any(question_lower.startswith(q_word) for q_word in question_words)
        has_action_keyword = any(a_word in question_lower for a_word in action_keywords)

        # Trigger if the intent is clear and it's not a question.
        if has_action_keyword and not is_a_question:
            user_wants_to_add_events = True
    
    if user_wants_to_add_events:
        # Prevent concurrent calendar operations
        if st.session_state.get('calendar_operation_in_progress'):
            st.warning("⏳ Calendar operation already in progress. Please wait...")
            return
        
        st.session_state['calendar_operation_in_progress'] = True
        
        try:
            with st.spinner("Adding event to your calendar..."):
                # Get the events that were previously found
                found_events_details = st.session_state.get('last_found_events_details', [])
                found_events_summaries = st.session_state.get('last_found_events', [])
                
                if not found_events_details:
                    response_message = "I don't have any events to add. Please search for events first."
                    st.session_state.chat_history.append(AIMessage(content=response_message))
                    return
                
                # Use the filter function to determine which events to add
                events_to_add = filter_events_to_add(question, found_events_summaries, found_events_details)
                
                # Handle special QUESTION return value - pass to main LLM
                if events_to_add == "QUESTION":
                    # User asked a question about the events - let the main conversation chain handle it
                    # Make sure the event context is available to the LLM
                    st.session_state.conversation_chain.retriever.event_list = found_events_summaries
                    st.session_state.conversation_chain.retriever.event_details = found_events_details
                    
                    # Clear the calendar operation flag and let it fall through to the main LLM
                    st.session_state.pop('calendar_operation_in_progress', None)
                    # Don't return here - let it fall through to the LLM at the end
                    user_wants_to_add_events = False  # Prevent calendar operation
                    
                elif events_to_add is None:
                    # Ambiguous request - ask for clarification
                    event_list_str = "\n".join([f"{i+1}. {summary}" for i, summary in enumerate(found_events_summaries)])
                    response_message = f"I found these events:\n{event_list_str}\n\nCould you please specify which events you'd like me to add? You can say 'all', specific numbers like '1 and 3', or mention event names."
                    st.session_state.chat_history.append(AIMessage(content=response_message))
                    return
                elif not events_to_add:
                    # No events matched the selection criteria
                    response_message = "I couldn't identify which specific events you want to add. Could you please be more specific? You can say 'all events', '1 and 3', or mention the event names."
                    st.session_state.chat_history.append(AIMessage(content=response_message))
                    return
                
                if events_to_add != "QUESTION":  # Only proceed with calendar operation if not a question
                    # COMPLETELY ISOLATED APPROACH - Run calendar operation in subprocess
                    # This avoids ALL Streamlit interference
                    st.info(f"🚀 Running calendar operation in isolated mode... Adding {len(events_to_add)} event(s)")
                    
                    # Create a temporary script to run the calendar operation
                    import tempfile
                    import subprocess
                    import sys
                    import json
                    
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
                        
                        print(f"Subprocess return code: {result.returncode}")
                        print(f"STDOUT: {result.stdout}")
                        print(f"STDERR: {result.stderr}")
                        
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
                                        response_message = f"✅ Successfully added '{events_to_add[0].get('name', 'the event')}' to your Google Calendar! {result_message}"
                                    else:
                                        response_message = f"✅ {result_message}"
                                elif result_type == 'PARTIAL':
                                    response_message = f"⚠️ {result_message}"
                                elif result_type == 'OAUTH_FAILED':
                                    response_message = f"❌ Could not connect to Google Calendar: {result_message}. Please try the manual test button in the sidebar first."
                                elif result_type == 'ACCESS_FAILED':
                                    response_message = f"❌ Could not establish calendar connection: {result_message}. Please use the '🧪 Test Calendar Integration' button in the sidebar first."
                                else:
                                    response_message = f"❌ Failed to add event(s): {result_message}"
                            else:
                                response_message = f"❌ Unexpected result format: {result_line}"
                        else:
                            if result.returncode == 0:
                                if len(events_to_add) == 1:
                                    response_message = f"✅ Calendar operation completed, but couldn't parse result. Check your Google Calendar for '{events_to_add[0].get('name', 'the event')}'."
                                else:
                                    response_message = f"✅ Calendar operation completed, but couldn't parse result. Check your Google Calendar for the {len(events_to_add)} event(s) you requested."
                            else:
                                response_message = f"❌ Calendar operation failed with return code {result.returncode}. Error: {result.stderr}"
                    
                    except subprocess.TimeoutExpired:
                        response_message = "❌ Calendar operation timed out after 60 seconds. Please try again or use the manual test button."
                    except Exception as e:
                        response_message = f"❌ Error running calendar operation: {str(e)}"
                    
                    finally:
                        # Clean up the temporary script
                        try:
                            os.unlink(temp_script_path)
                        except:
                            pass
                        
                        # Clear events from session since we've processed the request
                        st.session_state.pop('last_found_events', None)
                        st.session_state.pop('last_found_events_details', None)
        
        except Exception as e:
            # Handle any errors in the calendar operation
            response_message = f"❌ Error during calendar operation: {str(e)}"
            st.session_state.chat_history.append(AIMessage(content=response_message))
            return
            
        finally:
            # Always clear the operation flag
            st.session_state.pop('calendar_operation_in_progress', None)
        
        if user_wants_to_add_events:  # Only add response if we actually processed calendar events
            st.session_state.chat_history.append(AIMessage(content=response_message))
            return # IMPORTANT: Exit to prevent this from going to the LLM.

    # --- Core Conversation Logic ---
    # Sync the conversation chain's memory with the current session chat history.
    # This is crucial to prevent the chain from working with stale data, especially
    # after multi-turn interactions like the event search flow.
    st.session_state.conversation_chain.memory.chat_memory.messages = st.session_state.chat_history.copy()

    # Get the final response from the conversation chain
    response = st.session_state.conversation_chain({'question': question})
    
    # Append the assistant's response to the chat history.
    # We explicitly manage the history in st.session_state, so we only need the answer here.
    st.session_state.chat_history.append(AIMessage(content=response['answer']))

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
        initial_message = "Aloha! I'm here to help you with your Hawaii-based business questions. How are you doing today? I'd love to assist you with any information you need about your business in Hawaii.\n\nI can also help you find events happening in Hawaii. Just ask me about events and I'll do my best to find something for you!"
        
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

