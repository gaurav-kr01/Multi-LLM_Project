# Multi-LLM Dashboard

This is the code for the web interface that compares responses from Google Gemini, OpenAI GPT-4, and Anthropic Claude side-by-side using asynchronous requests.

## How to run the project

You will need Python 3.10 or higher installed on your computer to run this.

### 1. Set up the virtual environment
It is highly recommended to run this inside a virtual environment so the packages don't mess with your main system.

Open your terminal in the project folder and run:
```bash
python -m venv venv   

Next, activate it.
For Windows:
Bash
.\venv\Scripts\activate

For Mac/Linux:
Bash
source venv/bin/activate
2. Install the required packages
Once the virtual environment is activated (you should see (venv) in your terminal), install the dependencies:

Bash
pip install -r requirements.txt

3. Add your API keys
The app needs API keys to work.

Create a new file in the exact same folder as main.py and name it .env (make sure it's not .env.txt). Open it and paste your keys like this:

Ini, TOML     i have already saved the API keys in .env files , so don't include to paste it 
GOOGLE_API_KEY="your_google_key_here"
OPENAI_API_KEY="your_groq_key_here"
CLAUDE_API_KEY="your_groq_key_here"

4. Start the server
Run the following command to start the FastAPI server:

Bash
uvicorn main:app --reload
5. View the app
Open your web browser and go to https://www.google.com/search?q=http://127.0.0.1:8000

Common Issues
If you get a "ModuleNotFoundError", it usually means you forgot to activate the virtual environment before trying to run the server.

If the page loads but you get an "Unauthorized" or "401" error when you submit a prompt, double-check that your .env file is named correctly and the keys are valid.