import os
import asyncio
import json
from dotenv import load_dotenv
from agents import Agent, Runner, ModelSettings, OpenAIChatCompletionsModel, AsyncOpenAI, function_tool, WebSearchTool, SQLiteSession
from agents.mcp import MCPServerStdio
from agents.run_context import RunContextWrapper
from prompts import conduct_flight_research_prompt, itinerary_planner_agent_prompt, summarize_memory_prompt
from datetime import datetime
from db import save_session_to_db, load_session_from_db
## Tracing using Logfire  
import logfire
logfire.instrument_openai_agents()
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

# Load environment variables
load_dotenv('/Users/pdwivedi/Documents/Projects/flight_agent/.env')
logfire.configure(token= os.getenv('LOGFIRE_TOKEN'), service_name='flight_search_agent')

# Memory management constants
MAX_CONTEXT_TOKENS = 250000  # 250K token limit
SUMMARIZATION_THRESHOLD = 200000  # Start summarizing at 200K tokens
RECENT_MESSAGES_TO_KEEP = 5  # Keep last 5 messages after summarization

# Initialize OpenAI model
gpt_4_1 = OpenAIChatCompletionsModel( 
    model="gpt-4.1",
    openai_client=AsyncOpenAI()
)

def _today_str() -> str:
    return datetime.now().strftime("%a %b %-d, %Y")

@function_tool
async def think_tool(thoughts: str) -> str:
    """
    A thinking and planning tool for the agent to organize thoughts and plan actions.
    
    Args:
        thoughts: The agent's thoughts, plans, or notes about the current task
        
    Returns:
        Confirmation that thoughts were recorded
    """
    print(f"🤔 Agent Thinking: {thoughts}")
    print("=" * 60)
    return f"Thoughts recorded: {thoughts[:1000]}..." if len(thoughts) > 1000 else f"Thoughts recorded: {thoughts}"


async def summarize_conversation_memory(memory_content: str) -> str:
    """
    Summarize conversation memory using the summarize_memory_prompt.
    
    Args:
        memory_content: The raw conversation memory to summarize
        
    Returns:
        Summarized memory content
    """
    try:
        # Create summarization agent
        summarizer_agent = Agent(
            name="Memory Summarizer",
            model='gpt-5-mini',
            model_settings=ModelSettings(reasoning_effort='low'),
            instructions=summarize_memory_prompt.format(
                memory_content=memory_content,
                date=_today_str()
            )
        )
        
        # Run summarization
        result = await Runner.run(
            summarizer_agent, 
            "Please summarize this conversation memory according to the guidelines provided.",
            max_turns=1
        )
        
        # Extract summary from JSON response
        summary_text = result.final_output
        try:
            # Try to parse as JSON to extract the summary field
            if summary_text.strip().startswith('{'):
                summary_json = json.loads(summary_text)
                return summary_json.get('summary', summary_text)
            else:
                return summary_text
        except json.JSONDecodeError:
            # If not valid JSON, return the raw response
            return summary_text
            
    except Exception as e:
        print(f"❌ Error during memory summarization: {str(e)}")
        # Fallback: return a simple truncated version
        return f"[SUMMARIZATION ERROR] Original memory (truncated): {memory_content[:1000]}..."


async def check_and_summarize_session_memory(session: SQLiteSession, last_result=None) -> bool:
    """
    Check if session memory needs summarization and perform it if necessary.
    
    Args:
        session: The SQLiteSession to check
        last_result: The last Runner result to get token usage from
        
    Returns:
        True if memory was summarized, False otherwise
    """
    if not session or not last_result:
        return False
    
    try:
        # Get current token usage from the last result
        current_tokens = last_result.context_wrapper.usage.total_tokens
        print(f"📊 Current session token count: {current_tokens}")
        
        # Check if we need to summarize
        if current_tokens >= SUMMARIZATION_THRESHOLD:
            print(f"🧠 Memory approaching limit ({current_tokens} tokens). Starting summarization...")
            
            # Get session history for summarization
            # Note: We'll need to access the session's conversation history
            # This is a simplified approach - in practice, you might need to 
            # access the session's internal storage
            
            # Build memory content from session data
            # SQLiteSession uses session_id attribute, but we need to get it properly
            session_id = getattr(session, 'session_id', None)
            if not session_id:
                # Try alternative ways to get session ID
                session_id = getattr(session, 'id', None) or getattr(session, '_session_id', None)
            
            print(f"🔍 Debug: Session ID found: {session_id}")
            session_data = load_session_from_db(session_id) if session_id else None
            
            if session_data:
                memory_parts = []
                
                # Add initial messages
                messages = session_data.get('messages', [])
                if messages:
                    memory_parts.append("=== Initial Flight Search Conversation ===")
                    for msg in messages:
                        role = msg.get('role', 'unknown')
                        content = msg.get('content', '')
                        memory_parts.append(f"{role.title()}: {content}")
                
                # Add research brief
                research_brief = session_data.get('research_brief', '')
                if research_brief:
                    memory_parts.append(f"\n=== Flight Search Brief ===\n{research_brief}")
                
                # Add flight results
                flight_results = session_data.get('flight_results', '')
                if flight_results:
                    memory_parts.append(f"\n=== Flight Search Results ===\n{flight_results}")
                
                # Add chat messages (except the most recent ones we'll keep)
                chat_messages = session_data.get('chat_messages', [])
                if len(chat_messages) > RECENT_MESSAGES_TO_KEEP:
                    messages_to_summarize = chat_messages[:-RECENT_MESSAGES_TO_KEEP]
                    if messages_to_summarize:
                        memory_parts.append("\n=== Chat History ===")
                        for msg in messages_to_summarize:
                            if msg.get('role') != 'system':  # Skip system messages
                                role = msg.get('role', 'unknown')
                                content = msg.get('content', '')
                                memory_parts.append(f"{role.title()}: {content}")
                
                # Combine all memory content
                full_memory_content = "\n".join(memory_parts)
                
                # Summarize the memory
                summary = await summarize_conversation_memory(full_memory_content)
                
                # Update session data with summary
                session_data['messages'] = [
                    {
                        "role": "system", 
                        "content": f"[CONVERSATION SUMMARY] {summary}"
                    }
                ]
                
                # Keep only recent chat messages
                if len(chat_messages) > RECENT_MESSAGES_TO_KEEP:
                    session_data['chat_messages'] = [
                        {"role": "system", "content": f"[PREVIOUS CONVERSATION SUMMARY] {summary}"}
                    ] + chat_messages[-RECENT_MESSAGES_TO_KEEP:]
                
                # Add summarization metadata
                session_data['summarized_at'] = datetime.now().isoformat()
                session_data['original_token_count'] = current_tokens
                session_data['is_summarized'] = True
                
                # Save updated session data
                save_session_to_db(session_id, session_data)
                
                # Clear the SQLiteSession and add summary
                # SQLiteSession methods may vary, let's try different approaches
                try:
                    # Method 1: Try clear method
                    if hasattr(session, 'clear'):
                        session.clear()
                        print("🧠 Cleared session using clear() method")
                    
                    # Method 2: Try reset method
                    elif hasattr(session, 'reset'):
                        session.reset()
                        print("🧠 Cleared session using reset() method")
                    
                    # Method 3: Try to access and clear internal storage
                    elif hasattr(session, '_messages'):
                        session._messages = []
                        print("🧠 Cleared session by resetting _messages")
                    
                    # Add summary as system message to the session
                    summary_msg = f"[CONVERSATION SUMMARY] {summary}"
                    
                    # Try different methods to add the summary
                    if hasattr(session, 'add_message'):
                        session.add_message('system', summary_msg)
                        print("🧠 Added summary using add_message()")
                    elif hasattr(session, 'append'):
                        session.append({'role': 'system', 'content': summary_msg})
                        print("🧠 Added summary using append()")
                    elif hasattr(session, '_messages'):
                        session._messages.append({'role': 'system', 'content': summary_msg})
                        print("🧠 Added summary to _messages directly")
                    
                except Exception as session_error:
                    print(f"⚠️ Warning: Could not clear/update SQLiteSession: {session_error}")
                    print("Summary saved to database but SQLiteSession not updated")
                
                print(f"🧠 Memory summarized successfully. Original: {current_tokens} tokens")
                return True
        
        # Update token count in database even if no summarization
        if session_id:
            session_data = load_session_from_db(session_id)
            if session_data:
                session_data['token_count'] = current_tokens
                save_session_to_db(session_id, session_data)
                print(f"📊 Updated token count in DB: {current_tokens}")
        
        return False
        
    except Exception as e:
        print(f"⚠️ Warning: Memory management failed: {str(e)}")
        return False


async def search_flights_agent(query: str, session=None):
    """Flight search agent using Duffel MCP server."""
    
    # Get Duffel API key from environment (try both possible names)
    print(f"🛫 Searching flights for: {query}")
    print("=" * 60)
    
    try:
        # Create Flights MCP server using local uv installation
        # The server will use DUFFEL_API_KEY from the current environment
        async with MCPServerStdio(
            params={
                "command": "uv",
                "args": [
                    "--directory", 
                    "/Users/pdwivedi/Documents/Projects/flight_agent/flights-mcp",
                    "run", 
                    "flights-mcp"
                ],
            },
            # Increase timeout to handle slow Duffel API responses
            client_session_timeout_seconds=120.0,  # 2 minutes timeout
            # Cache tools list to reduce repeated MCP queries
            cache_tools_list=True
        ) as flights_server:
            
            # Create agents without handoffs first to avoid circular dependency
            ## Itinerary Planner Agent
            handoff_instructions_itinerary_planner = f"""{RECOMMENDED_PROMPT_PREFIX}
            continue chatting with the user but if they want to redo the flight search, handoff to the flight agent.
            """
            itinerary_planner_agent = Agent(
                name="Itinerary Planner Agent",
                model='gpt-5',
                model_settings=ModelSettings(reasoning_effort='medium'),
                instructions=handoff_instructions_itinerary_planner,
                tools=[think_tool, WebSearchTool()],
                handoffs=[]  # Will be set after flight_agent is created
            )

            # Create a flight search agent
            handoff_instructions_flight_agent = f"""{RECOMMENDED_PROMPT_PREFIX}
            continue chatting with the user but if they want to plan the itinerary, handoff to the itinerary planner agent.
            """
            flight_agent = Agent(
                name="Flight Search Agent with Duffel MCP",
                model='gpt-5',
                model_settings=ModelSettings(reasoning_effort='medium', tool_choice='auto'),
                instructions=conduct_flight_research_prompt.format(date=_today_str())+handoff_instructions_flight_agent,
                mcp_servers=[flights_server],
                tools=[WebSearchTool(), think_tool],
                handoffs=[itinerary_planner_agent],  # Can reference itinerary_planner_agent now
            )
            
            # Now set the handoffs for itinerary_planner_agent after flight_agent is created
            itinerary_planner_agent.handoffs = [flight_agent]
            
            print("🤖 Flight Agent initialized. Processing your request...")
            print("=" * 40)
            
            # Run the flight search
            result = await Runner.run(flight_agent, query, max_turns=30, session=session)
            
            # Check and manage memory after the run using SDK token tracking
            if session:
                await check_and_summarize_session_memory(session, result)
            
            print("\n✈️ === Flight Search Results ===")
            print(result.final_output)
            
            return result.final_output
            
    except Exception as e:
        error_msg = f"❌ Error during flight search: {str(e)}"
        print(error_msg)
        return error_msg

async def main():
    """Main function to run the flight search agent with user input."""
    
    print("✈️ === Flight Search Agent ===")
    print("Powered by Duffel API via MCP Server")
    print()
    
    
    # Example queries to demonstrate capabilities
    example_queries = [
        "Find a one-way flight from San Francisco to New York on September 15, 2025 for 1 adult in economy",
        "Search for round-trip flights from LAX to London, departing September 20 and returning September 27, 2025, for 2 adults in business class",
        "Find the cheapest flights from SFO to LAX for next week", 
        "Plan a multi-city trip: NYC to Paris on Sep 28, Paris to Rome on Oct 3, Rome back to NYC on Oct 8"
    ]
    
    print("Example queries you can try:")
    for i, example in enumerate(example_queries, 1):
        print(f"{i}. {example}")
    print()
    
    # Get user input
    user_query = input("Enter your flight search request (or press Enter for example 1): ").strip()
    if not user_query:
        user_query = example_queries[0]
    
    print(f"\n🔍 Processing: {user_query}")
    print()
    
    # Run the flight search
    await search_flights_agent(user_query)

# Alternative function for programmatic usage
async def find_flights(query: str, verbose: bool = True, session=None) -> str:
    """
    Programmatic interface for flight search.
    
    Args:
        query: Natural language flight search request
        verbose: Whether to print progress information
        session: SQLiteSession for persistent conversation memory
        
    Returns:
        String containing the flight search results
    """
    if verbose:
        print(f"🛫 Searching flights: {query}")
    
    return await search_flights_agent(query, session=session)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Flight search interrupted by user. Safe travels!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure DUFFEL_API_KEY is set in your .env file")
        print("2. Check that the flights-mcp directory path is correct")
        print("3. Verify that 'uv' is installed and the flights-mcp dependencies are set up")
        print("4. Run 'cd flights-mcp && uv sync' to install dependencies")
