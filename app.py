import streamlit as st
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
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

def get_pdf_text(pdf_files):
    
    text = ""
    for pdf_file in pdf_files:
        reader = PdfReader(pdf_file)
        for page in reader.pages:
            text = page.extract_text()
    return text

def get_chunk_text(text):
    text_splitter = CharacterTextSplitter(
        separator = "\n",
        chunk_size = 4000,
        chunk_overlap = 400,
        length_function = len
    )

    chunks = text_splitter.split_text(text)
    return chunks

def process_pdfs_in_batches(pdf_files, batch_size=10):
    all_chunks = []
    for i in range(0, len(pdf_files), batch_size):
        batch = pdf_files[i:i + batch_size]
        raw_text = get_pdf_text(batch)
        chunks = get_chunk_text(raw_text)
        all_chunks.extend(chunks)
    return all_chunks

def get_vector_store(text_chunks):
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_texts(texts=text_chunks, embedding=embeddings)
    return vectorstore

def get_conversation_chain(vector_store):
    
    # OpenAI Model
    llm = ChatOpenAI()

    # Custom prompt template
    template = """You are a helpful AI assistant that answers questions based on the provided context. 
    Use the following pieces of context to answer the question at the end.
    If you don't know the answer, just say that you don't know, don't try to make up an answer.

🔹 IMPORTANT: If the user asks you or ask if you could find events, continue the conversation as usual, addressing the user's query with full context, and naturally insert " EvNtSeArCh " where appropriate in the response. Please treat " EvNtSeArCh " as a placeholder for the events(this means that the events will appear where the placeholder is Ex. here are the events: " EvNtSeArCh " = here are the events: Alonzo Ball - 2025-06-24 at 10:00 AM at Honolulu, HI ).
    Before adding " EvNtSeArCh " make sure to always proceed it with something along the lines of "Here are the events I found for you" or "Here are the events coming up in your location" or something similar.
🔸 You may skip asking follow-up questions like "Would you like me to search for events?" in this case.
    - Only return events if they are happening in the future.
    - If the user doesnt prompt for a search but expresses interest in events ensure to ask them if they would like you to search for related local events coming up at the end of your response. DO not ask questions about the events. The only question related to the events you should ask is the one states before.
    - Ensure you are not confusing projects with events. Events are scheduled gathers, they are not indefinite constructs.m
    - After you return the events, end your message with something related to the conversation and ask if the user would like to add the events to their calendar. If the user agrees to this just add " AdD_CaL " to the end of your message. The system will automatically try to add events to their Google Calendar first, and if that fails, it will save them as a downloadable file.
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

    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)

    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm = llm,
        retriever = vector_store.as_retriever(),
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
    
    # Add user message to chat history
    st.session_state.chat_history.append(HumanMessage(content=question))
    
    response = st.session_state.conversation({'question':question})
    
    # Process EvNtSeArCh replacement in the latest bot response
    if response['chat_history']:
        latest_bot_message = response['chat_history'][-1]  # Last message is the bot's response
        if "EvNtSeArCh" in latest_bot_message.content:
            # Get events and replace the placeholder
            events = search_ticketmaster_events("")[0]

            event_message = "<br>" + "<br> * ".join(events) + "<br>"
            loc = latest_bot_message.content.find("EvNtSeArCh")
            latest_bot_message.content = latest_bot_message.content.replace("EvNtSeArCh", event_message)

        # Handle calendar integration when "AdD_CaL" is detected
        if "AdD_CaL" in latest_bot_message.content:
            events = search_ticketmaster_events("")[0]
            
            creds = get_credentials()

            if creds:
                # If we have credentials, proceed to add the event.
                with st.spinner("Adding events to Google Calendar..."):
                    calendar_result = add_events_to_calendar(events, "google", creds=creds)

                if "Successfully added" in calendar_result:
                    final_message = f"✅ **Events added to Google Calendar!**\n\n{calendar_result}"
                else:
                    final_message = f"❌ **Failed to add events.**\n\n**Reason:** {calendar_result}"
            else:
                # If authentication is required, set flags to trigger the auth flow.
                st.session_state.events_to_add = events
                st.session_state.pending_calendar_add = True
                st.session_state.trigger_auth_flow = True
                
                final_message = "First, I need access to your calendar. Please follow the authentication steps, and I'll add the events for you right after."

            latest_bot_message.content = latest_bot_message.content.replace("AdD_CaL", "").strip()
            latest_bot_message.content += f"\n\n---\n\n{final_message}"

    
    # Update the session state chat history with the full conversation
    st.session_state.chat_history = response['chat_history']

    # If OAuth is triggered, we need to rerun immediately to start the flow.
    if st.session_state.get('trigger_oauth', False):
        st.rerun()

def clear_chat():
    """Clear chat history and reset initial greeting"""
    st.session_state.chat_history = []
    st.session_state.initial_greeting_shown = False
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
    
    if "conversation" not in st.session_state:
        st.session_state.conversation = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
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
                st.rerun()
    
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

        if st.button("OK"):
            with st.spinner("Processing your PDFs..."):
                # Process PDFs in batches
                text_chunks = process_pdfs_in_batches(pdf_files)
                
                # Create Vector Store
                vector_store = get_vector_store(text_chunks)
                st.write("DONE")

                # Create conversation chain
                talk = get_conversation_chain(vector_store)
                st.session_state.conversation = talk
                
                # Set the conversation's memory to include the initial greeting
                if st.session_state.chat_history:
                    st.session_state.conversation.memory.chat_memory.messages = st.session_state.chat_history.copy()

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

