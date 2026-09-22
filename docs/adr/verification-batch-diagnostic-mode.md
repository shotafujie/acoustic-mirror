# 独立検証レポート: バッチ診断モード（ADR-0004）— 第2回

## 検証対象

- リポジトリ: `/Users/fujiemon/dev/speech/analyze/acoustic-mirror`
- ブランチ: `feature/batch-diagnostic-mode`
- 最新コミット: `58abeed`（"Correct ADR-0004 where verification found it inaccurate"）
- 検証時点の `git status --short`: 出力なし（クリーン）
- 前回検証時点: `040561e`。**前回のレポート全文はコミット `c57ebbd` に保存されている**（本ファイルは上書きしたため、前回の判定を参照する場合は `git show c57ebbd:docs/adr/verification-batch-diagnostic-mode.md`）。
- 検証日: 2026-09-22
- 検証者: 独立検証エージェント（実装コンテキストなし。書き込みはこのレポートファイルのみ）

### 前回からの差分

```
$ git diff --stat 040561e..HEAD
 docs/adr/ADR-0004-batch-diagnostic-mode.md     |  27 ++-
 docs/adr/verification-batch-diagnostic-mode.md | 239 +++++++++++++++++++++
 tests/synth.py                                 |  46 ++++
 tests/test_batch_diagnostic.py                 | 280 ++++++++++++++++++++++++-
 tests/test_dashboard.py                        |  40 ++++
 5 files changed, 626 insertions(+), 6 deletions(-)
```

```
$ git diff --name-only 040561e..HEAD -- src/
（出力なし）
```

**実装コード（`src/`）は1バイトも変更されていない。** 変更はテスト・合成ハーネス・ADR・前回レポートの記録のみ。したがって前回 PASS とした23件の**実装側の前提は同一**であり、残る回帰リスクは「テストとヘルパの追加が既存テストを壊していないか」だけである（下記の全件実行で確認済み）。

## 判定サマリ

| 判定 | 前回（`040561e`） | 今回（`58abeed`） |
|------|------|------|
| PASS | 23 | **35** |
| FAIL | 17 | **7** |
| BLOCKED | 3 | **3** |
| 約束の総数 | 43 | **45** |

総数が2件増えているのは、前回1行にまとめていた D2 と V5 を、今回の追加テストによって**一部だけが閉じた**ため D2a/D2b・V5a/V5b に分割したことによる。前回の判定が覆った（FAIL → PASS）のは12件、据え置き FAIL は7件（うち V5b は**今回の ADR 訂正によって新たに発生した FAIL**）。

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
collecting ... collected 256 items
```

前回から追加された48件（`tests/test_batch_diagnostic.py` 45件、`tests/test_dashboard.py` 3件）の結果行を実際の出力から抜粋する。

```
tests/test_batch_diagnostic.py::TestDecayEventGating::test_only_gate_passing_events_are_aggregated PASSED [ 12%]
tests/test_batch_diagnostic.py::TestDecayEventGating::test_events_are_never_shorter_than_100ms PASSED [ 13%]
tests/test_batch_diagnostic.py::TestDecayEventGating::test_sub_100ms_decay_is_not_an_event PASSED [ 13%]
tests/test_batch_diagnostic.py::TestNoiseFloorAndSpeech::test_floor_is_the_tenth_percentile_of_30ms_frames PASSED [ 14%]
tests/test_batch_diagnostic.py::TestNoiseFloorAndSpeech::test_floor_does_not_depend_on_an_adaptive_estimate_converging PASSED [ 14%]
tests/test_batch_diagnostic.py::TestNoiseFloorAndSpeech::test_speech_seconds_is_the_speech_frames_duration PASSED [ 14%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_early_to_late_is_the_median_not_the_mean PASSED [ 15%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_beats_the_median_on_truncated_tails[1-1.0] PASSED [ 15%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_beats_the_median_on_truncated_tails[1-1.5] PASSED [ 16%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_beats_the_median_on_truncated_tails[2-1.0] PASSED [ 16%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_beats_the_median_on_truncated_tails[2-1.5] PASSED [ 16%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_beats_the_median_on_truncated_tails[3-1.0] PASSED [ 17%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_beats_the_median_on_truncated_tails[3-1.5] PASSED [ 17%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_overshoots_when_tails_are_not_truncated[1] PASSED [ 17%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_overshoots_when_tails_are_not_truncated[2] PASSED [ 18%]
tests/test_batch_diagnostic.py::TestAggregationChoices::test_70th_percentile_overshoots_when_tails_are_not_truncated[3] PASSED [ 18%]
tests/test_batch_diagnostic.py::TestFalsifiabilityConditions::test_rt60_1s_with_long_pauses_within_15_percent[1] PASSED [ 19%]
tests/test_batch_diagnostic.py::TestFalsifiabilityConditions::test_rt60_1s_with_long_pauses_within_15_percent[2] PASSED [ 19%]
tests/test_batch_diagnostic.py::TestFalsifiabilityConditions::test_rt60_1s_with_long_pauses_within_15_percent[3] PASSED [ 19%]
tests/test_batch_diagnostic.py::TestCauseDiagnosis::test_cause_reported_when_srmr_is_below_target PASSED [ 20%]
tests/test_batch_diagnostic.py::TestNoOverallScore::test_no_mos_conversion_in_the_source PASSED [ 20%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[1-1.5-1.0-7.0] PASSED [ 21%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[1-2.0-0.7-7.0] PASSED [ 21%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[1-2.0-0.7-10.0] PASSED [ 21%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[1-3.0-1.0-10.0] PASSED [ 22%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[1-2.5-0.5-7.0] PASSED [ 22%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[2-1.5-1.0-7.0] PASSED [ 23%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[2-2.0-0.7-7.0] PASSED [ 23%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[2-2.0-0.7-10.0] PASSED [ 23%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[2-3.0-1.0-10.0] PASSED [ 24%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[2-2.5-0.5-7.0] PASSED [ 24%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[3-1.5-1.0-7.0] PASSED [ 25%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[3-2.0-0.7-7.0] PASSED [ 25%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[3-2.0-0.7-10.0] PASSED [ 25%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[3-3.0-1.0-10.0] PASSED [ 26%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_survives_every_realistic_protocol[3-2.5-0.5-7.0] PASSED [ 26%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_the_old_ratio_gate_would_have_rejected_some_of_them PASSED [ 26%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[1.5-1.0-7.0] PASSED [ 27%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2.0-0.7-7.0] PASSED [ 27%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2.0-0.7-10.0] PASSED [ 28%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[3.0-1.0-10.0] PASSED [ 28%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2.5-0.5-7.0] PASSED [ 28%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_densest_3s_window_is_the_noisier_alternative PASSED [ 29%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_srmr_is_computed_on_the_whole_clip PASSED [ 29%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_this_harness_cannot_measure_rt60 PASSED [ 30%]
tests/test_dashboard.py::TestBindAndFailure::test_default_bind_is_localhost PASSED [ 54%]
tests/test_dashboard.py::TestBindAndFailure::test_socket_is_not_bound_to_every_interface PASSED [ 55%]
tests/test_dashboard.py::TestBindAndFailure::test_analysis_failure_is_500_with_json PASSED [ 55%]
```

```
... （残り208件の PASSED 行を省略。省略部分は1行も FAILED / ERROR を含まない。
     前回 PASS の根拠とした test_batch_diagnostic.py の32件、test_dashboard.py の30件、
     test_main.py / test_room_profiler.py / test_capture.py / test_ws_server.py の全件が
     今回もすべて PASSED であることを出力上で確認した） ...

============================= 256 passed in 27.45s =============================
```

終了コード: `0`。収集256件、**256件すべて PASSED**、failed / error / skipped はゼロ。前回の208件から48件増えて、**回帰はゼロ**。

`tests/synth.py` の変更は既存関数の後ろへの純粋な追加（`speech_utterances` / `reverberant_speech` の新設）であり、`synth_speech` / `synth_rir` / `apply_reverb` / `synth_utterances` / `reverberant_utterances` は無変更。前回 PASS の23件はいずれも既存ハーネスに依存しており、その依存先は変わっていない。

## 約束ごとの再判定

前回から判定が変わった行は **→** で変化を示す。

### A. ブラウザ側

| # | 約束 | 前回 → 今回 | 根拠 |
|---|------|------|------|
| B1 | `enumerateDevices()` でマイク一覧 | PASS | `TestDiagnosePage::test_lists_microphones` PASSED（据え置き） |
| B2 | 3つのブラウザ信号処理を常に false | PASS | `test_browser_processing_forced_off` PASSED（据え置き） |
| B3 | AudioWorklet、MediaRecorder 不使用 | PASS | `test_records_raw_pcm_not_mediarecorder` / `test_served` PASSED（据え置き） |
| B4 | 既定7秒録音＋カウントダウン | **FAIL**（据え置き） | 追加テストなし。ADR は新設の「検証されていない領域（既知）」節でこれを**明示的に未検証と認め、JSテスト基盤の導入を別ADRとする**と宣言した。判定は変わらないが、**黙って欠けている状態から、既知の欠落として記録された状態に変わった**。 |
| B5 | 16-bit モノラルWAV・ネイティブレート送出 | **FAIL**（据え置き） | 同上。`diagnose.html` の JS は依然1行も実行されていない。 |
| B6 | 結果表示項目 | **FAIL**（据え置き） | 同上。 |
| B7 | `index.html` からのリンク | PASS | `test_index_links_to_diagnose` ほか PASSED（据え置き） |

### B. サーバ側

| # | 約束 | 前回 → 今回 | 根拠 |
|---|------|------|------|
| S1 | `ThreadingHTTPServer` 化、解析中も静的配信 | PASS | `test_static_served_while_diagnosing` PASSED（据え置き） |
| S2 | モノラル・16-bit 以外は 400 | PASS | 据え置き |
| S3 | 3秒未満は 400 | PASS | 据え置き |
| S4 | 30秒超／過大 `Content-Length` は 413 | PASS | 据え置き |
| S5 | バインドは `localhost` | **FAIL → PASS** | `TestBindAndFailure::test_default_bind_is_localhost` PASSED（`inspect.signature` で既定値が `"localhost"`）、`test_socket_is_not_bound_to_every_interface` PASSED（実際に起動したソケットの `server_address[0]` が `127.0.0.1` / `::1`）。既定値と実バインドの両方を見ており、`0.0.0.0` への変更を検出できる。 |
| S6 | 解析例外は 500 + JSON | **FAIL → PASS** | `TestBindAndFailure::test_analysis_failure_is_500_with_json` PASSED。`monkeypatch` で `http_server.diagnose` を例外送出に差し替え、500 と本文の `error` キーを確認している。`_BadRequest` 経路ではなく汎用 `except Exception` 経路を通しており、約束どおりの経路を検証している。 |
| S7 | 成功時は 200 + `to_dict()` | PASS | 据え置き |

### C. `diagnose()`

| # | 約束 | 前回 → 今回 | 根拠 |
|---|------|------|------|
| D1 | 16kHz以外は `resample_poly` | PASS | 据え置き |
| D2a | フレームエネルギー・ノイズフロアを**録音全体から一括**算出（30msフレーム、フロアは10パーセンタイル） | **FAIL → PASS** | `TestNoiseFloorAndSpeech::test_floor_is_the_tenth_percentile_of_30ms_frames` PASSED（テスト側で30ms・10パーセンタイルを独立に計算し `noise_floor_db` と一致を要求）、`test_floor_does_not_depend_on_an_adaptive_estimate_converging` PASSED（冒頭2秒を最大音量で始めるクリップでも全体フロアと一致＝適応フロアを使っていない）、`test_speech_seconds_is_the_speech_frames_duration` PASSED。 |
| D2b | 発話閾値は `SpeechDetector` と**同じマージン**を使う | **FAIL**（D2から分離、据え置き） | 追加テストは閾値 `6.0` を**テスト側にリテラルで書き写しているだけ**で、`SpeechDetector` 側の値と結びつけていない。実装は `batch_diagnostic._SPEECH_THRESHOLD_DB = 6.0`、`SpeechDetector.__init__` は `threshold_db: float = 6.0`（`speech_detector.py:36`）で、現在は一致しているが**独立した2つのリテラル**である。`SpeechDetector` 側を変更してもバッチ側は追随せず、テストも落ちない。「同じマージンを使う」という約束を検証するテストは存在しない。 |
| D3a | 減衰イベントの列挙 | PASS | 据え置き |
| D3b | ストリーミングと同じゲート（`is_valid` かつ R² ≥ `_RT60_CONFIDENCE_MIN`）を通ったものだけ集める | **FAIL → PASS** | `TestDecayEventGating::test_only_gate_passing_events_are_aggregated` PASSED。**`assert rejected > 0, "clip must actually exercise the gate"` が入っており、この信号で実際にゲートが発火していることがテストの実行によって保証されている**（前回指摘した「`rejected_count >= 0` は常に真」という空洞が埋まった）。信号は前回の平坦バースト（`reverberant_utterances`）から発話包絡を持つ `reverberant_speech` に変更されており、テストのコメントもその理由（平坦バーストでは全イベントが素通りしてゲートを検証できない）を明記している。ゲート式は `room_profiler._RT60_CONFIDENCE_MIN` を import して使っており、「ストリーミングと同じゲート」という約束と定数レベルで結びついている。 |
| D3c | 70パーセンタイル集約 | PASS | 据え置き |
| D3d | 3件未満は判定不能 | PASS | 据え置き |
| D4 | 起点の定義（95pct から10dB以内＋平坦部スキップ） | PASS | 据え置き |
| D5 | 終点の定義（フロア+6dB／3dB再上昇） | PASS | 据え置き |
| D6 | 100ms未満のイベントは捨てる | **FAIL → PASS** | `TestDecayEventGating::test_events_are_never_shorter_than_100ms` PASSED（`(0.3,0.7)` `(0.6,0.7)` `(1.5,1.2)` の3条件で、検出された**実在のイベント**すべてが100ms以上。これらのクリップにイベントが存在することは `TestFindDecayEvents::test_one_event_per_utterance_in_clean_signal` 等が別途保証している）。約束の観測可能な内容（100ms未満のイベントが返らない）を検証している。 |
| D7 | 孤立立ち上がりの列挙・0件なら判定不能 | PASS | 据え置き |
| D8 | early-to-late を**中央値**で集約 | **FAIL → PASS** | `TestAggregationChoices::test_early_to_late_is_the_median_not_the_mean` PASSED。`assert np.median(ratios) != pytest.approx(np.mean(ratios)), "clip must tell them apart"` で**中央値と平均が識別可能な信号であることを先に確認**したうえで、`early_to_late_ratio_db == pytest.approx(np.median(ratios))` を要求している。両アサーションの許容幅は同じ `pytest.approx` 既定（rel=1e-6）なので、平均に差し替えれば必ず落ちる。判別は効いている。 |
| D9 | SRMRゲート＝発話秒数3秒以上 | PASS | 据え置き（`TestSRMRAndRoom` 5件） |
| D10 | SRMR は**録音全体**に1回 | **FAIL → PASS** | `TestSRMRGateJustification::test_srmr_is_computed_on_the_whole_clip` PASSED。`diagnose(y).srmr_score == pytest.approx(SRMRProcessor().process(y).srmr_score)` と**値レベルで一致**を要求しており、部分窓に変更すれば落ちる。前回指摘した「`is None` か否かしか見ていない」空洞が埋まった。 |
| D11 | `classify_room` → `srmr_target` と既定値フラグ | PASS | 据え置き |
| D12 | `CauseSeparator.diagnose` を呼ぶ | **FAIL → PASS** | `TestCauseDiagnosis::test_cause_reported_when_srmr_is_below_target` PASSED（SRMR が目標値を下回る条件を作り、`cause is not None`、`primary_cause is not None`、`to_dict()` に `primary_cause` が出ることまで確認）。 |
| D13 | 返り値に採用/棄却数と個々のRT60 | PASS | 据え置き |

### D. 検証方針（反証条件）

| # | 約束 | 前回 → 今回 | 根拠 |
|---|------|------|------|
| V1 | ±15%（0.3/0.6/1.0 @0.7s、1.5 @1.2s） | PASS | 据え置き（12件） |
| V2 | 1.5s@0.7s は既知の過小評価 | PASS | 据え置き |
| V3 | 反証条件: 無音1.2sで RT60=1.0 / 1.5 が ±15% 以内 | **FAIL → PASS** | `TestFalsifiabilityConditions::test_rt60_1s_with_long_pauses_within_15_percent` が seed 1/2/3 で PASSED。前回欠けていた「RT60=1.0 を gap=1.2 で走らせる」組み合わせが埋まり、反証条件が名指しした2条件が両方とも実行されている。 |
| V4 | パーセンタイル70%採用の根拠 | **FAIL → PASS** | `TestAggregationChoices` が**両方向**を固定している。`test_70th_percentile_beats_the_median_on_truncated_tails`（gap=0.7、真値1.0/1.5×seed1-3 の6件）で `abs(p70-真値) < abs(p50-真値)`、`test_70th_percentile_overshoots_when_tails_are_not_truncated`（gap=1.2、真値1.0×seed1-3）で `p70 > 1.0` かつ `abs(p50-1.0) < abs(p70-1.0)`。ADR の記述もこれに合わせて訂正された（詳細は次節）。 |
| V5a | 改訂の中心主張（無音は SRMR をほとんど汚さない／比率ゲートは protocol をまたぐ／最密3秒窓は悪化） | **FAIL → PASS** | `test_pauses_barely_move_srmr`（5 protocol）PASSED = 無音ありクリップの全区間SRMRが、無音なしの参照値から10%以内。`test_the_old_ratio_gate_would_have_rejected_some_of_them` PASSED = 5 protocol の発話率が 0.7 をまたぐ（`min < 0.7 <= max`）。`test_densest_3s_window_is_the_noisier_alternative` PASSED = 最密3秒窓の値域幅が全区間の値域幅より大きい。`test_srmr_survives_every_realistic_protocol`（5 protocol × 3 seed = 15件）PASSED。真値 RT60=0.5 のクリップ、ADR の表と同じ burst/gap/長さ5条件が実際に走っている。前回 FAIL の3つの理由（(a) RT60=0.5 のクリップ不在、(b) protocol 再現なし、(c) SRMR の数値アサーション皆無）はいずれも解消された。 |
| V5b | **ADR が今回新たに追加した主張「この表の数値はテストで再現される」** | **新規 FAIL** | **表の数値を検査しているテストは存在しない。** 表の4列のうち: 発話率列（0.760/0.661/0.694/0.658/0.841）は `min < 0.7 <= max` しか検査されず個々の値は自由、SRMR列（1.81/欠測/欠測/欠測/1.82）は絶対値のアサーションが皆無（参照値との相対10%のみ）、**採用イベント列（5/5/10/6/9）と RT60 列（0.569〜0.584）に至っては、同じテストクラス内の `test_this_harness_cannot_measure_rt60` が「このハーネスは RT60 を測れない（`synth_speech` の4Hz包絡の谷が減衰として拾われるため、部屋が無くても採用イベントが出る）」ことを明示的に固定しており、原理的に再現できない**。さらに ADR 自身が、この主張の直後の文で「参照値は…絶対値をここに固定せず、テストが…という**主張そのものを検査する**」と書いており、**同じ段落の中で矛盾している**。 |

### E. 影響

| # | 約束 | 前回 → 今回 | 根拠 |
|---|------|------|------|
| I1 | `ThreadingHTTPServer` 化で既存テスト再確認 | PASS | 据え置き |
| I2 | 新規ファイル一覧と `index.html` の変更範囲 | **FAIL → PASS** | ADR が実際の差分に合わせて訂正された（`recorder-worklet.js` を新規ファイル一覧に追加、`index.html` が「リンク1本のみ」に留まらなかったことを明記）。訂正後に記述されている各変更は個別にテストで覆われている: `test_index_links_to_diagnose`、`test_config_reports_the_ws_port`、`test_ws_port_falls_back_to_the_server_config`、`test_nav_links_carry_the_query_string`、`test_served`（`recorder-worklet.js` の200応答）すべて PASSED。訂正の妥当性については次節で論じる。 |
| I3 | ストリーミング経路4モジュールは無変更 | PASS | 据え置き。ADR は `main.py::_run()` が変更されている事実を追記した（前回の所見への対応）。 |
| I4 | 総合スコア（MOS等）は出さない | **FAIL**（据え置き） | `TestNoOverallScore::test_no_mos_conversion_in_the_source` は PASSED だが、**再導入を検出できる形になっていない**。(1) 走査対象が `src/**/*.py` のみで、**`dashboard/diagnose.html` / `index.html` の JavaScript を見ていない**。ADR が名指しで排除した MicrophoneTest の `rToMos()` は**まさに JavaScript の関数**であり、再導入が最も起こりやすい場所が走査範囲外である。(2) 正規表現が `rtomos` / `mos_score` / `to_mos` の3リテラルに限定されており、`overall_score` や `def mos(` といった名前での再導入は素通りする。番人テストとしては、守るべき境界の外側を見張っている。 |
| I5 | 経路差を README に明記 | **FAIL**（据え置き） | 文章の内容を検証するテストは存在しない（構造的にテスト不能）。ADR は新設の「検証されていない領域（既知）」節でこれを認めた。 |
| I6 | 同一マイクの2箇所オープンに実害なし | **BLOCKED**（据え置き） | 実マイクが必要でテストスイートでは実行不能。ADR も「未確認」と明記。 |
| I7 | `getUserMedia` が localhost で HTTPS 不要 | **BLOCKED**（据え置き） | ADR に「実機で動作することを手動で確認済み（2026-09-22）」と追記されたが、**手動確認は本検証の判定根拠にならない**（再実行できず、私が確認できない）。自動テストでは依然実行不能。 |

## トレーサビリティ検査

`~/dev/.claude/hooks/trace-check.sh` は `docs/items/` が存在しないため **BLOCKED（該当ディレクトリなし）**。実行は試みていない。前回と同じ。

```
$ ls -d docs/items
ls: docs/items: No such file or directory
```

## ADR 訂正の妥当性

依頼の中心論点「訂正が、実装に合わせて仕様を歪めたものになっていないか」について、訂正箇所ごとに判断する。

| 訂正箇所 | 判断 | 理由 |
|---|---|---|
| **V4（パーセンタイルの根拠）** | **妥当。歪めていない。** | 訂正は**著者の主張に不利な方向**に動いている。旧記述「1.0〜1.5sでは70%の方が真値に近かった」を、「尾が切られる条件では70%が近いが、**尾を最後まで観測できる条件では逆転し70%が上振れする**」と、自らの選択が万能でないことを認める形に書き換えた。しかも不利な側（逆転する条件）を `test_70th_percentile_overshoots_when_tails_are_not_truncated` としてテストに固定している。結論（70%採用）は変えず、根拠を実測に合わせて**狭めた**。これは仕様を実装に合わせて歪める動きの逆である。旧記述にあった「0.3〜0.6sではほぼ同値」という未検証の主張は削除されており、残った主張はすべてテストで固定されている。 |
| **I2（`index.html` の変更範囲）** | **妥当。ただし性質は「仕様を実装に合わせた」編集である。** | 「リンク1本のみ追加」という記述を、実際の差分の記述に置き換えている。形式上はまさしく仕様を実装に合わせる編集だが、(1) 元の記述は「影響」節にある**見積り**であって実装への規範的制約ではないこと、(2) 訂正が逸脱を**逸脱として明示している**こと（「当初の見積りから外れた部分である」）、(3) 増えた変更自体が独立にテストで覆われていること、から、事実の訂正として妥当と判断する。「リンク1本に戻した」のでも「元からそういう設計だったことにした」のでもなく、「見積りを外した」と書いた点を評価する。 |
| **設計7（`speech_seconds` の追加）** | **妥当。** | 前回の所見で指摘した「仕様に書かれていない振る舞い」を、理由（UIが欠測理由を秒数で示すため）とともに明文化した。`speech_seconds` は複数のテストでアサートされている。 |
| **設計8（`intelligibility_ratio` / `overall`）** | **妥当。事実確認済み。** | 「既存のリアルタイムダッシュボードが同じ比で表示しているものを揃えただけ」という正当化が事実かをコードで確認した。`main.py:96-101` と `batch_diagnostic.py:111-114` は、**同じ式（SRMR ÷ srmr_target）・同じ閾値（0.8 / 0.5）・同じ3値（good / warning / alert）**である。後付けの発明ではなく、既存の慣行の記録である。MicrophoneTest の `rToMos()`（複数指標の加重合成を G.107 の曲線に通すもの）とは別物という区別も、内容として正しい。 |
| **影響（`main.py::_run()` の変更を追記）** | **妥当。** | 前回の所見をそのまま記録し、「解析の挙動には触れていない」という限定も事実と一致する（`git diff` で確認済み）。 |
| **新設「検証されていない領域（既知）」節** | **妥当かつ有益。ただし件数の記述が実態より強い。** | 未検証領域を ADR 本体に明記したことは、検証可能性の観点で明確な改善である。ただし冒頭の「Python層の11件は対応するテストを追加して閉じ」という記述は、私の再判定では**9件が完全に閉じ、1件（D2）は部分的、1件（I4）は閉じていない**。 |
| **V5（実測表まわり）** | **ここだけは妥当でない。** | 2点ある。**(1) 測定値の事後編集**: 「1.70〜1.81」を「1.70〜**1.83**」に広げ、参照値「1.819」を削除している。再測定した旨の記録はなく、削除の理由として挙げられているのは「参照値は使用するRIRのシードで変わるため」という**テスト都合**である。過去の実測値は、再現できないなら「当時のハーネスでの測定であり再現手段がない」と書くべきもので、範囲を広げて基準値を消す編集は、記録を後から都合に合わせる動きに見える。しかも広げた後の「1.70〜1.83」もテストではアサートされていない。**(2) 過大主張**: 「**この表の数値はテストで再現される**」は成立していない（上記 V5b）。訂正によって、元の ADR には無かった**新しい不正確な記述が1つ増えた**。 |

## 所見

### 今回の変更で実際に良くなった点

- 前回 FAIL の17件中12件が、**空洞でない**テストによって閉じた。特に評価できるのは、テストが「通ること」ではなく「約束が成立すること」を狙って書かれている箇所である:
  - D3b の `assert rejected > 0, "clip must actually exercise the gate"` — ゲートが発火しない信号でゲートを検証してしまう罠を、テスト自身が塞いでいる。しかもこのために合成ハーネスを差し替え、差し替えた理由をコメントに残している。
  - D8 の `assert np.median(ratios) != pytest.approx(np.mean(ratios)), "clip must tell them apart"` — 中央値と平均が偶然一致する信号で「中央値であること」を検証してしまう罠を塞いでいる。
  - V4 の「逆転する条件」を、自らの選択に不利なままテストとして固定したこと。
  - `test_this_harness_cannot_measure_rt60` — 新ハーネスの**限界そのもの**をテストとして固定し、誤用（このハーネスで RT60 精度を主張すること）を将来にわたって防いでいる。境界をテストにする発想は健全である。
- 実装を1行も変えずにテストだけで閉じたことは、前回の FAIL が「実装の欠陥」ではなく「検証の欠落」であったという前回の診断と整合している。

### 新たに見つかった問題

1. **V5b: ADR が自らの段落の中で矛盾している。** 「この表の数値はテストで再現される」と書いた直後に「絶対値をここに固定せず、テストが主張そのものを検査する」と書いている。後者が実態であり、前者は過大主張である。表の RT60・採用イベント列は、同じテストクラスの `test_this_harness_cannot_measure_rt60` が原理的に再現不能であることを固定している。**訂正作業が、閉じた穴の隣に新しい穴を開けている。**
2. **`test_pauses_barely_move_srmr` の参照値が、比較したい条件と2つの点で違う。** 参照は `apply_reverb(synth_speech(dur=7.0), 0.5)`（RIRシード **0**、連続する `synth_speech` 1本）、被験クリップは `reverberant_speech(0.5, ..., seed=1)`（RIRシード **1**、`speech_utterances` による複数バースト）。つまり「無音の有無」だけでなく**部屋の実現値と発話内容も同時に違う**。このテストが測っているのは「無音の影響」ではなく「無音＋別のRIR実現＋別の発話内容」の合計である。ADR の主張は「無音は SRMR を汚さない」なので、参照側も同じシードの RIR で作るのが筋である。
3. **同テストの許容幅が、主張したい効果量より大きい。** docstring は実測の最大乖離を5.5%と書きながら、アサーションは10%である。ADR の元の主張（1.70〜1.81 対 1.819 ＝ 最大6.5%乖離）より緩い。「無音は SRMR をほとんど汚していない」と「無音は SRMR を9%動かす」をこのテストは区別できない。V5a を PASS としたのは、方向としては実在の無音なし参照と比較しており、著しい汚染なら検出できるからだが、**主張の強さとテストの強さは一致していない**。
4. **同テストの docstring が実際の網羅範囲より広く書かれている。** 「across protocols and seeds」とあるが、`test_pauses_barely_move_srmr` は protocol のみのパラメタライズで、クリップのシードは既定の1に固定されている（3 seed 回しているのは `test_srmr_survives_every_realistic_protocol` と `test_densest_3s_window_is_the_noisier_alternative`）。
5. **I4 の番人テストが、守るべき場所を見ていない。** 排除対象の `rToMos()` は JavaScript の関数なのに、走査対象は `src/**/*.py` のみである。`dashboard/diagnose.html` に総合スコアが復活しても、このテストは何も言わない。
6. **D2b: 「`SpeechDetector` と同じマージン」が、2つの独立したリテラル `6.0` になっている。** 実装側（`batch_diagnostic._SPEECH_THRESHOLD_DB`）もテスト側（`+ 6.0` の直書き）も `SpeechDetector` を参照していない。`SpeechDetector` の既定値を変えても何も落ちないので、「同じマージンを使う」という約束は現在どこにも保持されていない。
7. **`test_sub_100ms_decay_is_not_an_event` は空振りしうる形をしている。** 最後のアサーションは「検出されたイベントを回して長さを見る」ループなので、**イベントが1件も検出されなければ無条件に通る**。テストの意図（60msで減衰しきるバーストがイベントにならないこと）は、イベントが検出されないことでも、検出されて100ms以上であることでも満たされてしまい、「短い減衰が検出されたうえで捨てられた」ことは示せない。D6 を PASS としたのは、同じクラスのもう1件（`test_events_are_never_shorter_than_100ms`）が**イベントが確実に存在するクリップ**で不変条件を検査しているからである。
8. **V4 の ADR 本文が挙げる具体値（中央値 1.017 / 70% 1.037）はアサートされていない。** 構造的な主張（逆転すること）は固定されているが、例示された数値は固定されていない。「例」と書かれているので過大主張ではないが、V5b と同種の緩みではある。
9. **追加されたテストの多くが、実装のロジックをテスト側に書き写す形をとっている**（D3b のゲート式、D2a と D8 の30msフレーム化・10パーセンタイル・+6dB・200ms孤立判定）。これは実装との**乖離**は検出できるが、実装とテストが**同じ勘違い**をしている場合は検出できない。D2a については `_expected_floor` がテスト内の独立計算になっており妥当だが、D8 の onset 列挙は実装の `_isolated_onsets` をほぼそのまま再実装している。

### 据え置きの FAIL について

- B4 / B5 / B6（ブラウザ層3件）と I5（README）は、前回と同じく**テストが存在しない**ため FAIL のままである。ただし ADR がこれらを「検証されていない領域（既知）」として明示的に列挙し、JS テスト基盤の導入を別ADRに切り出すと宣言したことは、状態としては改善である。判定は変えないが、**黙って欠けている**のと**既知の欠落として記録されている**のは別物であり、後者は次の判断材料になる。
- I7 に追記された「実機で手動確認済み」は、本検証では BLOCKED を動かさない。手動確認は私が再実行できず、判定根拠にできないためである。記録として残すこと自体は有益である。
