# QbMS-Model

A Query-based Meeting Summerizer Model.


# 📝 Meeting Summarizer API

A FastAPI-based service that summarizes meeting transcripts using **DeepSeek** models (via [OpenRouter](https://openrouter.ai/)).

---

## 🚀 Features

- Accepts a raw meeting transcript (plain text).
- Summarizes it into a **clear and concise summary**.
- Configurable generation parameters (`temperature`, `max_tokens`, etc.).
- Ready to test with **Postman** or `curl`.

---

## 📦 Installation

### 1. Clone the repository

```bash
https://github.com/KhalidSinan/QbMS-Model.git
cd QbMS-Model
```

### 2. Create & activate a virtual environment (optional but recommended)

```bash
python -m venv .venv
source venv/bin/activate   # On Linux/Mac
.\.venv\Scripts\activate      # On Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration

1. Get an API key from [OpenRouter](https://openrouter.ai/).(You can use DeepSeek through OpenRouter by selecting `deepseek-chat`.)
2. Create a `.env` file in the project root:

```env
DEEPSEEK_API_KEY=your_openrouter_api_key_here
```

---

## ▶️ Running the API

Start the FastAPI server with:

```bash
uvicorn main:app --reload
```

- By default, it runs on: **http://127.0.0.1:8000**

---

## 📡 API Endpoints

### **POST** `/summarize`

Summarize a meeting transcript.

#### Request body:

```json
{
  "transcript": "[Khalid] Hello Jake, how are you today?\n[Jake] Hi Khalid, I’m doing well, thanks..."
}
```

#### Response:

```json
{
  "summary": "Khalid and Jake greeted each other. Jake shared that he is working as a Flutter developer on a banking app with biometric login and transaction history. Khalid discussed AI tools for automating meeting summaries, and Jake expressed interest in trying them out."
}
```

---

## 🧪 Testing with Postman

1. Open Postman.
2. Create a new **POST request** to:
   ```
   http://127.0.0.1:8000/summarize
   ```
3. Under **Body → raw → JSON**, paste:
   ```json
   {
     "transcript": "[Khalid] Hello Jake, how are you today?\n[Jake] Hi Khalid, I’m doing well..."
   }
   ```
4. Hit **Send** → You’ll get the summarized text in the response.

---

## 📂 Project Structure

```
.
├── Meetin_Summerizer.py          # FastAPI app (API + summarization logic)
├── requirements.txt # Dependencies
├── .env             # API key configuration
└── README.md        # Documentation
```

---

## ⚠️ Notes

- Ensure your **OpenRouter API key** is valid.
- The model defaults to: `deepseek/deepseek-chat`.
- You can tweak parameters (`temperature`, `max_tokens`, etc.) in `main.py`.
