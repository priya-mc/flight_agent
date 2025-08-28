from datetime import datetime
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from typing import List, Dict

from agents import OpenAIChatCompletionsModel, AsyncOpenAI
# Load env for local runs
load_dotenv('/Users/priyadwivedi/Documents/priya-exptts/jarvis/openai_sdk_deep_research/.env')

gpt_4_1 = OpenAIChatCompletionsModel( 
        model="gpt-4.1",
        openai_client=AsyncOpenAI()
    )

from agents import Agent, ModelSettings, Runner
REASONING_EFFORT = 'low'

## Tracing using Logfire
import logfire
logfire.configure(token='pylf_v1_us_7KdmWMTct8mP4FxRNKSzXNPnysff2Stb4lG5cNZyLJXs', service_name='flight_scoping_agents')
logfire.instrument_openai_agents()

from prompts import (
    clarify_with_user_instructions,
    transform_messages_into_flight_search_brief_prompt,
)

def _today_str() -> str:
    return datetime.now().strftime("%a %b %-d, %Y")


class ClarifyWithUser(BaseModel):
    need_clarification: bool = Field(description="Whether the user needs to be asked a clarifying question.")
    questions: List[str] = Field(description="A list of questions to ask the user to clarify the report scope")


class FlightSearchBrief(BaseModel):
    flight_search_brief: str = Field(description="A flight search brief that will be used to guide the flight search.")

def _format_messages(messages: List[Dict[str, str]]) -> str:
    lines: List[str] = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "user":
            lines.append(f"User: {content}")
        else:
            lines.append(f"Assistant: {content}")
    return "\n\n".join(lines)

clarify_agent = Agent(
    name="Clarifier",
    model='gpt-5', ## model = gpt-5
    model_settings=ModelSettings(reasoning_effort=REASONING_EFFORT),
    instructions=clarify_with_user_instructions.format(date=_today_str()),
    output_type=ClarifyWithUser,
)


async def clarify_with_user(messages: List[Dict[str, str]]) -> ClarifyWithUser:
    message_str=_format_messages(messages)
    result = await Runner.run(clarify_agent, message_str)
    return result.final_output_as(ClarifyWithUser)

research_brief_agent = Agent(
    name="Flight Search Brief",
    model='gpt-5', ## model = gpt-5
    model_settings=ModelSettings(reasoning_effort=REASONING_EFFORT),
    instructions=transform_messages_into_flight_search_brief_prompt.format(date=_today_str()),
    output_type=FlightSearchBrief,
)

async def write_flight_search_brief(messages: List[Dict[str, str]]) -> FlightSearchBrief:
    message_str=_format_messages(messages)
    result = await Runner.run(research_brief_agent, message_str)
    return result.final_output_as(FlightSearchBrief)


### Desired Flow:
### 1. Get the initial user question
### 2. Run Clarify Agent
### 3. If need_clarification is true, ask the questions and get the user's response. Run Clarify Agent again.
### 4. If need_clarification is false, run the Research Brief Agent
### 5. Return the research brief

async def main(user_question: str):
    messages: List[Dict[str, str]] = []

    # 1) Get the initial user question (passed as parameter)
    if not user_question or not user_question.strip():
        print("No question provided. Exiting.")
        return None

    messages.append({"role": "user", "content": user_question.strip()})

    # 2) Run Clarify Agent, potentially loop while clarifications are needed
    max_clarification_rounds = 3
    for _ in range(max_clarification_rounds):
        clarify_result = await clarify_with_user(messages)

        if not clarify_result.need_clarification or not clarify_result.questions:
            break

        # 3) Ask questions to the user and collect responses
        questions_text = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(clarify_result.questions))
        print("\nI need a bit more detail to scope the research:")
        print(questions_text)

        answers: List[str] = []
        for i, q in enumerate(clarify_result.questions, start=1):
            try:
                answer = input(f"Answer to {i}: ").strip()
                answers.append(f"{i}. {answer}")
            except EOFError:
                print("\nInput interrupted. Using partial answers.")
                break

        # Record the Q&A in the conversation history
        messages.append({
            "role": "assistant",
            "content": f"Follow-up questions:\n{questions_text}",
        })
        messages.append({
            "role": "user",
            "content": "Answers:\n" + "\n".join(answers),
        })

    # 4) Generate the Research Brief using the finalized conversation
    flight_search_brief = await write_flight_search_brief(messages)

    # 5) Return (and print) the research brief
    print("\n=== Research Brief ===")
    print(flight_search_brief.flight_search_brief)
    return flight_search_brief


if __name__ == "__main__":
    import asyncio
    import sys
    
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Enter your research question: ").strip()
    
    asyncio.run(main(question))