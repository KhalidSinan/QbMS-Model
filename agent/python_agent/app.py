# # app.py (inside the 'python_agent' folder)
# import os
# import datetime
# import json
# from flask import Flask, request, jsonify

# # Import LangChain components
# from langchain_openai import ChatOpenAI
# from langchain.agents import AgentExecutor, create_json_chat_agent
# from langchain.tools import tool
# from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# # Import Google Calendar API
# from googleapiclient.discovery import build
# from google.oauth2.credentials import Credentials
# from google_auth_oauthlib.flow import InstalledAppFlow

# app = Flask(__name__)

# # Load environment variables
# from dotenv import load_dotenv
# load_dotenv()

# # Define the tools available to the agent
# @tool
# def create_google_calendar_event(task_description: str, deadline: str) -> str:
#     """
#     Creates a new event in the Google Calendar.
#     The function requires a clear task description and a deadline (e.g., "today at 5 PM").
#     Example usage: create_google_calendar_event(task_description="Send a project report", deadline="tomorrow at 10 AM")
#     """
#     try:
#         credentials_info = {
#             'access_token': os.getenv('GOOGLE_ACCESS_TOKEN_MOCK'),
#             'refresh_token': os.getenv('GOOGLE_REFRESH_TOKEN_MOCK'),
#             'client_id': os.getenv('GOOGLE_CLIENT_ID'),
#             'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
#         }
#         creds = Credentials.from_authorized_user_info(credentials_info)

#         service = build('calendar', 'v3', credentials=creds)

#         deadline_dt = datetime.datetime.now()
#         start_time = deadline_dt.isoformat()
#         end_time = (deadline_dt + datetime.timedelta(hours=1)).isoformat()

#         event = {
#             'summary': f"Task: {task_description}",
#             'description': f"Deadline: {deadline}",
#             'start': {'dateTime': start_time, 'timeZone': 'Europe/Amsterdam'},
#             'end': {'dateTime': end_time, 'timeZone': 'Europe/Amsterdam'},
#         }
        
#         service.events().insert(calendarId='primary', body=event).execute()
#         return f"Event for '{task_description}' created successfully."
#     except Exception as e:
#         return f"Error creating event: {e}"

# # قائمة الأدوات المتاحة للـ Agent
# tools = [create_google_calendar_event]

# # --- بناء الـ Agent باستخدام LangChain ---
# # Corrected prompt with tool placeholders
# prompt = ChatPromptTemplate.from_messages([
#     ("system", "You are an AI assistant that extracts tasks from meeting transcripts and adds them to Google Calendar."),
#     MessagesPlaceholder(variable_name="chat_history"),
#     ("human", "{input}"),
#     MessagesPlaceholder(variable_name="agent_scratchpad"),
# ])

# # Initialize the LLM
# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=os.getenv("OPENAI_API_KEY"))

# # The agent creation process needs to be correct.
# # This part is a bit tricky. We need to pass the tools correctly.
# from langchain import hub
# # First, load the prompt template from LangChain Hub
# prompt = hub.pull("hwchase17/structured-chat-agent")

# agent = create_json_chat_agent(llm, tools, prompt)
# agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# # --- نقطة النهاية (Endpoint) لـ API ---
# @app.route('/run_agent', methods=['POST'])
# def run_agent_endpoint():
#     data = request.get_json()
#     transcript = data.get('transcript', '')
    
#     if not transcript:
#         return jsonify({'error': 'Transcript is required'}), 400
    
#     try:
#         # Pass the tools and tool_names to the invoke method
#         tool_names = [tool.name for tool in tools]
#         result = agent_executor.invoke({"input": f"Extract tasks from this transcript:\n\n{transcript}", "tool_names": tool_names, "tools": tools})
#         return jsonify({'status': 'success', 'result': result['output']}), 200
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

# if __name__ == '__main__':
#     app.run(port=5000)




import os
import datetime
from flask import Flask, request, jsonify
from dateutil.parser import parse

# --- LangChain Imports ---
# FIX: Switched from OpenAI to Google Gemini for the language model
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_json_chat_agent
from langchain.tools import tool
from langchain import hub

# --- Google API Imports ---
# FIX: Corrected the typo from 'googleapient' to 'googleapiclient'
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

app = Flask(__name__)

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# --- Agent Configuration (Global) ---

# Pull the standard, compatible prompt from LangChain Hub.
# This prompt is designed to work with JSON-based chat agents and their tools.
PROMPT_TEMPLATE = hub.pull("hwchase17/structured-chat-agent")

# Initialize the Gemini Language Model
# Make sure GOOGLE_API_KEY is set in your .env file
LLM = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    temperature=0,
    convert_system_message_to_human=True # Important for compatibility with some prompts
)

# --- API Endpoint ---
@app.route('/run_agent', methods=['POST'])
def run_agent_endpoint():
    """
    Handles requests to process a transcript, extract tasks,
    and create Google Calendar events using a Gemini-powered agent.
    """
    data = request.get_json()
    
    transcript = data.get('transcript')
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    if not all([transcript, access_token, refresh_token]):
        return jsonify({'error': 'Transcript, access_token, and refresh_token are required'}), 400

    # --- Dynamic Tool Definition (Per-Request) ---
    # The tool is defined inside the endpoint to access the user-specific tokens.
    @tool
    def create_google_calendar_event(task_description: str, deadline: str) -> str:
        """
        Creates a new event in the user's primary Google Calendar.
        This tool requires a clear task description and a specific deadline
        (e.g., "tomorrow at 10 AM", "next Tuesday at 3pm", "August 25th 2025").
        """
        try:
            credentials_info = {
                'token': access_token,
                'refresh_token': refresh_token,
                'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
            creds = Credentials.from_authorized_user_info(credentials_info)

            # Refresh the token if it's expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

            service = build('calendar', 'v3', credentials=creds)

            # Parse the natural language deadline into a datetime object
            try:
                deadline_dt = parse(deadline)
            except (ValueError, TypeError):
                return f"Error: The deadline '{deadline}' is unclear. Please provide a more specific date and time."

            start_time = deadline_dt.isoformat()
            end_time = (deadline_dt + datetime.timedelta(hours=1)).isoformat()

            event_body = {
                'summary': f"Task: {task_description}",
                'description': f"Task extracted via AI from meeting transcript. Original deadline text: '{deadline}'",
                'start': {'dateTime': start_time, 'timeZone': 'Europe/Amsterdam'},
                'end': {'dateTime': end_time, 'timeZone': 'Europe/Amsterdam'},
            }
            
            created_event = service.events().insert(calendarId='primary', body=event_body).execute()
            return f"Success: Event for '{task_description}' was created. View it here: {created_event.get('htmlLink')}"
        except Exception as e:
            return f"Error: Failed to create Google Calendar event. Details: {e}"

    tools = [create_google_calendar_event]

    try:
        # Create the agent and executor for this specific request
        agent = create_json_chat_agent(LLM, tools, PROMPT_TEMPLATE)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True, 
            handle_parsing_errors="Something went wrong. Please try rephrasing your request."
        )

        # Combine instructions and the transcript into a single, clear input for the agent
        input_prompt = (
            "You are an intelligent assistant. Your goal is to analyze the transcript, "
            "identify every actionable task, and use the `create_google_calendar_event` tool for each one. "
            "**IMPORTANT RULE: If a deadline is vague or missing (e.g., 'next week', 'soon'), you MUST assume the deadline is 'tomorrow at 12:00 PM' and pass that string to the tool.** "
            "Do not ask for clarification. Always create an event."
            f"\n\n--- TRANSCRIPT ---\n{transcript}\n--- END TRANSCRIPT ---"
        )
        
        result = agent_executor.invoke({"input": input_prompt})

        return jsonify({'status': 'success', 'result': result['output']}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"An unexpected error occurred in the agent: {e}"}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)