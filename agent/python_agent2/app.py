import os
import datetime
import json
import ast
from flask import Flask, request, jsonify

# --- LangChain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_json_chat_agent
from langchain.tools import tool
from langchain import hub

# --- Google API Imports ---
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# --- Agent Configuration (Global) ---
PROMPT_TEMPLATE = hub.pull("hwchase17/structured-chat-agent")
LLM = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    temperature=0,
    convert_system_message_to_human=True
)

# --- API Endpoint ---
@app.route('/run_agent', methods=['POST'])
def run_agent_endpoint():
    """
    Handles requests to process a transcript, extract tasks,
    create Google Calendar events, and return a structured list of created tasks.
    """
    data = request.get_json()
    
    transcript = data.get('transcript')
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    if not all([transcript, access_token, refresh_token]):
        return jsonify({'error': 'Transcript, access_token, and refresh_token are required'}), 400

    # --- Dynamic Tool Definition (Per-Request) ---
    @tool
    def create_google_calendar_event(task_description: str, deadline_iso: str) -> str:
        """
        Creates a new event in Google Calendar.
        This tool requires a clear task description and a specific deadline
        in ISO 8601 format (e.g., 'YYYY-MM-DDTHH:MM:SS').
        For example: '2025-08-23T12:00:00'.
        """
        try:
            # ... [This tool's code remains unchanged] ...
            credentials_info = {
                'token': access_token,
                'refresh_token': refresh_token,
                'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
                'scopes': ['https://www.googleapis.com/auth/calendar']
            }
            creds = Credentials.from_authorized_user_info(credentials_info)

            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

            service = build('calendar', 'v3', credentials=creds)

            start_time_iso = deadline_iso
            deadline_dt = datetime.datetime.fromisoformat(start_time_iso)
            end_time_iso = (deadline_dt + datetime.timedelta(hours=1)).isoformat()

            event_body = {
                'summary': f"Task: {task_description}",
                'description': f"Task extracted via AI from meeting transcript.",
                'start': {'dateTime': start_time_iso, 'timeZone': 'Europe/Amsterdam'},
                'end': {'dateTime': end_time_iso, 'timeZone': 'Europe/Amsterdam'},
            }
            
            created_event = service.events().insert(calendarId='primary', body=event_body).execute()
            return f"Success: Event for '{task_description}' created. Link: {created_event.get('htmlLink')}"
        except Exception as e:
            return f"Error: Failed to create Google Calendar event. Details: {e}"

    tools = [create_google_calendar_event]

    try:
        agent = create_json_chat_agent(LLM, tools, PROMPT_TEMPLATE)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True, 
            handle_parsing_errors=True
        )

        input_prompt = (
            f"You are a meticulous assistant. Today's date is {datetime.date.today().isoformat()}. "
            "Your process is as follows:\n"
            "1. **Analyze the entire transcript** to identify every single actionable task.\n"
            "2. **For each task you identified**, you MUST use the `create_google_calendar_event` tool one by one, sequentially.\n"
            "3. **You MUST calculate the exact date and time** for deadlines like 'tomorrow' or 'next Tuesday' and provide it to the tool in the required ISO 8601 format ('YYYY-MM-DDTHH:MM:SS').\n"
            "4. **After, and only after, you have called the tool for ALL tasks**, your final answer MUST be a single, valid JSON object. This JSON object must have two keys: 'summary' (a string summarizing what you did) and 'created_tasks' (a list of objects, where each object has 'task_description' and 'deadline_iso')."
            f"\n\n--- TRANSCRIPT ---\n{transcript}\n--- END TRANSCRIPT ---"
        )
        
        result = agent_executor.invoke({"input": input_prompt})
        
        # --- ROBUST PARSING LOGIC ---
        output_data = result['output']
        final_output = None

        # Case 1: The agent correctly returns a dictionary.
        if isinstance(output_data, dict):
            final_output = output_data
        
        # Case 2: The agent returns a string that needs parsing.
        elif isinstance(output_data, str):
            try:
                # Try parsing as JSON first.
                final_output = json.loads(output_data)
            except (json.JSONDecodeError, TypeError):
                try:
                    # Fallback: Try parsing as a Python literal.
                    final_output = ast.literal_eval(output_data)
                except (ValueError, SyntaxError):
                    pass # Parsing failed

        # Validate the structure of the final dictionary.
        if not isinstance(final_output, dict) or 'created_tasks' not in final_output:
            # If validation fails, reset to None to trigger the fallback.
            final_output = None

        # If all parsing and validation fails, create a fallback response.
        if final_output is None:
            final_output = {
                # --- THIS IS THE FIX ---
                # Convert the output_data to a string using str() before concatenation.
                "summary": "Agent finished but did not return structured data. Raw output: " + str(output_data),
                "created_tasks": []
            }

        return jsonify({'status': 'success', 'result': final_output}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"An unexpected error occurred in the agent: {e}"}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)

