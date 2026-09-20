# Jev × Tic-Tac-Toe — 3×3 Spatial Decision Benchmark

Jevに**3×3の○×（Tic-Tac-Toe）盤面を2次元状態として渡し、毎回9マス全部から1マスを選ばせる**小さな実験環境です。

重要なのは、**埋まっているマスを候補から除外しない**ことです。Jevが標準的な○×のルールを理解しているなら、自分でoccupied cellを避けるはずです。これにより、単なる「合法手の中からの戦略選択」ではなく、次の2つを分離して観測できます。

- **Rule understanding**: 既に埋まっているマスを選ばないか（illegal move rate）
- **Strategy**: 合法手の中でminimax最善手を選べるか（optimal / legal rate）

## 起動

```bash
git clone https://github.com/Keitark/jev-tic-tac-toe.git
cd jev-tic-tac-toe
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # Windowsでは手動コピーでもOK
python web_app.py --open
```

ブラウザで `http://127.0.0.1:8002` を開きます。

## Jev設定

`.env` にキーを設定します。

```dotenv
JEV_API_KEY=your-key
# TYPESAFE_API_KEY も別名として使用可能
OPENROUTER_API_KEY=your-key
JEV_MODEL=jev-latest
OPENROUTER_MODEL=typesafe/jev-1.13
MODEL_TIMEOUT=30
```

Jevは `POST https://api.typesafe.ai/v1/systemone`、OpenRouterは `POST https://openrouter.ai/api/alpha/decisions` を使います。Rogue版 `jev-rogue` と同じ `state/questions` 形式です。

## 9候補を常に固定

Jevへのchoice criteriaは常に以下の9個です。

```text
cell_0_0  cell_0_1  cell_0_2
cell_1_0  cell_1_1  cell_1_2
cell_2_0  cell_2_1  cell_2_2
```

例えば盤面が

```text
X . O
. X .
O . .
```

でも `(0,0)`, `(0,2)`, `(1,1)`, `(2,0)` を候補から消しません。Jevがそこを選べば **illegal** と記録し、盤面と手番は進めません。

## Prompt mode

デフォルトの **Minimal** は、Jevに次だけを伝えます。

- standard 3×3 tic-tac-toe
- 自分がXかOか
- 座標系
- 現在の盤面

「occupied cellは選べない」とは明示しません。これがルール理解を見るモードです。

比較用に **Explicit** もあり、こちらは標準ルールを文章で明示します。

## Minimax oracle

3×3 Tic-Tac-Toeは全探索できるため、各合法手を完全に評価できます。

- `+1`: その手から最善プレイで勝てる
- `0`: 引き分け
- `-1`: 負ける
- `occupied`: そもそも違法

UIではJevの9マス確率、選択マス、illegal判定、minimax最善手、履歴を同時に表示します。

## モード

X/Oそれぞれを次から選べます。

- Human
- Jev
- OpenRouter Jev
- Random

Human vs Jev、Jev vs Random、Jev self-playなどを同じ画面で試せます。

## テスト

```bash
python -m unittest discover -s tests -v
```

テストでは「occupiedを含めて常に9候補」「illegalで手番が進まない」「minimax即勝ち検出」「Minimal promptがoccupied ruleを明示しない」を確認しています。

## 実験で見る値

- **Illegal rate** = illegal AI choices / all AI decisions
- **Optimal / legal** = minimax optimal legal choices / legal AI choices
- 各9マスに対するJev probability
- 勝敗
- 同一盤面を回転・反転させた symmetry consistency（今後の拡張候補）

このリポジトリは、TetrisやRogueより小さく、全状態を完全解析できる「Jevの2D判断の最小ベンチマーク」として使うことを狙っています。
