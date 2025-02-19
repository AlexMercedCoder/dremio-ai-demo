from flask import Flask, request, render_template, session
from dremio_simple_query.connect import DremioConnection
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from langchain.schema import AIMessage, HumanMessage
import os

# Load environment variables
load_dotenv()

# Flask setup with session handling
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Dremio connection setup
TOKEN = os.getenv("DREMIO_TOKEN")
ARROW_ENDPOINT = os.getenv("DREMIO_ARROW_ENDPOINT")
dremio = DremioConnection(TOKEN, ARROW_ENDPOINT)

# OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize LangChain chat model and memory
chat_model = ChatOpenAI(model_name="gpt-4o", openai_api_key=OPENAI_API_KEY)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Tool 1: Get Some Data from Dremio
def get_customer_list(_input=None):
    print("Fetching full customer list")
    query = """SELECT DISTINCT id, customer FROM source.customers;"""
    
    # Use toArrow() to get StreamBatchReader
    reader = dremio.toArrow(query)

    # Read all batches into an Arrow Table
    table = reader.read_all()
    
    # Convert Arrow Table to a string representation
    data_string = str(table)  # or table.format()

    if data_string.strip():
        return f"CUSTOMER LIST:\n{data_string}"
    
    return "No customers found."

get_customer_list_tool = Tool(
    name="get_customer_list",
    func=get_customer_list,
    description="Retrieves a list of all customer names and IDs from the database."
)

# Tool 2: Get Customer Data
def get_customer_data(customer_id: str):
    print(f"Fetching data for customer ID {customer_id}")
    query = f"""
    SELECT * FROM source.customer_data 
    WHERE company_id = '{customer_id}';
    """
    
    # Use toArrow() to get StreamBatchReader
    reader = dremio.toArrow(query)

    # Read all batches into an Arrow Table
    table = reader.read_all()
    
    # Convert Arrow Table to a string representation
    data_string = str(table)

    if data_string.strip():
        print("Customer data retrieved.")
        return data_string
    
    return "No data found for this customer."

get_customer_data_tool = Tool(
    name="get_customer_data",
    func=get_customer_data,
    description="Retrieves customer-specific data given a customer ID."
)

# Initialize AI Agent with tools
tools = [get_customer_list_tool, get_customer_data_tool]
agent = initialize_agent(
    tools, 
    chat_model, 
    agent="chat-conversational-react-description", 
    memory=memory, 
    verbose=True
)

@app.route("/", methods=["GET", "POST"])
def index():
    response = None

    # Reset chat history on refresh (GET request)
    if request.method == "GET":
        session.clear()

    # Initialize chat history if not set
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        user_question = request.form["question"]

        # Build contextual prompt considering past conversations
        past_chat = "\n".join([f"You: {msg['question']}\nAI: {msg['answer']}" for msg in session["chat_history"]])
        full_prompt = f"""
        You are a cheerful assistant for a sales agent looking to understand existing deals. 
        - If a customer name is provided, ensure correct spelling by checking the customer list.
        - Then retrieve their ID and fetch relevant customer data.
        - Finally, answer the user's question in a helpful and engaging way.

        Here is the conversation so far:
        {past_chat}

        User's New Question: {user_question}
        """

        # Try running the AI agent, and catch any errors
        try:
            agent_inputs = {"input": full_prompt}
            response = agent.run(agent_inputs)
        except Exception as e:
            response = f"Error: {str(e)}"  # Display the error message

        # Store chat history for continuity (APPEND new messages)
        session["chat_history"].append({"question": user_question, "answer": response})
        session.modified = True  # Ensure session updates persist

    return render_template("index.html", chat_history=session["chat_history"], response=response)

if __name__ == "__main__":
    app.run(debug=True)





