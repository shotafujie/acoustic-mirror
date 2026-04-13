# Acoustic Speech Monitor

難聴者が自分の発話品質をリアルタイムに把握するためのシステム。マイク入力から了解度（SRMR）を計測し、室内音響をプロファイリングし、了解度が低下した場合はその原因を特定してフィードバックを返す。

![Dashboard Screenshot](docs/images/dashboard.png)

ダッシュボードは4つの要素で構成される:

- **了解度リング（中央）** — SRMR / 目標値の比率を円弧で表示。1.0以上が緑、0.5〜1.0が黄、0.5未満が赤
- **室内プロファイル** — RT60（残響時間）、ノイズフロア、DRR（直接音対反射音比）、推定部屋タイプを表示
- **原因分析** — 了解度が目標を下回った場合、支配的な原因（残響・騒音・調音・距離）と対処法を表示
- **触覚パターンプレビュー** — Pixel Watchに送信される振動パターンを可視化（Phase 1.5で実機連携予定）

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 起動

```bash
python -m acoustic_mirror
```

ブラウザで http://localhost:8080 を開くとダッシュボードが表示される。

### オプション

```
--device ID        入力デバイスID
--sample-rate HZ   サンプルレート（デフォルト: 16000）
--ws-port PORT     WebSocketポート（デフォルト: 8765）
--http-port PORT   HTTPポート（デフォルト: 8080）
--list-devices     利用可能な入力デバイスを表示して終了
```

## テスト

```bash
pytest -v
```

## アーキテクチャ

```
Microphone (16kHz) → RingBuffer → [500ms chunk]
  → SpeechDetector (energy-based VAD)
    → SRMR (gammatone filterbank → Hilbert envelope → modulation spectrum)
    → RoomProfiler (blind RT60 / noise floor / DRR estimation)
      → CauseSeparator (rule-based diagnosis)
        → WebSocket → Browser Dashboard
```

### 技術スタック

| レイヤー | 技術 |
|---------|------|
| マイク入力 | sounddevice |
| 信号処理 | NumPy + SciPy |
| WebSocket | websockets (asyncio) |
| ダッシュボード | http.server + vanilla JS |

## ロードマップ

- **Phase 1** (現在): Mac上の音響解析 + ブラウザダッシュボード
- **Phase 1.5**: Android中継アプリ + Pixel Watch触覚フィードバック
- **Phase 2**: LLM-jp-Moshi統合、発話内容の言語的適切さ判定
- **Phase 3**: モバイルアプリ化、Mac依存除去
