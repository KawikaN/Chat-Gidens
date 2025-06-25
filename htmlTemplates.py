css = '''
<style>
/* Force dark mode for the entire app */
.stApp {
    background-color: #0e1117 !important;
    color: #ffffff !important;
}

/* Override Streamlit's default styling */
.main .block-container {
    background-color: #0e1117 !important;
    color: #ffffff !important;
}

/* Chat message styling */
.chat-message {
    padding: 1.5rem; 
    border-radius: 0.5rem; 
    margin-bottom: 1rem; 
    display: flex;
    background-color: #262730 !important;
    border: 1px solid #464646 !important;
}

.chat-message.user {
    background-color: #2b313e !important;
    border-color: #4a5568 !important;
}

.chat-message.bot {
    background-color: #475063 !important;
    border-color: #718096 !important;
}

.chat-message .avatar {
  width: 20%;
}

.chat-message .avatar img {
  max-width: 78px;
  max-height: 78px;
  border-radius: 50%;
  object-fit: cover;
}

.chat-message .message {
  width: 80%;
  padding: 0 1.5rem;
  color: #ffffff !important;
  white-space: pre-wrap;
}

/* Override Streamlit text input styling */
.stTextArea textarea {
    background-color: #262730 !important;
    color: #ffffff !important;
    border-color: #464646 !important;
}

.stTextArea textarea::placeholder {
    color: #a0a0a0 !important;
}

/* Override Streamlit button styling */
.stButton > button {
    background-color: #4CAF50 !important;
    color: white !important;
    border: none !important;
}

.stButton > button:hover {
    background-color: #45a049 !important;
}

/* Override sidebar styling */
.sidebar .sidebar-content {
    background-color: #0e1117 !important;
    color: #ffffff !important;
}

/* Override file uploader styling */
.stFileUploader {
    background-color: #262730 !important;
    border-color: #464646 !important;
}

/* Override form styling */
.stForm {
    background-color: #262730 !important;
    border-color: #464646 !important;
}
</style>
'''

bot_template = '''
<div class="chat-message bot">
    <div class="avatar">
        <img src="https://i.ibb.co/cN0nmSj/Screenshot-2023-05-28-at-02-37-21.png">
    </div>
    <div class="message">{{MSG}}</div>
</div>
'''

user_template = '''
<div class="chat-message user">
    <div class="avatar">
        <img src="https://i.ibb.co/rdZC7LZ/Photo-logo-1.png">
    </div>    
    <div class="message">{{MSG}}</div>
</div>
'''