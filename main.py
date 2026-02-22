import asyncio
import os
import uuid
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from google import genai
from google.genai import types 

load_dotenv()

app = FastAPI()

app.add_middleware(
    SessionMiddleware, 
    secret_key="Session_Secret_Key", 
    https_only=False, 
    same_site="lax"
)

templates = Jinja2Templates(directory="templates")


GEMINI_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GEMINI_KEY)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

CLAUDE_KEY = os.getenv("CLAUDE_API_KEY")


SERVER_SESSIONS = {}

def get_user_session(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        request.session["user_id"] = user_id
    if user_id not in SERVER_SESSIONS:
        SERVER_SESSIONS[user_id] = {"history_gemini": [], "history_claude": [], "history_openai": []}
    return user_id, SERVER_SESSIONS[user_id]




async def ask_gemini(history):
    """
    Provider: Google
    Model: Gemini 1.5 Flash (Specific Version 001)
    """
    try:
        formatted_history = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            part = types.Part(text=msg["content"])
            content = types.Content(role=role, parts=[part])
            formatted_history.append(content)

        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash', 
            contents=formatted_history
        )
        return response.text
    except Exception as e:
        return f"Gemini Error: {str(e)}"
    
async def ask_openai(history):
    """
    Provider: OpenAI (GPT-4o)
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_KEY}", 
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": history
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(
            "https://api.groq.com/openai/v1/chat/completions", 
            json=data, 
            headers=headers
        ))
        
        if response.status_code != 200:
            return f"OpenAI Error {response.status_code}: {response.text}"
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"OpenAI Connection Error: {e}"

async def ask_claude(history):
    """
    NAME: Claude
    ACTUAL: Groq (Llama 3.3 70B)
    """
    try:
       
        headers = {
            "Authorization": f"Bearer {CLAUDE_KEY}", 
            "Content-Type": "application/json"
        }
        
     
        data = {
            "model": "llama-3.3-70b-versatile", 
            "messages": history
        }
        
      
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: requests.post(
            "https://api.groq.com/openai/v1/chat/completions", 
            json=data, 
            headers=headers
        ))
        
        if response.status_code != 200:
            return f"Error {response.status_code}: {response.text}"
            
    
        return response.json()['choices'][0]['message']['content']

    except Exception as e:
        return f"Connection Error: {e}"




@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_id, session_data = get_user_session(request)
    SERVER_SESSIONS[user_id] = {"history_gemini": [], "history_claude": [], "history_openai": []}
    return templates.TemplateResponse("index.html", {"request": request, "responses": None})

@app.post("/", response_class=HTMLResponse)
async def ask_all(request: Request, prompt: str = Form(...)):
    user_id, session_data = get_user_session(request)
    first_turn_user = [{"role": "user", "content": prompt}]
    
   
    results = await asyncio.gather(
        ask_gemini(first_turn_user), 
        ask_claude(first_turn_user),
        ask_openai(first_turn_user)
    )
    
    session_data["history_gemini"] = [{"role": "user", "content": prompt}, {"role": "assistant", "content": results[0]}]
    session_data["history_claude"] = [{"role": "user", "content": prompt}, {"role": "assistant", "content": results[1]}]
    session_data["history_openai"] = [{"role": "user", "content": prompt}, {"role": "assistant", "content": results[2]}]
    SERVER_SESSIONS[user_id] = session_data


    responses = {"gemini": results[0], "llama": results[1], "mixtral": results[2]}
    return templates.TemplateResponse("index.html", {"request": request, "prompt": prompt, "responses": responses})

@app.get("/chat/{model_type}", response_class=HTMLResponse)
async def chat_view(request: Request, model_type: str):
    user_id, session_data = get_user_session(request)
    history = session_data.get(f"history_{model_type}", [])
    return templates.TemplateResponse("chat.html", {"request": request, "model_type": model_type, "chat_history": history})

@app.post("/chat/{model_type}")
async def chat_continue(request: Request, model_type: str, prompt: str = Form(...)):
    user_id, session_data = get_user_session(request)
    history = session_data.get(f"history_{model_type}", [])
    
    history.append({"role": "user", "content": prompt})
    
    if model_type == "gemini":
        bot_response = await ask_gemini(history)
    elif model_type == "claude":
        bot_response = await ask_claude(history)
    else:
        bot_response = await ask_openai(history)
    
    history.append({"role": "assistant", "content": bot_response})
    session_data[f"history_{model_type}"] = history
    SERVER_SESSIONS[user_id] = session_data
    
    return RedirectResponse(url=f"/chat/{model_type}", status_code=303)