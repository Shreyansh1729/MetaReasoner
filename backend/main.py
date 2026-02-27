"""FastAPI backend for MetaReasoner."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio
import os
from pathlib import Path

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings, get_council_for_query
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL

app = FastAPI(title="MetaReasoner API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    # --- CHANGED --- Added council models and chairman override
    council_models: List[str] | None = None
    chairman_model: str | None = None


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Settings(BaseModel):
    """Settings structure for API."""
    openrouter_api_key: str


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "MetaReasoner API"}


# --- CHANGED --- Added /api/models endpoint to fetch default council models
@app.get("/api/models")
async def get_models():
    """Get available models for the council."""
    return {
        "council_models": COUNCIL_MODELS,
        "chairman_model": CHAIRMAN_MODEL
    }


@app.get("/api/settings")
async def get_settings():
    """Get current settings from .env."""
    env_path = Path(__file__).parent.parent / ".env"
    api_key = ""
    
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"\'')
                    break
                    
    return {"openrouter_api_key": api_key}


@app.post("/api/settings")
async def update_settings(settings: Settings):
    """Update settings in .env."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path.touch()
        
    # Read existing or create new
    lines = []
    found_key = False
    
    with open(env_path, "r") as f:
        lines = f.readlines()
            
    # Update the key
    for i, line in enumerate(lines):
        if line.startswith("OPENROUTER_API_KEY="):
            lines[i] = f'OPENROUTER_API_KEY="{settings.openrouter_api_key}"\n'
            found_key = True
            break
            
    if not found_key:
        lines.append(f'OPENROUTER_API_KEY="{settings.openrouter_api_key}"\n')
        
    # Write back
    with open(env_path, "w") as f:
        f.writelines(lines)
        
    # Also update environment variable so it takes effect instantly
    os.environ["OPENROUTER_API_KEY"] = settings.openrouter_api_key
        
    return {"status": "success"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.get("/api/analytics")
async def get_analytics():
    """Get Elo ratings, cost summaries, and system usage stats."""
    # 1. Elo ratings
    elo_ratings = storage.calculate_elo_ratings()
    
    # 2. Cost summary and 3. Total conversations direct via SQLite
    conn = storage.get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(id) as cnt FROM conversations")
    total_conversations = c.fetchone()["cnt"]

    c.execute('''
        SELECT model, 
               SUM(tokens_in) as total_tokens_in, 
               SUM(tokens_out) as total_tokens_out 
        FROM model_responses 
        GROUP BY model
    ''')
    cost_rows = c.fetchall()
    conn.close()

    cost_summary = []
    for row in cost_rows:
        cost_summary.append({
            "model": row["model"],
            "total_tokens_in": row["total_tokens_in"] or 0,
            "total_tokens_out": row["total_tokens_out"] or 0
        })

    return {
        "elo_ratings": elo_ratings,
        "cost_summary": cost_summary,
        "total_conversations": total_conversations
    }


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    # --- CHANGED --- Pass council_models downward
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        request.council_models
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # --- CHANGED --- Resolve models dynamically
            council_models, detected_category = await get_council_for_query(request.content, request.council_models)

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            # --- CHANGED --- Pass council_models downward
            stage1_results = await stage1_collect_responses(request.content, council_models)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            # --- CHANGED --- Pass council_models downward
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results, council_models)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings, 'detected_category': detected_category}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            # --- CHANGED --- Loop through generator yielding token events until Sentinel
            stage3_result = None
            async for chunk in stage3_synthesize_final(request.content, stage1_results, stage2_results):
                if isinstance(chunk, dict) and chunk.get("done"):
                    stage3_result = {"model": chunk["model"], "response": chunk["response"]}
                else:
                    yield f"data: {json.dumps({'type': 'stage3_token', 'data': chunk})}\n\n"
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
