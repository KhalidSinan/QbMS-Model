from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Initialize FastAPI app
app = FastAPI(title="Meeting Summarizer API", version="1.0")

# Request schema


class TranscriptRequest(BaseModel):
    transcript: str


def summarize_meeting(transcript: str) -> str:
    """Summarizes a meeting transcript using DeepSeek via OpenRouter."""
    try:
        if not DEEPSEEK_API_KEY:
            raise ValueError("Missing DeepSeek API key.")

        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )

        system_prompt = (
            "You are an AI assistant specialized in summarizing meeting transcripts. "
            "Generate a clear and concise summary. "
            "Just summarize the meeting without extracting keypoints or anything else."
        )

        response = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is the meeting transcript:\n\n{transcript}"},
            ],
            stream=False,
            temperature=0.4,
            max_tokens=1024,
            top_p=0.9,
            presence_penalty=0,
            frequency_penalty=0
        )

        return response.choices[0].message.content

    except Exception as e:
        raise RuntimeError(f"Summarization failed: {str(e)}")


@app.post("/summarize")
def summarize_endpoint(request: TranscriptRequest):
    """API endpoint to summarize meeting transcript."""
    try:
        summary = summarize_meeting(request.transcript)
        return {"summary": summary}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Unexpected error: {str(e)}")
