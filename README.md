## Flight Agents

### Core Functionality
- Takes in a user request. If not on the topic of flight returns back saying its not valid
- Asks one round of clarifying questions and based on that write the scope for search
- Passes this to the flight MCP agent that does the search. That agent will have access to a MCP tool and a think tool to do the search. It can also have access to sub agents
- A main function connects all these
- Streamlit to see the results


