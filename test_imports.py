#!/usr/bin/env python3
"""
Test script to verify all imports work without problematic dependencies.
This helps ensure Streamlit Cloud deployment will succeed.
"""

def test_imports():
    """Test all imports used in the main application"""
    
    print("🔍 Testing imports for Streamlit Cloud compatibility...")
    
    try:
        import streamlit as st
        print("✅ streamlit")
    except ImportError as e:
        print(f"❌ streamlit: {e}")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv")
    except ImportError as e:
        print(f"❌ python-dotenv: {e}")
        return False
    
    try:
        from PyPDF2 import PdfReader
        print("✅ PyPDF2")
    except ImportError as e:
        print(f"❌ PyPDF2: {e}")
        return False
    
    try:
        from langchain.text_splitter import CharacterTextSplitter
        print("✅ langchain.text_splitter")
    except ImportError as e:
        print(f"❌ langchain.text_splitter: {e}")
        return False
    
    try:
        from langchain.embeddings import OpenAIEmbeddings
        print("✅ langchain.embeddings")
    except ImportError as e:
        print(f"❌ langchain.embeddings: {e}")
        return False
    
    try:
        from langchain.vectorstores import Chroma
        print("✅ langchain.vectorstores (Chroma)")
    except ImportError as e:
        print(f"❌ langchain.vectorstores: {e}")
        return False
    
    try:
        from langchain.memory import ConversationBufferMemory
        print("✅ langchain.memory")
    except ImportError as e:
        print(f"❌ langchain.memory: {e}")
        return False
    
    try:
        from langchain.chains import ConversationalRetrievalChain
        print("✅ langchain.chains")
    except ImportError as e:
        print(f"❌ langchain.chains: {e}")
        return False
    
    try:
        from langchain.chat_models import ChatOpenAI
        print("✅ langchain.chat_models")
    except ImportError as e:
        print(f"❌ langchain.chat_models: {e}")
        return False
    
    try:
        from langchain.prompts import PromptTemplate
        print("✅ langchain.prompts")
    except ImportError as e:
        print(f"❌ langchain.prompts: {e}")
        return False
    
    try:
        from langchain.schema import AIMessage, HumanMessage
        print("✅ langchain.schema")
    except ImportError as e:
        print(f"❌ langchain.schema: {e}")
        return False
    
    try:
        import requests
        print("✅ requests")
    except ImportError as e:
        print(f"❌ requests: {e}")
        return False
    
    try:
        import webbrowser
        print("✅ webbrowser")
    except ImportError as e:
        print(f"❌ webbrowser: {e}")
        return False
    
    try:
        import chromadb
        print("✅ chromadb")
    except ImportError as e:
        print(f"❌ chromadb: {e}")
        return False
    
    try:
        from google.auth.oauthlib.flow import InstalledAppFlow
        print("✅ google-auth-oauthlib")
    except ImportError as e:
        print(f"❌ google-auth-oauthlib: {e}")
        return False
    
    try:
        from googleapiclient.discovery import build
        print("✅ google-api-python-client")
    except ImportError as e:
        print(f"❌ google-api-python-client: {e}")
        return False
    
    print("\n🎉 All imports successful! App is ready for Streamlit Cloud deployment.")
    return True

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✅ Ready for deployment!")
    else:
        print("\n❌ Some imports failed. Check requirements.txt") 