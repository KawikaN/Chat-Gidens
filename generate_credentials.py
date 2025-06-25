#!/usr/bin/env python3
"""
Script to generate credentials.json from environment variables.
This keeps sensitive OAuth credentials secure.
"""

import os
import json
from dotenv import load_dotenv

def generate_credentials():
    """Generate credentials.json from environment variables"""
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials from environment variables
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    project_id = os.getenv('GOOGLE_PROJECT_ID')
    auth_uri = os.getenv('GOOGLE_AUTH_URI')
    token_uri = os.getenv('GOOGLE_TOKEN_URI')
    auth_provider_x509_cert_url = os.getenv('GOOGLE_AUTH_PROVIDER_X509_CERT_URL')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    
    # Validate that all required variables are present
    required_vars = {
        'GOOGLE_CLIENT_ID': client_id,
        'GOOGLE_PROJECT_ID': project_id,
        'GOOGLE_AUTH_URI': auth_uri,
        'GOOGLE_TOKEN_URI': token_uri,
        'GOOGLE_AUTH_PROVIDER_X509_CERT_URL': auth_provider_x509_cert_url,
        'GOOGLE_CLIENT_SECRET': client_secret
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file and ensure all Google OAuth credentials are set.")
        return False
    
    # Create credentials structure
    credentials = {
        "web": {
            "client_id": client_id,
            "project_id": project_id,
            "auth_uri": auth_uri,
            "token_uri": token_uri,
            "auth_provider_x509_cert_url": auth_provider_x509_cert_url,
            "client_secret": client_secret
        }
    }
    
    # Write to credentials.json
    try:
        with open('credentials.json', 'w') as f:
            json.dump(credentials, f, indent=2)
        print("✅ credentials.json generated successfully from environment variables!")
        return True
    except Exception as e:
        print(f"❌ Error writing credentials.json: {e}")
        return False

if __name__ == "__main__":
    generate_credentials() 