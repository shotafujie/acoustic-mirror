# 独立検証レポート: ストリーミングRT60のローリング窓化（ADR-0005 / issue #13）

## 検証対象

- リポジトリ: `/Users/fujiemon/dev/speech/analyze/acoustic-mirror`
- ブランチ: `fix/streaming-rt60-rolling-window`
- 最新コミット: **`74740da`**（"Trigger streaming RT60 on the decay, not on the VAD transition"）
- 検証時点の `git status --short`: **出力なし（クリーン）**
- 検証日: 2026-09-22
- 検証者: 独立検証エージェント（実装コンテキストなし。書き込みはこのレポートファイルのみ）

### 仕様書の所在

本リポジトリに `docs/items/` は存在せず、spec.md / test-design.md の工程は踏まれていない。
したがって**仕様書にあたるのは `docs/adr/ADR-0005-streaming-rt60-rolling-window.md`** であり、
その「決定 / 設計」「検証方針 V1〜V7」「反証条件」「既知の限界」を約束のリストに分解して判定した。
背景として issue #13、ADR-0003、ADR-0004 を参照した。

### 変更範囲

```
$ git show --stat 74740da
 benchmarks/streaming-rt60/README.md                |  26 ++++
 benchmarks/streaming-rt60/run.py                   |  61 ++++++++
 docs/adr/ADR-0005-streaming-rt60-rolling-window.md |   4 +-
 src/acoustic_mirror/analysis/rolling_rt60.py       |  86 +++++++++++
 src/acoustic_mirror/analysis/room_profiler.py      |  32 +++--
 src/acoustic_mirror/dashboard/index.html           |   6 +-
 src/acoustic_mirror/main.py                        |  62 +++-----
 tests/test_dashboard.py                            |   9 ++
 tests/test_main.py                                 | 126 +++++++---------
 tests/test_rolling_rt60.py                         | 160 +++++++++++++++++++++
 tests/test_room_profiler.py                        |  35 +++--
 11 files changed, 453 insertions(+), 154 deletions(-)
```

## 判定サマリ

| 判定 | 件数 |
|------|------|
| PASS | **15** |
| FAIL | **7** |
| BLOCKED | **1** |
| 約束の総数 | **23** |

FAIL 7件の内訳は2種類ある。
- **「テストは存在するが、守ると宣言した振る舞いを壊してもそのテストが落ちない」2件**: M1（R²ゲート）と V4（重複除外。`window_start` の算術も同じく無防備）。
- **「テストが1つも存在しない」5件**: V3b（ダッシュボードJS）/ D1b（集約定数）/ D1c（import構造）/ D2b（旧経路の削除）/ D4b（信頼度の中央値）。

**実装が間違っているという指摘ではない。** 実測では ADR が主張する値がすべて再現した（後述「ADRの数値の切り分け」）。
指摘は **「再現したことを固定している番人が、いくつかの約束には付いていない」** という一点に尽きる。

## テストスイート全体の実行結果

```
$ cd /Users/fujiemon/dev/speech/analyze/acoustic-mirror && .venv/bin/python -m pytest -v
============================= test session starts ==============================
platform darwin -- Python 3.13.12, pytest-9.0.3, pluggy-1.6.0 -- /Users/fujiemon/dev/speech/analyze/acoustic-mirror/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/fujiemon/dev/speech/analyze/acoustic-mirror
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function

（中略。PASSED 312件、FAILED / ERROR / SKIPPED いずれも0件）

============================= 312 passed in 31.86s =============================
```

**終了コード: `0`**

### 新規・変更されたテストの個別の行（`-v` 出力からの引用）

```
tests/test_dashboard.py::TestDashboardHTML::test_rt60_is_not_drawn_without_confidence PASSED [ 41%]
tests/test_main.py::TestAnalysisPipeline::test_rt60_comes_from_the_rolling_window PASSED [ 57%]
tests/test_main.py::TestAnalysisPipeline::test_rt60_does_not_depend_on_where_the_utterance_ends_in_a_chunk PASSED [ 57%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.3-0.7-1] PASSED [ 58%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.3-0.7-2] PASSED [ 59%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.3-0.7-3] PASSED [ 59%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.3-1.2-1] PASSED [ 59%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.3-1.2-2] PASSED [ 60%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.3-1.2-3] PASSED [ 60%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.4-0.7-1] PASSED [ 60%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.4-0.7-2] PASSED [ 61%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.4-0.7-3] PASSED [ 61%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.4-1.2-1] PASSED [ 61%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.4-1.2-2] PASSED [ 62%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.4-1.2-3] PASSED [ 62%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.6-0.7-1] PASSED [ 62%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.6-0.7-2] PASSED [ 63%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.6-0.7-3] PASSED [ 63%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.6-1.2-1] PASSED [ 63%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.6-1.2-2] PASSED [ 64%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.6-1.2-3] PASSED [ 64%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.8-0.7-1] PASSED [ 64%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.8-0.7-2] PASSED [ 65%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.8-0.7-3] PASSED [ 65%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.8-1.2-1] PASSED [ 65%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.8-1.2-2] PASSED [ 66%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[0.8-1.2-3] PASSED [ 66%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[1.0-0.7-1] PASSED [ 66%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[1.0-0.7-2] PASSED [ 66%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[1.0-0.7-3] PASSED [ 67%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[1.0-1.2-1] PASSED [ 67%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[1.0-1.2-2] PASSED [ 67%]
tests/test_rolling_rt60.py::TestAccuracy::test_reports_within_15_percent[1.0-1.2-3] PASSED [ 68%]
tests/test_rolling_rt60.py::TestTheCaseTheOldTriggerCouldNotSee::test_reverberant_room_with_short_pauses_is_measurable[0.8] PASSED [ 68%]
tests/test_rolling_rt60.py::TestTheCaseTheOldTriggerCouldNotSee::test_reverberant_room_with_short_pauses_is_measurable[1.0] PASSED [ 68%]
tests/test_rolling_rt60.py::TestRefusalInsteadOfAGuess::test_below_the_event_floor_nothing_is_reported PASSED [ 69%]
tests/test_rolling_rt60.py::TestRefusalInsteadOfAGuess::test_confidence_stays_zero_until_the_floor_is_reached PASSED [ 69%]
tests/test_rolling_rt60.py::TestRefusalInsteadOfAGuess::test_continuous_speech_produces_no_room_estimate PASSED [ 69%]
tests/test_rolling_rt60.py::TestEachDecayCountsOnce::test_an_event_seen_in_six_windows_is_adopted_once PASSED [ 70%]
tests/test_rolling_rt60.py::TestEachDecayCountsOnce::test_an_event_still_running_at_the_window_edge_waits PASSED [ 70%]
tests/test_rolling_rt60.py::TestTheConfidenceGateSurvivedTheMove::test_noise_does_not_enter_the_pool PASSED [ 70%]
tests/test_rolling_rt60.py::TestTheConfidenceGateSurvivedTheMove::test_a_rejected_event_is_counted_not_silently_dropped PASSED [ 71%]
tests/test_room_profiler.py::TestRoomProfiler::test_reports_what_the_estimator_sets PASSED [ 85%]
tests/test_room_profiler.py::TestRoomProfiler::test_an_unmeasured_room_reports_zero_confidence PASSED [ 86%]
```

## テストが約束を固定しているかの検査（変異による確認）

「312件通った」は「約束が守られている」と同義ではない。
**実装側の振る舞いを1箇所だけ壊し、テストスイートが落ちるかを観測した。**
落ちなければ、その約束には番人が付いていない。

実装ファイルは**一切変更していない**。pytest プラグイン（スクラッチ領域）でモジュール変数・メソッドを実行時に差し替えている。

| # | 壊した振る舞い | 壊し方 | 結果 |
|---|---|---|---|
| 1 | R²信頼度ゲート（ADR-0003） | `rolling_rt60._RT60_CONFIDENCE_MIN = -1.0` | **312 passed**（1件も落ちない） |
| 2 | 窓末尾イベントの不採用（V5） | `end >= len(window)` の判定を削除 | 3 failed, 309 passed |
| 3 | 重複採用の除外（V4） | 毎 `push` で `self._seen.clear()` | **312 passed**（1件も落ちない） |
| 4 | `window_start` の算術（V4の前提） | `push` に常に `window_start=0` を渡す | **312 passed**（1件も落ちない） |
| 5 | 採用件数の下限（V3） | `MIN_RT60_EVENTS = 1` | 1 failed, 311 passed |
| 6 | 集約の定数（pool=10 / p70） | `_POOL_SIZE = 5`, `_PERCENTILE = 50` | **312 passed**（1件も落ちない） |

変異2・5は番人が機能している。**変異1・3・4・6は、ADRが明示的に約束した振る舞いを完全に無効化しても、テストスイートが黙って通る。**

### 変異3が通る理由（`TestEachDecayCountsOnce` の構造的な空振り）

`test_an_event_seen_in_six_windows_is_adopted_once` は「1回流したあとの `event_count`」を `before` に取り、
同じ窓を再度流して `event_count == before` を主張する。

プールは `deque(maxlen=10)` である。重複除外が最初から完全に壊れている場合、
1回目の走査で `event_count` は**上限の10に飽和する**ため、2回目を流しても10のまま変わらない。
実測（`RollingRT60Estimator` を直接駆動、`reverberant_utterances(0.6, gap=1.2, seed=1)`）:

```
重複除外が正常:     1回目 event_count = 5,  seen keys = 5
重複除外を無効化:   1回目 event_count = 10, 再push後 = 10  -> assertion (equal) holds? True
```

つまりこのテストは、**除外が効いているときにだけ意味を持ち、除外が壊れたときには飽和に隠れて通る。**

### 変異1が通る理由（`TestTheConfidenceGateSurvivedTheMove` の2テストがゲートに到達していない）

クラスのdocstringは「ADR-0003 が `RoomProfiler.update_rt60` に置いたR²ゲートが、移動先でも効いていることを固定する」と宣言している。実測:

- `test_noise_does_not_enter_the_pool`: 白色雑音を `push` した時点で `find_decay_events` が返すイベント数は **0件**。
  `event_count == 0` はゲートの結果ではなく「そもそもイベントが検出されなかった」結果である。
  同条件での `rejected_count` も **0**（＝ゲートは一度も呼ばれていない）。
- `test_a_rejected_event_is_counted_not_silently_dropped`: `rejected_count > 0` は成立するが、
  棄却の内訳を実測すると **`is_valid == False` が1件、R²ゲートによる棄却が0件、採用0件**。
  棄却しているのは `estimate_rt60_from_decay` のレンジ判定であり、**R²ゲートではない**。

したがって、クラス名が主張する「ゲートが移動に耐えた」ことを確かめているテストは**存在しない**。

## 約束ごとの判定

凡例: 「根拠」は実行したテストの名前と結果。テストが無い場合はその事実を書く。

### 決定・設計（ADR-0005「決定」節）

| ID | 約束 | 判定 | 根拠 |
|---|---|---|---|
| D1a | 採用イベントが3件未満の間は `rt60` が `None`（1件を部屋として出さない） | **PASS** | `test_below_the_event_floor_nothing_is_reported` PASSED / `test_confidence_stays_zero_until_the_floor_is_reached` PASSED。変異5（下限を1に）で `test_below_the_event_floor_nothing_is_reported` が `assert 0.42 is None` で失敗＝番人が機能 |
| D1b | 集約は プール上限10・70パーセンタイル | **FAIL** | 定数を固定するテストが存在しない。変異6（pool=5 / p50 ＝ADRが不採用とした現行集約）で **312 passed**。ADR自身の表でも p50/pool5 の最悪誤差は11.5%で、テストの許容幅±15%を通過する |
| D1c | `find_decay_events` はバッチから **import** し再実装しない | **FAIL** | 「同じ規則が2箇所にあると片方だけ直る」という理由つきで決定されているが、同一性を固定するテスト（例: `rolling_rt60.find_decay_events is batch_diagnostic.find_decay_events`）は存在しない。import文の存在自体はソースで確認した |
| D2a | `srmr_window` が渡されたとき推定器へ渡し、実パイプライン経路でRT60が出る | **PASS** | `test_rt60_comes_from_the_rolling_window` PASSED（`pipeline.process()` を実駆動し真値0.6を±15%以内で報告）/ `test_rt60_does_not_depend_on_where_the_utterance_ends_in_a_chunk` PASSED |
| D2b | 旧経路（`_prev_chunk` による遷移検出・`_extract_decay_segment`・`_find_speech_offset`）を削除する | **FAIL** | 削除自体を固定するテストが存在しない。`grep -rn` で `src/` に定義・参照が残っていないことは確認した（残存はテスト/ベンチの**docstring内の言及**のみ） |
| D3 | `RoomProfiler` はプールを持たず `set_rt60(value, confidence)` の結果を運ぶだけになる | **PASS** | `test_reports_what_the_estimator_sets` PASSED / `test_an_unmeasured_room_reports_zero_confidence` PASSED |
| D4a | 3件に満たない間の信頼度は 0 | **PASS** | `test_confidence_stays_zero_until_the_floor_is_reached` PASSED |
| D4b | 3件以降の信頼度は「プール内のR²の**中央値**」 | **FAIL** | 中央値であることを固定するテストが存在しない。既存テストは `confidence > 0.0` / `> 0.5` としか主張せず、R²が全件同値の合成入力しか与えていない |
| D6 | `SpeechDetector` / SRMR再計算ゲート / `_is_isolated_onset` は変更しない | **PASS** | `git show --stat 74740da` に `speech_detector.py` / `srmr.py` / `cause_separator.py` は含まれない。`main.py` の差分でも `_is_isolated_onset` とSRMRゲートは文脈行のみ。既存の番人 `test_isolated_onset_gate_allows_onset_after_genuine_silence` PASSED / `test_isolated_onset_gate_blocks_onset_after_trailing_speech` PASSED を含む312件が全通過 |

### 検証方針 V1〜V7

| ID | 約束 | 判定 | 根拠 |
|---|---|---|---|
| V1 | 10条件（真値5 × ポーズ2）すべてで報告し誤差±15%以内。シード1/2/3で固定 | **PASS** | `TestAccuracy::test_reports_within_15_percent[...]` **30件すべて PASSED**（上の引用参照）。`assert est.rt60 is not None` と `abs(est.rt60 - true)/true <= 0.15` の両方を持つ |
| V2 | 現行が遷移0回になる条件（真値0.8以上・ポーズ0.7s）で報告できる | **PASS** | `test_reverberant_room_with_short_pauses_is_measurable[0.8]` PASSED / `[1.0]` PASSED。テスト自身が `_vad_transitions(clip) == 0` を先に主張しており、**旧トリガが盲目であるという前提ごと固定している**（前提が崩れたらテストが落ちる） |
| V3a | 採用3件未満の間は `rt60_confidence == 0` | **PASS** | `test_below_the_event_floor_nothing_is_reported` PASSED / `test_an_unmeasured_room_reports_zero_confidence` PASSED（`RoomProfile.rt60 == _DEFAULT_RT60` かつ `rt60_confidence == 0.0`） |
| V3b | ダッシュボードが信頼度0のとき値を描かない | **FAIL** | `test_rt60_is_not_drawn_without_confidence` PASSED だが、これは `index.html` の**ソース文字列一致**であり、JavaScriptを実行するテストは存在しない。テスト自身のdocstringが「pins that the guard is present, not that it works」と明記している。ADR-0004 の第3回検証が B4 / B6 を同じ理由で FAIL としたのと同じ扱いとする |
| V4 | 同じ減衰イベントが二重に採用されない（窓は0.5秒ずつ進むので最大6窓に現れる） | **FAIL** | `test_an_event_seen_in_six_windows_is_adopted_once` PASSED だが、**変異3（重複除外の完全無効化）でも312件全通過**。`deque(maxlen=10)` の飽和に隠れて、壊れたときに落ちない。さらに変異4（`window_start` を常に0）でも312件全通過で、**重複除外の鍵となる絶対位置の計算にも番人が無い** |
| V5 | 窓末尾で途切れているイベントを採用しない | **PASS** | `test_an_event_still_running_at_the_window_edge_waits` PASSED。空振りでないことを実測で確認した（当該1.2秒窓に対し `find_decay_events` は `(16480, 19200)` を1件返し、`len(window) == 19200` ＝まさに末尾到達で弾かれている。同じクリップを2秒分与えると同イベントは `(16480, 26560)` に伸びる）。変異2で3件失敗＝番人が機能 |
| V6 | 連続発話では値を出さない（偽の部屋を作らない） | **PASS** | `test_continuous_speech_produces_no_room_estimate` PASSED。実測でも採用0件・棄却0件・`rt60 is None` |
| V7 | 1チャンクあたりの処理時間が500msチャンクに対して十分小さい | **PASS** | `benchmarks/streaming-rt60/run.py` を実行。最悪 **1.86ms = 500msの0.37%**（README記録は1.68ms / 0.34%、同オーダーで再現）。ただし閾値の assert が無く回帰の番人にはならない（所見O5） |

### ADR-0003 から移された約束（経路削除で消えていないか）

| ID | 約束 | 判定 | 根拠 |
|---|---|---|---|
| M1 | R² ≥ `_RT60_CONFIDENCE_MIN`(0.5) のゲートが `RoomProfiler.update_rt60` から推定器へ移り、**同じ強さで**効いている | **FAIL** | `TestTheConfidenceGateSurvivedTheMove` の2件はともに PASSED だが、**どちらもゲートに到達していない**（白色雑音はイベント0件、もう一方の棄却1件は `is_valid == False` によるもので R²ゲートによる棄却は0件）。変異1（ゲート無効化）で **312 passed**。旧テスト `test_low_confidence_estimate_does_not_update_rt60` が持っていた「ゲートを通らない推定は `rt60` を動かさない」という主張は、**移動先で弱まっている** |
| M2 | 100ms未満の減衰は使わない（旧 `_extract_decay_segment` の長さ下限） | **PASS** | `find_decay_events` 側の `_MIN_EVENT_SECONDS = 0.1` が同じ床を持ち、既存の番人が残っている。`tests/test_batch_diagnostic.py::TestDecayEventGating::test_events_are_never_shorter_than_100ms` PASSED / `test_sub_100ms_decay_is_not_an_event` PASSED。**import している以上、この2件は今やストリーミング経路の番人でもある** |
| M3 | 発話終端がチャンク内のどこに落ちても推定が到達可能（旧 reachability guard） | **PASS** | `test_rt60_does_not_depend_on_where_the_utterance_ends_in_a_chunk` PASSED。**旧テストより強い**（旧: 16位相のうち5位相以上で推定が1件でも入ればよい / 新: 8位相**すべて**で信頼度>0かつ真値±15%以内を要求） |

### 反証条件

| ID | 反証条件 | 判定 | 根拠 |
|---|---|---|---|
| F1 | 10条件のうち1つでも報告できない、または誤差が±15%超 | **PASS**（反証されず） | V1 の30件全通過 |
| F2 | 連続発話で偽のRT60が出る | **PASS**（反証されず） | V6 |
| F3 | 1チャンクあたりの処理時間が**現行比で10倍**を超える | **BLOCKED** | 比較が実施されていない。`benchmarks/streaming-rt60/README.md` 自身が「現行の `_extract_decay_segment` は遷移が起きたときしか走らないため比較の分母が定義できない」と述べ、基準を「実時間予算に対する割合」へ差し替えている。**差し替えはベンチのREADMEにだけ書かれており、ADR本文の反証条件は元の文言のまま**（所見O6） |

## ADRの数値の切り分け（テストで再現されるのか、文書にしかない記録か）

依頼の論点2。ADR-0005 に出てくる表を、「テストが再現する」「ベンチが再現する」「文書にしかない」に分けた。
**検証者自身が独立に再測定した結果も併記する。**

| ADRの表 | テスト/ベンチによる再現 | 検証者の再測定 |
|---|---|---|
| コンテキストの表・**「真値0.8以上／ポーズ0.7sで遷移0回」** | **あり**。`test_reverberant_room_with_short_pauses_is_measurable` が `_vad_transitions(clip) == 0` を主張 | — |
| コンテキストの表・遷移回数4/1/5/4/1、採用件数、表示値0.949・1.060、信頼度1.00/0.99 | **なし（文書のみ）**。旧実装は削除済みで、これらを再現するコードはリポジトリに残っていない | 再現不能（旧経路が存在しない） |
| 論点2「窓長 3s / 5s / 7s の比較表」（報告数・最悪誤差・1チャンクあたり） | **なし（文書のみ）** | 未実施 |
| 論点3「pool × パーセンタイルの比較表」（最悪誤差 11.5 / 10.3 / 8.5 / 11.0 / 8.5%） | **なし（文書のみ）**。変異6のとおり、どの組み合わせでもテストは通る | 未実施 |
| コミットメッセージの「after」列（10条件の実測値） | **部分的**。テストは±15%以内しか主張せず、個々の値は固定していない | **10条件すべてを `pipeline.process()` 実経路で再測定し、一致を確認した**（下表） |
| 既知の限界「speech_utterances で 0.202、3件採用/10件棄却」 | **なし（ストリーミング側にテストなし。ADR-0004 の batch 側テストのみ）** | **既定引数で完全に再現**（採用3 / 棄却10 / rt60 = 0.202） |
| 既知の限界「真値1.0・ポーズ0.7sで −8.5%」 | 誤差が±15%以内であることのみテストが固定 | **−8.5% を再現** |

### 検証者による実経路の再測定（`AnalysisPipeline.process()` を500msチャンクで駆動、シード1）

```
gap  true  reported  err%    conf
0.7  0.3   0.296     -1.5%   1.00
0.7  0.4   0.405     +1.2%   1.00
0.7  0.6   0.613     +2.2%   1.00
0.7  0.8   0.793     -0.9%   1.00
0.7  1.0   0.915     -8.5%   1.00
1.2  0.3   0.293     -2.2%   1.00
1.2  0.4   0.409     +2.2%   1.00
1.2  0.6   0.616     +2.7%   1.00
1.2  0.8   0.812     +1.5%   1.00
1.2  1.0   1.030     +3.0%   1.00
```

コミットメッセージが挙げた7行の「after」値（0.296 / 0.613 / 0.793 / 0.915 / 0.293 / 0.616 / 1.030）と**すべて一致**する。
**issue #13 の症状は、実経路で解消している。**
- 前半（残響が強いほど測れない）: 真値0.8/1.0・ポーズ0.7s が `0.200 / 信頼度0.00` から `0.793 / 0.915` に変わった。
- 後半（1件の推定が信頼度1.00で出る）: 3件未満は `rt60 = None` → `rt60_confidence = 0.0` となり、値は出ない。

## トレーサビリティ検査

```
$ ~/dev/.claude/hooks/trace-check.sh
/Users/fujiemon/dev/.claude/hooks/trace-check.sh: line 47: ITEMS_DIR: unbound variable
```

引数なしでは実行できない（`ITEMS_DIR` 未設定でスクリプトが停止する）。`docs/adr` を与えた場合:

```
$ ~/dev/.claude/hooks/trace-check.sh docs/adr
=== traceability check ===
スコープ: docs/adr （このアイテムに属するIDのみ検査）

[adr] spec.md がありません — 検査をスキップしました

[テストコード] 検出したテストケースID: 0件 (探索起点: .)

孤児: 0件 — 仕様・テスト設計・テストコード・検証はすべて対応が取れています。
```

**孤児: 0件。ただしこれは「対応が取れている」ことを意味しない。**
本リポジトリは `docs/items/<アイテム>/spec.md` を持たず、`SPEC-NNN` / `TC-NNN-M` のID記法も使っていないため、
検査は「検査対象が0件」として終了しているだけである。ADR-0004 の検証でも同じ理由で BLOCKED とされている。

## 所見（判定は動かさないが記録すべきこと）

### O1. `deque(maxlen=10)` の飽和が、V4のテストを構造的に無効化している

上の「変異3が通る理由」のとおり。テストを直す方向は2つある（どちらを採るかは実装者の判断であり、検証者は指定しない）。
- 採用件数ではなく **`len(est._seen)`（一意キーの数）** を主張する
- プール飽和の影響を受けない短いクリップ、または「同一イベントを含む2窓を明示的に push して採用が1回であること」を直接主張する

### O2. 重複除外は「鍵の完全一致」であり、許容幅を持たない

鍵は `(window_start + start) // 160`（10ms単位）で、`find_decay_events` のフレームも10msなので、
**イベント開始位置が窓ごとに1フレームでもずれれば別イベントとして採用される**。
`find_decay_events` は窓ごとに `np.percentile` でノイズフロアと発話レベルを取り直すため、原点判定が窓によってずれる可能性は構造的に存在する。
実測した条件（`reverberant_utterances(0.6, gap=1.2, seed=1)`）では5イベントに対し一意キーも5でずれは起きていないが、**これを固定しているテストは無い**。

### O3. 本番ループの `_samples_seen` は、チャンクが連続して届くことを仮定している

`main.py` の `_run` は `await asyncio.sleep(0.5)` のポーリングで `buf.get_window()`（直近8000サンプル）を読む。
リングバッファは書き込み位置を返さないので、**ループの周期が実時間からずれると、同じサンプルを二度読む／読み飛ばすことがあり得る**。
一方 `_samples_seen += len(chunk)` は「毎回ちょうど1チャンク分の新規サンプルが来た」と数える。
コード中のコメントは「a gap would at worst let one event through twice」と書いているが、
ずれが累積した場合に `window_start` が実位置から乖離し続ける点までは書かれていない。
**この経路（`_run` のループ）を駆動するテストは存在しない。** 変異4のとおり `window_start` 計算そのものにも番人が無い。

### O4. 下限のテストが `_accept` を直接叩いており、実経路（`push`）を通っていない

`test_below_the_event_floor_nothing_is_reported` と `test_confidence_stays_zero_until_the_floor_is_reached` は
`est._accept(0.42)` を呼ぶ。プライベートメソッドの直接呼び出しであり、`_accept` の既定引数 `r_squared: float = 1.0` は
**テストからしか使われない**（`push` は常に2引数で呼ぶ）。下限の振る舞い自体は変異5で番人が確認できたので判定は動かさないが、
「テストのためだけに存在する既定引数」がプロダクションコードに残っている。

### O5. ベンチマークには閾値の assert が無い

`benchmarks/streaming-rt60/run.py` は数値を印字するだけで、成功/失敗を返さない。
V7 は実行結果をもって PASS としたが、**処理時間が10倍になってもこのファイルは何も言わない**。

### O6. 反証条件の差し替えが、ADR本文に反映されていない

ADR-0005 の反証条件は「1チャンクあたりの処理時間が**現行比で10倍**を超える」のままだが、
`benchmarks/streaming-rt60/README.md` は「比較の分母が定義できない」として基準を別のもの（実時間予算に対する割合）へ置き換えている。
**反証条件はロードマップの仮説判定に使う材料であり、実測できない条件がADRに残っていると、判定のときに何をもって反証とするかが分からない。**

### O7. 削除済み関数への言及がテストのdocstringに残っている

`tests/test_room_profiler.py:102` の docstring が
「`_extract_decay_segment` can actually produce (a single 500ms chunk's remainder — see the reachability sweep in test_main.py)」
と、**削除された関数と、書き換えられて存在しなくなったテスト**を現在形で参照している。
（そのテスト自身 `test_reachable_across_rt60_range_at_realistic_window_lengths` は PASSED であり、内容は `estimate_rt60_from_decay` の到達性なので有効。記述だけが古い。）

### O8. `_seen` と `_rejected` は上限なく増える

`RollingRT60Estimator._seen` は採用・棄却を問わず全イベントの鍵を保持し続け、刈り取られない。
1イベント/秒として1時間で3600要素程度であり実害は小さいが、プールに `maxlen` を置いた理由（「部屋やマイクが変わったときに古い測定が残り続けない」）は
`_seen` には適用されていない。**長時間稼働で部屋が変わり、たまたま同じ絶対位置鍵が再来した場合、そのイベントは無言で捨てられる。**

### O9. 既知の限界の数値は正確だった

ADR が「既知の限界」に書いた `speech_utterances`（残響ゼロ）での 0.202 / 3件採用 / 10件棄却は、既定引数で**完全に再現した**。
ポーズやシードを変えると採用が2件に落ちて `None` になる条件もある（gap=0.7 / 1.2 では報告されない）。
つまりこの床は常に出るわけではないが、**出るときは 0.20 という「小さい部屋」に見える値として、信頼度1.00で画面に出る。**
ADR はこれを別問題として残すと宣言しており、本検証はその宣言の当否を判定しない。ただし**ストリーミング側にこの床を固定するテストは無い**（ADR-0004 の batch 側 `test_this_harness_cannot_measure_rt60` のみ）。

## 旧テスト2本の「書き換え」についての判定（依頼の論点1）

| 旧テスト | 旧テストが守っていた約束 | 新テスト | 強さの比較 |
|---|---|---|---|
| `test_rt60_uses_prev_chunk_decay` | `_extract_decay_segment` が手組みの `frame_energies` から減衰を切り出し、`update_rt60` が真値0.3を誤差0.1以内・信頼度>0.9で返す | `test_rt60_comes_from_the_rolling_window` | **約束の対象が消えたため比較不能だが、置き換えとしては妥当。** 旧テストは削除済みAPIの単体確認であり、手組みの `frame_energies` に依存していた。新テストは `pipeline.process()` の実経路を合成残響クリップで駆動する。信頼度の閾値は 0.9 → 0.5 に緩んでいるが、対象が理想指数減衰から実信号に変わっているため単純な弱化とは言えない |
| `test_rt60_estimation_is_reachable_across_utterance_end_phase` | 16位相のうち**5位相以上**で推定が1件でも入る | `test_rt60_does_not_depend_on_where_the_utterance_ends_in_a_chunk` | **強くなった。** 8位相**すべて**で信頼度>0かつ真値±15%以内を要求する（M3） |
| `test_low_confidence_estimate_does_not_update_rt60`（`RoomProfiler` の信頼度ゲート） | ADR-0003 のR²ゲート: ゲートを通らない推定は中央値プールに入らず `rt60` を動かさない | `TestTheConfidenceGateSurvivedTheMove`（2件） | **弱くなった（M1 = FAIL）。** 新テストはどちらもR²ゲートに到達していない。旧テストは `if/else` の逃げ道を持つ弱いテストではあったが、少なくとも `estimate_rt60_from_decay` を雑音に対して実行し、ゲートの判断を通していた |

なお、`test_room_profiler.py` に新設された `test_an_unmeasured_room_reports_zero_confidence` は
旧テストの後継ではなく、**別の約束（未測定を信頼度0で表す）を守る新しいテスト**である。旧テストの約束を引き継いではいない。

## 削除された経路の保証の行き先（依頼の論点4）

| 削除されたもの | 持っていた保証 | 移動先 | 判定 |
|---|---|---|---|
| `_extract_decay_segment` の「減衰は100ms以上」 | 短すぎる減衰をT20フィットに掛けない | `find_decay_events` の `_MIN_EVENT_SECONDS = 0.1` | **移った（M2 PASS）**。番人も `test_batch_diagnostic.py` 側に実在 |
| `_extract_decay_segment` の「最後の発話フレームの次から切り出す」 | 発話本体をフィットに含めない | `find_decay_events` の `_PLATEAU_DB` による原点の前送り | 機能としては存在（バッチ側テストが番人）。ストリーミング固有の番人は無い |
| `_find_speech_offset` | 上記の補助 | 同上 | 同上 |
| `_prev_chunk` | 遷移検出の入力 | **廃止**（設計上不要） | **D2b FAIL**（削除を固定するテストが無い。grepでは残存なし） |
| `RoomProfiler.update_rt60` のR²ゲート | ADR-0003 の信頼度ゲート | `RollingRT60Estimator.push` | **M1 FAIL**（移りはしたが、番人が付いてこなかった） |
| `RoomProfiler._rt60_estimates`（maxlen=5 中央値） | 単発の推定で `rt60` が飛ばない | `RollingRT60Estimator`（maxlen=10 / p70）+ 3件下限 | 下限は D1a PASS。集約定数は **D1b FAIL** |
| `RoomProfiler._last_rt60_confidence` | 「最後の1件のR²」 | プール内R²の中央値 | **D4b FAIL**（中央値であることのテストが無い） |

`_prev_speech` と `_prev_frame_energies` は削除されておらず、early-to-late ratio の孤立立ち上がり判定（`main.py:151`, `main.py:189`）で
引き続き使われている。ADR の「`_prev_speech`/`_prev_chunk` による遷移検出…は削除する」は
**「遷移検出（RT60起動条件）を削除する」の意味で正しく実装されている**（フィールドそのものの削除ではない）。

## 総括

**実装は、ADR-0005 が主張したことを実際にやっている。**
検証者が独立に再測定した10条件は、コミットメッセージの数値と桁も符号も一致し、issue #13 の2つの症状（残響が強いほど測れない／1件を信頼度1.00で出す）は実経路で解消している。
削除された経路が持っていた100msの床は `find_decay_events` 側に実在し、そこには番人も付いている。
発話終端の位相に対する到達性は、旧テストより**強い**主張に置き換わっている。

**問題は、テストが約束に追いついていない箇所があることである。**
振る舞いを1箇所ずつ壊す変異試験で、**ADRが明示的に決定した4つの振る舞い（R²ゲート・重複除外・`window_start` の算術・集約定数）は、完全に無効化しても312件のテストが1件も落ちない**ことが分かった。
とりわけ重いのは次の2点である。

1. **M1**: ADR-0003 のR²ゲートは「移した」と書かれ、`TestTheConfidenceGateSurvivedTheMove` というクラス名で守られているように見えるが、
   その2テストはどちらもゲートに到達していない。**クラス名が主張していることを、中身が確かめていない。**
   これは「テストが無い」より危険で、次にここを触る人は守られていると信じる。
2. **V4**: 重複除外のテストは `deque` の飽和に隠れ、除外が壊れたときに落ちない。
   ADR が「窓が0.5秒ずつ進むので同じイベントが最大6つの窓に現れる」と問題を正確に認識したうえで置いた番人が、その問題に対して盲目である。

V3b（ダッシュボード）は ADR-0004 の検証が3回にわたり B4/B6 として FAIL 据え置きとしてきたものと同種で、
ブラウザJSを実行するテスト基盤が無いという構造的な欠落である。テストを1本書いて閉じる類のものではない。

**FAIL 7件はいずれも「実装が間違っている」ではなく「その約束を守る番人が存在しないか、存在しても落ちない」である。**
判定を PASS に動かすには、実装ではなくテストを足す必要がある。
