import asyncio
import streamlit as st
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv('/Users/priyadwivedi/Documents/priya-exptts/jarvis/openai_sdk_deep_research/.env')

from scoping_agents import clarify_with_user, write_flight_search_brief
# from research_agent_mcp import conduct_research  # COMMENTED OUT FOR TESTING

st.set_page_config(page_title="Flight Search Assistant", page_icon="🔬", layout="wide")
st.title("🔬 Flight Search Assistant")
st.markdown("Generate flight search briefs and conduct comprehensive flight search using AI agents")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, str]] = []
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

# User input
user_input = st.text_area("Enter your flight search question:", height=100)

if st.button("🚀 Start Flight Search Process", disabled=st.session_state.waiting_for_answers):
    if user_input.strip():
        st.session_state.messages = [{"role": "user", "content": user_input.strip()}]
        st.session_state.waiting_for_answers = False
        st.rerun()

# Process clarification flow
if st.session_state.messages and not st.session_state.waiting_for_answers:
    async def run_clarification():
        return await clarify_with_user(st.session_state.messages)
    
    with st.spinner("Analyzing your flight search question..."):
        clarify_result = asyncio.run(run_clarification())
    
    if clarify_result.need_clarification and clarify_result.questions:
        st.session_state.waiting_for_answers = True
        st.session_state.current_questions = clarify_result.questions
        st.rerun()
    else:
        # No clarification needed, generate research brief
        async def generate_brief():
            return await write_flight_search_brief(st.session_state.messages)
        
        with st.spinner("Generating flight search brief..."):
            research_brief = asyncio.run(generate_brief())
        
        # Store the research brief in session state
        st.session_state.research_brief = research_brief.flight_search_brief
        
        st.success("Flight Search Brief Generated!")
        st.markdown("### Flight Search Brief")
        st.write(st.session_state.research_brief)
        
        # Add button to conduct research (COMMENTED OUT FOR TESTING)
        # col1, col2 = st.columns(2)
        # with col1:
        #     if st.button("🔍 Conduct Research", disabled=st.session_state.conducting_research):
        #         st.session_state.conducting_research = True
        #         st.rerun()
        # with col2:
        if st.button("Start Over"):
            st.session_state.messages = []
            st.session_state.waiting_for_answers = False
            st.session_state.current_questions = []
            st.session_state.flight_search_brief = None
            st.session_state.research_results = None
            st.session_state.conducting_research = False
            st.rerun()

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

# Handle clarifying questions
if st.session_state.waiting_for_answers and st.session_state.current_questions:
    st.markdown("### Clarifying Questions")
    st.write("Please answer the following questions to help scope your research:")
    
    answers = []
    for i, question in enumerate(st.session_state.current_questions):
        answer = st.text_input(f"{i+1}. {question}", key=f"answer_{i}")
        answers.append(f"{i+1}. {answer}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Submit Answers"):
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
            
            st.session_state.waiting_for_answers = False
            st.session_state.current_questions = []
            st.rerun()
    
    with col2:
        if st.button("Skip Questions"):
            st.session_state.waiting_for_answers = False
            st.session_state.current_questions = []
            st.rerun()


