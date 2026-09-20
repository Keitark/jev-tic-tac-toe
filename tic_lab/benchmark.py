from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .controller import Controller, Decision, ProviderError
from .game import TicTacToe, other


BACKENDS = ("jev", "openrouter", "random", "legal-random")
ILLEGAL_POLICIES = ("forfeit", "retry")


@dataclass
class SideStats:
    decisions: int = 0
    legal: int = 0
    illegal: int = 0
    optimal_legal: int = 0

    def observe(self, legal: bool, optimal: bool | None) -> None:
        self.decisions += 1
        if legal:
            self.legal += 1
            if optimal:
                self.optimal_legal += 1
        else:
            self.illegal += 1


@dataclass
class GameResult:
    game: int
    subject_mark: str
    winner: str
    subject_result: str
    reason: str
    attempts: int
    moves: int
    subject_decisions: int
    subject_legal: int
    subject_illegal: int
    subject_optimal_legal: int
    opponent_decisions: int
    opponent_legal: int
    opponent_illegal: int
    opponent_optimal_legal: int


def legal_random_decision(game: dict, rng: random.Random) -> Decision:
    legal = [a["id"] for a, value in zip(game["actions"], game["board"]) if value == "."]
    if not legal:
        raise ProviderError("No legal moves remain.")
    choice = rng.choice(legal)
    probabilities = {a["id"]: (1 / len(legal) if a["id"] in legal else 0.0) for a in game["actions"]}
    return Decision(choice, probabilities, None, "legal-random", 0.0)


def make_chooser(backend: str, seed: int, prompt_mode: str):
    if backend == "legal-random":
        rng = random.Random(seed)
        return lambda game: legal_random_decision(game, rng)
    controller = Controller(backend, seed=seed, prompt_mode=prompt_mode)
    return controller.choose


def exact_binomial_upper(wins: int, losses: int) -> float | None:
    """P[X >= wins] for X~Binomial(wins+losses, .5); draws are conditioned out."""
    n = wins + losses
    if n == 0:
        return None
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / (2 ** n)


def exact_binomial_two_sided(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    low = min(wins, losses)
    tail = sum(math.comb(n, k) for k in range(0, low + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if total == 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * math.sqrt((p * (1 - p) / total) + z * z / (4 * total * total)) / denom
    return center - radius, center + radius


def summarize(results: list[GameResult], subject: str, opponent: str, illegal_policy: str) -> dict:
    completed = [r for r in results if r.subject_result in ("W", "D", "L")]
    wins = sum(r.subject_result == "W" for r in completed)
    draws = sum(r.subject_result == "D" for r in completed)
    losses = sum(r.subject_result == "L" for r in completed)
    n = len(completed)
    decisive = wins + losses
    score_rate = (wins + 0.5 * draws) / n if n else None
    decisive_win_rate = wins / decisive if decisive else None
    ci = wilson_interval(wins, decisive)

    subject_decisions = sum(r.subject_decisions for r in completed)
    subject_legal = sum(r.subject_legal for r in completed)
    subject_illegal = sum(r.subject_illegal for r in completed)
    subject_optimal = sum(r.subject_optimal_legal for r in completed)
    opponent_decisions = sum(r.opponent_decisions for r in completed)
    opponent_illegal = sum(r.opponent_illegal for r in completed)

    by_mark = {}
    for mark in ("X", "O"):
        subset = [r for r in completed if r.subject_mark == mark]
        mw = sum(r.subject_result == "W" for r in subset)
        md = sum(r.subject_result == "D" for r in subset)
        ml = sum(r.subject_result == "L" for r in subset)
        by_mark[mark] = {"games": len(subset), "wins": mw, "draws": md, "losses": ml}

    return {
        "subject": subject,
        "opponent": opponent,
        "illegal_policy": illegal_policy,
        "games": n,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score_rate": score_rate,
        "decisive_games": decisive,
        "decisive_win_rate": decisive_win_rate,
        "decisive_win_rate_wilson95": list(ci) if ci else None,
        "p_superiority_one_sided": exact_binomial_upper(wins, losses),
        "p_difference_two_sided": exact_binomial_two_sided(wins, losses),
        "subject_illegal_rate": subject_illegal / subject_decisions if subject_decisions else None,
        "subject_optimal_rate_legal": subject_optimal / subject_legal if subject_legal else None,
        "subject_decisions": subject_decisions,
        "subject_illegal": subject_illegal,
        "opponent_illegal_rate": opponent_illegal / opponent_decisions if opponent_decisions else None,
        "by_subject_mark": by_mark,
    }


def run_one(
    game_number: int,
    subject_backend: str,
    opponent_backend: str,
    subject_mark: str,
    seed: int,
    prompt_mode: str,
    illegal_policy: str,
    max_illegal_streak: int,
) -> GameResult:
    game = TicTacToe()
    side_backend = {
        subject_mark: subject_backend,
        other(subject_mark): opponent_backend,
    }
    chooser = {
        mark: make_chooser(side_backend[mark], seed + game_number * 101 + (0 if mark == "X" else 1), prompt_mode)
        for mark in ("X", "O")
    }
    stats = {"X": SideStats(), "O": SideStats()}
    illegal_streak = 0
    forced_winner = None
    reason = "normal"

    while not game.result and forced_winner is None:
        mark = game.turn
        snapshot = game.snapshot()
        decision = chooser[mark](snapshot)
        probability = decision.probabilities.get(decision.choice)
        move = game.play(decision.choice, decision.source, probability)
        stats[mark].observe(move.legal, move.optimal)

        if move.legal:
            illegal_streak = 0
            continue

        illegal_streak += 1
        if illegal_policy == "forfeit":
            forced_winner = other(mark)
            reason = f"illegal_forfeit:{mark}"
        elif illegal_streak >= max_illegal_streak:
            forced_winner = other(mark)
            reason = f"illegal_streak_forfeit:{mark}"

    winner = forced_winner or game.result or "DRAW"
    if winner == "DRAW":
        subject_result = "D"
    elif winner == subject_mark:
        subject_result = "W"
    else:
        subject_result = "L"

    ss = stats[subject_mark]
    os = stats[other(subject_mark)]
    return GameResult(
        game=game_number,
        subject_mark=subject_mark,
        winner=winner,
        subject_result=subject_result,
        reason=reason,
        attempts=game.attempts,
        moves=game.moves,
        subject_decisions=ss.decisions,
        subject_legal=ss.legal,
        subject_illegal=ss.illegal,
        subject_optimal_legal=ss.optimal_legal,
        opponent_decisions=os.decisions,
        opponent_legal=os.legal,
        opponent_illegal=os.illegal,
        opponent_optimal_legal=os.optimal_legal,
    )


def run_benchmark(
    games: int,
    subject: str,
    opponent: str,
    seed: int,
    prompt_mode: str,
    illegal_policy: str,
    max_illegal_streak: int,
    progress_every: int,
) -> tuple[list[GameResult], dict]:
    results: list[GameResult] = []
    for index in range(games):
        subject_mark = "X" if index % 2 == 0 else "O"
        try:
            result = run_one(
                game_number=index + 1,
                subject_backend=subject,
                opponent_backend=opponent,
                subject_mark=subject_mark,
                seed=seed,
                prompt_mode=prompt_mode,
                illegal_policy=illegal_policy,
                max_illegal_streak=max_illegal_streak,
            )
        except ProviderError as exc:
            raise RuntimeError(f"game {index + 1}: provider error: {exc}") from exc
        results.append(result)
        if progress_every and (index + 1) % progress_every == 0:
            summary = summarize(results, subject, opponent, illegal_policy)
            print(
                f"[{index + 1}/{games}] W/D/L="
                f"{summary['wins']}/{summary['draws']}/{summary['losses']} "
                f"score={summary['score_rate']:.3f} "
                f"illegal={summary['subject_illegal_rate']:.3f}",
                file=sys.stderr,
                flush=True,
            )
    return results, summarize(results, subject, opponent, illegal_policy)


def write_json(path: str, results: list[GameResult], summary: dict, args: argparse.Namespace) -> None:
    payload = {
        "format": "jev-tic-tac-toe-benchmark/v1",
        "config": vars(args),
        "summary": summary,
        "games": [asdict(r) for r in results],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: str, results: list[GameResult]) -> None:
    rows = [asdict(r) for r in results]
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(summary: dict) -> None:
    print(f"subject: {summary['subject']}  opponent: {summary['opponent']}")
    print(f"illegal policy: {summary['illegal_policy']}")
    print(f"games: {summary['games']}")
    print(f"W/D/L: {summary['wins']}/{summary['draws']}/{summary['losses']}")
    print(f"score rate: {summary['score_rate']:.4f}")
    if summary["decisive_win_rate"] is not None:
        lo, hi = summary["decisive_win_rate_wilson95"]
        print(f"decisive win rate: {summary['decisive_win_rate']:.4f} (95% Wilson {lo:.4f}..{hi:.4f})")
        print(f"p(superiority, one-sided exact binomial): {summary['p_superiority_one_sided']:.6g}")
        print(f"p(difference, two-sided exact binomial): {summary['p_difference_two_sided']:.6g}")
    print(f"subject illegal rate: {summary['subject_illegal_rate']:.4f}")
    print(f"subject optimal/legal: {summary['subject_optimal_rate_legal']:.4f}")
    print(f"as X: {summary['by_subject_mark']['X']}")
    print(f"as O: {summary['by_subject_mark']['O']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Headless Jev tic-tac-toe benchmark")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--player", choices=BACKENDS, default="jev", dest="subject")
    parser.add_argument("--opponent", choices=BACKENDS, default="random")
    parser.add_argument("--prompt", choices=("minimal", "explicit"), default="minimal", dest="prompt_mode")
    parser.add_argument("--illegal-policy", choices=ILLEGAL_POLICIES, default="forfeit")
    parser.add_argument("--max-illegal-streak", type=int, default=20)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--csv", dest="csv_path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.games < 2:
        parser.error("--games must be at least 2")
    if args.max_illegal_streak < 1:
        parser.error("--max-illegal-streak must be >= 1")
    if args.progress_every < 0:
        parser.error("--progress-every must be >= 0")
    results, summary = run_benchmark(
        games=args.games,
        subject=args.subject,
        opponent=args.opponent,
        seed=args.seed,
        prompt_mode=args.prompt_mode,
        illegal_policy=args.illegal_policy,
        max_illegal_streak=args.max_illegal_streak,
        progress_every=args.progress_every,
    )
    print_summary(summary)
    if args.json_path:
        write_json(args.json_path, results, summary, args)
    if args.csv_path:
        write_csv(args.csv_path, results)
    return 0
