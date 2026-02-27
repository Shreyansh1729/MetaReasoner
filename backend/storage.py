"""SQLite-based storage for conversations."""

import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "metareasoner.db")


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at DATETIME,
            query_type TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            created_at DATETIME
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS model_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            model TEXT,
            stage INTEGER,
            response TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            latency_ms INTEGER,
            cost_usd REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            evaluator_model TEXT,
            subject_model TEXT,
            rank_position INTEGER,
            accuracy_score REAL,
            reasoning_score REAL,
            completeness_score REAL,
            clarity_score REAL,
            confidence REAL
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on import
init_db()


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    conn = get_db_connection()
    c = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    
    # Store minimal metadata
    c.execute(
        "INSERT INTO conversations (id, title, created_at, query_type) VALUES (?, ?, ?, ?)",
        (conversation_id, "New Conversation", created_at, "GENERAL")
    )
    conn.commit()
    conn.close()

    return {
        "id": conversation_id,
        "created_at": created_at,
        "title": "New Conversation",
        "messages": []
    }


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT c.id, c.created_at, c.title, COUNT(m.id) as message_count
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    ''')
    rows = c.fetchall()
    conn.close()

    conversations = []
    for row in rows:
        conversations.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "title": row["title"],
            "message_count": row["message_count"]
        })

    return conversations


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    conv_row = c.fetchone()
    if not conv_row:
        conn.close()
        return None

    conversation = {
        "id": conv_row["id"],
        "created_at": conv_row["created_at"],
        "title": conv_row["title"],
        "messages": []
    }

    c.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC", (conversation_id,))
    msg_rows = c.fetchall()

    for msg in msg_rows:
        if msg["role"] == "user":
            conversation["messages"].append({
                "role": "user",
                "content": msg["content"]
            })
        else:
            msg_id = msg["id"]

            # Load stage 1
            c.execute("SELECT * FROM model_responses WHERE message_id = ? AND stage = 1 ORDER BY id ASC", (msg_id,))
            s1_rows = c.fetchall()
            stage1 = []
            for r in s1_rows:
                stage1.append({
                    "model": r["model"],
                    "response": r["response"]
                })

            # Create reverse mapping for labels
            model_to_label = {r["model"]: f"Response {chr(65+i)}" for i, r in enumerate(stage1)}

            # Load stage 2
            c.execute("SELECT * FROM model_responses WHERE message_id = ? AND stage = 2 ORDER BY id ASC", (msg_id,))
            s2_rows = c.fetchall()
            stage2 = []
            for r in s2_rows:
                evaluator_model = r["model"]
                
                c.execute(
                    "SELECT * FROM rankings WHERE message_id = ? AND evaluator_model = ? ORDER BY rank_position ASC", 
                    (msg_id, evaluator_model)
                )
                rank_rows = c.fetchall()

                parsed_ranking = []
                rubric = []
                has_rubric = False

                for rank in rank_rows:
                    subject_model = rank["subject_model"]
                    label = model_to_label.get(subject_model, subject_model)
                    
                    if rank["rank_position"] != 99:
                        parsed_ranking.append(label)

                    if rank["accuracy_score"] is not None:
                        has_rubric = True
                        rubric.append({
                            "response_label": label.replace("Response ", ""),
                            "accuracy": rank["accuracy_score"],
                            "reasoning": rank["reasoning_score"],
                            "completeness": rank["completeness_score"],
                            "clarity": rank["clarity_score"],
                            "confidence": rank["confidence"]
                        })

                s2_dict = {
                    "model": evaluator_model,
                    "ranking": r["response"]
                }
                
                if parsed_ranking:
                    s2_dict["parsed_ranking"] = parsed_ranking
                if has_rubric:
                    s2_dict["rubric"] = rubric
                    
                stage2.append(s2_dict)

            # Load stage 3
            c.execute("SELECT * FROM model_responses WHERE message_id = ? AND stage = 3", (msg_id,))
            s3_row = c.fetchone()
            if s3_row:
                stage3 = {
                    "model": s3_row["model"],
                    "response": s3_row["response"]
                }
            else:
                stage3 = None

            conversation["messages"].append({
                "role": "assistant",
                "stage1": stage1,
                "stage2": stage2,
                "stage3": stage3
            })

    conn.close()
    return conversation


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, "user", content, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conn = get_db_connection()
    c = conn.cursor()
    created_at = datetime.utcnow().isoformat()

    c.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, "assistant", "", created_at)
    )
    msg_id = c.lastrowid

    label_to_model = {f"Response {chr(65+i)}": r["model"] for i, r in enumerate(stage1)}

    for r in stage1:
        c.execute(
            "INSERT INTO model_responses (message_id, model, stage, response) VALUES (?, ?, ?, ?)",
            (msg_id, r["model"], 1, r["response"])
        )

    for r in stage2:
        evaluator_model = r["model"]
        c.execute(
            "INSERT INTO model_responses (message_id, model, stage, response) VALUES (?, ?, ?, ?)",
            (msg_id, evaluator_model, 2, r["ranking"])
        )

        parsed_ranking = r.get("parsed_ranking", [])
        rubric = r.get("rubric", [])

        if rubric:
            for ev in rubric:
                label_short = ev.get('response_label', '')
                label = f"Response {label_short}"
                subject_model = label_to_model.get(label, f"unknown_{label_short}")
                
                try:
                    rank_pos = parsed_ranking.index(label) + 1
                except ValueError:
                    rank_pos = 99

                c.execute('''
                    INSERT INTO rankings (
                        message_id, evaluator_model, subject_model, rank_position,
                        accuracy_score, reasoning_score, completeness_score, clarity_score, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    msg_id, 
                    evaluator_model, 
                    subject_model, 
                    rank_pos,
                    ev.get("accuracy"), 
                    ev.get("reasoning"), 
                    ev.get("completeness"),
                    ev.get("clarity"), 
                    ev.get("confidence")
                ))
        else:
            for i, label in enumerate(parsed_ranking):
                subject_model = label_to_model.get(label, f"unknown_{label}")
                c.execute('''
                    INSERT INTO rankings (
                        message_id, evaluator_model, subject_model, rank_position
                    ) VALUES (?, ?, ?, ?)
                ''', (
                    msg_id, evaluator_model, subject_model, i + 1
                ))

    if stage3:
        c.execute(
            "INSERT INTO model_responses (message_id, model, stage, response) VALUES (?, ?, ?, ?)",
            (msg_id, stage3.get("model", ""), 3, stage3.get("response", ""))
        )

    conn.commit()
    conn.close()


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
    conn.commit()
    conn.close()


def calculate_elo_ratings() -> List[Dict[str, Any]]:
    """
    Calculate Elo ratings for all models based on Stage 2 rankings.
    Returns:
        List of dicts with 'model', 'elo', 'wins', 'losses', 'appearances'
    """
    conn = get_db_connection()
    c = conn.cursor()
    # Get all rankings that have a valid rank_position
    c.execute('''
        SELECT message_id, evaluator_model, subject_model, rank_position 
        FROM rankings 
        WHERE rank_position != 99
        ORDER BY message_id, evaluator_model, rank_position ASC
    ''')
    ranking_rows = c.fetchall()
    
    # Also get all stage1 responses to count appearances accurately
    c.execute('SELECT message_id, model FROM model_responses WHERE stage = 1')
    stage1_rows = c.fetchall()
    conn.close()

    from collections import defaultdict
    elo = defaultdict(lambda: 1000.0)
    wins = defaultdict(int)
    losses = defaultdict(int)
    
    # Count appearances (how many times a model gave a Stage 1 response)
    appearances = defaultdict(int)
    for r in stage1_rows:
        appearances[r["model"]] += 1
        # ensure they are at least initialized in the elo dict even if they have 0 wins/losses
        _ = elo[r["model"]]

    # Group rankings by message_id and evaluator_model
    groups = defaultdict(list)
    for r in ranking_rows:
        groups[(r["message_id"], r["evaluator_model"])].append(r)

    K = 32.0

    for (msg_id, eval_model), ranks in groups.items():
        # ranks is already sorted by rank_position
        n = len(ranks)
        for i in range(n):
            for j in range(i + 1, n):
                model_a = ranks[i]["subject_model"]
                model_b = ranks[j]["subject_model"]
                rank_a = ranks[i]["rank_position"]
                rank_b = ranks[j]["rank_position"]
                
                # if rank_position is the same, skip (draw)
                if rank_a == rank_b:
                    continue
                    
                # a is sorted before b, so rank_a < rank_b (a wins)
                winner = model_a if rank_a < rank_b else model_b
                loser = model_b if rank_a < rank_b else model_a

                rating_w = elo[winner]
                rating_l = elo[loser]

                expected_w = 1.0 / (1.0 + 10.0 ** ((rating_l - rating_w) / 400.0))
                expected_l = 1.0 / (1.0 + 10.0 ** ((rating_w - rating_l) / 400.0))

                elo[winner] = rating_w + K * (1.0 - expected_w)
                elo[loser] = rating_l + K * (0.0 - expected_l)

                wins[winner] += 1
                losses[loser] += 1

    results = []
    for model, rating in elo.items():
        results.append({
            "model": model,
            "elo": round(rating),
            "wins": wins[model],
            "losses": losses[model],
            "appearances": appearances[model]
        })

    # Sort descending by elo
    results.sort(key=lambda x: x["elo"], reverse=True)
    return results
