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
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import datetime
import json
import os
import pickle
import webbrowser
import requests
from langchain.schema import AIMessage, HumanMessage
from google.auth.exceptions import RefreshError
from langchain.schema.retriever import BaseRetriever
from langchain.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.schema import Document
from typing import List, Callable, Dict
import shutil
import chromadb

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
        """Check if a query is asking for events."""
        event_keywords = ["event", "concert", "show", "game"]
        return any(keyword in query.lower() for keyword in event_keywords)

    def start_event_search(self, query: str):
        """Initiate the event search flow."""
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

        # Default to the next 2 months if no dates are specified
        start_date = self.state.get('start_date') or datetime.datetime.now()
        end_date = self.state.get('end_date') or (start_date + datetime.timedelta(days=60))

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
    """Cached wrapper for the event search function to prevent repeated API calls."""
    return search_ticketmaster_events(query, city, start_date, end_date)


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
    
    st.rerun() # Rerun to update the sidebar UI

# Custom Retriever for injecting event data
class EventInjectingRetriever(BaseRetriever):
    """A custom retriever that injects real-time event information into the context."""
    vectorstore_retriever: BaseRetriever
    event_list: List[str] = [] # Will be populated with event data

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        """Overrides the default method to add event context when needed."""
        # First, get the relevant documents from the underlying vector store.
        docs = self.vectorstore_retriever.get_relevant_documents(query, callbacks=run_manager.get_child())

        # Next, check if we have events to inject
        if self.event_list:
            # Store the found events in session state for later use in calendar confirmation
            st.session_state.last_found_events = self.event_list

            # Format the events into a string and create a special Document.
            event_list_str = "\n".join(self.event_list)
            event_doc = Document(page_content=f"\n\nReal-time Events:\n---\n{event_list_str}\n---")
            
            # Prepend the event document to the context for the LLM.
            docs.insert(0, event_doc)
        
        return docs

# Calendar integration constants and functions
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_credentials():
    """
    Gets valid Google Calendar credentials from token.pickle.
    Refreshes the token if it's expired. Does NOT initiate a new auth flow.
    """
    creds = None
    if os.path.exists('token.pickle'):
        try:
            with open('token.pickle', 'rb') as token_file:
                creds = pickle.load(token_file)
        except Exception as e:
            print(f"Error loading token.pickle: {e}")
            return None # Token file is corrupt.

    # If credentials are not valid, attempt to refresh them.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # The refresh token is invalid or revoked. Delete the token and force re-authentication.
                print(f"Token refresh failed: {e}. Re-authentication is required.")
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                return None
            except Exception as e:
                # Handle other potential exceptions during refresh.
                print(f"Failed to refresh token with a general error: {e}")
                return None
            
            # Save the newly refreshed credentials for the next run.
            with open('token.pickle', 'wb') as token_file:
                pickle.dump(creds, token_file)
        else:
            # If there are no credentials or they cannot be refreshed, return None to trigger auth flow.
            return None
    
    return creds

def run_auth_flow():
    """
    Initiates the full, browser-based authentication flow.
    This should only be called when the user explicitly clicks a login button.
    """
    try:
        if not os.path.exists('credentials.json'):
            st.error("Authentication error: `credentials.json` not found. Please follow setup instructions.")
            return None

        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        with st.spinner("A browser tab has been opened for authentication. Please complete the sign-in process."):
            creds = flow.run_local_server(
                port=8080,
                prompt='consent',
                access_type='offline'
            )
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token_file:
            pickle.dump(creds, token_file)
        
        st.success("Authentication successful!")
        return creds
    except Exception as e:
        st.error(f"The authentication flow failed: {e}")
        return None

def add_event_to_google_calendar(event_data, creds):
    """Add a single event to Google Calendar"""
    if not creds:
        return False, "Authentication credentials were not provided."
        
    try:
        service = build('calendar', 'v3', credentials=creds)
        
        event = {
            'summary': event_data.get('summary', 'Event'),
            'location': event_data.get('location', ''),
            'description': event_data.get('description', ''),
            'start': {
                'dateTime': event_data.get('start_time'),
                'timeZone': 'Pacific/Honolulu',
            },
            'end': {
                'dateTime': event_data.get('end_time'),
                'timeZone': 'Pacific/Honolulu',
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        return True, f"Event created: {event.get('htmlLink')}"
        
    except Exception as e:
        # Catch potential googleapiclient.errors.HttpError for auth issues
        if 'invalid_grant' in str(e) or 'invalid_credentials' in str(e):
            print("Authentication error during API call. Deleting token to force re-auth.")
            if os.path.exists('token.pickle'):
                os.remove('token.pickle')
        return False, f"Failed to add event: {str(e)}"

def parse_event_string(event_string):
    """Parse event string from Ticketmaster into calendar event format"""
    try:
        # Example formats:
        # "Event Name - YYYY-MM-DD at Venue"
        # "Event Name - YYYY-MM-DD at HH:MM AM/PM at Venue"
        parts = event_string.split(' - ')
        if len(parts) < 2:
            return None

        name = parts[0]
        details = " - ".join(parts[1:])
        
        # Split details into date/time and venue
        if ' at ' not in details:
            return None
        
        # The last ' at ' separates the time from the venue
        time_venue_split = details.rsplit(' at ', 1)
        date_time_str = time_venue_split[0]
        venue = time_venue_split[1]
        
        # Determine the datetime format
        try:
            # Try to parse with time
            dt = datetime.datetime.strptime(date_time_str, "%Y-%m-%d at %I:%M %p")
        except ValueError:
            try:
                # Fallback to parsing with date only (default time)
                dt = datetime.datetime.strptime(date_time_str, "%Y-%m-%d")
                dt = dt.replace(hour=10, minute=0) # Default to 10:00 AM
            except ValueError:
                return None # Could not parse date

        end_dt = dt + datetime.timedelta(hours=2)  # Assume 2-hour duration
        
        return {
            'summary': name,
            'location': venue,
            'description': f'Event found via chatbot: {event_string}',
            'start_time': dt.isoformat(),
            'end_time': end_dt.isoformat()
        }
        
    except Exception:
        return None

def add_events_to_calendar(events, calendar_type="google", creds=None):
    """Add events to calendar (Google Calendar or iCal file)"""
    if calendar_type == "google":
        if not creds:
            return "Authentication credentials are required to add events to Google Calendar."

        success_count = 0
        failed_count = 0
        results = []
        
        for event_string in events:
            if event_string == "No Ticketmaster events found.":
                continue
                
            event_data = parse_event_string(event_string)
            if event_data:
                success, message = add_event_to_google_calendar(event_data, creds)
                if success:
                    success_count += 1
                    results.append(f"✅ {event_data['summary']}")
                else:
                    failed_count += 1
                    results.append(f"❌ {event_data['summary']}: {message}")
            else:
                failed_count += 1
                results.append(f"❌ Failed to parse: {event_string}")
        
        if success_count > 0:
            return f"Successfully added {success_count} events to Google Calendar. {failed_count} events failed."
        else:
            return f"Failed to add any events to Google Calendar. {failed_count} events failed."
    
    elif calendar_type == "ical":
        # Create iCal file
        ical_content = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Chatbot//Calendar//EN\n"
        
        for event_string in events:
            if event_string == "No Ticketmaster events found.":
                continue
                
            event_data = parse_event_string(event_string)
            if event_data:
                # Convert to iCal format
                start_dt = datetime.datetime.fromisoformat(event_data['start_time'])
                end_dt = datetime.datetime.fromisoformat(event_data['end_time'])
                
                ical_content += f"""BEGIN:VEVENT
SUMMARY:{event_data['summary']}
LOCATION:{event_data['location']}
DESCRIPTION:{event_data['description']}
DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}
END:VEVENT
"""
        
        ical_content += "END:VCALENDAR"
        
        # Save to file
        filename = f"hawaii_events_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.ics"
        with open(filename, 'w') as f:
            f.write(ical_content)
        
        return f"Successfully created iCal file: {filename}. You can import this file into your calendar application."

def test_calendar_integration():
    """Test calendar integration with a sample event"""
    try:
        test_event = {
            'summary': 'Test Event from Chatbot',
            'location': 'Honolulu, HI',
            'description': 'This is a test event created by the chatbot.',
            'start_time': (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat(),
            'end_time': (datetime.datetime.now() + datetime.timedelta(hours=2)).isoformat(),
        }
        
        creds = get_credentials()
        if creds:
            success, message = add_event_to_google_calendar(test_event, creds)
            if success:
                return f"✅ **Test successful!** {message}"
            else:
                return f"❌ **Test failed:** {message}"
        else:
            return "❌ **Test failed:** Google Calendar authentication required"
    except Exception as e:
        return f"❌ **Test error:** {str(e)}"

def get_google_auth_prompt():
    """Get instructions for Google Calendar setup"""
    return """
    **Google Calendar Setup Instructions:**
    
    1. **Create Google Cloud Project:**
       - Go to [Google Cloud Console](https://console.cloud.google.com/)
       - Create a new project or select existing one
    
    2. **Enable Calendar API:**
       - Go to "APIs & Services" > "Library"
       - Search for "Google Calendar API"
       - Click "Enable"
    
    3. **Create OAuth Credentials:**
       - Go to "APIs & Services" > "Credentials"
       - Click "Create Credentials" > "OAuth 2.0 Client IDs"
       - Choose "Desktop application"
       - Download the credentials file
    
    4. **Save Credentials:**
       - Rename the downloaded file to `credentials.json`
       - Place it in the same directory as this application
    
    5. **Grant Access:**
       - Use the "Grant Calendar Access" button in the sidebar
       - Follow the authentication process
    """

def clear_authentication():
    """Clear saved authentication tokens and any related session state."""
    try:
        if os.path.exists('token.pickle'):
            os.remove('token.pickle')
        # Clear any other session-related auth flags if they exist
        st.session_state.pop('google_auth_creds', None)
        st.success("Authentication cleared. You will be asked to grant access again.")
    except Exception as e:
        st.error(f"Error clearing authentication: {str(e)}")

def clear_cached_status():
    """Clear any cached status - this is a no-op for our implementation"""
    pass

def force_clear_authentication():
    """Force clear all authentication - same as clear_authentication"""
    return clear_authentication()

def clear_authentication_for_permissions_issue():
    """Clear authentication specifically for permissions issues"""
    return clear_authentication()

def generate_credentials_from_env():
    """Generate credentials.json from environment variables"""
    try:
        # This would need to be implemented based on your environment setup
        # For now, return False to indicate it's not implemented
        return False
    except Exception as e:
        return False


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

def get_conversation_chain(vector_store):
    
    # OpenAI Model
    llm = ChatOpenAI()

    # Custom prompt template
    template = """You are a helpful AI assistant that answers questions based on the provided context. 
    Use the following pieces of context to answer the question at the end.
    If you don't know the answer, just say that you don't know, don't try to make up an answer.
    
    If the user expresses interest about finding events, use the "Real-time Events" list provided in the context to answer them.
    Present the events in a clear, user-friendly format. If the list is empty, kindly inform the user that you couldn't find any events for the specified city.
    After presenting the events, please ask the user if they would like to have them added to their calendar.
    Also, let them know that the search was for the next two months by default and that they can ask to search for events in a different city or over a different time period.

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
    vector_store_retriever = vector_store.as_retriever()
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
    if st.session_state.conversation is None:
        st.error("Please upload and process your PDFs first!")
        return

    # Always add the user's message to history first.
    st.session_state.chat_history.append(HumanMessage(content=question))
    
    event_manager = EventSearchManager()

    # If we are waiting for a city, the user's question is the city
    if event_manager.state['awaiting_city']:
        question = event_manager.handle_city_response(question)
        # We now have the city, so we can proceed to search for events
        # The question is now the original query
    
    # Check if the query is for an event and we don't have a city
    if event_manager.is_event_query(question) and not event_manager.state['city']:
        response_message = event_manager.start_event_search(question)
        st.session_state.chat_history.append(AIMessage(content=response_message))
        st.rerun()
        return

    # Check if the user is confirming to add events to the calendar.
    confirmation_keywords = ["yes", "sure", "ok", "yep", "add them", "please do", "sounds good"]
    # Add a check for last_found_events to ensure we have events to add
    if 'last_found_events' in st.session_state and any(keyword in question.lower() for keyword in confirmation_keywords):
        if len(st.session_state.chat_history) > 1:
            # Check if the last bot message was a question about adding events.
            last_bot_message = st.session_state.chat_history[-2] # User's msg is last, bot's is second-to-last
            if isinstance(last_bot_message, AIMessage) and "add" in last_bot_message.content.lower() and "calendar" in last_bot_message.content.lower():
                # The user confirmed. Trigger the calendar workflow.
                with st.spinner("Accessing your calendar..."):
                    # Use the events we already found and stored in the session state
                    events = st.session_state.last_found_events
                    creds = get_credentials()
                    
                    if creds:
                        calendar_result = add_events_to_calendar(events, "google", creds=creds)
                        response_message = f"Great! I've added those to your calendar. Here's the summary: {calendar_result}"
                        # Clean up the stored events after they've been used
                        del st.session_state.last_found_events
                    else:
                        st.session_state.events_to_add = events
                        st.session_state.pending_calendar_add = True
                        st.session_state.trigger_auth_flow = True
                        response_message = "To add events, I need access to your calendar. Please follow the steps to grant permission, and I'll add them right after."
                
                # Add the final confirmation message from the AI and stop processing.
                st.session_state.chat_history.append(AIMessage(content=response_message))
                st.rerun()
                return

    # If we have a city, we can search for events and inject them.
    event_params = event_manager.get_search_params()
    if event_params:
        with st.spinner(f"Finding events in {event_params['city']}..."):
            # The 'query' for the event search can be the original user query, or empty
            original_query = event_manager.state['original_query'] or question
            events, _ = cached_search_ticketmaster_events(original_query, **event_params)
            
            # Pass events to the retriever
            st.session_state.conversation.retriever.event_list = events
            
            # Reset the event manager so we ask for city next time
            event_manager.reset()
    else:
        # Ensure retriever has no events if not an event query
        st.session_state.conversation.retriever.event_list = []


    response = st.session_state.conversation({'question':question})
    
    # The new logic for handling events is now part of the prompt,
    # so the old post-processing block is no longer needed.
    if response['chat_history']:
        # The response object contains the full history, including the latest AI message.
        # We replace our session state history with this to keep it in sync.
        st.session_state.chat_history = response['chat_history']
    
    # No need to rerun here; the form submission handles it.


def initialize_conversation():
    """Initialize the conversation chain and store it in session state."""
    vector_store = get_vector_store()
    st.session_state.conversation = get_conversation_chain(vector_store)

    # Sync conversation memory with chat history if it exists
    if st.session_state.chat_history:
        st.session_state.conversation.memory.chat_memory.messages = st.session_state.chat_history.copy()


def clear_chat():
    """Clear chat history and reset initial greeting"""
    st.session_state.chat_history = []
    st.session_state.initial_greeting_shown = False
    
    # Clear the conversation memory in the chain
    if "conversation" in st.session_state and st.session_state.conversation:
        st.session_state.conversation.memory.clear()

    # Also clear any lingering event data
    if 'last_found_events' in st.session_state:
        del st.session_state.last_found_events
    st.rerun()

def handle_text_input():
    """Handle text input submission"""
    if st.session_state.user_input and st.session_state.user_input.strip():
        question = st.session_state.user_input.strip()
        handle_user_input(question)
        # Clear the input after processing
        st.session_state.user_input = ""

def handle_send_button():
    """Handle send button click"""
    if st.session_state.user_input and st.session_state.user_input.strip():
        question = st.session_state.user_input.strip()
        handle_user_input(question)
        # Clear the input after processing
        st.session_state.user_input = ""
        st.rerun()

def on_text_change():
    """Handle text area changes and detect Enter key"""
    if st.session_state.user_input and st.session_state.user_input.strip():
        # Check if the last character is a newline (Enter was pressed)
        if st.session_state.user_input.endswith('\n'):
            # Remove the trailing newline and submit
            question = st.session_state.user_input.rstrip('\n')
            if question.strip():  # Only submit if there's actual content
                handle_user_input(question)
                # Don't modify session state here - let the widget handle it
                st.rerun()

def main():
    load_dotenv()
    st.set_page_config(
        page_title='Chat with Your own PDFs', 
        page_icon=':books:',
        layout='wide',
        initial_sidebar_state='expanded'
    )

    # Initialize data store directories
    initialize_data_store()

    # Post-authentication logic: check if a task was pending
    if st.session_state.get('pending_calendar_add'):
        creds = get_credentials()
        if creds:
            events_to_add = st.session_state.get('events_to_add', [])
            if events_to_add:
                with st.spinner("Completing post-authentication task: Adding events..."):
                    calendar_result = add_events_to_calendar(events_to_add, "google", creds=creds)
                    if "Successfully added" in calendar_result:
                        st.success(f"Events added to Google Calendar! {calendar_result}")
                    else:
                        st.error(f"Failed to add events after authentication. Reason: {calendar_result}")
            
            # Clean up session state flags
            del st.session_state.pending_calendar_add
            if 'events_to_add' in st.session_state:
                del st.session_state.events_to_add

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
    
    # Check if we need to restore session state (e.g., after OAuth)
    if "session_restored" not in st.session_state:
        st.session_state.session_restored = False
    
    # Try to restore session state if not already restored
    if not st.session_state.session_restored:
        if restore_session_state():
            st.session_state.session_restored = True
            st.success("✅ Session restored successfully!")
    
    # Initialize chat history before conversation
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Initialize conversation chain if not already done
    if "conversation" not in st.session_state or st.session_state.conversation is None:
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
    
    # Use text_area instead of text_input for better UX
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    
    # Create a container for the text input with custom styling
    input_container = st.container()
    with input_container:
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([6, 1])
            with col1:
                user_input = st.text_area(
                    "Ask anything to your PDF:",
                    key="user_input",
                    height=100,  # Fixed height
                    max_chars=2000,  # Limit characters
                    placeholder="Type your question here... (Press Enter to submit)",
                    help="Press Enter to submit your question"
                )
            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                submit_button = st.form_submit_button("Send", type="primary", use_container_width=True)
            
            if submit_button and user_input and user_input.strip():
                handle_user_input(user_input.strip())
                # The form submission naturally causes a rerun, so this is not needed.
    
    # Display chat history
    if st.session_state.chat_history:
        for i, message in enumerate(reversed(st.session_state.chat_history)):
            if i % 2 == 0:
                st.write(user_template.replace("{{MSG}}", message.content), unsafe_allow_html=True)
            else:
                # Convert newlines to HTML line breaks for bot messages
                formatted_message = convert_newlines_to_html(message.content)
                st.write(bot_template.replace("{{MSG}}", formatted_message), unsafe_allow_html=True)

    # Trigger the authentication flow if requested by the app logic
    if st.session_state.get('trigger_auth_flow'):
        del st.session_state.trigger_auth_flow  # Consume the flag
        run_auth_flow()
        st.rerun()

    with st.sidebar:
        st.subheader("Upload your Documents Here: ")
        pdf_files = st.file_uploader("Choose your PDF Files and Press OK", type=['pdf'], accept_multiple_files=True)

        if pdf_files:
            add_pdfs_to_store(pdf_files)

        st.subheader("Manage Knowledge Base")
        
        with st.expander("Remove Uploaded PDFs"):
            # Display stored PDFs by listing files in the PDF storage directory
            stored_pdfs = [f for f in os.listdir(PDF_STORAGE_PATH) if f.endswith('.pdf')]

            if not stored_pdfs:
                st.info("No PDFs have been added yet.")
            else:
                st.write("Click the trash icon to remove a PDF:")
                for pdf_name in stored_pdfs:
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
                clear_cached_status()
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
            clear_authentication()
            st.rerun()
        
        # Add regenerate credentials button
        if st.button("🔧 Regenerate Credentials", help="Regenerate credentials.json from environment variables"):
            st.write("🔧 **DEBUG**: Regenerating credentials.json from environment variables...")
            if generate_credentials_from_env():
                st.success("✅ credentials.json regenerated successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to regenerate credentials.json. Check your environment variables or Streamlit secrets.")
        
        # Add test calendar integration button
        if st.button("🧪 Test Calendar Integration", help="Add a test event to your Google Calendar to verify it's working"):
            st.write("🧪 **DEBUG**: Testing calendar integration...")
            test_result = test_calendar_integration()
            st.markdown(test_result)
        
        # Add debug events button
        if st.button("🔍 Debug Events", help="Show what events are being fetched and parsed"):
            st.write("🔍 **DEBUG**: Fetching events from Ticketmaster...")
            events = search_ticketmaster_events("")[0]
            st.write(f"**Found {len(events)} events:**")
            for i, event in enumerate(events):
                st.write(f"{i+1}. {event}")
            
            st.write("🔍 **DEBUG**: Parsing events for calendar...")
            for i, event in enumerate(events):
                if event != "No Ticketmaster events found.":
                    parsed = parse_event_string(event)
                    st.write(f"**Event {i+1} parsed as:**")
                    st.json(parsed)
        
        # Check Google Calendar access status
        creds = get_credentials()
        if creds:
            st.success("✅ Google Calendar is connected!")
            st.info("You can now add events directly to your calendar from the chat.")
        else:
            st.warning("🔐 Google Calendar not connected.")
            
            # Add authentication button with better styling
            if st.button("🔐 Grant Calendar Access", type="primary"):
                run_auth_flow()
                st.rerun()
            
            st.info("💡 **Pro tip**: Connect your calendar so events can be added instantly when you need them!")
            
            # Show additional help
            with st.expander("🔧 Need help with OAuth?"):
                st.markdown("""
                **If you're getting redirect_uri_mismatch errors:**
                1. Wait 2-3 minutes for Google Cloud changes to apply
                2. Or run: `python quick_fix_web_client.py` for guided setup
                3. Or run: `python create_desktop_credentials.py` for new desktop credentials
                """)
        
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

def save_session_state():
    """Save current session state to a temporary file."""
    try:
        session_data = {
            'chat_history': [
                {'type': 'human', 'content': msg.content} if isinstance(msg, HumanMessage) 
                else {'type': 'ai', 'content': msg.content} 
                for msg in st.session_state.get('chat_history', [])
            ],
            'events_to_add': st.session_state.get('events_to_add', []),
        }
        
        # Save to a fixed file path that will persist across the redirect.
        with open(".temp_session.json", 'w') as f:
            json.dump(session_data, f)
        
        print("✅ Session state saved for OAuth redirect.")
        return True
    except Exception as e:
        print(f"❌ Error saving session state: {e}")
        return False

def restore_session_state():
    """Restore session state from the temporary file after OAuth."""
    try:
        if os.path.exists(".temp_session.json"):
            with open(".temp_session.json", 'r') as f:
                session_data = json.load(f)
            
            # Restore chat history
            st.session_state.chat_history = []
            for msg_data in session_data.get('chat_history', []):
                if msg_data['type'] == 'human':
                    st.session_state.chat_history.append(HumanMessage(content=msg_data['content']))
                else:
                    st.session_state.chat_history.append(AIMessage(content=msg_data['content']))
            
            # Restore pending events
            st.session_state.events_to_add = session_data.get('events_to_add', [])
            
            # Clean up the temp file immediately after use.
            os.remove(".temp_session.json")
            
            print("✅ Session state restored after OAuth redirect.")
            return True
        return False
    except Exception as e:
        print(f"❌ Error restoring session state: {e}")
        return False

if __name__ == '__main__':
    main()

