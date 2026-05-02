import os
import asyncio
import uuid
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from google import genai
from groq import AsyncGroq
from google.genai import types
from dotenv import load_dotenv

# --- 1. SETUP & SECRETS ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GOOGLE_API_KEY or not GROQ_API_KEY:
    print("❌ ERROR: API Keys missing in .env file!")

client = genai.Client(api_key=GOOGLE_API_KEY) 
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    SessionMiddleware, 
    secret_key="IIT_Patna_Secure_Key_2026",
    https_only=False, 
    same_site="lax"
)

# --- 2. SESSION MANAGEMENT ---
SERVER_SESSIONS = {}

def get_user_session(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        user_id = str(uuid.uuid4())
        request.session["user_id"] = user_id
        request.session.modified = True 
    
    if user_id not in SERVER_SESSIONS:
        SERVER_SESSIONS[user_id] = {
            "history_gemini": [],
            "history_llama": [],
            "history_mixtral": []
        }
    return user_id, SERVER_SESSIONS[user_id]

# --- 3. AI ENGINES ---
async def ask_gemini(history):
    try:
        formatted = [types.Content(role="model" if m["role"]=="assistant" else "user", 
                                   parts=[types.Part(text=m["content"])]) for m in history]
        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=formatted)
        return response.text
    except Exception as e:
        return f"Gemini Error: {str(e)}"

async def ask_llama(history):
    try:
        chat = await groq_client.chat.completions.create(messages=history, model="llama-3.3-70b-versatile")
        return chat.choices[0].message.content
    except Exception as e:
        return f"Llama Error: {str(e)}"

async def ask_mixtral(history):
    try:
        chat = await groq_client.chat.completions.create(messages=history, model="mixtral-8x7b-32768")
        return chat.choices[0].message.content
    except Exception as e:
        return f"Mixtral Error: {str(e)}"

# --- 4. ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        user_id, session = get_user_session(request)
        # Explicit arguments prevent the "unhashable dict" error
        return templates.TemplateResponse(
            request=request, 
            name="index.html", 
            context={"request": request, "session": session}
        )
    except Exception as e:
        return HTMLResponse(content=f"<h1>Home Page Crash</h1><p>Error: {str(e)}</p>", status_code=500)

@app.get("/compare")
async def compare_models(request: Request, prompt: str):
    user_id, session = get_user_session(request)
    for m in ["gemini", "llama", "mixtral"]:
        session[f"history_{m}"].append({"role": "user", "content": prompt})
    
    try:
        res = await asyncio.gather(
            ask_gemini(session["history_gemini"]),
            ask_llama(session["history_llama"]),
            ask_mixtral(session["history_mixtral"])
        )
        session["history_gemini"].append({"role": "assistant", "content": res[0]})
        session["history_llama"].append({"role": "assistant", "content": res[1]})
        session["history_mixtral"].append({"role": "assistant", "content": res[2]})
        return {"gemini": res[0], "llama": res[1], "mixtral": res[2]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/chat/{model_name}", response_class=HTMLResponse)
async def chat_page(request: Request, model_name: str):
    user_id, session = get_user_session(request)
    return templates.TemplateResponse(
        request=request,
        name="chat.html", 
        context={
            "request": request, 
            "model_name": model_name, 
            "session": session
        }
    )

@app.get("/chat/{model_name}/api")
async def chat_api(model_name: str, prompt: str, request: Request):
    user_id, session = get_user_session(request)
    h_key = f"history_{model_name}"
    session[h_key].append({"role": "user", "content": prompt})
    
    if model_name == "gemini": ans = await ask_gemini(session[h_key])
    elif model_name == "llama": ans = await ask_llama(session[h_key])
    else: ans = await ask_mixtral(session[h_key])
        
    session[h_key].append({"role": "assistant", "content": ans})
    return {"answer": ans}