import os
import asyncio
from dotenv import load_dotenv
from agents import Agent, Runner, ModelSettings, OpenAIChatCompletionsModel, AsyncOpenAI
from agents.mcp import MCPServerStdio
from agents.run_context import RunContextWrapper

## Tracing using Logfire  
import logfire
logfire.configure(token='pylf_v1_us_7KdmWMTct8mP4FxRNKSzXNPnysff2Stb4lG5cNZyLJXs', service_name='flight_search_agent')
logfire.instrument_openai_agents()

# Load environment variables
load_dotenv('/Users/priyadwivedi/Documents/priya-exptts/jarvis/openai_sdk_deep_research/.env')

# Initialize OpenAI model
gpt_4_1 = OpenAIChatCompletionsModel( 
    model="gpt-4.1",
    openai_client=AsyncOpenAI()
)

async def search_flights_agent(query: str):
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
                    "/Users/priyadwivedi/Documents/priya-exptts/jarvis/openai_sdk_deep_research/flights-mcp",
                    "run", 
                    "flights-mcp"
                ],
            }
        ) as flights_server:
            
            # Optional: List available tools from the server
            run_context = RunContextWrapper(context=None)
            temp_agent = Agent(name="temp", instructions="temp")
            tools = await flights_server.list_tools(run_context, temp_agent)
            
            print("Available Flight MCP tools:")
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")
            print()
            
            # Create a flight search agent
            flight_agent = Agent(
                name="Flight Search Agent with Duffel MCP",
                model=gpt_4_1,
                model_settings=ModelSettings(reasoning_effort='medium'),
                instructions="""You are a helpful flight search assistant with access to real-time flight data via Duffel API. 

CAPABILITIES:
- Search for one-way, round-trip, and multi-city flights
- Get detailed information about specific flight offers
- Compare prices across different options
- Handle various cabin classes (economy, premium_economy, business, first)
- Work with flexible dates and times

AVAILABLE TOOLS:
1. search_flights: Main tool for searching flights
   - Parameters: type, origin, destination, departure_date, return_date (for round-trip), adults, cabin_class, etc.
   - Supports one_way, round_trip, and multi_city flight types
2. get_offer_details: Get comprehensive details about a specific flight offer using offer_id
3. search_multi_city: Specialized tool for complex multi-city itineraries

IMPORTANT GUIDELINES:
- Always ask for clarification if travel details are ambiguous
- Use 3-letter IATA airport codes (e.g., SFO, LAX, JFK, LHR)
- For dates, use YYYY-MM-DD format
- When presenting results, highlight key details like price, duration, stops, and departure times
- If a user asks about a specific offer, use get_offer_details for comprehensive information
- For complex multi-city trips, use the search_multi_city tool
- Always show the most relevant and cost-effective options first
- Explain any limitations (like number of stops or time constraints)

RESPONSE FORMATTING:
- Present flight options in an easy-to-read format
- Include departure/arrival times, duration, price, airline, and stop information
- Highlight the best deals or most convenient options
- Provide offer IDs for flights users might want to explore further

Be friendly, informative, and help users make informed travel decisions.""",
                mcp_servers=[flights_server]
            )
            
            print("🤖 Flight Agent initialized. Processing your request...")
            print("=" * 40)
            
            # Run the flight search
            result = await Runner.run(flight_agent, query)
            
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
async def find_flights(query: str, verbose: bool = True) -> str:
    """
    Programmatic interface for flight search.
    
    Args:
        query: Natural language flight search request
        verbose: Whether to print progress information
        
    Returns:
        String containing the flight search results
    """
    if verbose:
        print(f"🛫 Searching flights: {query}")
    
    return await search_flights_agent(query)

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
