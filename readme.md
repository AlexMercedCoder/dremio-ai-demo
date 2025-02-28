# Dremio AI Demo Guide

# Table of Contents

  - [Step 1: Setup Environment](#step-1-setup-environment)
  - [Step 2: Setup Dremio](#step-2-setup-dremio)
  - [Step 3: Running the AI Agent](#step-3-running-the-ai-agent)
  - [Tear Down the Environment](#tear-down-the-environment)


## Step 1: Setup Environment

- fork/clone the repo
- cd into the repo
- create a virtual environment `python -m venv venv`
- activate the virtual environment `source venv/bin/activate`
- install the requirements `pip install -r requirements.txt`
- start up Dremio & Minio with `docker-compose up`

## Step 2: Setup Dremio

- Go to localhost:9047
- create a `username` and `password` and make sure to put them in your `.env`
- add an s3 source with the follow details
  - general
    - name: `minio`
    - access key: `admin`
    - secret key: `password`
    - encrypy connection: `false`
  - Advanced Options
    - Set `Compatibility Mode` to `true`
    - root path: `/lakehouse`
    - connection properties:
      - `fs.s3a.path.style.access` = `true`
      - `fs.s3a.endpoint` = `minio:9000`

- Create 3 spaces named `raw`, `business`, and `application`

- Go into your minio source and promote/format the 4 CSV files as datasets, make sure to check off the so it extracts the header

- Let's create our `raw` layer representing views on the raw table, this enables us to easily move the table layer without having to rebuild our other layers.

```sql
-- CREATE OUR RAW LAYER
CREATE VIEW raw.customers AS SELECT * FROM minio.sampledata."customers.csv";
CREATE VIEW raw.products AS SELECT * FROM minio.sampledata."products.csv";
CREATE VIEW raw.purchases AS SELECT * FROM minio.sampledata."purchases.csv";
CREATE VIEW raw.store_locations AS SELECT * FROM minio.sampledata."store_locations.csv";
```

- Let's join our fact table `purchases` to our dimension tables `customers`, `products`, and `store_locations` to create our business layer representing our cleaned, modeled data.

```sql
-- Join Our Views for out Dimensional Model in the Business Layer
CREATE VIEW business.purchases
AS SELECT   p.purchase_id,
            p.quantity,
            p.invoiced,
            p.paid,
            c.customer_id,
            c.first_name,
            c.last_name,
            c.address AS customer_address,
            pr.product_id,
            pr.product_name,
            pr.price,
            pr.category,
            pr.description,
            s.store_id,
            s.address AS store_address,
            s.city,
            s.state,
            s.county
FROM        raw.purchases AS p
LEFT JOIN   raw.customers AS c
ON          p.customer_id = c.customer_id
LEFT JOIN   raw.products AS pr
ON          p.product_id = pr.product_id
INNER JOIN  raw.store_locations AS s
ON          p.store_id = s.store_id;
```

- Now we can create views from this data in our application layer for particular use cases like BI or in this case AI.

```sql

-- View of Purchases Invoiced but Not Yet Paid
CREATE VIEW application.unpaid_invoices AS SELECT * FROM business.purchases where invoiced = True and paid = False;

-- VIEW of Purchases from Wisconsim
CREATE VIEW application.wi_purchases AS SELECT * FROM business.purchases WHERE state = 'WI';

```

## Step 3: Running the AI Agent

The code for the agent already exists in `app.py` so assuming you python environment with all dependencies installed is active you can run the agent by running `python app.py`.

Then go to localhost:5000 in your browser and ask questions like "Do we have any unpaid purchases?" or "any purchases for Wisconsin?"

This works because in the code we define 'tools'which are a function and description. The function describes the good to retrieve the data and description is a description of the tool that allows the AI agent to determine the context on when to use the tool.

Here is the tool in `app.py`
```python
# Tool: Get Purchases Data
def get_purchases(_input=None):
    print("Fetching full customer list")
    query = """SELECT * FROM business.purchases"""
    
    # Use toArrow() to get StreamBatchReader
    reader = dremio.toArrow(query)

    # Read all batches into an Arrow Table
    table = reader.read_all()
    
    # Convert Arrow Table to a string representation
    data_string = str(table)  # or table.format()

    if data_string.strip():
        return f"CUSTOMER LIST:\n{data_string}"
    
    return "No purchases found."

get_purchases_tool = Tool(
    name="get_purchases",
    func=get_purchases,
    description="Retrieves a list of purchases from the database."
)

# Initialize AI Agent with tools
tools = [get_purchases_tool]
agent = initialize_agent(
    tools, 
    chat_model, 
    agent="chat-conversational-react-description", 
    memory=memory, 
    verbose=True
)
```

Now this is pulling the full `buiness.purchases` table from the database and returning it as a string. If the table gets too large, it will not fit it the AI Models context window so this is where we'd use more narrow views for specific questions and create additional tools that pull from those views so the AI agent can use the right tool for the right question.

## Tear Down the Environment

When done with the demo environment you clearn up the docker containers and volumtes with the command.

```bash
docker-compose down -v
```

# **Dremio AI Chat Tool Template Guide**

## Table of Contents
- [Getting Started](#getting-started)
- [Overview](#overview)
- [Overview of `app.py`](#overview-of-apppy)
  - [User Input and Context Retrieval](#1-user-input-and-context-retrieval)
  - [Querying and Data Integration](#2-querying-and-data-integration)
  - [Chat Session and Context Management](#3-chat-session-and-context-management)
  - [Frontend and User Experience](#4-frontend-and-user-experience)
- [Customizing to Your Needs](#customizing-to-your-needs)
  - [Color Scheme](#color-scheme)
  - [Creating Tools for the Agent](#creating-tools-for-the-agent)
  - [Customizing the Agent Prompt](#customizing-the-agent-prompt)
  - [Customize the Model](#customize-the-model)

## Getting Started

- fork/clone the repo
- cd into the repo
- create a virtual environment `python -m venv venv`
- activate the virtual environment `source venv/bin/activate`
- install the requirements `pip install -r requirements.txt`
- customize the app based on the guidance in the customization section
- run the app `python app.py`
- open your browser and go to `http://localhost:5000`
- rename `example.env` to `.env` and fill in the variables with your dremio and openai credentials

* Take some time to prepare your data in Dremio creating tables with the data you'd want accessible to the agent and renaming any columns to make their purpose as clear to the agent as possible.

---


## **Overview**
This template can be used to create basic AI agent tools on top of data on Dremio.

---

## **Overview of `app.py`**

### **1. User Input and Context Retrieval**


- **`app.py`**  
  - Users submit **a single natural language question** without specifying a customer.  
  - The AI agent decides when to:  
    1. **Retrieve a customer list** (to verify customer name spelling).  
    2. **Find the customer ID**.  
    3. **Fetch customer-specific data** from Dremio.  
  - The AI dynamically **calls the necessary tools** to retrieve and incorporate data into its response.  
  - **Context from previous messages is preserved**, allowing for a **continuous, conversational experience**.  

---

### **2. Querying and Data Integration**
  
- **`app.py`**  
  - Uses **LangChain tools** to execute **on-demand queries**.  
  - The AI agent determines **when to query** for customer names, IDs, or customer-specific data.  
  - Responses **dynamically adapt** based on retrieved data.  

---

### **3. Chat Session and Context Management**

- **`app.py`**  
  - Maintains **a continuous chat experience**, preserving context across responses.  
  - **Chat history accumulates naturally** like a real chat app.  
  - **Resets on refresh**, but within a session, it **remembers previous exchanges**.  

---

### **4. Frontend and User Experience**

#### **`index.html` (Used with `app3.py`)**
- Theme customizable using CSS Variables
- **Chat input remains at the bottom** (like modern messaging apps).  
- **Messages accumulate correctly** instead of replacing previous ones.  
- AI automatically determines whether it needs to fetch additional data.  
- **Auto-scrolls to the latest message** for a seamless experience.  

---

## Customizing to your needs

### Color Scheme

In `index.html` customize the colors in the css variables to your desired scheme.

```css
            --background-gradient-start: #1e3c72;
            --background-gradient-end: #2a5298;
            --text-color: white;
            --chat-container-bg: rgba(255, 255, 255, 0.1);
            --chat-box-bg: rgba(255, 255, 255, 0.2);
            --scrollbar-thumb: rgba(255, 255, 255, 0.5);
            --scrollbar-track: rgba(255, 255, 255, 0.1);
            --user-message-bg: rgba(173, 216, 230, 0.8);
            --user-message-text: #004466;
            --ai-message-bg: rgba(255, 255, 255, 0.8);
            --ai-message-text: #003366;
            --input-bg: white;
            --button-bg: #00aaff;
            --button-hover-bg: #0088cc;
            --loading-text-color: white;
            --pre-bg: rgba(255, 255, 255, 0.1);
        }
```


### Creating Tools for the Agent

You'll want to create tools so the agent can retrieve data for particular types of tasks you want them handle. Just customize the existings tools in the `app.py` to your needs. In general they should get a very specific amount of data that fits into the AI models context window, so design queries accordingly. So if the table with the data has LOTS of data then think of tools that can help the agent get the narrow data they need. Like in the example below the agent first can pull a list of customers to get a customers id so it can pull a narrower number of records from customer_data table vs just putting all customer data in the prompt which would greatly exceed the context window of the AI model and error:

```py
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
```

Make sure all your tools are included in the initialization of the agent.

```py
# Initialize AI Agent with tools
tools = [get_customer_list_tool, get_customer_data_tool] #<-- all tools listed here
agent = initialize_agent(
    tools, 
    chat_model, 
    agent="chat-conversational-react-description", 
    memory=memory, 
    verbose=True
)
```

### Customizing the Agent Prompt

Customize this portion of the AI Agent Prompt in `app.py` so that is describes how the agent should think of itself and guidance on using the tools provided.

```
        You are a cheerful assistant for a sales agent looking to understand existing deals. 
        - If a customer name is provided, ensure correct spelling by checking the customer list.
        - Then retrieve their ID and fetch relevant customer data.
        - Finally, answer the user's question in a helpful and engaging way.
```

### Customize the Model

The model is currently using `gpt4o` which requires an enterprise OpenAI Key in your `.env` if you want to use a different OpenAI model like `gpt-4` or `gpt-3.5-turbo` then just update the `model_name` property in the `ChatOpenAI` function. If you want to use another model consult the Langchain documentation for connecting to your preferred model whether running in the cloud or locally.

```py
# OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize LangChain chat model and memory
chat_model = ChatOpenAI(model_name="gpt-4o", openai_api_key=OPENAI_API_KEY)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
```
