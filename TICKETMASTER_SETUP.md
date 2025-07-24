# Ticketmaster API Setup Guide

To enable Ticketmaster events in your enhanced event search system, you need to set up a Ticketmaster API key.

## 🎫 **Step 1: Get Ticketmaster API Key**

1. Go to [Ticketmaster Developer Portal](https://developer.ticketmaster.com/)
2. Sign up for a free developer account
3. Create a new app/project
4. Copy your API key (Consumer Key)

## 🔧 **Step 2: Configure the API Key**

### Option A: Environment Variable (Recommended)
```bash
export TICKETMASTER_API_KEY='your_api_key_here'
```

### Option B: Add to .env file
```bash
# Add this line to your .env file
TICKETMASTER_API_KEY=your_api_key_here
```

### Option C: Streamlit Secrets (for deployment)
```toml
# Add to .streamlit/secrets.toml
TICKETMASTER_API_KEY = "your_api_key_here"
```

## ✅ **Step 3: Test the Integration**

Run this command to test if Ticketmaster events are working:

```bash
python debug_ticketmaster_integration.py
```

You should see output like:
```
Ticketmaster found: X events
Enhanced search returned: Y total events (local + Ticketmaster)
```

## 🌟 **Expected Results**

Once configured, when users search for events, they will see:

**Local Hawaii Events (from your database):**
- Poke Bowl Festival
- Hawaii Business Connect Networking  
- Hula Under the Stars
- Hawaiian Quilting Circle

**PLUS Ticketmaster Events:**
- Concerts in Honolulu
- Sports events
- Theater shows
- Festivals and exhibitions

## 📊 **Event Display Format**

Events will be categorized and displayed like:

```
**Food & Culinary:**
1. Poke Bowl Festival - 2025-02-20 at Kapiolani Park

**Business & Networking:**
2. Hawaii Business Connect Networking - 2025-02-18 at Honolulu Convention Center

**Music & Entertainment:**
3. Concert Name - Date at Venue (from Ticketmaster)

**Live Events (Ticketmaster):**
4. Sports Event - Date at Stadium
```

## 🔍 **Troubleshooting**

- **API Key Issues**: Make sure your key is valid and not expired
- **Rate Limits**: Ticketmaster has rate limits; the app handles this gracefully
- **No Events Found**: This is normal for small cities; local events will still show

## 💡 **Benefits of Integration**

✅ **Comprehensive Event Coverage**: Local + Live events  
✅ **Real-time Data**: Fresh Ticketmaster events  
✅ **Smart Categorization**: Events grouped by type  
✅ **Graceful Fallback**: Works even if Ticketmaster is unavailable  
✅ **User Preference Tracking**: System learns what users like 