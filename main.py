import os 
import asyncio
import uuid # generate unique id 
from fastapi import FastAPI , Request #request is used to add browser info 
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware   #the cookie maker
from google import genai    #google sdk , that help to convert python standard od eto grammar that google demand
from groq import AsyncGroq   #"The Async Version for speed"
from google.genai import types  
from dotenv import load_dotenv


#loading secret key vault
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)     #wake up google client 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client  = AsyncGroq(api_key = GROQ_API_KEY)

#initialization of server 
app= FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

#turn on the cookie maker 
app.add_middleware( SessionMiddleware, 
    secret_key= " My_Secret_Key",
    https_only = False, # Syntax Fix: Changed "False" (string) to False (boolean)
    same_site = "lax"
    )

#The server memory (Locker Room )
SERVER_SESSIONS = {}

#helper function that do work when user visit 
def get_user_session(request:Request):
    user_id= request.session.get("user_id") #looking inside request.session dictnory to search user_id

    if not user_id:
        user_id = str(uuid.uuid4())   #creating user id 

        request.session["user_id"] = user_id
    if user_id not in SERVER_SESSIONS:
        SERVER_SESSIONS[user_id]= {
            "history_gemini":[],
            "history_llama":[],
            "history_mixtral":[]
        }

    return user_id, SERVER_SESSIONS[user_id] #function return one or more than one value as tuple
    
async def ask_gemini(history):  #function is to take the normal history, translate it into Google's strict corporate grammar, send it to the internet, and return the answer
    try:
        formatted_history = []  
        for msg in history:
            #Check the role: if it's "assistant", Google wants "model"
            if msg["role"]=="assistant":
                role = "model"
            else:
                role ="user"
            #pack the text nto Google Part box
            part = types.Part(text=msg["content"])
            # 3. Pack the role and the part into the "Content" box
            content = types.Content(role=role, parts=[part])
            
            # 4. Put that finished box into our "envelope" (the list)
            formatted_history.append(content)

    # Send the finished list to Google and await the response
    #await tells Python: "Pause this specific function right here, go do other work if you need to, and wake me back up ONLY when Google has the answer ready."
        response = await client.aio.models.generate_content(   #generating answer asynchronously(aio),so that while server is waiting for Google to think of an answer, it can still handle other users. It doesn't "freeze" computer.
            model='gemini-2.5-flash',  #by using this model 
            contents=formatted_history #thats the payload , means translated user;s question and previous chat 
        )
        
        # Return only the text answer
        return response.text
    except Exception as e:
        # If the internet dies or the API key is wrong, this catches the crash!
        return f"Gemini Error: {str(e)}"

#llama engine 
async def ask_llama(history):
    try:
        #using Asyncgroq  client to send the message 
        chat_completion = await groq_client.chat.completions.create(
            messages = history, # Syntax Fix: Changed 'message' to 'messages'
            model = "llama-3.3-70b-versatile"  #The llama3 brain 
        )

        return chat_completion.choices[0].message.content  #. Groq sends back a very deep "folder," and we have to dig three levels deep to find the AI's actual words.
    except Exception as e :
        return f"LLama Error{str(e)}"

#Mixtral engine
async def ask_mixtral(history):
    try:
        #using Asyncgroq  client to send the message 
        chat_completion = await groq_client.chat.completions.create(
            messages = history, # Syntax Fix: Changed 'message' to 'messages'
            model = "llama-3.1-8b-instant"  #The mixtral-8x7b-32768 
        )

        return chat_completion.choices[0].message.content  #. Groq sends back a very deep "folder," and we have to dig three levels deep to find the AI's actual words.
    except Exception as e :
        return f"Mixtral Error{str(e)}"

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    # Fix: Get session so index.html can show previous answers on 'Back'
    user_id, session = get_user_session(request)
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "session": session
    })

@app.get("/chat/{model_name}", response_class=HTMLResponse)
async def chat_page(request: Request, model_name: str):
    # Fix: Get session so chat.html can show the full conversation history
    user_id, session = get_user_session(request)
    return templates.TemplateResponse("chat.html", {
        "request": request, 
        "model_name": model_name,
        "session": session
    })

@app.get("/test-ai")
async def test_ai():
    # 1. We create a fake "history" list to send to the function
    # Remember: It must be a LIST of DICTIONARIES
    test_history = [
        {"role": "user", "content": "Hey Gemini! I am building a dashboard. If you can read this, tell me one short joke about programmers."}
    ]
    
    # 2. Now we call your brand new function
    # await - Don't send the response to the browser yet! Wait until Gemini finished typing and returns the text
    answer = await ask_gemini(test_history)
    
    # 3. Return the answer to the browser screen
    return {
        "status": "Success",
        "ai_response": answer
    }

@app.get("/test-groq")
async def test_groq():
    test_msg = [{"role": "user", "content": "Explain what a black hole is to a 5-year-old in one sentence."}]
    llama_ans = await ask_llama(test_msg)
    mixtral_ans = await ask_mixtral(test_msg)
    
    return {
        "llama": llama_ans,
        "mixtral": mixtral_ans
    }

# 1. NEW ROUTE: This handles the real user input from your dashboard
@app.get("/compare")
async def compare_models(request: Request, prompt: str):
    # 2. Get the user's personal session (The "Locker Room")
    user_id, session = get_user_session(request)
    
    # 3. Save the new question into the history for all 3 models
    # This allows the AI to "remember" the conversation
    session["history_gemini"].append({"role": "user", "content": prompt})
    session["history_llama"].append({"role": "user", "content": prompt})
    session["history_mixtral"].append({"role": "user", "content": prompt})
    
    # 4. ASYNCIO GATHER: This is the "Magic" for your resume.
    # It fires all three API calls at the exact same time instead of one-by-one.
    try:
        gemini_ans, llama_ans, mixtral_ans = await asyncio.gather(
            ask_gemini(session["history_gemini"]),
            ask_llama(session["history_llama"]),
            ask_mixtral(session["history_mixtral"])
        )
        
        # 5. Save the AI's answers back into the session memory
        session["history_gemini"].append({"role": "assistant", "content": gemini_ans})
        session["history_llama"].append({"role": "assistant", "content": llama_ans})
        session["history_mixtral"].append({"role": "assistant", "content": mixtral_ans})
        
        return {
            "gemini": gemini_ans,
            "llama": llama_ans,
            "mixtral": mixtral_ans
        }
    except Exception as e:
        return {"error": str(e)}
    

@app.get("/chat/{model_name}", response_class=HTMLResponse)
async def chat_page(request: Request, model_name: str):
    # This renders your new page and tells the HTML which model it is using
    return templates.TemplateResponse("chat.html", {
        "request": request, 
        "model_name": model_name
    })
# Add this to main.py
@app.get("/chat/{model_name}/api")
async def chat_api(model_name: str, prompt: str, request: Request):
    user_id, session = get_user_session(request)
    history_key = f"history_{model_name}"
    
    # Preserve history for multi-turn chat
    session[history_key].append({"role": "user", "content": prompt})
    
    if model_name == "gemini":
        answer = await ask_gemini(session[history_key])
    elif model_name == "llama":
        answer = await ask_llama(session[history_key])
    else:
        answer = await ask_mixtral(session[history_key])
        
    session[history_key].append({"role": "assistant", "content": answer})
    return {"answer": answer}