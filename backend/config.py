"""Configuration for MetaReasoner."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Council members - list of OpenRouter model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# --- CHANGED --- Added Router Model and Council Presets
ROUTER_MODEL = "google/gemini-2.5-flash"

COUNCIL_PRESETS = {
    "CODING": ["deepseek/deepseek-coder", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"],
    "MATH": ["openai/o1-mini", "google/gemini-1.5-pro", "anthropic/claude-3.5-sonnet"],
    "CREATIVE_WRITING": ["anthropic/claude-3-opus", "google/gemini-2.5-flash", "mistralai/mixtral-8x7b-instruct"],
    "FACTUAL_RESEARCH": ["perplexity/llama-3.1-sonar-large-128k-online", "openai/gpt-4o", "x-ai/grok-2"],
    "REASONING": ["openai/o1", "anthropic/claude-3.5-sonnet", "google/gemini-1.5-pro"],
    "GENERAL": COUNCIL_MODELS
}

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# --- CHANGED --- Added Anti-AI System Prompts
STAGE1_SYSTEM_PROMPT = (
    "You are an expert advisor. Respond directly to the prompt without ANY AI "
    "affirmations, filler, or conversational padding "
    "(e.g., no 'Certainly!', 'Of course!', 'Great question!', 'I\\'d be happy to', 'Here is', 'I hope this helps'). "
    "Use a strict academic register. Focus entirely on data and logic."
)

STAGE2_SYSTEM_PROMPT = (
    "You are a critical evaluator. Respond directly without ANY AI affirmations, "
    "filler, or conversational padding. Use a strict academic register. "
    "Be bluntly critical of the responses you are evaluating. Do not use diplomatic "
    "softening or false praise. Focus entirely on flaws, data, and logic. "
    "RETURN ONLY A RAW JSON OBJECT with no markdown fences, no preamble, and no explanation. "
    "The schema must be EXACTLY: {\"evaluations\": [{\"response_label\": \"A\", \"accuracy\": 8, \"reasoning\": 9, \"completeness\": 7, \"clarity\": 8, \"confidence\": 0.9}, ...]} "
    "where scores are 1-10 and confidence is 0.0-1.0 representing how certain you are in your own assessment."
)
