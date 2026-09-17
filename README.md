# LogPilot

### AI Agent for Autonomous Logistics Exception Resolution

AgentHiveAI is an AI-powered logistics agent that helps resolve shipment exceptions such as failed deliveries, damaged packages, address issues, and delivery delays.

Instead of just showing the problem, the agent looks at the shipment, understands the exception, decides what action should be taken, and carries it out when it is safe to do so. For actions that need human intervention, it pauses and asks for approval.

**Live Demo**

**Try AgentHiveAI:**  
-> https://agenthiveai-5.onrender.com/

---

## Problem

Logistics teams handle a large number of shipment exceptions every day.

A typical exception requires an operator to:

- Find the shipment
- Check its current status
- Understand what went wrong
- Decide what should be done
- Contact or update the relevant system
- Track whether the issue was actually resolved

Doing this manually for every exception is slow and repetitive.

The goal of AgentHiveAI is to automate this process while keeping humans in control of important decisions.

---

## Our Solution

AgentHiveAI works as an **AI operations agent**, not just a chatbot.

It follows this flow:

```text
Shipment Exception
        ↓
Shipment Lookup
        ↓
Understand the Exception
        ↓
Decide the Best Action
        ↓
Risk Check
        ↓
 ┌─────────────────┐
 │ Approval needed?│
 └───────┬─────────┘
         │
    ┌────┴────┐
    │         │
   Yes        No
    │         │
    ↓         ↓
Human       Execute
Approval    Action
    │         │
    └────┬────┘
         ↓
   Resolution
```

This allows routine cases to be handled automatically while high-impact actions can be reviewed by a human.

---

## Key Features

### AI-powered decision making
The agent uses an LLM to understand the shipment exception and determine the next appropriate action.

### Shipment-aware tools
The agent can retrieve and work with shipment information instead of making decisions from the user's message alone.

### Risk-based actions
Actions are checked against a risk policy before execution.

### Human-in-the-loop approvals
If an action requires approval, the workflow pauses and creates an approval request instead of executing it blindly.

### Persistent data with Supabase
Supabase is used for storing and retrieving application data.

### Streamlit interface
A Streamlit application provides the main interface for interacting with the agent.

### FastAPI approval API
A FastAPI service provides endpoints for viewing and responding to pending approval requests.

---

## Tech Stack

| Area | Technology |
|---|---|
| Language | Python |
| AI / LLM | Groq |
| Agent | LLM + Tool Calling |
| Backend API | FastAPI |
| UI | Streamlit |
| Database | Supabase |
| Configuration | Python-dotenv |
| Version Control | Git + GitHub |
| Deployment | Render |

---

## Architecture

```text
                    ┌──────────────────┐
                    │   Streamlit UI   │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │    AI Agent      │
                    │                  │
                    │  LLM + Prompts   │
                    │  Tool Calling    │
                    └────────┬─────────┘
                             │
               ┌─────────────┼─────────────┐
               ↓             ↓             ↓
        ┌────────────┐ ┌────────────┐ ┌─────────────┐
        │  Shipment  │ │ Risk       │ │   Groq LLM  │
        │   Tools    │ │   Policy   │ │             │
        └─────┬──────┘ └────────────┘ └─────────────┘
              │
              ↓
        ┌────────────┐
        │  Supabase  │
        └────────────┘

              High-risk action
                     │
                     ↓
             ┌──────────────┐
             │  Approval    │
             │   Workflow   │
             └──────┬───────┘
                    ↓
              ┌───────────┐
              │ FastAPI   │
              │ Approval  │
              │    API    │
              └───────────┘
```

---

## Example

Consider a shipment with a failed delivery.

Instead of an operator manually checking everything, AgentHiveAI can:

```text
1. Identify the shipment
2. Retrieve the shipment details
3. Understand why delivery failed
4. Determine possible actions
5. Check the risk of the action
6. Execute the action if it is safe
7. Ask for human approval if required
8. Continue after approval
9. Return the final resolution
```

The same approach can be extended to other logistics exceptions such as damaged shipments, address problems, and delays.

---

## Human-in-the-Loop

One of the main ideas behind AgentHiveAI is that **automation should not mean removing humans completely**.

The agent can handle routine operations on its own, but actions with higher impact can be sent to an approval queue.

The operator can then:

- View the pending request
- Understand the proposed action
- Approve it
- Reject it

This gives the system a balance between automation and control.

---

## Project Structure

```text
AgentHiveAI/
│
├── AgentHiveAI/
│   └── backend/
│       │
│       ├── agent/
│       │   ├── tools/
│       │   │   ├── __init__.py
│       │   │   └── shipment.py
│       │   │
│       │   ├── __init__.py
│       │   ├── core.py
│       │   ├── llm.py
│       │   └── prompt.py
│       │
│       ├── tests/
│       │
│       ├── agent.py
│       ├── api.py
│       ├── app.py
│       ├── approvals.py
│       ├── mock_sys.py
│       ├── risk_policy.py
│       ├── supabase_client.py
│       ├── tools.py
│       └── requirements.txt
│
├── .gitignore
└── README.md
```

### Main Files

- `agent/core.py` — Core agent workflow
- `agent/llm.py` — LLM integration
- `agent/prompt.py` — Agent prompts and instructions
- `agent/tools/shipment.py` — Shipment-related tools
- `api.py` — FastAPI approval API
- `app.py` — Streamlit application
- `approvals.py` — Approval handling
- `risk_policy.py` — Action risk rules
- `supabase_client.py` — Supabase connection
- `mock_sys.py` — Mock logistics system
- `tools.py` — Supporting tools
- `tests/` — Tests for the project

---

# How to Run

## Prerequisites

Make sure you have:

- Python 3.10+
- Git
- A Groq API key
- A Supabase project

---

## 1. Clone the repository

```bash
git clone https://github.com/DevCrewOfficial/AgentHiveAI.git
cd AgentHiveAI
```

---

## 2. Navigate to the backend

```bash
cd AgentHiveAI/backend
```

---

## 3. Create a virtual environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 5. Add environment variables

Create a `.env` file inside:

```text
AgentHiveAI/backend/.env
```

Add:

```env
GROQ_API_KEY=your_groq_api_key
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_api_key
```

Do not commit `.env` or expose your API keys publicly.

---

## 6. Run the Streamlit application

From the `backend` directory:

```bash
streamlit run app.py
```

The terminal will provide the local URL for the application.

---

## 7. Run the FastAPI service

Open another terminal and activate the virtual environment again.

Then:

```bash
cd AgentHiveAI/backend
```

Run:

```bash
uvicorn api:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

---

## API Endpoints

The approval API provides endpoints for managing pending actions.

```text
GET  /approvals
GET  /approvals/{approval_id}

POST /approvals/{approval_id}/approve
POST /approvals/{approval_id}/reject
```

---

## Environment Variables

The application currently uses:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Authentication for the Groq API |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase API key |

Keep these values in environment variables rather than hard-coding them in the source code.

---

## Deployment

The backend can be deployed as a Python web service on Render.

For deployment, configure the following environment variables in Render:

```text
GROQ_API_KEY
SUPABASE_URL
SUPABASE_KEY
```

The backend is located at:

```text
AgentHiveAI/backend
```

So when configuring the Render service, use:

```text
Root Directory: AgentHiveAI/backend
```

Use the appropriate start command depending on the service being deployed.

For the FastAPI service:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

---

## Current Status

AgentHiveAI is currently being developed as a hackathon project.

The core workflow includes:

- AI-based exception analysis
- Shipment lookup
- Tool calling
- Risk evaluation
- Human approval
- Supabase integration
- Streamlit interface
- FastAPI approval API

---

## Team

### DevCrewOfficial

Built collaboratively by:

- **Pulla Indira Keerthana** 
- **Praharsha Maroju**
- **Jyothi Sri**


Built for the hackathon.

---

## Repository

[AgentHiveAI](https://github.com/DevCrewOfficial/AgentHiveAI)
