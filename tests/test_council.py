import pytest
import httpx
from httpx import Response
from backend.council import (
    parse_ranking_from_text,
    calculate_aggregate_rankings,
    stage1_collect_responses,
    run_full_council,
)
from backend.config import OPENROUTER_API_URL

def test_parse_ranking_no_hallucination():
    """
    (1) build a fake response where 'Response A' appears in the critique text
    before the FINAL RANKING section, confirm it does NOT appear in the
    parsed output from the critique section
    """
    text = '''
I have reviewed the answers. Response A is okay, but Response B is better.
Response C is also good.

FINAL RANKING:
1. Response B
2. Response C
'''
    parsed = parse_ranking_from_text(text)
    assert parsed == ["Response B", "Response C"]
    assert "Response A" not in parsed

def test_parse_ranking_missing_section():
    """
    (2) pass text with no FINAL RANKING: header, confirm empty list returned
    """
    text = "I think Response A is the best overall, followed by Response B."
    parsed = parse_ranking_from_text(text)
    assert parsed == []

def test_parse_ranking_valid():
    """
    (3) pass a correctly formatted FINAL RANKING block, confirm correct ordered list returned
    """
    text = '''Some thoughts...
FINAL RANKING:
1. Response C
2. Response A
3. Response B
'''
    parsed = parse_ranking_from_text(text)
    assert parsed == ["Response C", "Response A", "Response B"]

def test_aggregate_rankings_self_score_discounted():
    """
    (4) build fake stage2 results where one evaluator matches the subject model,
    confirm that model's self-score is weighted at 0.5
    """
    stage2_results = [
        {
            "model": "model_1",
            "ranking": "FINAL RANKING:\n1. Response A\n2. Response B",
            "parsed_ranking": ["Response A", "Response B"],
            "rubric": None
        }
    ]
    label_to_model = {
        "Response A": "model_1",
        "Response B": "model_2"
    }
    
    # model_1 ranked Response A (itself) as #1. Score for #1 of 2 is (2 - 1 + 1) * 10 = 20.
    # Its self-weight is 0.5, so 20 * 0.5 = 10.
    # model_1 ranked Response B as #2. Score for #2 of 2 is (2 - 2 + 1) * 10 = 10.
    # Its peer-weight is 1.0, so 10 * 1.0 = 10.
    
    aggregate = calculate_aggregate_rankings(stage2_results, label_to_model)
    
    scores = {item["model"]: item["total_score"] for item in aggregate}
    assert scores["model_1"] == 10.0
    assert scores["model_2"] == 10.0

@pytest.mark.asyncio
async def test_stage1_partial_failure(mock_openrouter):
    """
    (5) mock two models where one returns a valid response and the other raises
    a timeout, confirm stage1 returns exactly one result and does not raise
    """
    models = ["model_success", "model_timeout"]
    
    def side_effect(request):
        req_body = request.read().decode("utf-8")
        if "model_timeout" in req_body:
            raise httpx.TimeoutException("Timeout")
        return Response(200, json={
            "id": "gen-123",
            "choices": [{"message": {"content": "Success content"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}
        })
        
    mock_openrouter.post("/api/v1/chat/completions").mock(side_effect=side_effect)
    
    # Run stage1 with exactly these 2 models
    results = await stage1_collect_responses("Hello", council_models=models)
    
    assert len(results) == 1
    assert results[0]["model"] == "model_success"
    assert results[0]["response"] == "Success content"

@pytest.mark.asyncio
async def test_run_full_council_minimum_guard(mock_openrouter):
    """
    (6) mock all models to return None, confirm run_full_council returns the
    minimum-models error message without crashing
    """
    models = ["model_1", "model_2", "model_3"]
    
    # Mock all to timeout so they return None
    mock_openrouter.post("/api/v1/chat/completions").mock(side_effect=httpx.TimeoutException("Timeout"))
    
    s1, s2, s3, meta = await run_full_council("Hello", council_models=models)
    
    assert len(s1) == 0
    assert len(s2) == 0
    assert s3["model"] == "error"
    assert "At least two models are required" in s3["response"]
