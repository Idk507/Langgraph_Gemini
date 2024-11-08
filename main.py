from langchain import hub 
from langchain.agents import Tool, create_json_agent 
from langchain_google_genai import ChatGoogleGenerativeAI 
import os 
from typing import TypedDict, Annotated, Union
from langchain_core.agents import AgentFinish
from langchain_core.agents import AgentAction 
from langchain_core.messages import BaseMessage
import operator 
import json
from langgraph.graph import END, StateGraph 
from langgraph.prebuilt import ToolInvocation 
from langgraph.prebuilt.tool_executor import ToolExecutor
from langchain_core.agents import AgentActionMessageLog 
import streamlit as st
from langchain_community.utilities import GoogleSerperAPIWrapper

st.set_page_config(page_title="Langchain Google Generative AI", page_icon="🤖", layout="wide")

def main():
    st.title("Langchain Google Generative AI")

    input_text = st.text_area("Enter your text")

    if st.button("Run Agent"):
        # Use environment variable or secrets management for API keys
        os.environ["SERPER_API_KEY"] = "your_serper_api_key"  # Note: API key should not be hardcoded

        search = GoogleSerperAPIWrapper()

        def toggle_case(word):
            toggle_result = ""
            for char in word:
                if char.isupper():
                    toggle_result += char.lower()
                elif char.islower():
                    toggle_result += char.upper()
                else:
                    toggle_result += char
            return toggle_result
        
        def sort_string(string):
            return ''.join(sorted(string))
        
        tools = [
            Tool(
                name="Search",
                func=search.run,
                description="Useful for when you need to answer questions about current events"
            ),
            Tool(
                name="Toggle Case",
                func=lambda word: toggle_case(word),
                description="Toggles the case of each character in the word"
            ),
            Tool(
                name="Sort String",
                func=lambda string: sort_string(string),
                description="Sorts the string alphabetically"
            )
        ]

        prompt = hub.pull("hwchase17/react")  # Fixed typo in hub name

        llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key="your_google_api_key",  # Note: API key should not be hardcoded
            convert_system_message_to_human=True,
            verbose=True
        )

        class AgentState(TypedDict):
            input: str 
            chat_history: list[BaseMessage]
            agent_outcome: Union[AgentAction, AgentFinish, None]
            return_direct: bool 
            intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]

        tool_executor = ToolExecutor(tools)

        def run_agent(state):
            agent_outcome = agent_runnable.invoke(state)
            return {"agent_outcome": agent_outcome}
        
        def execute_tools(state):
            agent_outcome = state['agent_outcome']
            
            if isinstance(agent_outcome, AgentActionMessageLog):
                tool_name = agent_outcome.tool
                tool_input = agent_outcome.tool_input
                
                action = ToolInvocation(
                    tool=tool_name,
                    tool_input=tool_input
                )
                
                response = tool_executor.invoke(action)
                return {"intermediate_steps": [(state["agent_outcome"], response)]}
            return {"intermediate_steps": []}
        
        def should_continue(state):
            if isinstance(state['agent_outcome'], AgentActionMessageLog):
                if state.get("return_direct", False):
                    return "final"
                return "continue"
            return "end"
                
        def first_agent(inputs):
            action = AgentActionMessageLog(
                tool="Search",
                tool_input=inputs["input"],
                log="",
                message_log=[]
            )
            return {"agent_outcome": action}
        
        workflow = StateGraph(AgentState)

        workflow.add_node("agent", run_agent)
        workflow.add_node("action", execute_tools)
        workflow.add_node("final", execute_tools)
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "continue": "action",
                "end": END,
                "final": END
            }
        )

        workflow.add_edge("action", "agent")

        app = workflow.compile()

        inputs = {
            "input": input_text,
            "chat_history": [],
            "return_direct": False,
            "intermediate_steps": []
        }
        
        results = []
        for s in app.stream(inputs):
            result = list(s.values())[0]
            results.append(result)
            st.write(result)

if __name__ == "__main__":
    main()