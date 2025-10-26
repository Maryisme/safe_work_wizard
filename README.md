


This is a project that helps users decide whether they have a harassment
case worth pursuing for the Human Rights Tribunal.

The users will answer a few questions pertaining to their situation, including describing it 
and then based on the legal standards and case precedent from the cases we have given to 
the LLM in our database it can then decide if this case is worth pursuing and give some
important information.

The backend is built in python and stores the parsed cases in a database, it runs the 
API get and post points in server.py as well as the OpenAI API key calls.

The frontend is built in html/css and javascript, it stores the results of the answers given
from the user and when the submit button is clicked it sends them to the LLM via API request
in JSON format, it also handles the frontend styling and effects using the DOM.




1. INSTRUCTIONS for running python server:

pre-requisites - 
    1. python 3.9-3.12 installed
    2. a working openai key with credits on it

terminal commands to install and run code:
python3 -m venv .venv
source .venv/bin/activate
pip install flask flask-cors python-dotenv chromadb openai

running server -> python server.py

2. INSTRUCTIONS for running JavaScript server:

npm install
running server -> npm run dev

3. Running both servers
To run both servers you must run each in their own terminal and then go to the
localhost being run by npm which will be functional if the backend and frontend
servers are both running
