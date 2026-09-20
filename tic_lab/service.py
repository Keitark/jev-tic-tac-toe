from __future__ import annotations

import copy
import secrets
import threading
import time

from .controller import Controller, ProviderError, api_key
from .game import TicTacToe


class AppError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class Service:
    def __init__(self):
        self.lock = threading.RLock()
        self.csrf = secrets.token_urlsafe(24)
        self.game = TicTacToe()
        self.controllers = {"X": "human", "O": "jev"}
        self.prompt_mode = "minimal"
        self.seed = 17
        self.controller_instances: dict[tuple[str, str], Controller] = {}
        self.last_decision = None
        self.error = None
        self.busy = False
        self.playing = False
        self.interval = 0.6
        self.epoch = 0
        self.thread = None
        self.stats = {"ai_decisions": 0, "legal": 0, "illegal": 0, "optimal_legal": 0}

    def _controller(self, mark: str) -> Controller:
        backend = self.controllers[mark]
        key = (mark, backend)
        if key not in self.controller_instances:
            self.controller_instances[key] = Controller(backend, self.seed + (0 if mark == "X" else 1), self.prompt_mode)
        ctrl = self.controller_instances[key]
        ctrl.prompt_mode = self.prompt_mode
        return ctrl

    def snapshot(self) -> dict:
        with self.lock:
            total_legal = self.stats["legal"]
            return {
                "game": self.game.snapshot(),
                "controllers": copy.deepcopy(self.controllers),
                "prompt_mode": self.prompt_mode,
                "seed": self.seed,
                "interval": self.interval,
                "last_decision": copy.deepcopy(self.last_decision),
                "error": self.error,
                "busy": self.busy,
                "playing": self.playing,
                "stats": {
                    **self.stats,
                    "illegal_rate": self.stats["illegal"] / self.stats["ai_decisions"] if self.stats["ai_decisions"] else 0.0,
                    "optimal_rate_legal": self.stats["optimal_legal"] / total_legal if total_legal else 0.0,
                },
            }

    def status(self) -> dict:
        return {
            "csrf": self.csrf,
            "keys": {name: bool(api_key(name)) for name in ("jev", "openrouter")},
            **self.snapshot(),
        }

    def configure(self, data: dict) -> dict:
        controllers = data.get("controllers", self.controllers)
        prompt_mode = data.get("prompt_mode", self.prompt_mode)
        seed = data.get("seed", self.seed)
        interval = data.get("interval", self.interval)
        if not isinstance(controllers, dict) or set(controllers) != {"X", "O"}:
            raise AppError("Controllers must define X and O.")
        for backend in controllers.values():
            if backend not in ("human", "random", "jev", "openrouter"):
                raise AppError("Unknown controller.")
            if backend in ("jev", "openrouter") and not api_key(backend):
                raise AppError(f"{backend} key is missing. Edit .env and restart.")
        if prompt_mode not in ("minimal", "explicit"):
            raise AppError("Unknown prompt mode.")
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise AppError("Seed must be an unsigned 32-bit integer.")
        if type(interval) not in (int, float) or not 0.1 <= interval <= 10:
            raise AppError("Interval must be 0.1-10 seconds.")
        with self.lock:
            if self.busy or self.playing:
                raise AppError("Pause before changing settings.", 409)
            self.controllers = dict(controllers)
            self.prompt_mode = prompt_mode
            self.seed = seed
            self.interval = float(interval)
            self.controller_instances.clear()
            return self.snapshot()

    def new(self, data: dict) -> dict:
        self.pause()
        with self.lock:
            self.configure(data)
            self.game = TicTacToe()
            self.last_decision = None
            self.error = None
            self.stats = {"ai_decisions": 0, "legal": 0, "illegal": 0, "optimal_legal": 0}
            return self.snapshot()

    def human_move(self, data: dict) -> dict:
        action = data.get("action")
        with self.lock:
            if self.busy or self.playing:
                raise AppError("Pause before a manual move.", 409)
            if self.game.result:
                raise AppError("Game has ended.", 409)
            if self.controllers[self.game.turn] != "human":
                raise AppError(f"{self.game.turn} is controlled by {self.controllers[self.game.turn]}.", 409)
            try:
                record = self.game.play(action, "human")
            except ValueError as exc:
                raise AppError(str(exc)) from exc
            self.last_decision = {"choice": action, "source": "human", "probabilities": {}, "move": record.dict()}
            return self.snapshot()

    def _ai_once_locked(self) -> None:
        if self.game.result:
            raise AppError("Game has ended.", 409)
        mark = self.game.turn
        backend = self.controllers[mark]
        if backend == "human":
            raise AppError(f"{mark} is waiting for a human move.", 409)
        game_before = self.game.snapshot()
        self.busy = True
        try:
            decision = self._controller(mark).choose(game_before)
            probability = decision.probabilities.get(decision.choice)
            record = self.game.play(decision.choice, decision.source, probability)
            self.stats["ai_decisions"] += 1
            if record.legal:
                self.stats["legal"] += 1
                if record.optimal:
                    self.stats["optimal_legal"] += 1
            else:
                self.stats["illegal"] += 1
            self.last_decision = {**decision.dict(), "player": mark, "move": record.dict(), "board_before": game_before["board"]}
        finally:
            self.busy = False

    def ai_step(self) -> dict:
        with self.lock:
            if self.busy or self.playing:
                raise AppError("Another run is active.", 409)
            self.error = None
            try:
                self._ai_once_locked()
            except ProviderError as exc:
                self.error = str(exc)
                raise AppError(str(exc), 502) from exc
            return self.snapshot()

    def play(self) -> dict:
        with self.lock:
            if self.busy or self.playing:
                raise AppError("Another run is active.", 409)
            self.playing = True
            self.error = None
            self.epoch += 1
            epoch = self.epoch
            self.thread = threading.Thread(target=self._loop, args=(epoch,), daemon=True)
            self.thread.start()
            return self.snapshot()

    def _loop(self, epoch: int) -> None:
        consecutive_illegal = 0
        try:
            while True:
                with self.lock:
                    if epoch != self.epoch or not self.playing or self.game.result:
                        break
                    if self.controllers[self.game.turn] == "human":
                        break
                    before_illegal = self.stats["illegal"]
                    self._ai_once_locked()
                    if self.stats["illegal"] > before_illegal:
                        consecutive_illegal += 1
                    else:
                        consecutive_illegal = 0
                    if consecutive_illegal >= 20:
                        self.error = "Paused after 20 consecutive illegal AI choices on the same turn."
                        break
                time.sleep(self.interval)
        except (AppError, ProviderError) as exc:
            with self.lock:
                self.error = str(exc)
        except Exception:
            with self.lock:
                self.error = "Local worker error."
        finally:
            with self.lock:
                if epoch == self.epoch:
                    self.playing = False
                    self.busy = False

    def pause(self) -> dict:
        with self.lock:
            self.playing = False
            self.epoch += 1
            return self.snapshot()
