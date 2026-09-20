from __future__ import annotations

import math
import os
import random
import time
from dataclasses import dataclass, asdict

import requests

from .game import cell_id


class ProviderError(RuntimeError):
    pass


@dataclass
class Decision:
    choice: str
    probabilities: dict[str, float]
    confidence: float | None
    source: str
    latency_ms: float

    def dict(self) -> dict:
        return asdict(self)


def api_key(backend: str) -> str:
    if backend == "jev":
        return os.getenv("JEV_API_KEY", "").strip() or os.getenv("TYPESAFE_API_KEY", "").strip()
    if backend == "openrouter":
        return os.getenv("OPENROUTER_API_KEY", "").strip()
    return ""


def validate_probabilities(probabilities, keys: set[str]) -> dict[str, float]:
    if not isinstance(probabilities, dict) or set(probabilities) != keys:
        raise ProviderError("Probabilities must cover exactly all nine cells.")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in probabilities.values()):
        raise ProviderError("Probabilities must be finite numbers in [0, 1].")
    if abs(sum(probabilities.values()) - 1.0) > 0.005:
        raise ProviderError("Probabilities do not sum to one.")
    return {k: float(v) for k, v in probabilities.items()}


def board_text(board: list[str]) -> str:
    return "\n".join(" ".join(board[r * 3:(r + 1) * 3]) for r in range(3))


def model_state(game: dict, prompt_mode: str = "minimal") -> str:
    base = (
        "STANDARD 3x3 TIC-TAC-TOE.\n"
        f"You are {game['turn']}. Choose your next move.\n"
        "Coordinates use row,column with row 1 at the top and column 1 at the left.\n"
        "Board symbols: X, O, and . for empty.\n"
        f"CURRENT BOARD:\n{board_text(game['board'])}\n"
    )
    if prompt_mode == "explicit":
        base += (
            "Use the standard rules: players alternate placing a mark in an empty cell; "
            "an occupied cell cannot be played; three in a row wins.\n"
        )
    base += "Return one move, not an explanation."
    return base


def build_payload(game: dict, backend: str, prompt_mode: str = "minimal") -> dict:
    model = os.getenv("JEV_MODEL", "jev-latest") if backend == "jev" else os.getenv("OPENROUTER_MODEL", "typesafe/jev-1.13")
    criteria = {cell_id(i): f"row {i // 3 + 1}, column {i % 3 + 1}" for i in range(9)}
    return {
        "model": model,
        "state": model_state(game, prompt_mode),
        "questions": {
            "action": {
                "type": "choice",
                "instructions": "Choose the single next move for this tic-tac-toe position.",
                "criteria": criteria,
            }
        },
    }


class Controller:
    def __init__(self, backend: str, seed: int = 17, prompt_mode: str = "minimal"):
        if backend not in ("random", "jev", "openrouter"):
            raise ValueError("Unknown backend")
        if prompt_mode not in ("minimal", "explicit"):
            raise ValueError("Unknown prompt mode")
        self.backend = backend
        self.rng = random.Random(seed)
        self.prompt_mode = prompt_mode

    def choose(self, game: dict) -> Decision:
        action_ids = [a["id"] for a in game["actions"]]
        if len(action_ids) != 9:
            raise ProviderError("The benchmark requires exactly nine unfiltered candidates.")
        started = time.perf_counter()

        if self.backend == "random":
            choice = self.rng.choice(action_ids)
            return Decision(choice, {aid: 1 / 9 for aid in action_ids}, None, "random", (time.perf_counter() - started) * 1000)

        key = api_key(self.backend)
        if not key:
            raise ProviderError(f"{self.backend} key is missing. Edit .env and restart.")
        endpoint = "https://api.typesafe.ai/v1/systemone" if self.backend == "jev" else "https://openrouter.ai/api/alpha/decisions"
        payload = build_payload(game, self.backend, self.prompt_mode)
        timeout = float(os.getenv("MODEL_TIMEOUT", "30"))
        timeout = min(90, max(1, timeout)) if math.isfinite(timeout) else 30
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=(5, timeout),
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise ProviderError("Provider connection failed or timed out; no move was applied.") from exc
        if response.status_code != 200:
            raise ProviderError(f"Provider returned HTTP {response.status_code}; no move was applied.")
        try:
            answer = response.json()["answers"]["action"]
            choice = answer["choice"]
            probabilities = validate_probabilities(answer["probabilities"], set(action_ids))
            confidence = answer.get("confidence")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Unexpected provider response schema; no move was applied.") from exc
        if choice not in action_ids:
            raise ProviderError("Provider selected a cell outside the nine candidates.")
        if confidence is not None and (type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ProviderError("Provider returned invalid confidence.")
        return Decision(choice, probabilities, confidence, self.backend, (time.perf_counter() - started) * 1000)
