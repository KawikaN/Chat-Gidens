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
from calendar_integration import calendar_integration
# from transformers import pipeline
import requests
from langchain.schema import AIMessage, HumanMessage
import webbrowser

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
            # if events:
                # event_lines = []
                # for e in events:
                    # name = e.get('name', 'Unknown')
                    # start = e.get('dates', {}).get('start', {}).get('localDate', 'Unknown')
                    # venue = e.get('_embedded', {}).get('venues', [{}])[0].get('name', 'Unknown')
                    # event_lines.append(f"• {name} — {start} at {venue}")
                # event_message = "\n".join(event_lines)
                # print("kk ", event_message)
            # else:
                # event_message = "No events found at this time."
            
            # Replace the placeholder with actual events
            # for i in search_ticketmaster_events("")[0]:
                # print(i)
            event_message = "<br>" + "<br> * ".join(events) + "<br>"
            loc = latest_bot_message.content.find("EvNtSeArCh")
            latest_bot_message.content = latest_bot_message.content.replace("EvNtSeArCh", event_message)

        # Handle calendar integration when "AdD_CaL" is detected
        if "AdD_CaL" in latest_bot_message.content:
            # Get the events that were displayed
            events = search_ticketmaster_events("")[0]
            
            # Check current access status first
            has_access, status = calendar_integration.check_google_calendar_access()
            
            if has_access:
                # Already authenticated, try to add events directly
                calendar_result = calendar_integration.add_events_to_calendar(events, "google")
                if "Successfully added" in calendar_result:
                    calendar_result = f"✅ **Events added to Google Calendar!**\n\n{calendar_result}"
                else:
                    # Google Calendar failed, fall back to iCal
                    calendar_result = calendar_integration.add_events_to_calendar(events, "ical")
                    if "Successfully created iCal file:" in calendar_result:
                        file_path = calendar_result.split("Successfully created iCal file: ")[1].split(". You can")[0]
                        st.session_state.ical_file_path = file_path
                        calendar_result = f"📅 **Events saved as iCal file**\n\n{calendar_result}\n\nYou can download the file from the sidebar."
                    else:
                        calendar_result = f"❌ **Calendar integration failed**\n\n{calendar_result}"
            else:
                # No access - check if we should attempt OAuth or just use fallback
                if ("authentication required" in status.lower() or 
                    "token expired" in status.lower() or 
                    "not connected" in status.lower() or
                    "permissions insufficient" in status.lower() or
                    "re-authenticate" in status.lower()):
                    
                    # Special handling for insufficient permissions - auto-clear and provide clear instructions
                    if "permissions insufficient" in status.lower():
                        # Automatically clear the problematic authentication
                        clear_message = calendar_integration.clear_authentication_for_permissions_issue()
                        calendar_result = f"🔐 **Google Calendar Permissions Issue Fixed**\n\n{clear_message}\n\n**What happened:** Your Google account was connected but didn't have calendar permissions.\n\n**Solution:** I've cleared your authentication. Please use the 'Grant Calendar Access' button in the sidebar to re-authenticate with proper calendar permissions.\n\n**For now, events have been saved as an iCal file that you can download from the sidebar.**"
                    else:
                        # User needs to authenticate - provide instructions instead of auto-initiating OAuth
                        calendar_result = f"🔐 **Google Calendar Authentication Required**\n\n{status}\n\n**To add events to your Google Calendar:**\n1. Use the 'Grant Calendar Access' button in the sidebar\n2. Follow the authentication process\n3. Then try adding events again\n\n**For now, events have been saved as an iCal file that you can download from the sidebar.**"
                    
                    # Save events as iCal file as fallback
                    ical_result = calendar_integration.add_events_to_calendar(events, "ical")
                    if "Successfully created iCal file:" in ical_result:
                        file_path = ical_result.split("Successfully created iCal file: ")[1].split(". You can")[0]
                        st.session_state.ical_file_path = file_path
                        calendar_result += f"\n\n📅 **iCal file created:** {ical_result}"
                else:
                    # Other issues (setup required, etc.) - just use iCal fallback
                    calendar_result = f"⚠️ **Google Calendar Issue**\n\n{status}\n\n**Events have been saved as an iCal file that you can download from the sidebar.**"
                    
                    # Save events as iCal file
                    ical_result = calendar_integration.add_events_to_calendar(events, "ical")
                    if "Successfully created iCal file:" in ical_result:
                        file_path = ical_result.split("Successfully created iCal file: ")[1].split(". You can")[0]
                        st.session_state.ical_file_path = file_path
                        calendar_result += f"\n\n📅 **iCal file created:** {ical_result}"
            
            # Remove "AdD_CaL" from the message and add calendar result
            latest_bot_message.content = latest_bot_message.content.replace("AdD_CaL", "")
            latest_bot_message.content += f"\n\n📅 **Calendar Update:** {calendar_result}"

    
    # Update the session state chat history with the full conversation
    st.session_state.chat_history = response['chat_history']

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

evt = False
def main():
    load_dotenv()
    st.set_page_config(
        page_title='Chat with Your own PDFs', 
        page_icon=':books:',
        layout='wide',
        initial_sidebar_state='expanded'
    )

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
                calendar_integration.clear_cached_status()
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
            st.write("🗑️ **DEBUG**: Clearing all authentication...")
            calendar_integration.force_clear_authentication()
            st.success("✅ Authentication cleared! You'll need to re-authenticate.")
            st.rerun()
        
        # Add regenerate credentials button
        if st.button("🔧 Regenerate Credentials", help="Regenerate credentials.json from environment variables"):
            st.write("🔧 **DEBUG**: Regenerating credentials.json from environment variables...")
            from calendar_integration import generate_credentials_from_env
            if generate_credentials_from_env():
                st.success("✅ credentials.json regenerated successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to regenerate credentials.json. Check your environment variables or Streamlit secrets.")
        
        # Add test calendar integration button
        if st.button("🧪 Test Calendar Integration", help="Add a test event to your Google Calendar to verify it's working"):
            st.write("🧪 **DEBUG**: Testing calendar integration...")
            test_result = calendar_integration.test_calendar_integration()
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
                    parsed = calendar_integration.parse_event_string(event)
                    st.write(f"**Event {i+1} parsed as:**")
                    st.json(parsed)
        
        # Check Google Calendar access status
        has_access, status = calendar_integration.check_google_calendar_access()
        
        if has_access:
            st.success("✅ Google Calendar is ready to use!")
            st.info("Events will be automatically added to your Google Calendar when you agree to add them.")
            st.info("💡 **Note**: Your authentication will persist across sessions. You won't need to re-authenticate unless the token expires.")
        else:
            # Show appropriate message based on status
            if "setup required" in status.lower():
                st.error("🔧 Google Calendar setup required")
                with st.expander("📋 Setup Instructions"):
                    st.markdown(calendar_integration.get_google_auth_prompt())
            elif ("authentication required" in status.lower() or 
                  "token expired" in status.lower() or 
                  "not connected" in status.lower() or
                  "timed out" in status.lower() or
                  "access error" in status.lower() or
                  "permissions insufficient" in status.lower() or
                  "re-authenticate" in status.lower()):
                
                # Special handling for insufficient permissions
                if "permissions insufficient" in status.lower():
                    st.error("🔐 Google Calendar permissions insufficient")
                    st.warning("Your Google account is connected but doesn't have calendar permissions. This usually happens when the OAuth flow didn't request calendar access.")
                    
                    # Add clear authentication button for this specific case
                    if st.button("🗑️ Clear & Re-authenticate", type="secondary", help="Clear current authentication and start fresh OAuth"):
                        calendar_integration.force_clear_authentication()
                        st.success("✅ Authentication cleared! Please use the 'Grant Calendar Access' button below to re-authenticate with proper calendar permissions.")
                        st.rerun()
                    
                    st.info("💡 **Solution**: Clear your current authentication and re-authenticate to grant proper calendar permissions.")
                
                st.warning("🔐 Google Calendar authentication required")
                
                # Add authentication button with better styling
                auth_col1, auth_col2 = st.columns([1, 2])
                with auth_col1:
                    if st.button("🔐 Grant Calendar Access", type="primary"):
                        # Save current session state before OAuth
                        session_file = save_session_state()
                        
                        # Show detailed instructions before starting OAuth
                        st.info("""
                        **🔐 Google Calendar Authentication Process:**
                        
                        1. **Browser will open** - Google sign-in page will appear
                        2. **Sign in with Google** - Use your Google account
                        3. **Grant permissions** - Allow calendar access
                        4. **Success page** - You'll see a success message
                        5. **Auto-close** - Browser window should close automatically
                        6. **Return to chatbot** - You're all set!
                        
                        **💡 Tip:** If the browser doesn't close automatically, just close it manually.
                        """)
                        
                        with st.spinner("🔐 Opening Google sign-in page..."):
                            success, message = calendar_integration.initiate_oauth_flow()
                            if success:
                                st.success("🎉 Authentication Successful!")
                                st.info(message)
                                st.balloons()  # Add some celebration!
                                
                                # Restore session state after successful OAuth
                                if session_file:
                                    restore_session_state()
                                
                                st.rerun()  # Refresh to show updated status
                            else:
                                st.error("❌ Authentication Failed")
                                st.error(message)
                                
                                # Restore session state even if OAuth failed
                                if session_file:
                                    restore_session_state()
                                
                                with st.expander("📋 Setup Instructions"):
                                    st.markdown(calendar_integration.get_google_auth_prompt())
                
                with auth_col2:
                    st.info("💡 **Pro tip**: Set up authentication now so events can be added instantly when you need them!")
                
                # Show additional help
                with st.expander("🔧 Need help with OAuth?"):
                    st.markdown("""
                    **If you're getting redirect_uri_mismatch errors:**
                    1. Wait 2-3 minutes for Google Cloud changes to apply
                    2. Or run: `python quick_fix_web_client.py` for guided setup
                    3. Or run: `python create_desktop_credentials.py` for new desktop credentials
                    """)
            else:
                st.error(f"❌ Google Calendar issue: {status}")
                with st.expander("📋 Setup Instructions"):
                    st.markdown(calendar_integration.get_google_auth_prompt())
        
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
    """Save current session state to a temporary file"""
    try:
        import json
        import tempfile
        
        session_data = {
            'chat_history': [msg.content for msg in st.session_state.chat_history],
            'conversation_ready': st.session_state.conversation is not None,
            'initial_greeting_shown': st.session_state.initial_greeting_shown,
            'user_input': st.session_state.get('user_input', ''),
            'pdf_files_processed': True if st.session_state.conversation else False
        }
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(session_data, temp_file)
        temp_file.close()
        
        # Store the file path in session state
        st.session_state.temp_session_file = temp_file.name
        print(f"✅ Session state saved to: {temp_file.name}")
        return temp_file.name
    except Exception as e:
        print(f"❌ Error saving session state: {e}")
        return None

def restore_session_state():
    """Restore session state from temporary file"""
    try:
        import json
        import os
        
        if 'temp_session_file' in st.session_state and os.path.exists(st.session_state.temp_session_file):
            with open(st.session_state.temp_session_file, 'r') as f:
                session_data = json.load(f)
            
            # Restore chat history
            if 'chat_history' in session_data:
                from langchain.schema import AIMessage, HumanMessage
                restored_history = []
                for i, content in enumerate(session_data['chat_history']):
                    if i % 2 == 0:  # Bot messages
                        restored_history.append(AIMessage(content=content))
                    else:  # User messages
                        restored_history.append(HumanMessage(content=content))
                st.session_state.chat_history = restored_history
            
            # Restore other state
            if 'initial_greeting_shown' in session_data:
                st.session_state.initial_greeting_shown = session_data['initial_greeting_shown']
            
            if 'user_input' in session_data:
                st.session_state.user_input = session_data['user_input']
            
            # Clean up temp file
            try:
                os.remove(st.session_state.temp_session_file)
                del st.session_state.temp_session_file
            except:
                pass
            
            print("✅ Session state restored successfully")
            return True
        else:
            print("ℹ️ No session state file found to restore")
            return False
    except Exception as e:
        print(f"❌ Error restoring session state: {e}")
        return False

if __name__ == '__main__':
    main()

