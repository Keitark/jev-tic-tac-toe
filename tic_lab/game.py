from __future__ import annotations

from dataclasses import dataclass, asdict
from functools import lru_cache

MARKS = ("X", "O")
ALL_CELLS = tuple(range(9))
WIN_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


def cell_id(index: int) -> str:
    row, col = divmod(index, 3)
    return f"cell_{row}_{col}"


def cell_index(action_id: str) -> int:
    parts = action_id.split("_")
    if len(parts) != 3 or parts[0] != "cell":
        raise ValueError("Unknown cell id")
    row, col = int(parts[1]), int(parts[2])
    if row not in range(3) or col not in range(3):
        raise ValueError("Cell out of range")
    return row * 3 + col


def winner_of(board: tuple[str | None, ...]) -> str | None:
    for a, b, c in WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def terminal_result(board: tuple[str | None, ...]) -> str | None:
    winner = winner_of(board)
    if winner:
        return winner
    if all(board):
        return "DRAW"
    return None


def other(mark: str) -> str:
    return "O" if mark == "X" else "X"


@lru_cache(maxsize=None)
def minimax_value(board: tuple[str | None, ...], turn: str) -> int:
    """Value from `turn`'s perspective: +1 win, 0 draw, -1 loss."""
    result = terminal_result(board)
    if result:
        if result == "DRAW":
            return 0
        return 1 if result == turn else -1

    best = -2
    for index in ALL_CELLS:
        if board[index] is not None:
            continue
        next_board = list(board)
        next_board[index] = turn
        next_board_t = tuple(next_board)
        result = terminal_result(next_board_t)
        if result == turn:
            value = 1
        elif result == "DRAW":
            value = 0
        else:
            value = -minimax_value(next_board_t, other(turn))
        best = max(best, value)
        if best == 1:
            break
    return best if best != -2 else 0


def action_values(board: tuple[str | None, ...], turn: str) -> dict[str, int | None]:
    values: dict[str, int | None] = {}
    for index in ALL_CELLS:
        aid = cell_id(index)
        if board[index] is not None:
            values[aid] = None
            continue
        next_board = list(board)
        next_board[index] = turn
        next_board_t = tuple(next_board)
        result = terminal_result(next_board_t)
        if result == turn:
            values[aid] = 1
        elif result == "DRAW":
            values[aid] = 0
        else:
            values[aid] = -minimax_value(next_board_t, other(turn))
    return values


@dataclass
class MoveRecord:
    attempt: int
    player: str
    action: str
    row: int
    col: int
    legal: bool
    source: str
    optimal: bool | None
    minimax_value: int | None
    probability: float | None = None

    def dict(self) -> dict:
        return asdict(self)


class TicTacToe:
    def __init__(self):
        self.board: list[str | None] = [None] * 9
        self.turn = "X"
        self.result: str | None = None
        self.attempts = 0
        self.moves = 0
        self.history: list[MoveRecord] = []

    @property
    def board_tuple(self) -> tuple[str | None, ...]:
        return tuple(self.board)

    def reset(self) -> None:
        self.__init__()

    def all_actions(self) -> list[dict]:
        # Intentionally unfiltered: occupied cells stay in the candidate set.
        return [
            {
                "id": cell_id(i),
                "row": i // 3,
                "col": i % 3,
                "label": f"row {i // 3 + 1}, column {i % 3 + 1}",
            }
            for i in ALL_CELLS
        ]

    def analysis(self) -> dict:
        if self.result:
            return {"action_values": {cell_id(i): None for i in ALL_CELLS}, "optimal_moves": []}
        values = action_values(self.board_tuple, self.turn)
        legal_values = [v for v in values.values() if v is not None]
        best = max(legal_values) if legal_values else None
        optimal = [aid for aid, value in values.items() if value is not None and value == best]
        return {"action_values": values, "optimal_moves": optimal, "position_value": best}

    def play(self, action_id: str, source: str = "human", probability: float | None = None) -> MoveRecord:
        if self.result:
            raise ValueError("Game has already ended")

        index = cell_index(action_id)
        row, col = divmod(index, 3)
        current = self.turn
        before = self.analysis()
        legal = self.board[index] is None
        self.attempts += 1

        if legal:
            value = before["action_values"][action_id]
            optimal = action_id in before["optimal_moves"]
            self.board[index] = current
            self.moves += 1
            self.result = terminal_result(self.board_tuple)
            if self.result is None:
                self.turn = other(current)
        else:
            value = None
            optimal = None

        record = MoveRecord(
            attempt=self.attempts,
            player=current,
            action=action_id,
            row=row,
            col=col,
            legal=legal,
            source=source,
            optimal=optimal,
            minimax_value=value,
            probability=probability,
        )
        self.history.append(record)
        return record

    def snapshot(self) -> dict:
        analysis = self.analysis()
        return {
            "board": [cell or "." for cell in self.board],
            "turn": self.turn,
            "result": self.result,
            "attempts": self.attempts,
            "moves": self.moves,
            "actions": self.all_actions(),
            "analysis": analysis,
            "history": [item.dict() for item in self.history[-40:]],
        }
