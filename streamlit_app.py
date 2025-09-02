import asyncio
import streamlit as st
from dotenv import load_dotenv
from typing import List, Dict, Optional
import uuid

load_dotenv('/Users/pdwivedi/Documents/Projects/flight_agent/.env')

from scoping_agents import clarify_with_user, write_flight_search_brief
from single_agent_mcp import find_flights, search_flights_agent
from agents import SQLiteSession
from db import (
    save_session_to_db, 
    load_session_from_db, 
    get_all_sessions, 
    delete_session_from_db,
    update_session_title
)
# Agent routing function
async def route_to_agent(query: str, current_agent: str, session):
    """
    Route the query to the appropriate agent based on current agent state.
    
    Args:
        query: User query
        current_agent: Current agent ("flight_agent" or "itinerary_agent")
        session: SQLiteSession
        
    Returns:
        Agent response
    """
    print(f"🎯 Routing to agent: {current_agent}")
    
    if current_agent == "itinerary_agent":
        # For now, we'll use the flight agent function but with itinerary context
        # In the future, you might want to create a separate itinerary agent function
        itinerary_context = f"[ITINERARY PLANNING MODE] {query}\n\nNote: You are now in itinerary planning mode. Focus on helping the user plan their trip itinerary, activities, and travel arrangements."
        return await find_flights(itinerary_context, verbose=False, session=session)
    else:
        # Default to flight agent
        return await find_flights(query, verbose=False, session=session)

# Simple token estimation for UI display (rough approximation)
def estimate_tokens_for_session(session_data: dict) -> int:
    """
    Simple token estimation for UI display purposes.
    This is a rough approximation - actual token counting is done by the agents SDK.
    """
    try:
        total_chars = 0
        
        # Count characters in messages
        messages = session_data.get('messages', [])
        if messages:
            for msg in messages:
                content = msg.get('content', '') if msg else ''
                if content:
                    total_chars += len(content)
        
        # Count characters in chat messages
        chat_messages = session_data.get('chat_messages', [])
        if chat_messages:
            for msg in chat_messages:
                content = msg.get('content', '') if msg else ''
                if content:
                    total_chars += len(content)
        
        # Count characters in other fields (handle None values)
        research_brief = session_data.get('research_brief') or ''
        flight_results = session_data.get('flight_results') or ''
        
        total_chars += len(research_brief)
        total_chars += len(flight_results)
        
        # Rough approximation: 4 characters per token (this is very approximate)
        return max(total_chars // 4, 0)  # Ensure we don't return negative values
    
    except Exception as e:
        print(f"Warning: Could not estimate tokens: {e}")
        return 0  # Return 0 if estimation fails

# Handoff detection function
def detect_handoff(response_text: str) -> Optional[Dict[str, str]]:
    """
    Detect if a response contains an agent handoff.
    
    Args:
        response_text: The agent's response text
        
    Returns:
        Dictionary with handoff info if detected, None otherwise
    """
    if not response_text:
        return None
    
    # Common handoff indicators
    handoff_indicators = [
        "handoff to",
        "transferring to",
        "switching to",
        "handing over to",
        "passing to",
        "itinerary planner",
        "flight agent",
        "flight search agent"
    ]
    
    response_lower = response_text.lower()
    
    # Check for handoff indicators
    for indicator in handoff_indicators:
        if indicator in response_lower:
            # Try to determine which agent
            if "itinerary" in response_lower or "planner" in response_lower:
                return {
                    "type": "handoff",
                    "to_agent": "Itinerary Planner Agent",
                    "from_agent": "Flight Search Agent",
                    "indicator": indicator
                }
            elif "flight" in response_lower and ("search" in response_lower or "agent" in response_lower):
                return {
                    "type": "handoff", 
                    "to_agent": "Flight Search Agent",
                    "from_agent": "Itinerary Planner Agent",
                    "indicator": indicator
                }
    
    # Check for specific agent mentions that might indicate handoffs
    if "itinerary planner" in response_lower and ("help" in response_lower or "assist" in response_lower):
        return {
            "type": "handoff",
            "to_agent": "Itinerary Planner Agent", 
            "from_agent": "Flight Search Agent",
            "indicator": "agent mention"
        }
    
    return None
# from research_agent_mcp import conduct_research  # COMMENTED OUT FOR TESTING

st.set_page_config(
    page_title="Flight Search Assistant", 
    page_icon="✈️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for beautiful styling
st.markdown("""
<style>
    /* Main container styling */
    .main > div {
        padding-top: 2rem;
    }
    
    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* Card styling */
    .card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid #e1e8ed;
        margin-bottom: 1rem;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Success message styling */
    .stSuccess {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        border-radius: 8px;
    }
    
    /* Chat message styling */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Spinner styling */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* Input styling */
    .stTextArea > div > div > textarea {
        border-radius: 8px;
        border: 2px solid #e1e8ed;
        transition: border-color 0.3s ease;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Progress indicators */
    .progress-step {
        display: flex;
        align-items: center;
        margin: 1rem 0;
        padding: 1rem;
        background: #f8f9fa;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    
    .progress-step.completed {
        border-left-color: #38ef7d;
        background: #f0fff4;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .status-badge.processing {
        background: #fff3cd;
        color: #856404;
    }
    
    .status-badge.completed {
        background: #d4edda;
        color: #155724;
    }
    
    .status-badge.error {
        background: #f8d7da;
        color: #721c24;
    }
    
    /* Handoff indicator styling */
    .handoff-indicator {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        border: 1px solid #ff9a9e;
        border-radius: 8px;
        padding: 0.75rem;
        margin: 0.5rem 0;
        color: #721c24;
        font-weight: 600;
        box-shadow: 0 2px 10px rgba(255, 154, 158, 0.2);
    }
    
    .handoff-indicator .handoff-arrow {
        font-size: 1.2rem;
        margin: 0 0.5rem;
    }
    
    /* Agent name styling in handoffs */
    .agent-name {
        background: rgba(255, 255, 255, 0.8);
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# Main header
st.markdown("""
<div class="main-header">
    <h1>✈️ Flight Search Assistant</h1>
    <p>AI-powered flight search with intelligent scoping and real-time results</p>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "waiting_for_answers" not in st.session_state:
    st.session_state.waiting_for_answers = False
if "current_questions" not in st.session_state:
    st.session_state.current_questions = []
if "research_brief" not in st.session_state:
    st.session_state.research_brief = None
if "research_results" not in st.session_state:
    st.session_state.research_results = None
if "conducting_research" not in st.session_state:
    st.session_state.conducting_research = False
if "flight_results" not in st.session_state:
    st.session_state.flight_results = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = False
if "processing_chat" not in st.session_state:
    st.session_state.processing_chat = False
if "step" not in st.session_state:
    st.session_state.step = "input"  # input, clarifying, brief_generated, searching, results, chat
if "error_message" not in st.session_state:
    st.session_state.error_message = None
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "sqlite_session" not in st.session_state:
    st.session_state.sqlite_session = None
if "current_agent" not in st.session_state:
    st.session_state.current_agent = "flight_agent"  # Default to flight agent
if "last_handoff" not in st.session_state:
    st.session_state.last_handoff = None

# Tab interface for session management
tab1, tab2 = st.tabs(["🆕 New Search", "📂 Resume Search"])

with tab1:
    # New search tab
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Start a New Flight Search")
    with col2:
        if st.button("➕ Create New Session", type="primary"):
            # Create new session
            new_session_id = str(uuid.uuid4())
            st.session_state.current_session_id = new_session_id
            st.session_state.sqlite_session = SQLiteSession(new_session_id)
            
            # Reset all session state for new search
            for key in ['messages', 'waiting_for_answers', 'current_questions', 'research_brief', 
                       'flight_results', 'chat_messages', 'chat_mode', 'processing_chat']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.step = "input"
            st.session_state.error_message = None
            st.rerun()

with tab2:
    # Resume search tab
    st.markdown("### Resume Previous Search")
    
    # Get all sessions
    sessions = get_all_sessions()
    
    if sessions:
        # Display sessions in a nice format
        for session in sessions:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    # Session info
                    status_emoji = "✅" if session['step'] == "results" else "🔄" if session['step'] in ["searching", "clarifying"] else "📝"
                    
                    # Add memory status indicator
                    memory_indicator = ""
                    if session.get('is_summarized', False):
                        memory_indicator = " 🧠"  # Brain emoji for summarized sessions
                    elif session.get('token_count', 0) > 150000:  # Approaching limit
                        memory_indicator = " ⚠️"  # Warning for high token count
                    
                    st.write(f"{status_emoji} **{session['title']}**{memory_indicator}")
                    
                    # Enhanced caption with token info
                    caption_parts = [f"Step: {session['step'].title()}", f"Updated: {session['updated_at'][:16]}"]
                    if session.get('token_count', 0) > 0:
                        token_count = session['token_count']
                        if token_count > 1000:
                            caption_parts.append(f"Tokens: {token_count//1000}K")
                        else:
                            caption_parts.append(f"Tokens: {token_count}")
                    if session.get('is_summarized', False):
                        caption_parts.append("Summarized")
                    
                    st.caption(" | ".join(caption_parts))
                
                with col2:
                    if st.button("📂 Resume", key=f"resume_{session['session_id']}"):
                        # Load session
                        session_data = load_session_from_db(session['session_id'])
                        if session_data:
                            st.session_state.current_session_id = session['session_id']
                            st.session_state.sqlite_session = SQLiteSession(session['session_id'])
                            
                            # Load session data into streamlit state
                            st.session_state.step = session_data['step']
                            st.session_state.messages = session_data['messages']
                            st.session_state.research_brief = session_data['research_brief']
                            st.session_state.flight_results = session_data['flight_results']
                            st.session_state.chat_messages = session_data['chat_messages']
                            st.session_state.initial_handoff = session_data.get('initial_handoff', None)
                            
                            # Restore agent state
                            st.session_state.current_agent = session_data.get('current_agent', 'flight_agent')
                            st.session_state.last_handoff = session_data.get('last_handoff', None)
                            
                            # Set appropriate flags
                            st.session_state.chat_mode = session_data['step'] == 'chat'
                            st.session_state.waiting_for_answers = False
                            st.session_state.processing_chat = False
                            
                            st.success(f"Resumed session: {session_data['title']}")
                            st.rerun()
                
                with col3:
                    if st.button("✏️ Rename", key=f"rename_{session['session_id']}"):
                        st.session_state[f"rename_mode_{session['session_id']}"] = True
                        st.rerun()
                
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_{session['session_id']}"):
                        delete_session_from_db(session['session_id'])
                        st.success("Session deleted!")
                        st.rerun()
                
                # Rename functionality
                if st.session_state.get(f"rename_mode_{session['session_id']}", False):
                    new_title = st.text_input(
                        "New title:", 
                        value=session['title'], 
                        key=f"new_title_{session['session_id']}"
                    )
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 Save", key=f"save_{session['session_id']}"):
                            # Update title in database
                            update_session_title(session['session_id'], new_title)
                            st.session_state[f"rename_mode_{session['session_id']}"] = False
                            st.success("Title updated!")
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ Cancel", key=f"cancel_{session['session_id']}"):
                            st.session_state[f"rename_mode_{session['session_id']}"] = False
                            st.rerun()
                
                st.divider()
    else:
        st.info("No previous searches found. Start a new search in the 'New Search' tab!")

# Show current session info if active
if st.session_state.current_session_id:
    # Get current session data to show memory status
    try:
        current_session_data = {
            'step': st.session_state.step,
            'messages': st.session_state.get('messages', []),
            'research_brief': st.session_state.get('research_brief', ''),
            'flight_results': st.session_state.get('flight_results', ''),
            'chat_messages': st.session_state.get('chat_messages', [])
        }
        current_tokens = estimate_tokens_for_session(current_session_data)
        
        # Create memory status message
        memory_status = ""
        if current_tokens > 200000:  # Approaching summarization threshold
            memory_status = f" | 🧠 Memory: {current_tokens//1000}K tokens (will summarize soon)"
        elif current_tokens > 100000:
            memory_status = f" | 📊 Memory: {current_tokens//1000}K tokens"
        elif current_tokens > 0:
            memory_status = f" | 📊 Memory: {current_tokens} tokens"
        
        st.info(f"🔗 Current Session: {st.session_state.current_session_id[:8]}...{memory_status}")
    except Exception:
        st.info(f"🔗 Current Session: {st.session_state.current_session_id[:8]}...")

# Progress indicator for current session
if st.session_state.current_session_id:
    progress_steps = {
        "input": "📝 Enter your flight search question",
        "clarifying": "🤔 Analyzing and clarifying requirements", 
        "brief_generated": "📋 Flight search brief generated",
        "searching": "✈️ Searching for flights",
        "results": "✅ Flight results ready",
        "chat": "💬 Chat with agent"
    }

    # Show progress
    current_step = st.session_state.step
    
    # Special handling for clarifying questions
    if current_step == "clarifying" and st.session_state.waiting_for_answers:
        st.markdown('<div class="progress-step"><strong>🤔 Answering clarifying questions</strong></div>', unsafe_allow_html=True)
    else:
        for step, description in progress_steps.items():
            if step == current_step:
                st.markdown(f'<div class="progress-step"><strong>{description}</strong></div>', unsafe_allow_html=True)
            elif list(progress_steps.keys()).index(step) < list(progress_steps.keys()).index(current_step):
                st.markdown(f'<div class="progress-step completed">{description} ✓</div>', unsafe_allow_html=True)

# Error display
if st.session_state.error_message:
    st.error(f"❌ {st.session_state.error_message}")
    if st.button("🔄 Clear Error"):
        st.session_state.error_message = None
        st.rerun()

# Auto-save session data function
def save_current_session():
    if st.session_state.current_session_id:
        session_data = {
            'step': st.session_state.step,
            'messages': st.session_state.get('messages', []),
            'research_brief': st.session_state.get('research_brief', ''),
            'flight_results': st.session_state.get('flight_results', ''),
            'chat_messages': st.session_state.get('chat_messages', []),
            'initial_handoff': st.session_state.get('initial_handoff', None),
            'status': 'active'
        }
        
        # Calculate and add token count
        try:
            session_data['token_count'] = estimate_tokens_for_session(session_data)
        except Exception as e:
            print(f"Warning: Could not estimate tokens: {e}")
            session_data['token_count'] = 0
        
        # Add current agent and handoff state to session data
        session_data['current_agent'] = st.session_state.get('current_agent', 'flight_agent')
        session_data['last_handoff'] = st.session_state.get('last_handoff', None)
        
        save_session_to_db(st.session_state.current_session_id, session_data)

# Main search flow - only show if there's an active session
if st.session_state.current_session_id:
    
    # User input section
    if st.session_state.step == "input":
        st.markdown("### 🎯 What flight are you looking for?")
        user_input = st.text_area(
            "Describe your travel needs:", 
            height=100,
            placeholder="e.g., I need a round-trip flight from San Francisco to New York, departing September 15th and returning September 22nd, for 2 adults in economy class."
        )

        if st.button("🚀 Start Flight Search Process", disabled=st.session_state.step != "input"):
            if user_input.strip():
                st.session_state.messages = [{"role": "user", "content": user_input.strip()}]
                st.session_state.step = "clarifying"
                st.session_state.error_message = None
                
                # Generate a title from the user input
                title = user_input.strip()[:50] + "..." if len(user_input.strip()) > 50 else user_input.strip()
                session_data = {
                    'title': title,
                    'step': 'clarifying',
                    'messages': st.session_state.messages,
                    'status': 'active'
                }
                save_session_to_db(st.session_state.current_session_id, session_data)
                st.rerun()
            else:
                st.session_state.error_message = "Please enter your flight search question first."

    # Clarification processing
    elif st.session_state.step == "clarifying" and st.session_state.messages and not st.session_state.waiting_for_answers:
        try:
            with st.spinner("🤔 Analyzing your flight search question..."):
                async def run_clarification():
                    return await clarify_with_user(st.session_state.messages, session=st.session_state.sqlite_session)
                
                clarify_result = asyncio.run(run_clarification())
            
            if clarify_result.need_clarification and clarify_result.questions:
                st.session_state.waiting_for_answers = True
                st.session_state.current_questions = clarify_result.questions
                # Keep step as "clarifying" but show questions
                save_current_session()
            else:
                # No clarification needed, generate research brief
                with st.spinner("📋 Generating flight search brief..."):
                    async def generate_brief():
                        return await write_flight_search_brief(st.session_state.messages, session=st.session_state.sqlite_session)
                    
                    research_brief = asyncio.run(generate_brief())
                
                st.session_state.research_brief = research_brief.flight_search_brief
                st.session_state.step = "brief_generated"
                save_current_session()
                st.rerun()
                
        except Exception as e:
            st.session_state.error_message = f"Error during clarification: {str(e)}"
            st.session_state.step = "input"
            save_current_session()

    # Brief generated - show brief and search button
    elif st.session_state.step == "brief_generated" and st.session_state.research_brief:
        st.success("✅ Flight Search Brief Generated!")
        
        # Enhanced research brief display
        st.markdown("### 📋 Flight Search Brief")
        
        # Create a nicely formatted container for the brief
        with st.container():
            # Add some custom styling for the brief
            st.markdown("""
            <div style="
                background-color: #f8f9fa;
                border: 1px solid #e1e8ed;
                border-radius: 12px;
                padding: 1.5rem;
                margin: 1rem 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            ">
            """, unsafe_allow_html=True)
            
            # Display the brief with better formatting
            brief_lines = st.session_state.research_brief.split('\n')
            formatted_brief = []
            
            for line in brief_lines:
                line = line.strip()
                if line:
                    # Add bullet points for better readability
                    if not line.startswith('•') and not line.startswith('-') and len(line) > 20:
                        formatted_brief.append(f"• {line}")
                    else:
                        formatted_brief.append(line)
            
            # Display the formatted brief
            st.markdown('\n\n'.join(formatted_brief))
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Add a collapsible section for the raw brief (for reference)
        with st.expander("🔍 View Raw Brief", expanded=False):
            st.code(st.session_state.research_brief, language="text")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✈️ Search Flights Now", type="primary"):
                st.session_state.step = "searching"
                st.rerun()
        with col2:
            if st.button("🔄 Start Over"):
                # Reset everything
                for key in ['messages', 'waiting_for_answers', 'current_questions', 'research_brief', 
                           'flight_results', 'chat_messages', 'chat_mode', 'processing_chat']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.step = "input"
                st.session_state.error_message = None
                st.rerun()

    # Flight searching
    elif st.session_state.step == "searching":
        try:
            with st.spinner("✈️ Contacting Duffel API and searching for flights..."):
                async def run_flights():
                    return await find_flights(st.session_state.research_brief, verbose=False, session=st.session_state.sqlite_session)
                
                flight_results = asyncio.run(run_flights())
                
                # Check for handoffs in initial flight search
                handoff_info = detect_handoff(flight_results)
                if handoff_info:
                    st.session_state.initial_handoff = handoff_info
                    st.session_state.last_handoff = handoff_info
                    # Update current agent based on handoff
                    if handoff_info.get('to_agent') == 'Itinerary Planner Agent':
                        st.session_state.current_agent = "itinerary_agent"
                    elif handoff_info.get('to_agent') == 'Flight Search Agent':
                        st.session_state.current_agent = "flight_agent"
                
                st.session_state.flight_results = flight_results
                st.session_state.step = "results"
                save_current_session()
                st.rerun()
                
        except Exception as e:
            st.session_state.error_message = f"Error searching flights: {str(e)}"
            st.session_state.step = "brief_generated"
            save_current_session()

    # Results display
    elif st.session_state.step == "results" and st.session_state.flight_results:
        st.success("🎉 Flight Search Completed!")
        
        # Show handoff indicator if detected
        if st.session_state.get("initial_handoff"):
            handoff_info = st.session_state.initial_handoff
            st.markdown(f"""
            <div class="handoff-indicator">
                🔄 <strong>Agent Handoff Detected</strong>
                <span class="handoff-arrow">→</span>
                <span class="agent-name">{handoff_info['from_agent']}</span>
                <span class="handoff-arrow">→</span>
                <span class="agent-name">{handoff_info['to_agent']}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Results in a nice container
        with st.container():
            st.markdown("### ✈️ Flight Search Results")
            
            # Display results in an expandable section
            with st.expander("📊 View Flight Details", expanded=True):
                st.text(st.session_state.flight_results)
        
        # Action buttons with better styling
        st.markdown("### 🎯 What would you like to do next?")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="📄 Download Results",
                data=str(st.session_state.flight_results),
                file_name="flight_results.txt",
                mime="text/plain",
                help="Download the flight search results as a text file"
            )
        
        with col2:
            if st.button("💬 Chat with Flight Agent", help="Ask questions and get more details"):
                st.session_state.step = "chat"
                st.session_state.chat_mode = True
                # Initialize chat with context
                if not st.session_state.chat_messages:
                    st.session_state.chat_messages = [
                        {"role": "system", "content": f"Previous search brief: {st.session_state.research_brief}"},
                        {"role": "assistant", "content": f"I've found some flight options for you! 🎉\n\nHow can I help you further? I can:\n\n✈️ Get more details about specific flights\n📅 Search for alternative dates or routes\n💰 Compare prices and options\n🔍 Help you understand the results\n\nWhat would you like to know?"}
                    ]
                st.rerun()
        
        with col3:
            if st.button("🔄 New Search", help="Start a completely new flight search"):
                # Reset everything
                for key in ['messages', 'waiting_for_answers', 'current_questions', 'research_brief', 
                           'flight_results', 'chat_messages', 'chat_mode', 'processing_chat']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.step = "input"
                st.session_state.error_message = None
                st.rerun()

    # Chat Interface
    elif st.session_state.step == "chat" and st.session_state.chat_messages:
        st.markdown("---")
        
        # Show current agent indicator
        current_agent_name = "Flight Search Agent" if st.session_state.current_agent == "flight_agent" else "Itinerary Planner Agent"
        agent_emoji = "✈️" if st.session_state.current_agent == "flight_agent" else "🗺️"
        
        st.markdown(f"### 💬 Chat with {agent_emoji} {current_agent_name}")
        
        # Show agent status
        if st.session_state.current_agent == "flight_agent":
            st.markdown("🤖 Ask follow-up questions, get more details, or search for alternatives!")
        else:
            st.markdown("🗺️ Let's plan your itinerary! Ask about activities, accommodations, or travel arrangements!")
        
        # Display chat messages in a scrollable container
        chat_container = st.container()
        with chat_container:
            for i, message in enumerate(st.session_state.chat_messages):
                if message["role"] == "system":
                    continue  # Don't display system messages
                elif message["role"] == "user":
                    with st.chat_message("user", avatar="👤"):
                        st.write(message["content"])
                elif message["role"] == "assistant":
                    with st.chat_message("assistant", avatar="🤖"):
                        # Check for handoff information
                        if "handoff" in message:
                            handoff_info = message["handoff"]
                            # Display handoff indicator with custom styling
                            st.markdown(f"""
                            <div class="handoff-indicator">
                                🔄 <strong>Agent Handoff</strong>
                                <span class="handoff-arrow">→</span>
                                <span class="agent-name">{handoff_info['from_agent']}</span>
                                <span class="handoff-arrow">→</span>
                                <span class="agent-name">{handoff_info['to_agent']}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.write(message["content"])
        
        # Chat input - only show if not processing
        if not st.session_state.get("processing_chat", False):
            user_message = st.chat_input(
                "Ask me about the flights, request alternatives, or get more details...",
                disabled=st.session_state.get("processing_chat", False)
            )
            
            if user_message:
                # Add user message to chat
                st.session_state.chat_messages.append({"role": "user", "content": user_message})
                st.session_state.processing_chat = True
                st.rerun()
        
        # Process chat message asynchronously
        if st.session_state.get("processing_chat", False):
            try:
                with st.spinner("🤖 Flight agent is thinking..."):
                    # Build conversation context
                    conversation_context = f"""
                    Original Search Brief: {st.session_state.research_brief}
                    
                    Previous Flight Search Results: {st.session_state.flight_results}
                    
                    Chat History:
                    """
                    
                    # Add recent chat messages (last 10 to avoid token limits)
                    recent_messages = st.session_state.chat_messages[-10:]
                    for msg in recent_messages[1:]:  # Skip system message
                        if msg["role"] == "user":
                            conversation_context += f"\nUser: {msg['content']}"
                        elif msg["role"] == "assistant":
                            conversation_context += f"\nAssistant: {msg['content']}"
                    
                    # Get the latest user message
                    latest_message = st.session_state.chat_messages[-1]["content"]
                    
                    # Create focused query
                    full_query = f"{conversation_context}\n\nLatest User Question: {latest_message}\n\nPlease respond helpfully to the user's question about their flight search."
                    
                    # Run async function with SQLiteSession, routing to correct agent
                    async def run_chat():
                        # Use the SQLiteSession for persistent conversation and route to correct agent
                        return await route_to_agent(full_query, st.session_state.current_agent, st.session_state.sqlite_session)
                    
                    agent_response = asyncio.run(run_chat())
                    
                    # Check for handoffs in the response
                    handoff_info = detect_handoff(agent_response)
                    
                    # Update current agent if handoff detected
                    if handoff_info:
                        st.session_state.last_handoff = handoff_info
                        # Update current agent based on handoff
                        if handoff_info.get('to_agent') == 'Itinerary Planner Agent':
                            st.session_state.current_agent = "itinerary_agent"
                            print(f"🔄 Handoff detected: Switching to Itinerary Planner Agent")
                        elif handoff_info.get('to_agent') == 'Flight Search Agent':
                            st.session_state.current_agent = "flight_agent"
                            print(f"🔄 Handoff detected: Switching to Flight Search Agent")
                    
                    # Add agent response
                    message_data = {
                        "role": "assistant", 
                        "content": agent_response
                    }
                    
                    # Add handoff metadata if detected
                    if handoff_info:
                        message_data["handoff"] = handoff_info
                    
                    st.session_state.chat_messages.append(message_data)
                    
            except Exception as e:
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": f"❌ I apologize, but I encountered an error: {str(e)}\n\nPlease try rephrasing your question or ask something else!"
                })
            
            finally:
                st.session_state.processing_chat = False
                save_current_session()  # Save chat progress
                st.rerun()
        
        # Chat controls with better styling
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ Clear Chat", help="Clear the chat history"):
                st.session_state.chat_messages = [
                    {"role": "system", "content": f"Previous search brief: {st.session_state.research_brief}"},
                    {"role": "assistant", "content": f"I've found some flight options for you! 🎉\n\nHow can I help you further? I can:\n\n✈️ Get more details about specific flights\n📅 Search for alternative dates or routes\n💰 Compare prices and options\n🔍 Help you understand the results\n\nWhat would you like to know?"}
                ]
                st.rerun()
        
        with col2:
            if st.button("⬅️ Back to Results", help="Return to flight results"):
                st.session_state.step = "results"
                st.session_state.chat_mode = False
                st.rerun()
        
        with col3:
            if st.button("🔄 New Search", help="Start a new flight search"):
                # Reset everything
                for key in ['messages', 'waiting_for_answers', 'current_questions', 'research_brief', 
                           'flight_results', 'chat_messages', 'chat_mode', 'processing_chat']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.session_state.step = "input"
                st.session_state.error_message = None
                st.rerun()

else:
    # No active session - show instructions
    st.markdown("---")
    st.info("👆 **Get Started:** Create a new search session or resume a previous one using the tabs above!")
    
    st.markdown("""
    ### ✨ Features:
    - 🔍 **Intelligent Flight Search** - AI-powered scoping and search
    - 💬 **Interactive Chat** - Ask follow-up questions and get alternatives  
    - 💾 **Session Persistence** - Resume searches anytime
    - 📊 **Comprehensive Results** - Detailed flight information with download options
    """)
    
    st.markdown("""
    ### 🚀 How it works:
    1. **Create a new session** or resume an existing one
    2. **Describe your travel needs** in natural language
    3. **Get clarifying questions** if needed for better results
    4. **Review the search brief** generated by AI
    5. **Get real-time flight results** from Duffel API
    6. **Chat with the agent** for alternatives and details
    """)

# Conduct research if requested (COMMENTED OUT FOR TESTING)
# if st.session_state.conducting_research and st.session_state.research_brief:
#     async def run_research():
#         return await conduct_research(st.session_state.research_brief)
#     
#     with st.spinner("🔍 Conducting research using MCP-enabled agent... This may take several minutes."):
#         research_results = asyncio.run(run_research())
#     
#     # Store results and reset conducting flag
#     st.session_state.research_results = research_results
#     st.session_state.conducting_research = False
#     st.rerun()

# Display research results if available (COMMENTED OUT FOR TESTING)
# if st.session_state.research_results:
#     st.success("Research Completed!")
#     st.markdown("### Research Results")
#     st.write(st.session_state.research_results)
#     
#     # Add buttons for actions
#     col1, col2, col3 = st.columns(3)
#     with col1:
#         if st.button("📋 Copy Results"):
#             st.write("Results copied to clipboard!")  # Note: actual clipboard functionality would need additional setup
#     with col2:
#         if st.button("📄 Download Report"):
#             # Create a downloadable text file
#             st.download_button(
#                 label="Download as Text",
#                 data=f"# Research Brief\n\n{st.session_state.research_brief}\n\n# Research Results\n\n{st.session_state.research_results}",
#                 file_name="research_report.txt",
#                 mime="text/plain"
#             )
#     with col3:
#         if st.button("🔄 New Research"):
#             st.session_state.messages = []
#             st.session_state.waiting_for_answers = False
#             st.session_state.current_questions = []
#             st.session_state.research_brief = None
#             st.session_state.research_results = None
#             st.session_state.conducting_research = False
#             st.rerun()

# Handle clarifying questions - only show if there's an active session
if st.session_state.current_session_id and st.session_state.waiting_for_answers and st.session_state.current_questions:
    st.markdown("---")
    st.markdown("### 🤔 Clarifying Questions")
    st.write("Please answer the following questions to help me better understand your flight search needs:")
    
    answers = []
    for i, question in enumerate(st.session_state.current_questions):
        answer = st.text_input(f"{i+1}. {question}", key=f"answer_{i}")
        answers.append(f"{i+1}. {answer}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Submit Answers", type="primary"):
            # Add Q&A to conversation
            questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(st.session_state.current_questions))
            st.session_state.messages.append({
                "role": "assistant", 
                "content": f"Follow-up questions:\n{questions_text}"
            })
            st.session_state.messages.append({
                "role": "user", 
                "content": "Answers:\n" + "\n".join(answers)
            })
            
            # Clear clarification state and move to brief generation
            st.session_state.waiting_for_answers = False
            st.session_state.current_questions = []
            st.session_state.step = "clarifying"  # This will trigger brief generation
            save_current_session()
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip Questions"):
            st.session_state.waiting_for_answers = False
            st.session_state.current_questions = []
            st.session_state.step = "clarifying"  # This will trigger brief generation
            save_current_session()
            st.rerun()


