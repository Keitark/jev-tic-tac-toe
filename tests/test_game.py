import unittest

from tic_lab.controller import build_payload, model_state
from tic_lab.game import TicTacToe


class TicTacToeTests(unittest.TestCase):
    def test_candidates_are_always_nine(self):
        game = TicTacToe()
        game.play("cell_0_0")
        self.assertEqual(len(game.all_actions()), 9)
        self.assertIn("cell_0_0", {a["id"] for a in game.all_actions()})

    def test_illegal_move_does_not_change_turn_or_board(self):
        game = TicTacToe()
        game.play("cell_1_1")
        self.assertEqual(game.turn, "O")
        before = game.board[:]
        record = game.play("cell_1_1", "test")
        self.assertFalse(record.legal)
        self.assertEqual(game.turn, "O")
        self.assertEqual(game.board, before)

    def test_minimax_finds_immediate_win(self):
        game = TicTacToe()
        for move in ["cell_0_0", "cell_1_0", "cell_0_1", "cell_1_1"]:
            game.play(move)
        analysis = game.analysis()
        self.assertEqual(analysis["action_values"]["cell_0_2"], 1)
        self.assertIn("cell_0_2", analysis["optimal_moves"])

    def test_payload_has_all_nine_even_when_occupied(self):
        game = TicTacToe()
        game.play("cell_0_0")
        payload = build_payload(game.snapshot(), "jev", "minimal")
        criteria = payload["questions"]["action"]["criteria"]
        self.assertEqual(len(criteria), 9)
        self.assertIn("cell_0_0", criteria)

    def test_minimal_prompt_does_not_spell_out_occupied_rule(self):
        game = TicTacToe()
        prompt = model_state(game.snapshot(), "minimal").lower()
        self.assertNotIn("occupied", prompt)
        self.assertNotIn("cannot be played", prompt)


if __name__ == "__main__":
    unittest.main()
