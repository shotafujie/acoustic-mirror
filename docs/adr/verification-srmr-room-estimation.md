# 独立検証レポート: SRMR / RT60 / DRR 是正（ADR-0001, ADR-0002, ADR-0003）

## 検証対象

- リポジトリ: `/Users/fujiemon/dev/speech/analyze/acoustic-mirror`
- ブランチ: `feature/srmr-and-room-estimation-validity`（検証時点で `git status` はクリーン、最新コミット `ef87b96`）
- 検証者: 独立検証エージェント（実装コンテキストなし、Edit/Write はこのレポートファイルのみに使用）

## 制約条件（トレーサビリティの鎖について）

本アイテムでは、ユーザーの明示的指示（「ADRを書いて実装」）により **仕様策定（`skills/spec`）とテスト設計（`skills/test-design`）の工程が意図的にスキップされ**、ADR（Architecture Decision Record）から直接実装に入っている。そのため:

- `docs/items/` ディレクトリは存在しない。
- `TC-NNN-M` 形式のテストIDは存在しない。
- 通常のトレーサビリティの鎖（仕様 ⇄ テスト設計 ⇄ 検証）は本来の形で存在しない。

この検証では、代替の「守ると宣言したこと」の根拠として以下3件のADRの「決定」「設計」節を使用した。各ADRから検証すべき個別の約束を独立にリストアップし（実装コードを読む前に列挙）、それぞれについてテスト実行結果のみを根拠にPASS/FAIL/BLOCKEDを判定した。

- `docs/adr/ADR-0001-srmr-align-with-reference-implementation.md`
- `docs/adr/ADR-0002-decouple-srmr-window-from-feedback-interval.md`
- `docs/adr/ADR-0003-rt60-drr-estimation-validity.md`

`hooks/trace-check.sh` は `docs/items/` が存在しないため **BLOCKED（該当ディレクトリなし）** として記録する（実行を試みず、対象ディレクトリの不在により構造的に実行不可と判断）。

## テストスイート全体の実行結果

```
cd /Users/fujiemon/dev/speech/analyze/acoustic-mirror && source .venv/bin/activate && python -m pytest -v
```

```
============================= test session starts ==============================
platform darwin -- Python 3.13.12, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/fujiemon/dev/speech/analyze/acoustic-mirror
configfile: pyproject.toml
testpaths: tests
plugins: cov-7.1.0, asyncio-1.3.0
collected 150 items

... (全150件、下記PASS判定の根拠として個別に参照したテストを含む) ...

============================= 150 passed in 3.28s ==============================
```

終了コード: `0`。150件全て `PASSED`、失敗・エラーなし。

## 約束ごとの判定

### ADR-0001: SRMRをSRMRpy準拠の方向に寄せ、閾値を実測で引き直す

| # | 約束（決定/設計節より） | 判定 | 根拠 |
|---|---|---|---|
| 1 | 包絡ダウンサンプリングを `env[::N]`（ナイーブストライド）から `scipy.signal.decimate` によるアンチエイリアス処理に置き換える（issue #4） | **PASS** | `src/acoustic_mirror/analysis/srmr.py` の `compute_modulation_energy` が `scipy.signal.decimate(..., ftype="fir", zero_phase=True)` を使用。`tests/test_srmr.py::TestModulationEnergy::test_high_frequency_envelope_content_does_not_alias_into_modulation_bands` が300Hzエイリアシングプローブの漏れエネルギーが参照エネルギーの1%未満であることを検証し、PASSED。 |
| 2 | 変調スペクトルFFT前にHann窓を掛け、低変調帯域から高変調帯域へのスペクトル漏れを抑える（issue #5） | **FAIL** | コードは `np.hanning(n_fft)` を適用している（`srmr.py:151`）ことをコードリーディングで確認したが、**この窓関数によるスペクトル漏れ抑制効果を独立に検証するテストが存在しない**。`test_srmr.py` 内に "leak" / "window" / "hann" を検証するテストケースは、アンチエイリアス用の1件（上記#1）のみで、窓関数の効果を単体で確認するテストはない。テストが存在しない以上PASSにはできない。 |
| 3 | 「Reference: Falk et al. (2010)」の表記を「原法の簡略実装であり絶対値は一致しない」に修正し、K\*固定・変調帯域上限100Hz(docstring)の差分を明記する（issue #6） | **FAIL** | `srmr.py` のモジュールdocstring・`_modulation_filterbank_centers`のdocstringに該当する記述（簡略化の明記、docs/adr/ADR-0001参照）があることをコードリーディングで確認したが、**ドキュメント文言の正しさを検証する自動テストは存在しない**。この約束はテストで検証可能な性質のものではなく、構造的にFAILとなる。 |
| 4 | 検証ハーネス（`synth_speech()` / `synth_rir()`）を#4より前に用意し、実測とテストの両方の計測器として使う（issue #10） | **PASS** | `tests/synth.py` に `synth_speech`, `synth_rir`, `apply_reverb` が実装されている。`tests/test_srmr.py::TestSRMRValidityAgainstSyntheticReverb::test_srmr_decreases_as_rt60_increases` がこのハーネスを import して使用し、PASSED。 |
| 5 | #4/#5/#2適用後の分布を実測し、`_SRMR_TARGETS` をその分布に基づいて設定する | **FAIL** | `room_profiler.py` の `_SRMR_TARGETS` にADRの実測条件（3秒窓、5条件）に対応するコメントと具体的な数値（QUIET_SMALL=3.3等）が記載されていることをコードリーディングで確認したが、**この具体的な数値そのものを検証するテストが存在しない**。`tests/test_room_profiler.py::TestRoomClassification::test_all_room_types_have_srmr_target` は「値が0より大きい」ことしか検証しておらず、実測分布に基づいて設定されたことの検証にはならない。 |

### ADR-0002: SRMR解析窓をVAD/フィードバック更新間隔から分離する

| # | 約束 | 判定 | 根拠 |
|---|---|---|---|
| 1 | `SRMR_WINDOW_SAMPLES = 3 * SAMPLE_RATE` で2本目の`RingBuffer`を追加する | **PASS** | `main.py` に定数定義あり、`_run()` で `srmr_buf = RingBuffer(window_size=SRMR_WINDOW_SAMPLES)` を生成。`tests/test_capture.py::TestAudioCapture::test_callback_writes_to_srmr_buffer` PASSED。 |
| 2 | `open_stream()` を `Sequence[RingBuffer]` ではなく `vad_buffer: RingBuffer, srmr_buffer: RingBuffer` の明示引数にする | **PASS** | `src/acoustic_mirror/audio/capture.py` の `open_stream` シグネチャが明示引数。`test_callback_writes_to_vad_buffer` / `test_callback_writes_to_srmr_buffer` の両方がPASSED、コールバックが両バッファへ書き込むことを個別に検証している。 |
| 3 | `AnalysisPipeline` が直近`is_speech`履歴を`deque(maxlen=6)`で保持する | **PASS** | `main.py` の `AnalysisPipeline.__init__` で `self._srmr_speech_history: deque[bool] = deque(maxlen=_SRMR_HISTORY_LEN)`、`_SRMR_HISTORY_LEN = 6`。ゲート挙動は下記#4のテストで間接検証。 |
| 4 | ゲート判定を状態を持たない純粋関数 `should_recompute_srmr(recent_speech_ratio, seconds_since_last_compute, buffer_full)` として実装し、70%閾値・1秒間引きの条件を変更しない | **PASS** | `tests/test_main.py::TestShouldRecomputeSrmr::test_true_on_boundary_values` PASSED（純粋関数自体の境界値テスト）。加えて `TestAnalysisPipeline::test_pipeline_skips_srmr_when_no_speech_initially`、`test_pipeline_does_not_compute_srmr_without_a_full_window`、`test_pipeline_computes_srmr_for_speech`、`test_pipeline_does_not_recompute_srmr_before_gate_interval` が全てPASSED、パイプライン経由のゲート挙動も検証済み。 |
| 5 | 持ち越しスコアの鮮度を示す `age_seconds` を `AnalysisResult` に追加する | **PASS** | `AnalysisResult.srmr_age_seconds` フィールドが存在し、`to_dict()` にも出力。`tests/test_main.py`（`test_srmr_persists_across_silence` 内、L97）で `second.srmr_age_seconds >= first.srmr_age_seconds` を検証、PASSED。 |
| 6 | 500msの主ループ・VAD/RT60/DRRロジックは変更しない | **PASS** | `main.py` の `CHUNK_SAMPLES = 8000`（500ms）が維持され、RT60推定は引き続き500msチャンク（`_prev_chunk`）ベース。`test_rt60_uses_prev_chunk_decay`、`test_rt60_estimation_is_reachable_across_utterance_end_phase` PASSED。 |

### ADR-0003: RT60/DRR推定を前提の成立する条件に限定して是正する

| # | 約束 | 判定 | 根拠 |
|---|---|---|---|
| 1 | RT60推定をSchroeder積分に置き換え、生波形ではなく既存の10msフレームエネルギー配列に適用する | **PASS** | `room_profiler.py::estimate_rt60_from_decay` が `energies`（10msフレーム配列）に対し `np.cumsum(energies[::-1])[::-1]` を適用。`TestRT60Estimation::test_known_rt60_short/medium/long`、`test_clean_decay_has_high_confidence` 全てPASSED。 |
| 2 | Schroeder積分末尾の打ち切り誤差（knee）対策として、割合ではなく固定時間（50ms）でトリムする | **PASS** | `_RT60_SCHROEDER_TAIL_TRIM_MS = 50.0` が定数として実装。`TestRT60Estimation::test_short_windows_are_accurate_or_self_reject`（100/120/150/200/300/500msでパラメタライズ）と `test_truncated_decay_stays_within_tolerance` が全てPASSED。 |
| 3 | 回帰区間をT20（-5dB〜-25dB）に限定し60dBに外挿、T10等へのフォールバックはせず`is_valid=False`とする | **PASS** | コードはT20マスクのみを使用しフォールバックロジックがない。`test_too_short_signal_is_invalid` PASSED（フォールバックせず無効化されることを確認）。 |
| 4 | 信頼度は`linregress`の`rvalue`を再利用し`rvalue**2`とする。別途R²計算を追加しない | **FAIL** | コードは `stats.linregress` の戻り値から `confidence = float(rvalue**2)` を計算しており二重計算はないことをコードリーディングで確認したが、**「二重計算が存在しないこと」自体を検証するテストは存在しない**（信頼度の数値が妥当であることを検証するテストはあるが、それは計算方法の一意性を証明しない）。 |
| 5 | `_extract_decay_segment`の最低減衰長を50ms→100msに引き上げる | **PASS** | `main.py::_extract_decay_segment` に `if len(decay) < int(self._sample_rate * 0.1): return None` を確認。`test_rt60_estimation_is_reachable_across_utterance_end_phase` PASSED（到達可能性の実測テスト）。 |
| 6 | `estimate_rt60_from_decay`の戻り値型変更（`RT60Estimate`dataclass）を`RoomProfiler.update_rt60`内部に閉じ込め、`_rt60_estimates`は`deque[float]`のまま維持する | **FAIL** | コードリーディングでは `RoomProfiler._rt60_estimates: deque[float] = deque(maxlen=5)` が維持され、`update_rt60`内で`RT60Estimate`を受けて`.rt60`のみをdequeに追加していることを確認したが、**この型の閉じ込めそのものを検証するテスト（型チェックや外部露出がないことの検証）は存在しない**。 |
| 7 | `RoomProfiler`に`_last_rt60_confidence`を新設し、直近の採用済み推定の信頼度で上書きする | **PASS** | `tests/test_room_profiler.py`（L206, L213, L228, L230付近）で `rt60_confidence` の存在・高信頼値・低信頼推定が反映されないことを検証。`tests/test_main.py:200`の`profile.rt60_confidence > 0.9`も含め全てPASSED。 |
| 8 | R²閾値 `RT60_CONFIDENCE_MIN=0.5` でゲートし、下回る推定は`_rt60_estimates`に追加しない | **PASS** | `TestRoomProfiler::test_low_confidence_estimate_does_not_update_rt60` PASSED。 |
| 9 | `estimate_drr` → `estimate_early_to_late_ratio` へリネーム | **PASS** | `room_profiler.py` に旧名`estimate_drr`は存在せず、`estimate_early_to_late_ratio`のみ。`TestEarlyToLateRatio::test_pure_direct_sound_high_ratio`等3件がPASSED。 |
| 10 | `RoomProfile.drr_db` → `early_to_late_ratio_db` へリネームし、`cause_separator.py`・`dashboard/index.html`の消費箇所も更新する | **PASS** | `grep`の結果、`src/`全体で`drr_db`という文字列は存在せず、`early_to_late_ratio_db`に統一済み（`cause_separator.py:57`、`dashboard/index.html:280`含む）。`TestRoomProfiler::test_update_early_to_late_ratio`PASSED。 |
| 11 | オンセット直前200ms無音の「孤立立ち上がりゲート」を`AnalysisPipeline`（main.py）側に実装する | **PASS** | `main.py::_is_isolated_onset`に実装。`test_isolated_onset_gate_allows_onset_after_genuine_silence`、`test_isolated_onset_gate_blocks_onset_after_trailing_speech`、`test_early_to_late_ratio_not_updated_on_non_isolated_onset` 全てPASSED。 |
| 12 | `RoomProfile`に`rt60_confidence`フィールドを追加する | **PASS** | `RoomProfile`dataclassに`rt60_confidence: float = 0.0`が存在。上記#7のテストで併せて検証されPASSED。 |

## トレーサビリティ検査

`hooks/trace-check.sh`（`~/dev/.claude/hooks/trace-check.sh`）は `docs/items/` ディレクトリが存在しないため **BLOCKED（該当ディレクトリなし）**。実行は試みていない（対象ディレクトリの構造的不在により実行不可と判断したため）。

## 集計

- PASS: 18件
- FAIL: 5件
- BLOCKED: 1件（トレーサビリティ検査）

## 所見

- FAILと判定した5件はいずれも「コードを読む限りADRの記述通りに実装されている」ことをコードリーディングで確認済みである。しかし本検証の判定基準は「テスト実行結果のみ」であり、これらはいずれも**対応する自動テストが存在しない**ため、疑わしきをPASSにしないという制約に従いFAILとした。内訳:
  - Hann窓によるスペクトル漏れ抑制効果（issue #5）を直接検証するテストがない。アンチエイリアス（issue #4）には専用テストがあるのに対し、窓関数には対になるテストが欠けている。
  - docstringの記述内容（Falk et al.との差分の明記）はテスト対象になり得ない性質の約束であり、構造的に「検証するテストが存在しない」に該当する。
  - `_SRMR_TARGETS`の具体的な数値がADR記載の実測分布と一致していることを検証するテストがない（存在テストのみ）。
  - RT60信頼度計算の「二重計算をしない」という実装方針、および`RT60Estimate`型を`RoomProfiler`内部に閉じ込めるという設計方針は、いずれも実装の内部構造に関する約束であり、外部から観測可能な振る舞いのテストでは直接検証できない。
- ADR-0003の「実装時に判明した既知の限界」節（長いRT60の系統的過小評価、Schroeder積分が定数/緩増加信号でも有限値を返しうる限界）はADR自体が「許容するリスク」として明記しており、これらに対応する規約違反ではないため判定対象に含めていない。
- テストスイート全体は150件全てPASSEDで、実行自体に問題はなかった。FAIL判定はテストの失敗によるものではなく、「約束を検証するテストの不在」による。
