"""Episodic memory store for the agent — persists task executions to disk."""
import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path.home() / ".gws_agent" / "memory.jsonl"


def save_episode(goal: str, tasks: list[dict], outcome: str) -> None:
    """Save a completed task episode to the memory file."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    episode = {
        "timestamp": datetime.utcnow().isoformat(),
        "goal": goal,
        "tasks": tasks,
        "outcome": outcome,
    }
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(episode) + "\n")


def recall_similar(goal: str, max_results: int = 3) -> list[dict]:
    """Keyword-based recall from past episodes (no vector DB needed for beginners)."""
    if not MEMORY_FILE.exists():
        return []
    goal_words = set(goal.lower().split())
    scored: list[tuple[int, dict]] = []
    with open(MEMORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                ep = json.loads(line)
                past_words = set(ep.get("goal", "").lower().split())
                score = len(goal_words & past_words)
                if score > 0:
                    scored.append((score, ep))
            except Exception:
                continue
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:max_results]]
