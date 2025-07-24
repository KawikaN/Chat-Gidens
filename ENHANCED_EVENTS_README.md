# Enhanced Event Management System

This enhanced event management system provides intelligent event discovery, topic-based filtering, user preference tracking, and uncertainty handling for the Hawaii Business Assistant chatbot.

## 🌟 Key Features

### 1. **Topic-Based Event Filtering**
- Users can search for events by specific topics or categories
- Intelligent LLM-powered topic detection from natural language queries
- Support for multiple topic filtering with user preference selection

**Examples:**
- "Show me music events" → Finds concerts, performances, festivals
- "Any business networking events?" → Filters for professional meetups
- "Find food festivals" → Discovers culinary events and tastings

### 2. **Uncertain Event Handling**
- System identifies events with unclear descriptions or insufficient information
- Stores uncertain events separately for user review
- Offers to show uncertain events when no clear matches are found

**Examples:**
- Events with vague titles like "Big Wave Bash" or "The Experiment"
- Events missing key details (date, venue, description)
- Events with invitation-only or TBA information

### 3. **User Preference Tracking**
- Tracks which events users view and add to calendar
- Builds user interest profile over time
- Suggests similar events based on past preferences

**Tracked Actions:**
- Events viewed
- Events added to calendar
- Event types frequently accessed
- Topic preferences

### 4. **External Research Capability**
- Can research additional event information using web search
- Enhances event details with found information
- Suggests improvements to event database

**Research Areas:**
- Ticket pricing
- Event duration
- Age restrictions
- Additional event details

### 5. **Clean Event Display Format**
- Shows only essential information in chat (name, date, location)
- Detailed information available on request
- Organized by event categories for better browsing

## 🔧 Setup and Installation

### 1. Run the Sample Data Script
```bash
python sample_events_data.py
```

This will create:
- Sample events in various categories
- Uncertain events for testing
- Sample user preference data
- All necessary data files in `data_store/`

### 2. Data Files Created
- `data_store/event_database.json` - Main event storage
- `data_store/user_event_preferences.json` - User interaction tracking
- `data_store/uncertain_events.json` - Events needing clarification
- `data_store/event_research_suggestions.json` - Research findings

## 💬 Usage Examples

### Basic Event Searches
```
User: "Find me some music events"
Bot: Aloha! I found these events for you:

**Music:**
1. Jazz at Blue Note - 2025-02-15 at Blue Note Hawaii

Would you like me to add any of these to your calendar?
```

### Topic Selection Flow
```
User: "Show me business and food and music events"
Bot: I detected you're interested in events related to: business, food, music. 
     Would you like me to show events for all these topics, or would you prefer 
     to focus on specific ones?

User: "Just business and food please"
Bot: Great! Here are the events for your selected topics:
     [filtered results]
```

### Uncertain Events
```
User: "Find events in Honolulu"
Bot: [shows regular events]
     
     I also have 3 event(s) that I'm not completely sure about based on 
     their titles and descriptions. Would you like me to show you these 
     events so you can decide if they interest you?

User: "Yes, show them"
Bot: **Events I'm uncertain about:**
     *(These events had unclear descriptions or titles)*
     
     1. **Big Wave Bash**
        📅 Date: 2025-03-10
        📍 Venue: Secret Location TBA
        📝 Description: Something big is coming to the North Shore. Details TBA.
        ❓ Reason for uncertainty: unclear_description
```

## 🛠️ Technical Implementation

### Core Components

1. **EnhancedEventManager** (`enhanced_events.py`)
   - Main event storage and retrieval
   - Topic filtering with LLM intelligence
   - User preference tracking
   - Uncertain event management

2. **TopicBasedEventSearch** (`enhanced_topic_search.py`)
   - Topic detection from user queries
   - Multi-topic handling and selection
   - Uncertain event presentation

3. **EnhancedEventConversationFlow** (`enhanced_topic_search.py`)
   - Conversation state management
   - Integration with existing chat flow
   - Response formatting and user interaction

### Integration Points

The enhanced system integrates with the existing `app.py` through:
- Modified `handle_user_input()` function
- Enhanced event search logic
- Calendar integration with preference tracking
- Streamlit session state management

## 🎯 Event Data Format

### Regular Events
```json
{
  "name": "Event Name",
  "date": "2025-02-15",
  "venue": "Venue Name",
  "description": "Event description...",
  "categories": ["music", "jazz", "entertainment"],
  "event_type": "Music",
  "ticket_price": "$45-65",
  "age_restrictions": "21+",
  "duration": "2 hours"
}
```

### Uncertain Events
```json
{
  "event": {
    "name": "Unclear Event",
    "date": "2025-03-10",
    "venue": "TBA",
    "description": "Vague description"
  },
  "reason": "unclear_description",
  "status": "pending_review"
}
```

## 🔍 Advanced Features

### 1. Research Integration
When enabled, the system can:
- Search the web for additional event information
- Extract relevant details using LLM analysis
- Store research suggestions for manual review
- Enhance event descriptions with found data

### 2. Similar Event Suggestions
Based on user preferences, suggests:
- Events in similar categories
- Same venue types
- Similar artists or performers
- Related event themes

### 3. Smart Event Addition
When users add events to calendar:
- Tracks the action for preference learning
- Updates user interest profile
- Influences future event recommendations
- Maintains interaction history

## 🚀 Future Enhancements

### Planned Features
1. **Web Search Integration**
   - Real-time event research
   - Automatic event database updates
   - Price and availability checking

2. **Event Categorization**
   - Automatic event tagging
   - Smart category suggestions
   - Improved filtering algorithms

3. **User Profiles**
   - Persistent user preferences
   - Cross-session learning
   - Personalized event recommendations

4. **Event Validation**
   - Automatic event verification
   - Crowd-sourced event updates
   - Real-time event status checking

## 🤝 Contributing

To add new events or improve the system:

1. **Add Events Manually:**
   ```python
   from enhanced_events import EnhancedEventManager
   manager = EnhancedEventManager()
   
   event_data = {
       "name": "Your Event",
       "date": "2025-XX-XX",
       "venue": "Venue Name",
       "description": "Event description",
       "categories": ["category1", "category2"]
   }
   
   manager.add_event_to_database(event_data, source="manual")
   ```

2. **Report Uncertain Events:**
   When you encounter events with unclear information, the system will automatically categorize them as uncertain for review.

3. **Improve Topic Detection:**
   The LLM-based topic detection can be enhanced by updating the prompts in `enhanced_topic_search.py`.

## 📊 Analytics and Insights

The system tracks:
- Most popular event types
- User search patterns
- Successful event additions
- Topic preferences over time
- Uncertain event resolution rates

This data helps improve:
- Event recommendations
- Search result relevance
- User experience
- System accuracy

## 🎉 Getting Started

1. Run `python sample_events_data.py` to set up sample data
2. Start the main application: `streamlit run app.py`
3. Try topic-based searches: "Find me music events"
4. Explore uncertain events: "Show me uncertain events"
5. Add events to calendar to build your preference profile

The enhanced event system makes discovering and managing Hawaii events more intelligent, personalized, and user-friendly! 