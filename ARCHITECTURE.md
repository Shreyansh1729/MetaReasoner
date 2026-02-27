# Developer Reference: MetaReasoner Architecture

This document serves as the primary technical specification and architectural reference for the MetaReasoner application. It outlines the core components, data flows, and design decisions to facilitate future development and maintenance.

## Architecture Overview

MetaReasoner implements a synchronous, three-stage orchestration pipeline designed to aggregate, evaluate, and synthesize responses from multiple Large Language Models.

### Backend Infrastructure

**`config.py`**
- Manages the active configuration state and system-level prompts (`STAGE1_SYSTEM_PROMPT` and `STAGE2_SYSTEM_PROMPT`).
- Stores `COUNCIL_PRESETS` for dynamic routing, `COUNCIL_MODELS`, and `CHAIRMAN_MODEL` (the synthesizer).
- Ingests environmental variables, specifically `OPENROUTER_API_KEY`.

**`openrouter.py`**
- Contains the HTTP client logic using `httpx`.
- Implements `query_model()` for singular requests, `query_models_parallel()` for concurrent execution, and `stream_model()` for token-by-token SSE streaming.
- Contains the HTTP client logic using `httpx`.
- Implements `query_model()` for singular requests and `query_models_parallel()` for concurrent execution via `asyncio.gather()`.
- Built-in fault tolerance: isolated model failures yield `None` and do not halt the entire pipeline.

**`council.py` (The Orchestrator)**
- **Stage 1 (`stage1_collect_responses`)**: Initiates concurrent prompt dissemination to all active models using an anti-AI system prompt.
- **Stage 2 (`stage2_collect_rankings`)**: Manages the anonymization layer mapping real model identifiers to strict pseudonyms. Models generate structured JSON rubric scoring. Evaluators assign points across accuracy, reasoning, completeness, clarity, and confidence.
- **Stage 3 (`stage3_synthesize_final`)**: Constructs the final aggregation prompt for the Chairman model, streamed token-by-token back to the client.

**`storage.py` & `main.py`**
- **Storage**: Provides a persistent, schema-driven SQLite database (`data/metareasoner.db`). It captures raw conversations, normalized model metrics (tokens, costs), and pairwise rankings to compute Elo ratings.
- **Main**: Exposes the application via FastAPI. It utilizes background tasks for streaming SSE events, defines the RESTful endpoints for message submission, and exposes the `/api/analytics` and `/api/settings` features.

### Frontend Subsystem

**`App.jsx` & UI Components**
- **Architecture**: A modular React application built with Vite containing dual-pane viewing (`Chat` vs `Analytics`).
- **`ChatInterface.jsx`**: Manages the primary user interaction loop, securely encapsulating the multi-stage response metadata, Model Selection checkboxes, and markdown Export functionality.
- **`Stage1.jsx`, `Stage2.jsx`, `Stage3.jsx`**: Dedicated view components for parsing and rendering the discrete stages of the deliberation pipeline. Stage 3 streams incoming tokens down to the DOM in real-time.
- **`Analytics.jsx` & `SettingsModal.jsx`**: Handles presentation of the system-wide Elo leaderboard, token/cost tracking, and dynamically saving the OpenRouter API Key to `.env`.

## Technical Specifications & Best Practices

1. **Relative Imports**: The backend enforces explicit relative imports (`from .module import X`). Execution must always occur via module execution from the project root: `python -m backend.main`.
2. **CORS Policies**: Strict Cross-Origin Resource Sharing is enforced. If deploying to production, modify the `allow_origins` array in `main.py`.
3. **Structured Eval (JSON)**: The Stage 2 ranking parser utilizes strict JSON parsing to extract a 5-point rubric per evaluated model. Fallback regex is included but should be avoided.
4. **Elo Computation**: Pairwise K=32 Elo ratings are calculated dynamically upon requesting the `/api/analytics` endpoint directly from the SQLite `rankings` and `model_responses` tables.

## Extending the Platform

Future iterations of the MetaReasoner should consider:
- Real-time parameter tuning via the administrative UI.
- Native support for alternative inference protocols (e.g., direct OpenAI / Anthropic APIs bypassing OpenRouter).
- Advanced data export capabilities for academic or auditing purposes.
