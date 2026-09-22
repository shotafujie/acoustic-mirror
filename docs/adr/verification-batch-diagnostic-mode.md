# 独立検証レポート: バッチ診断モード（ADR-0004）

## 検証対象

- リポジトリ: `/Users/fujiemon/dev/speech/analyze/acoustic-mirror`
- ブランチ: `feature/batch-diagnostic-mode`
- 最新コミット: `040561e`（`040561ef2771738f9879611d435125ea5d5a7bbb`、"Gate batch SRMR on seconds of speech (ADR-0004)"）
- 検証時点の `git status --short`: 出力なし（クリーン）
- 検証日: 2026-09-22
- 検証者: 独立検証エージェント（実装コンテキストなし。書き込みはこのレポートファイルのみ）

## 制約条件（トレーサビリティの鎖について）

先行レポート `docs/adr/verification-srmr-room-estimation.md` と同じく、本アイテムでもユーザーの明示的指示により **仕様策定（`skills/spec`）とテスト設計（`skills/test-design`）が意図的にスキップされ**、ADR から直接実装に入っている。そのため:

- `docs/items/` ディレクトリは存在しない（`ls docs/items` → `No such file or directory`）。
- `TC-NNN-M` 形式のテストIDは存在しない。

「守ると宣言したこと」の根拠は `docs/adr/ADR-0004-batch-diagnostic-mode.md` の **「決定」「設計」「検証方針（反証条件）」「影響」** の各節とし、実装コードを読む前に個別の約束を列挙してから検証した。判定根拠は**テストの実行結果のみ**である。コードリーディングは「約束を検証するテストが存在するか」「失敗の事実を正確に書くため」に限って用い、コードが正しく見えることを PASS の根拠にはしていない。

## 判定サマリ

| 判定 | 件数 |
|------|------|
| PASS | 23 |
| FAIL | 17 |
| BLOCKED | 3 |
| **約束の総数** | 43 |

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
collecting ... collected 208 items

tests/test_batch_diagnostic.py::TestFindDecayEvents::test_one_event_per_utterance_in_clean_signal PASSED [  0%]
tests/test_batch_diagnostic.py::TestFindDecayEvents::test_event_starts_after_burst_plateau PASSED [  0%]
tests/test_batch_diagnostic.py::TestFindDecayEvents::test_event_ends_before_next_utterance PASSED [  1%]
tests/test_batch_diagnostic.py::TestFindDecayEvents::test_no_events_in_silence PASSED [  1%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[1-0.3] PASSED [  2%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[1-0.6] PASSED [  2%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[1-1.0] PASSED [  3%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[2-0.3] PASSED [  3%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[2-0.6] PASSED [  4%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[2-1.0] PASSED [  4%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[3-0.3] PASSED [  5%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[3-0.6] PASSED [  5%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_within_15_percent_with_normal_pauses[3-1.0] PASSED [  6%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_long_rt60_within_15_percent_with_long_pauses[1] PASSED [  6%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_long_rt60_within_15_percent_with_long_pauses[2] PASSED [  7%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_long_rt60_within_15_percent_with_long_pauses[3] PASSED [  7%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_long_rt60_short_pauses_is_known_underestimate PASSED [  8%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_reports_accepted_event_values PASSED [  8%]
tests/test_batch_diagnostic.py::TestRT60Validity::test_fewer_than_three_events_gives_no_rt60 PASSED [  9%]
tests/test_batch_diagnostic.py::TestResampling::test_48k_input_matches_16k_estimate PASSED [  9%]
tests/test_batch_diagnostic.py::TestInputValidation::test_rejects_clip_shorter_than_minimum PASSED [ 10%]
tests/test_batch_diagnostic.py::TestEarlyToLateRatio::test_estimated_from_isolated_onsets PASSED [ 10%]
tests/test_batch_diagnostic.py::TestEarlyToLateRatio::test_none_without_isolated_onsets PASSED [ 11%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_srmr_computed_on_speechy_clip PASSED [ 11%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_srmr_computed_when_pauses_lower_the_ratio PASSED [ 12%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_srmr_skipped_when_speech_shorter_than_srmr_window PASSED [ 12%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_srmr_skipped_when_clip_is_short_despite_high_ratio PASSED [ 12%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_srmr_skipped_when_mostly_silent PASSED [ 13%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_room_classified_from_estimated_rt60 PASSED [ 13%]
tests/test_batch_diagnostic.py::TestSRMRAndRoom::test_room_uses_default_rt60_when_undetermined PASSED [ 14%]
tests/test_batch_diagnostic.py::TestToDict::test_serializable_shape PASSED [ 14%]
tests/test_batch_diagnostic.py::TestToDict::test_undetermined_metrics_serialize_as_null PASSED [ 15%]

... （tests/test_buffer.py, tests/test_capture.py, tests/test_cause_separator.py の全PASSED行を省略。
     省略部分は1行も FAILED / ERROR を含まない。全208件の内訳は末尾の集計行のとおり） ...

tests/test_dashboard.py::TestHTTPServer::test_serves_index_html PASSED   [ 30%]
tests/test_dashboard.py::TestHTTPServer::test_content_type_is_html PASSED [ 30%]
tests/test_dashboard.py::TestHTTPServer::test_static_files_are_revalidated PASSED [ 31%]
tests/test_dashboard.py::TestHTTPServer::test_config_reports_the_ws_port PASSED [ 31%]
tests/test_dashboard.py::TestHTTPServer::test_config_reports_null_when_no_ws_port_is_wired PASSED [ 32%]
tests/test_dashboard.py::TestHTTPServer::test_404_for_unknown_path PASSED [ 32%]
tests/test_dashboard.py::TestDashboardHTML::test_html_contains_websocket_connection PASSED [ 33%]
tests/test_dashboard.py::TestDashboardHTML::test_ws_port_falls_back_to_the_server_config PASSED [ 33%]
tests/test_dashboard.py::TestDashboardHTML::test_html_contains_intelligibility_ring PASSED [ 34%]
tests/test_dashboard.py::TestDashboardHTML::test_html_contains_room_profile_card PASSED [ 34%]
tests/test_dashboard.py::TestDashboardHTML::test_html_contains_cause_card PASSED [ 35%]
tests/test_dashboard.py::TestDashboardHTML::test_html_contains_haptic_preview PASSED [ 35%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_returns_diagnostic_json PASSED [ 36%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_accepts_48k PASSED   [ 36%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_rejects_too_short PASSED [ 37%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_rejects_stereo PASSED [ 37%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_rejects_non_16bit PASSED [ 37%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_rejects_garbage PASSED [ 38%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_rejects_oversized_body PASSED [ 38%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_rejects_over_30_seconds PASSED [ 39%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_post_to_other_path_is_404 PASSED [ 39%]
tests/test_dashboard.py::TestDiagnoseEndpoint::test_static_served_while_diagnosing PASSED [ 40%]
tests/test_dashboard.py::TestDiagnosePage::test_served PASSED            [ 40%]
tests/test_dashboard.py::TestDiagnosePage::test_browser_processing_forced_off PASSED [ 41%]
tests/test_dashboard.py::TestDiagnosePage::test_records_raw_pcm_not_mediarecorder PASSED [ 41%]
tests/test_dashboard.py::TestDiagnosePage::test_lists_microphones PASSED [ 42%]
tests/test_dashboard.py::TestDiagnosePage::test_posts_wav_to_api PASSED  [ 42%]
tests/test_dashboard.py::TestDiagnosePage::test_index_links_to_diagnose PASSED [ 43%]
tests/test_dashboard.py::TestDiagnosePage::test_diagnose_links_back PASSED [ 43%]
tests/test_dashboard.py::TestDiagnosePage::test_nav_links_carry_the_query_string PASSED [ 44%]
tests/test_dashboard.py::TestDiagnosePage::test_hidden_attribute_beats_grid_display PASSED [ 45%]

... （tests/test_haptic_patterns.py, tests/test_main.py, tests/test_room_profiler.py,
     tests/test_scaffold.py, tests/test_speech_detector.py, tests/test_srmr.py,
     tests/test_ws_server.py の全PASSED行を省略。省略部分は1行も FAILED / ERROR を含まない） ...

============================= 208 passed in 14.12s =============================
EXIT_CODE=0
```

終了コード: `0`。収集208件、**208件すべて PASSED**、failed / error / skipped はゼロ。

補助的に、約束「ストリーミング経路を変更しない」「index.html にはリンク1本のみ追加」の**観測事実**として以下も記録する（判定根拠ではなく、事実の特定のため）。ADR-0004 の作業が始まる直前のコミット `cbbef64` からの差分:

```
$ git diff --stat cbbef64..HEAD
 README.md                                         |  11 +
 docs/adr/ADR-0004-batch-diagnostic-mode.md        | 142 ++++++++
 src/acoustic_mirror/analysis/batch_diagnostic.py  | 262 +++++++++++++++
 src/acoustic_mirror/dashboard/diagnose.html       | 382 ++++++++++++++++++++++
 src/acoustic_mirror/dashboard/http_server.py      | 111 ++++++-
 src/acoustic_mirror/dashboard/index.html          |  28 +-
 src/acoustic_mirror/dashboard/recorder-worklet.js |  11 +
 src/acoustic_mirror/main.py                       |   9 +-
 tests/synth.py                                    |  44 +++
 tests/test_batch_diagnostic.py                    | 184 +++++++++++
 tests/test_dashboard.py                           | 215 ++++++++++++
 11 files changed, 1386 insertions(+), 13 deletions(-)
```

```
$ git diff --name-only cbbef64..HEAD -- src/acoustic_mirror/audio src/acoustic_mirror/feedback src/acoustic_mirror/analysis/room_profiler.py src/acoustic_mirror/analysis/srmr.py src/acoustic_mirror/analysis/speech_detector.py src/acoustic_mirror/analysis/cause_separator.py
（出力なし）
```

## 約束ごとの判定

### A. ブラウザ側（設計節「ブラウザ側（新規 `dashboard/diagnose.html`）」）

| # | 約束 | 判定 | 根拠 |
|---|------|------|------|
| B1 | `enumerateDevices()` でマイク一覧をドロップダウン表示する | **PASS** | `tests/test_dashboard.py::TestDiagnosePage::test_lists_microphones` PASSED（`enumerateDevices` と `deviceId` の存在を検証）。 |
| B2 | getUserMedia で `echoCancellation` / `noiseSuppression` / `autoGainControl` を**常に** false にする | **PASS** | `TestDiagnosePage::test_browser_processing_forced_off` PASSED（3つの制約すべてが `false` で記述されていることを検証）。 |
| B3 | AudioWorklet で Float32 PCM を集める。MediaRecorder は使わない | **PASS** | `TestDiagnosePage::test_records_raw_pcm_not_mediarecorder` PASSED（`audioWorklet.addModule` の存在と `MediaRecorder` の不在を検証）。`TestDiagnosePage::test_served` PASSED で `recorder-worklet.js` が 200 で配信されることも確認。 |
| B4 | 既定7秒録音（カウントダウン表示付き） | **FAIL** | **この約束を検証するテストが存在しない**。`tests/test_dashboard.py::TestDiagnosePage` の8件は、ブラウザAPI制約・ワークレット・マイク一覧・POST先・リンク・CSS に関する文字列検査のみで、録音長の既定値（7秒）にもカウントダウン表示にも言及するテストはない。 |
| B5 | 16-bit PCM モノラル WAV にエンコードし、**ブラウザのネイティブサンプルレートのまま**送る | **FAIL** | `TestDiagnosePage::test_posts_wav_to_api` は `/api/diagnose` と `RIFF` という文字列がページに含まれることしか検証しておらず、**チャネル数1・16-bit・ネイティブレート送出のいずれも検証していない**。サーバ側のリサンプリング（下記 D1）にはテストがあるが、それはクライアントがネイティブレートで送ることの検証にはならない。 |
| B6 | 結果表示: SRMR・了解度比・部屋種別・RT60（採用イベント数とばらつき付き）・early-to-late ratio・ノイズフロア・原因診断 | **FAIL** | **表示項目を検証するテストが存在しない**。`index.html` 側には `TestDashboardHTML::test_html_contains_room_profile_card` 等の表示項目テストがあるのに対し、`diagnose.html` 側には対応するテストが1件もない。 |
| B7 | 既存 `index.html` からリンクを1本張る | **PASS** | `TestDiagnosePage::test_index_links_to_diagnose` PASSED、`test_diagnose_links_back` PASSED、`test_nav_links_carry_the_query_string` PASSED。 |

### B. サーバ側（設計節「サーバー側」1）

| # | 約束 | 判定 | 根拠 |
|---|------|------|------|
| S1 | `DashboardServer` を `ThreadingHTTPServer` に替え、解析中も静的配信が詰まらない | **PASS** | `TestDiagnoseEndpoint::test_static_served_while_diagnosing` PASSED（解析POSTを別スレッドで走らせている最中に `index.html` が 0.5秒以内に返ることを検証）。 |
| S2 | 本文を `wave` で読み、モノラル・16-bit 以外は 400 | **PASS** | `TestDiagnoseEndpoint::test_rejects_stereo`（400）、`test_rejects_non_16bit`（400）、`test_rejects_garbage`（400）すべて PASSED。 |
| S3 | 3秒未満（`SRMR_WINDOW_SAMPLES` 相当）は 400 | **PASS** | `TestDiagnoseEndpoint::test_rejects_too_short` PASSED（1秒のWAVが 400、本文に `error` キー）。 |
| S4 | 30秒超（または相当の `Content-Length`）は 413 | **PASS** | `TestDiagnoseEndpoint::test_rejects_over_30_seconds` PASSED（31秒→413）、`test_rejects_oversized_body` PASSED（本文を読む前に `Content-Length` だけで 413）。 |
| S5 | バインドは既存どおり `localhost` | **FAIL** | **バインド先を検証するテストが存在しない**。`tests/test_dashboard.py` の各テストは自ら `host="localhost"` を渡してサーバを起動しており、既定値や外部インターフェースに開いていないことを検証していない。 |
| S6 | 解析例外は 500 + JSON エラー | **FAIL** | **500応答を検証するテストが存在しない**。`TestDiagnoseEndpoint` の9件が検証しているステータスは 200 / 400 / 413 / 404 のみで、解析中の例外を誘発して 500 と JSON 本文を確認するテストは1件もない。 |
| S7 | 成功時は 200 + `DiagnosticResult.to_dict()` | **PASS** | `TestDiagnoseEndpoint::test_returns_diagnostic_json` PASSED（200、`application/json`、`type == "diagnostic"`、`rt60.value` が非 None）、`test_accepts_48k` PASSED。 |

### C. `analysis/batch_diagnostic.py` の `diagnose()`（設計節「サーバー側」2）

| # | 約束 | 判定 | 根拠 |
|---|------|------|------|
| D1 | 16kHz 以外なら `resample_poly` で 16kHz に変換する | **PASS** | `tests/test_batch_diagnostic.py::TestResampling::test_48k_input_matches_16k_estimate` PASSED（48kHz入力のRT60が16kHz入力の推定と相対10%以内、duration も一致）。`TestDiagnoseEndpoint::test_accepts_48k` PASSED。 |
| D2 | フレームエネルギーとノイズフロアを録音全体から一括算出する（30msフレーム、フロアは低位パーセンタイル(10%)、発話閾値は `SpeechDetector` と同じマージン） | **FAIL** | **フレームサイズ・ノイズフロアのパーセンタイル・発話閾値マージンのいずれも検証するテストが存在しない**。`DiagnosticResult.noise_floor_db` の値を確認するテストも、`SpeechDetector` の適応フロアを使っていないことを確認するテストもない。`speech_seconds` / `speech_ratio` は SRMR ゲートのテスト（D9）で間接的に使われるだけで、算出方式自体は検証されていない。 |
| D3a | 録音全体から減衰イベントを列挙する | **PASS** | `TestFindDecayEvents::test_one_event_per_utterance_in_clean_signal`（7秒クリップで5〜9件）、`test_no_events_in_silence`（無音では0件）PASSED。 |
| D3b | ストリーミングと同じゲート（`is_valid` かつ R² ≥ `_RT60_CONFIDENCE_MIN`）を通った推定だけを集める | **FAIL** | **ゲートによる棄却を検証するテストが存在しない**。`TestRT60Validity::test_reports_accepted_event_values` の該当アサーションは `assert result.rt60_rejected_count >= 0` であり、これは常に真で棄却の有無を区別しない。低信頼・無効な減衰イベントが集約から除外されることを確認するテストは1件もない（ストリーミング側には `test_low_confidence_estimate_does_not_update_rt60` がある）。 |
| D3c | 採用イベントをパーセンタイル70%で集約する | **PASS** | `TestRT60Validity::test_reports_accepted_event_values` PASSED（`result.rt60 == pytest.approx(np.percentile(result.rt60_events, 70))`）。 |
| D3d | 採用イベントが3件未満なら RT60 は「判定不能」とし、値を出さない | **PASS** | `TestRT60Validity::test_fewer_than_three_events_gives_no_rt60` PASSED（`rt60 is None` かつ `"rt60" in defaulted_metrics`）。 |
| D4 | 減衰イベントの起点: 発話レベル（95パーセンタイル）から10dB以内の極大フレーム。区間最大値から3dB以内に留まる最後のフレームまで起点を後ろへずらす | **PASS** | `TestFindDecayEvents::test_event_starts_after_burst_plateau` PASSED（0.2〜0.5秒のバーストに対し、起点が 0.4s〜0.55s の範囲、すなわち平坦部の後にあることを検証）。 |
| D5 | 終点: ノイズフロア+6dB以下、または追跡中の最小値から3dB超の再上昇のどちらか早い方 | **PASS** | `TestFindDecayEvents::test_event_ends_before_next_utterance` PASSED（RT60=1.5s・無音0.7sのクリップで、各イベントの終点が次イベントの起点以下）。`test_no_events_in_silence` PASSED。 |
| D6 | 起点から終点まで100ms未満のイベントは捨てる | **FAIL** | **この最小長を検証するテストが存在しない**。`TestFindDecayEvents` の4件はいずれもイベント数・起点位置・終点順序・無音時0件を見るだけで、100ms未満のイベントが棄却されることを確認していない。 |
| D7 | Early-to-late ratio: 孤立立ち上がり（直前200msが無音）をすべて列挙して適用し、0件なら判定不能 | **PASS** | `TestEarlyToLateRatio::test_estimated_from_isolated_onsets` PASSED（`early_to_late_event_count >= 1` かつ値が非 None）、`test_none_without_isolated_onsets` PASSED（無音区間なしのクリップで値が None、`defaulted_metrics` に記載）。 |
| D8 | Early-to-late ratio を**中央値**で集約する | **FAIL** | **中央値であることを検証するテストが存在しない**。RT60 側には集約方法を明示的に検証するテスト（D3c）があるのに対し、early-to-late 側には `np.median` との一致を確認するアサーションが1つもなく、平均・最大等に変えてもテストは通る。 |
| D9 | SRMR: **発話区間の合計秒数が3秒以上**の場合に限り算出し、満たさない場合は判定不能（本日の改訂。比率ゲートからの置き換え） | **PASS** | `TestSRMRAndRoom::test_srmr_computed_when_pauses_lower_the_ratio` PASSED（`speech_ratio < 0.7` かつ `speech_seconds >= 3.0` で SRMR が算出される＝比率ゲートに戻したら落ちる）、`test_srmr_skipped_when_speech_shorter_than_srmr_window` PASSED（発話実量 < 3秒で None）、`test_srmr_skipped_when_clip_is_short_despite_high_ratio` PASSED（`speech_ratio >= 0.7` でもクリップが短ければ None＝秒数ゲートであることを裏側から固定）、`test_srmr_skipped_when_mostly_silent` PASSED、`test_srmr_computed_on_speechy_clip` PASSED。 |
| D10 | SRMR は**録音全体**に対して `SRMRProcessor` を1回かける（最密3秒窓を選ぶ方式は採らない） | **FAIL** | **「録音全体に1回」であることを検証するテストが存在しない**。SRMR 関連の5テストはいずれも `srmr_score` が None か否かしか見ておらず、全区間に対する算出か部分窓に対する算出かを区別できない。ADR がこの選択（全区間 vs 最密3秒窓）を明示的に比較して採用した以上、区別しないテストは採用の検証にならない。 |
| D11 | `classify_room` → `srmr_target` を既存関数で呼び、判定不能の指標は既定値で分類したうえでフラグを付ける | **PASS** | `TestSRMRAndRoom::test_room_classified_from_estimated_rt60` PASSED（推定RT60が `room_profile.rt60` に入り、部屋種別が reverberant 系）、`test_room_uses_default_rt60_when_undetermined` PASSED（既定値0.2で分類され `defaulted_metrics` に `rt60`）、`TestToDict::test_undetermined_metrics_serialize_as_null` PASSED。 |
| D12 | `CauseSeparator.diagnose` を既存関数のまま呼ぶ | **FAIL** | **バッチ経路で原因診断が行われることを検証するテストが存在しない**。`TestToDict::test_serializable_shape` が検査するキーは `type` / `rt60` / `early_to_late_ratio` / `room_profile` / `defaulted_metrics` のみで、`primary_cause` に触れるアサーションは `tests/test_batch_diagnostic.py` にも `tests/test_dashboard.py` にも存在しない。 |
| D13 | 返り値に集約値に加え、採用・棄却イベント数と採用された個々のRT60値を含める | **PASS** | `TestRT60Validity::test_reports_accepted_event_values` PASSED（`rt60_events` が3件以上）、`TestToDict::test_serializable_shape` PASSED（`rt60` が `value` / `events` / `rejected_count`、`early_to_late_ratio` が `value_db` / `event_count` を持ち、JSON シリアライズ可能）。 |

### D. 検証方針（反証条件）節

| # | 約束 | 判定 | 根拠 |
|---|------|------|------|
| V1 | 合格基準: 300msバースト×7秒の合成発話列を `synth_rir` で畳み込み -60dB雑音を加えた信号で、真値 RT60 = 0.3 / 0.6 / 1.0 / 1.5s の各値で**相対誤差 ±15% 以内**（1.5s は無音1.2s） | **PASS** | `TestRT60Validity::test_within_15_percent_with_normal_pauses` が真値 0.3 / 0.6 / 1.0 × seed 1/2/3 の**9件すべて PASSED**（`abs(rt60 - true)/true <= 0.15`）。`test_long_rt60_within_15_percent_with_long_pauses` が真値1.5s・無音1.2s × seed 1/2/3 の**3件すべて PASSED**。信号生成は `tests/synth.py::reverberant_utterances`（0.3秒バースト、`synth_rir` 畳み込み、-60dBFS 白色雑音）で ADR 記載の条件と一致。 |
| V2 | 無音0.7sでの RT60=1.5s は約22%の過小評価であり、これを「既知の限界」としてテストに記録する | **PASS** | `TestRT60Validity::test_long_rt60_short_pauses_is_known_underestimate` PASSED（`1.05 <= rt60 < 1.275`、すなわち15%以上の過小評価であることを固定）。 |
| V3 | 反証条件: **無音1.2sの条件で RT60 = 1.0 / 1.5s** の誤差が ±15% を超えないこと | **FAIL** | 1.5s・無音1.2s は3seedで検証され PASSED だが、**RT60 = 1.0s を無音1.2s で走らせるテストが存在しない**。1.0s は `gap=0.7`（既定）でのみ検証されている（`test_within_15_percent_with_normal_pauses`）。反証条件が名指しした条件の組み合わせの一方が未実行である。 |
| V4 | パーセンタイル値は試作で50%と70%を比較し、0.3〜0.6sではほぼ同値、1.0〜1.5sでは70%の方が真値に近かったため70%を採用する | **FAIL** | 採用値が70パーセンタイルであること自体は D3c で PASS。しかし**50%と70%を比較した主張を裏付けるテストが存在しない**。`tests/` 全体で `percentile` を含むアサーションは `test_reports_accepted_event_values` の1行のみで、50パーセンタイルでの集約値を計算・比較する箇所はない。 |
| V5 | **本日の改訂の根拠**: 合成クリップ（真値RT60=0.5s、-60dB床）での実測表（burst/gap 5条件の発話率0.658〜0.841・SRMR・採用イベント数・RT60）と、「発話率0.66〜0.78のクリップの全区間SRMRは1.70〜1.81で、無音なし連続7秒の参照値1.819とほぼ同じ」という主張 | **FAIL** | **この主張を裏付けるテストが存在しない**。(a) 真値 RT60=0.5s のクリップを使うテストは `tests/` に1件もない（バッチ側で使われている真値は 0.3 / 0.6 / 1.0 / 1.5）。(b) 表の5条件（1.5s/1.0s、2.0s/0.7s×2、3.0s/1.0s、2.5s/0.5s、うち10秒クリップ2件）に対応する burst/gap/長さの組み合わせを走らせるテストが存在しない（`reverberant_utterances` の burst は 0.3s 固定、dur は 7.0s 固定）。(c) SRMR の**数値**を検証するアサーションがバッチ側に1つもない（`srmr_score is None` / `is not None` のみ）。したがって「無音は SRMR をほとんど汚していない（1.70〜1.81 対 参照1.819）」という、ゲート変更を正当化している中心的な実測主張は、現在走るテストによって一切裏付けられていない。 |

### E. 影響節

| # | 約束 | 判定 | 根拠 |
|---|------|------|------|
| I1 | `ThreadingHTTPServer` 化に伴い既存 `tests/test_dashboard.py` を再確認する（静的配信の挙動は変わらない） | **PASS** | `TestHTTPServer` の6件（`test_serves_index_html` / `test_content_type_is_html` / `test_static_files_are_revalidated` / `test_config_reports_the_ws_port` / `test_config_reports_null_when_no_ws_port_is_wired` / `test_404_for_unknown_path`）、`TestDashboardHTML` の6件すべて PASSED。 |
| I2 | 新規ファイルは `analysis/batch_diagnostic.py`・`dashboard/diagnose.html`・対応テスト。**`index.html` にはリンク1本のみ追加** | **FAIL** | 新規ファイルと対応テストは存在し全件 PASSED だが、`index.html` への変更は**リンク1本にとどまっていない**。`git diff cbbef64..HEAD -- src/acoustic_mirror/dashboard/index.html` は 28行の変更を示し、内訳はナビゲーションリンク1行に加えて、WebSocketポート解決処理の書き換え（`resolveWsPort()` の新設、`connect()` の async 化、`/api/config` への fetch、ナビゲーションリンクへの `location.search` 付与）である（コミット `c6b160c`）。また新規ファイルとして `dashboard/recorder-worklet.js` が追加されており、ADR の列挙にない。 |
| I3 | ストリーミング経路（`AnalysisPipeline` / `RoomProfiler` / `WSBroadcaster` / `capture.py`）は変更しない | **PASS** | `git diff --name-only cbbef64..HEAD -- src/acoustic_mirror/audio src/acoustic_mirror/feedback src/acoustic_mirror/analysis/room_profiler.py ...` は出力なし（ファイル無変更）。テスト面では `tests/test_main.py`（`TestShouldRecomputeSrmr` 5件、`TestAnalysisPipeline` 13件）、`tests/test_room_profiler.py`（全件）、`tests/test_capture.py`（6件）、`tests/test_ws_server.py`（6件）がすべて PASSED で、回帰は観測されていない。 |
| I4 | **総合スコア（MOS等）は出さない**。`rToMos()` 相当の式は流用しない | **FAIL** | **この否定的約束を検証するテストが存在しない**。`grep -rn -i "mos\b\|rToMos" src/` は該当なしで、実装には存在しないことを確認したが、将来の追加を検出するテストは1件もない。 |
| I5 | ブラウザ経由とサーバー（sounddevice）経由で数値が完全には一致しない可能性を許容リスクとし、**README に明記する** | **FAIL** | `README.md:39` に該当記述（「リアルタイムモニターはサーバー側（`--device`）で、マイク診断はブラウザ側で録音する。入力経路が違うため、同じマイクでも両者の数値が完全には一致しないことがある」）が存在することを確認したが、**README の記述内容を検証するテストが存在しない**（先行レポートの ADR-0001 #3 と同種の、テスト対象になり得ない約束）。 |
| I6 | バッチ診断中もサーバー側の `sounddevice` ストリームは動き続け、同一マイクを2箇所から開いても実害がない（macOS CoreAudio） | **BLOCKED** | 実マイクデバイスとブラウザの同時使用が必要で、テストスイートでは実行できない。`tests/test_capture.py` は `sounddevice` をモックしており、この共有挙動を確認できない。成否を判定できない。 |
| I7 | ブラウザの `getUserMedia` は `localhost` なら HTTPS 不要（secure context 扱い）で、既存の `localhost` バインドのまま動く | **BLOCKED** | 実ブラウザでの `getUserMedia` 実行が必要で、テストスイートでは実行できない。`TestDiagnosePage` はすべて HTML の静的文字列検査であり、実際の権限取得を確認していない。成否を判定できない。 |

## トレーサビリティ検査

`~/dev/.claude/hooks/trace-check.sh` は `docs/items/` ディレクトリが存在しないため **BLOCKED（該当ディレクトリなし）**。実行は試みていない（対象ディレクトリの構造的不在により実行不可と判断。先行レポートと同じ扱い）。

```
$ ls -d docs/items
ls: docs/items: No such file or directory
```

| # | 孤児 | 件数 |
|---|------|------|
| 1 | 検証されていない仕様 | 測定不能（BLOCKED） |
| 2 | テストケースの無い仕様 | 測定不能（BLOCKED） |
| 3 | 設計にあるがコードに無いTC | 測定不能（BLOCKED） |
| 4 | コードにあるが設計に無いTC | 測定不能（BLOCKED） |
| 5 | 親仕様が存在しないTC | 測定不能（BLOCKED） |

## 所見

- **テストは1件も失敗していない。** 208件すべて PASSED、終了コード0。本レポートの FAIL 17件は**テストの失敗によるものではなく、すべて「約束を検証するテストが存在しない」ことによる**。先行レポート（`verification-srmr-room-estimation.md`）と同じ基準を適用した結果である。
- **改訂の中心主張（V5）が無防備である点が、今回もっとも重い所見。** 本日の改訂は「発話率ゲートはバッチでは代理として成立しない」「無音は SRMR をほとんど汚していない（実測1.70〜1.81 対 参照1.819）」という2つの主張でゲート変更を正当化している。前者の**結論**（秒数でゲートする挙動）は D9 の5テストで堅く固定されているが、後者の**根拠**にあたる数値は1つもテストになっていない。ADR の表に載った条件（真値RT60=0.5s、burst 1.5〜3.0s、gap 0.5〜1.0s、10秒クリップ）は `tests/synth.py::reverberant_utterances` のシグネチャ（burst 0.3s固定、dur 7.0s固定）では再現できず、再現するには合成ハーネス自体の拡張が要る。ADR 自身が「実環境の暗騒音がより強く SRMR を汚す可能性は否定できない。実機での再確認を残課題とする」と書いているが、**合成信号での主張すら現在は回帰から外れている**ことは記録しておく。
- V3（反証条件）の FAIL は挙動の失敗ではなく**条件の組み合わせの欠落**である。RT60=1.0s は無音0.7s（より短く、観測できる減衰が切れやすい条件）では±15%以内で PASSED しており、無音1.2sでも通る蓋然性は高い。しかし反証条件が名指しした条件そのものは走っていないため、推測で PASS にはしなかった。
- I2 の `index.html` 変更超過について: 増えた変更（`/api/config` からのWSポート取得）は ADR-0004 の主題とは別の不具合修正（コミット `c6b160c`）であり、それ自体は `test_config_reports_the_ws_port` / `test_ws_port_falls_back_to_the_server_config` / `test_nav_links_carry_the_query_string` で検証され PASSED している。ADR に書かれた影響範囲（「リンク1本のみ」）を実際の変更が超えている、という事実として記録する。
- 同様に、ADR は「ストリーミング経路は変更しない」としているが、`src/acoustic_mirror/main.py` の `_run()` が6行追加・3行削除で変更されている（WSブロードキャスタを先に起動し、その実ポートを `DashboardServer` に渡す）。ADR が名指しした4つ（`AnalysisPipeline` / `RoomProfiler` / `WSBroadcaster` / `capture.py`）自体は無変更なので I3 は PASS としたが、配線コードには手が入っている。
- 仕様に書かれていない振る舞いとして、`DiagnosticResult.to_dict()` が `intelligibility_ratio` と `overall`（good / warning / alert の3値）を出力している。ADR の設計節にこの2フィールドの記述はない。`tests/test_batch_diagnostic.py::TestToDict::test_serializable_shape` もこの2キーを検査しておらず、判定不能時に欠落する（`srmr_score` が None のとき付与されない）という条件分岐も検証されていない。
- `dashboard/diagnose.html`（382行）に対するテストは HTML の文字列包含チェック8件のみで、録音長・WAVエンコード（チャネル数/ビット深度/サンプルレート）・結果描画ロジックは1行も実行されていない。B4/B5/B6 の FAIL はこのテスト空白の別表現であり、JavaScript を実行するテスト基盤がないことが構造的な原因と観測される。
