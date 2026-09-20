# Jev Tic-Tac-Toe Benchmark Results

## Environment

- 実行日: 2026-09-21 (JST)
- benchmark code commit: `aafbb8985037103fa9689f50ffd48d073fa8e65d`
- Python: 3.11.0
- Jev model: `jev-latest`
- Prompt mode: `minimal`
- Games: 1000 per benchmark
- Seed: 17
- Strict illegal policy: `forfeit`
- Legal-random illegal policy: `retry` (20回連続illegalでforfeit)
- Jev API key: 設定済み（値は記録しない）

The benchmark keeps all nine cell candidates for every model decision. During
the run, Jev returned some two-decimal probability distributions summing to
`0.99`; the provider adapter now normalizes only this small rounding drift
while continuing to reject missing cells, non-finite values, out-of-range
values, and larger distribution errors.

## Test status

- `python -m unittest discover -s tests -v`: **10 tests passed**
- API-free 100-game smoke test (`legal-random` vs `legal-random`): completed
- Jev 10-game smoke test: completed, 9 W / 0 D / 1 L, illegal rate 0.0500

## Jev vs unfiltered Random

Both sides choose from all nine cells. An occupied choice forfeits the game.
This evaluates rule understanding and strategy together.

| Metric | Result |
|---|---:|
| Games | 1000 |
| Wins | 954 |
| Draws | 4 |
| Losses | 42 |
| Score rate | 0.9560 |
| Decisive win rate | 0.9578 |
| 95% Wilson CI | 0.9435–0.9687 |
| One-sided exact p-value | 3.90925e-226 |
| Two-sided exact p-value | 7.81850e-226 |
| Jev illegal rate | 0.0070 |
| Jev optimal/legal rate | 0.8138 |

### By Jev mark

| Jev mark | Games | Wins | Draws | Losses |
|---|---:|---:|---:|---:|
| X | 500 | 487 | 3 | 10 |
| O | 500 | 467 | 1 | 32 |

## Jev vs legal Random

The legal-random opponent chooses only empty cells. Jev still receives all
nine candidates; illegal Jev choices are recorded and retried on the same
turn, with a 20-consecutive-illegal forfeit limit.

| Metric | Result |
|---|---:|
| Games | 1000 |
| Wins | 551 |
| Draws | 159 |
| Losses | 290 |
| Score rate | 0.6305 |
| Decisive win rate | 0.6552 |
| 95% Wilson CI | 0.6224–0.6865 |
| One-sided exact p-value | 7.93541e-20 |
| Two-sided exact p-value | 1.58708e-19 |
| Jev illegal rate | 0.0108 |
| Jev optimal/legal rate | 0.7478 |

### By Jev mark

| Jev mark | Games | Wins | Draws | Losses |
|---|---:|---:|---:|---:|
| X | 500 | 338 | 69 | 93 |
| O | 500 | 213 | 90 | 197 |

## Interpretation

- The strict Random comparison evaluates rule understanding and strategy because both players can select occupied cells.
- The legal-random comparison is more strategy-oriented because the opponent is restricted to empty cells while Jev’s illegal choices remain observable.
- Effect size, X/O-specific results, illegal rate, and optimal/legal rate should be considered alongside p-values.
- A high illegal rate would make win rate alone insufficient for evaluating the model.
- These results show performance under this benchmark configuration; they do not by themselves prove general intelligence.

## Raw data

- [Strict JSON](results/jev-vs-random-strict.json)
- [Strict CSV](results/jev-vs-random-strict.csv)
- [Legal-random JSON](results/jev-vs-legal-random.json)
- [Legal-random CSV](results/jev-vs-legal-random.csv)
