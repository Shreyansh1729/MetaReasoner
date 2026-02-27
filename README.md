# MetaReasoner – Multi-LLM Consensus & Evaluation System

![MetaReasoner System Overview](header.png)

MetaReasoner is an advanced, locally-hosted web application that leverages a multi-agent architectural pattern to synthesize highly accurate and rigorously evaluated responses from multiple Large Language Models (LLMs). By distributing user queries across a configurable panel of distinct LLMs, MetaReasoner ensures that the final output benefits from diverse reasoning models and cross-validation prior to presentation.

The system interfaces with multiple models via the OpenRouter API, abstracting away the complexities of managing disparate model endpoints while retaining full control over prompt engineering and response aggregation.

## System Workflow

MetaReasoner executes a deterministic pipeline for every user inquiry:

1. **Router Model Classification**
   The query is first classified by a cheap, fast Router model (e.g., Gemini Flash) to assign it to one of six specialized `COUNCIL_PRESETS` (Coding, Math, Factual, Creative, Reasoning, or General).
2. **Stage 1: Unbiased Elicitation (Generation)**
   The user's prompt is asynchronously dispatched to every model in the active configuration. The system aggregates these independent outputs, preventing models from influencing each other.
3. **Stage 2: Blind Peer-Review (Evaluation)**
   Each generated response from Stage 1 is anonymized. Evaluator models assess their peers' outputs based on a robust 5-point JSON Rubric (accuracy, reasoning, completeness, clarity, confidence) returning raw JSON scores.
4. **Stage 3: Executive Synthesis (Conclusion)**
   A designated "Chairman" model receives the original prompt, all independent responses, and the complete rubric scores. The Chairman token-streams a definitive, authoritative, and singular response back to the user.

## Core Setup

### 1. Dependency Resolution

MetaReasoner requires modern Python and Node.js environments. The project is managed using `uv` for the backend and `npm` for the frontend.

**Backend Setup:**
```bash
uv sync
```

**Frontend Setup:**
```bash
cd frontend
npm install
cd ..
```

### 2. Environment Configuration

You must provide a valid OpenRouter API key to interface with the external LLMs. You can either construct this file manually or **configure it dynamically via the "Settings" button in the Web UI**.

```bash
OPENROUTER_API_KEY=your_secure_api_key_here
```

The system requires no database setup commands. By default, it manages all conversations, token costs, and rankings using an auto-initializing SQLite database file stored at `data/metareasoner.db`.

### 3. Model Configuration (Optional)

You can customize the underlying architecture by modifying `backend/config.py`. Define your panel models and designate a Chairman:

```python
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

CHAIRMAN_MODEL = "google/gemini-3-pro-preview"
```

## Running the Application

**Option A: Automated Startup**
```bash
./start.sh
```

**Option B: Manual Startup**

Start the FastAPI application:
```bash
uv run python -m backend.main
```

Start the Vite development server:
```bash
cd frontend
npm run dev
```

Navigate to `http://localhost:3000` to access the interface.

## System Architecture

- **Backend:** FastAPI, Python 3.10+, async httpx for parallel requests
- **Database:** SQLite3 schema for messages, token costs, and pairwise rank history
- **Frontend:** React, Vite, react-markdown, customized CSS
- **Features:** Elo Dashboard Analytics, Markdown Export capabilities, API Key state toggling
