"""3-stage MetaReasoner orchestration."""

import json
from typing import List, Dict, Any, Tuple, AsyncGenerator
from typing import List, Dict, Any, Tuple, AsyncGenerator
from .openrouter import query_models_parallel, query_model, stream_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL, STAGE1_SYSTEM_PROMPT, STAGE2_SYSTEM_PROMPT, ROUTER_MODEL, COUNCIL_PRESETS


# --- CHANGED --- Added optional council_models list
async def stage1_collect_responses(user_query: str, council_models: List[str] = None) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    # --- CHANGED --- Prepend system prompt
    messages = [
        {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
        {"role": "user", "content": user_query}
    ]

    # --- CHANGED --- Use user-provided active models or fallback to default
    active_models = council_models if council_models is not None else COUNCIL_MODELS

    # Query all models in parallel
    responses = await query_models_parallel(active_models, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


# --- CHANGED --- Added optional council_models override block
async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    council_models: List[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Now provide your evaluation:"""

    # --- CHANGED --- Prepend system prompt
    messages = [
        {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
        {"role": "user", "content": ranking_prompt}
    ]

    # --- CHANGED --- Use provided council_models or default from config
    active_models = council_models if council_models is not None else COUNCIL_MODELS

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(active_models, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            
            # --- CHANGED --- Attempt to parse JSON rubric
            rubric = None
            parsed_ranking = []
            
            clean_text = full_text.strip()
            # Strip markdown fences
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            try:
                data = json.loads(clean_text)
                if isinstance(data, dict) and "evaluations" in data:
                    rubric = data["evaluations"]
                    # Generate parsed_ranking from rubric (highest score to lowest)
                    sorted_evals = sorted(
                        rubric, 
                        key=lambda x: (x.get('accuracy', 0) + x.get('reasoning', 0) + x.get('completeness', 0) + x.get('clarity', 0)) * x.get('confidence', 1.0), 
                        reverse=True
                    )
                    parsed_ranking = [f"Response {ev.get('response_label')}" for ev in sorted_evals if 'response_label' in ev]
            except Exception:
                pass
            
            if not parsed_ranking:
                parsed_ranking = parse_ranking_from_text(full_text)

            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed_ranking,
                "rubric": rubric
            })

    return stage2_results, label_to_model


# --- CHANGED --- Converted to async generator for streaming
async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> AsyncGenerator[Any, None]:
    """
    Stage 3: Chairman synthesizes final response (streaming).

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Yields:
        String tokens as they stream in, and finally a dict with the full response
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of MetaReasoner. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model with streaming
    accumulated_text = ""
    async for chunk in stream_model(CHAIRMAN_MODEL, messages):
        accumulated_text += chunk
        yield chunk

    # Yield the final sentinel dictionary
    yield {
        "model": CHAIRMAN_MODEL,
        "done": True,
        "response": accumulated_text
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[-1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

    # Return empty list if no valid ranking section is found
    return []


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and scores, sorted best to worst
    """
    from collections import defaultdict

    # Track total score for each model
    model_scores = defaultdict(float)
    model_counts = defaultdict(int)

    num_options = len(label_to_model)

    for ranking in stage2_results:
        evaluator_model = ranking['model']
        rubric = ranking.get('rubric')

        if rubric:
            for ev in rubric:
                label = f"Response {ev.get('response_label', '')}"
                if label in label_to_model:
                    subject_model = label_to_model[label]
                    
                    accuracy = float(ev.get('accuracy', 0))
                    reasoning = float(ev.get('reasoning', 0))
                    completeness = float(ev.get('completeness', 0))
                    clarity = float(ev.get('clarity', 0))
                    confidence = float(ev.get('confidence', 1.0))
                    
                    raw_score = (accuracy + reasoning + completeness + clarity) * confidence
                    weight = 0.5 if evaluator_model == subject_model else 1.0
                    weighted_score = raw_score * weight
                    
                    model_scores[subject_model] += weighted_score
                    model_counts[subject_model] += 1
        else:
            # Fallback to regex parsing/parsed_ranking
            parsed_ranking = ranking.get('parsed_ranking', [])
            if not parsed_ranking:
                parsed_ranking = parse_ranking_from_text(ranking.get('ranking', ''))

            for position, label in enumerate(parsed_ranking, start=1):
                if label in label_to_model:
                    subject_model = label_to_model[label]
                    weight = 0.5 if evaluator_model == subject_model else 1.0
                    # Fallback scoring: 10 * (max_rank - position + 1)
                    mock_score = float((num_options - position + 1) * 10)
                    model_scores[subject_model] += mock_score * weight
                    model_counts[subject_model] += 1

    aggregate = []
    for model, total_score in model_scores.items():
        aggregate.append({
            "model": model,
            "total_score": round(total_score, 2),
            "average_rank": round(total_score, 2),  # Keep average_rank key to avoid breaking UI that expects it
            "rankings_count": model_counts[model]
        })

    # Sort by total_score descending
    aggregate.sort(key=lambda x: x.get('total_score', 0), reverse=True)

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


# --- CHANGED --- Added dynamic query classification
async def classify_query(user_query: str) -> str:
    """Classify user query to select the best council."""
    prompt = f"""Analyze the following user query and classify it into EXACTLY ONE of the following categories:
CODING
MATH
CREATIVE_WRITING
FACTUAL_RESEARCH
REASONING
GENERAL

Query: {user_query}

Return ONLY the category name. No other text."""

    messages = [{"role": "user", "content": prompt}]
    
    response = await query_model(ROUTER_MODEL, messages, timeout=10.0)
    if response:
        content = response.get('content', '').strip().upper()
        # Clean markdown if present
        if '\n' in content:
            content = content.split('\n')[0].strip()
        for cat in COUNCIL_PRESETS.keys():
            if cat in content:
                return cat
    return "GENERAL"


# --- CHANGED --- Added council resolution function
async def get_council_for_query(user_query: str, user_override: List[str] = None) -> Tuple[List[str], str]:
    """Resolve council either from user selection or by dynamic routing."""
    if user_override and len(user_override) > 0:
        return user_override, "MANUAL_OVERRIDE"
    
    category = await classify_query(user_query)
    return COUNCIL_PRESETS.get(category, COUNCIL_PRESETS["GENERAL"]), category


# --- CHANGED --- Included council_models as parameter and hooked up dynamic routing
async def run_full_council(user_query: str, council_models: List[str] = None) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question
        council_models: Optional user override for council selection

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Resolve models dynamically
    resolved_models, detected_category = await get_council_for_query(user_query, council_models)

    # Stage 1: Collect individual responses
    # --- CHANGED --- pass down user overrides
    stage1_results = await stage1_collect_responses(user_query, resolved_models)

    # --- CHANGED --- Validated that len() >= 2. A single response breaks Stage 2 parsing mathematically.
    if len(stage1_results) < 2:
        return stage1_results, [], {
            "model": "error",
            "response": "At least two models are required for consensus. Please try again."
        }, {"detected_category": detected_category}

    # Stage 2: Collect rankings
    # --- CHANGED --- pass down user overrides
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, resolved_models)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    # --- CHANGED --- For non-streaming run_full_council, buffer the generator
    stage3_result = None
    async for chunk in stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    ):
        if isinstance(chunk, dict) and chunk.get("done"):
            stage3_result = chunk

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "detected_category": detected_category
    }

    return stage1_results, stage2_results, stage3_result, metadata
