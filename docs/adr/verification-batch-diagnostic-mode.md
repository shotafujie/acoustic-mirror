# 独立検証レポート: バッチ診断モード（ADR-0004）— 第3回

## 検証対象

- リポジトリ: `/Users/fujiemon/dev/speech/analyze/acoustic-mirror`
- ブランチ: `feature/batch-diagnostic-mode`
- 最新コミット: **`24698ab`**（"Fix what the second verification found in the first round's fixes"）
- 検証時点の `git status --short`: 出力なし（クリーン）
- 検証日: 2026-09-22
- 検証者: 独立検証エージェント（実装コンテキストなし。書き込みはこのレポートファイルのみ）

### 過去のレポートの所在

本ファイルは3回上書きされている。過去分は git 履歴にある。

| 回 | 対象コミット | 保存先 |
|---|---|---|
| 第1回 | `040561e` | `git show c57ebbd:docs/adr/verification-batch-diagnostic-mode.md` |
| 第2回 | `58abeed` | `git show 24698ab:docs/adr/verification-batch-diagnostic-mode.md` |
| 第3回（本文書） | `24698ab` | 本ファイル |

**第2回レポートが改変されずに記録されたことを確認した。** `24698ab` はこのファイルを361行変更しているが、これは私が作業ツリーに書いた第2回レポートがそのままコミットされたものである（行数246が私の書き出し時と一致、全17個の節見出しと判定サマリの数値「| PASS | 23 | **35** |」が原文のまま、「訂正作業が、閉じた穴の隣に新しい穴を開けている」「ここだけは妥当でない」といった実装者に不利な記述も削られていない）。

### 依頼されたコミット番号との相違（事実として記録）

依頼では対象を `fe844e2` としていたが、ブランチの HEAD は `24698ab` である。`fe844e2` はオブジェクトとしては存在するがどのブランチからも参照されておらず、`git diff 24698ab fe844e2` は**出力なし＝ツリーが完全に同一**である（コミットメッセージも同一。amend による重複と観測される）。検証対象の内容は依頼されたものと一致するため、`24698ab` に対して検証した。

### 前回からの差分

```
$ git diff --stat 58abeed..HEAD
 docs/adr/ADR-0004-batch-diagnostic-mode.md     |  14 +-
 docs/adr/verification-batch-diagnostic-mode.md | 361 +++++++++++++------------
 tests/test_batch_diagnostic.py                 |  63 +++--
 3 files changed, 240 insertions(+), 198 deletions(-)
```

```
$ git diff --name-only 58abeed..HEAD -- src/
（出力なし）
```

**実装コード（`src/`）は3回の検証を通じて1バイトも変更されていない。** 変更はテスト・合成ハーネス・ADR・検証レポートのみ。

## 判定サマリ

| 判定 | 第1回 `040561e` | 第2回 `58abeed` | 第3回 `24698ab` |
|------|------|------|------|
| PASS | 23 | 35 | **38** |
| FAIL | 17 | 7 | **4** |
| BLOCKED | 3 | 3 | **3** |
| 約束の総数 | 43 | 45 | **45** |

今回 FAIL → PASS に変わったのは **I4 / D2b / V5b の3件**。残る FAIL 4件は **B4 / B5 / B6（ブラウザJS層）と I5（READMEの記述）** で、いずれも「テストが存在しない」ことによるものであり、ADR が「検証されていない領域（既知）」節で明示的に未検証と認め、JSテスト基盤の導入を別ADRに切り出すと宣言している範囲と一致する。

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
collecting ... collected 267 items
```

今回変更・追加された行の実際の出力:

```
tests/test_batch_diagnostic.py::TestDecayEventGating::test_sub_100ms_decay_is_not_an_event PASSED [ 13%]
tests/test_batch_diagnostic.py::TestNoiseFloorAndSpeech::test_speech_threshold_is_the_one_speech_detector_uses PASSED [ 14%]
tests/test_batch_diagnostic.py::TestNoOverallScore::test_no_mos_conversion_in_the_source PASSED [ 20%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[1-1.5-1.0-7.0] PASSED [ 26%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[1-2.0-0.7-7.0] PASSED [ 26%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[1-2.0-0.7-10.0] PASSED [ 27%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[1-3.0-1.0-10.0] PASSED [ 27%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[1-2.5-0.5-7.0] PASSED [ 28%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2-1.5-1.0-7.0] PASSED [ 28%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2-2.0-0.7-7.0] PASSED [ 28%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2-2.0-0.7-10.0] PASSED [ 29%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2-3.0-1.0-10.0] PASSED [ 29%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[2-2.5-0.5-7.0] PASSED [ 29%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[3-1.5-1.0-7.0] PASSED [ 30%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[3-2.0-0.7-7.0] PASSED [ 30%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[3-2.0-0.7-10.0] PASSED [ 31%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[3-3.0-1.0-10.0] PASSED [ 31%]
tests/test_batch_diagnostic.py::TestSRMRGateJustification::test_pauses_barely_move_srmr[3-2.5-0.5-7.0] PASSED [ 31%]
```

```
... （残り249件の PASSED 行を省略。省略部分は1行も FAILED / ERROR を含まない） ...

============================= 267 passed in 30.77s =============================
EXIT_CODE=0
```

終了コード: `0`。収集267件、**267件すべて PASSED**、failed / error / skipped はゼロ。前回256件から11件増（`test_pauses_barely_move_srmr` が5→15パラメータで+10、`test_speech_threshold_is_the_one_speech_detector_uses` で+1）。**回帰ゼロ。**

## 修正6件の判定

### 1. V5 の ADR 訂正 — **FAIL（V5b）→ PASS。過大な記述は解消された。**

撤回・訂正の内容を実際の差分で確認した。

- 「**この表の数値はテストで再現される**」という断定は**撤回されている**。現在この文字列が ADR に残っているのは、経緯を説明する括弧書きの中で**自らそれを過大記述だったと述べている箇所のみ**である（`grep` で確認）。
- 測定値は元に戻っている: 「1.70〜1.81」「参照値 1.819」「最密3秒窓 1.55〜1.89」がすべて復帰。第2回で指摘した「再測定の記録がないまま範囲を広げ、基準値を削除した」編集は取り消された。
- 「再現される / 再現されない」の分割が、実際のテストと**1対1で照合できる**:

| ADR が「再現される」と書いている項目 | 対応テスト | 実行結果 |
|---|---|---|
| 発話率が 0.7 をまたぐこと | `test_the_old_ratio_gate_would_have_rejected_some_of_them`（`min < 0.7 <= max`） | PASSED |
| 5条件すべてで秒数ゲートなら SRMR が算出されること | `test_srmr_survives_every_realistic_protocol`（5×3=15件） | 全件 PASSED |
| 無音を入れても全区間SRMRが参照から10%以内 | `test_pauses_barely_move_srmr`（5×3=15件） | 全件 PASSED |
| 最密3秒窓の方がばらつきが大きいこと | `test_densest_3s_window_is_the_noisier_alternative` | PASSED |

  **4項目すべてが、書かれたとおりの内容を検査するテストに対応している。過大な項目は見当たらない。**
- 「再現されない: 採用イベント列と RT60 列」が明記され、理由（`synth_speech` の4Hz包絡の谷が減衰イベントとして拾われる）と、それを固定しているテスト（`test_this_harness_cannot_measure_rt60`）が示され、「**この2列を RT60 の精度の主張として読んではいけない**」と読み方まで禁じている。
- 本文の「RT60 は同じクリップで 5〜10 イベントを採用して**真値付近を出している**のに」という記述も、「同じクリップで**減衰イベントは 5〜10 件取れている**のに」に修正されている。このハーネスで支持できない精度の主張が本文からも取り除かれた。
- 一度測定値を書き換えた経緯そのものが ADR に残された。

第2回で私が FAIL とした根拠（(1) 段落内の自己矛盾、(2) 再現不能な列を再現されると書いたこと、(3) 測定値の事後編集）は3つとも解消されている。**V5b を PASS とする。**

### 2. I4（番人テストの走査範囲）— **FAIL → PASS**

`test_no_mos_conversion_in_the_source` PASSED。走査対象が `src.rglob("*")` かつ `suffix in (".py", ".js", ".html")` に広がり、`dashboard/diagnose.html`・`index.html`・`recorder-worklet.js` が範囲に入った。**ADR が名指しで排除した `rToMos()` が実在しうる場所（JavaScript）を、番人が初めて見るようになった。** 正規表現も `\br?_?to_?mos\b|\bmos\b|overall[_ ]?score` に広がり、`rToMos` / `toMos` / `to_mos` / 単独の `mos` / `overall_score` / `overall score` を捕捉する。第2回の FAIL 理由（「守るべき境界の外側を見張っている」）は解消された。

### 3. D2b（`SpeechDetector` と同じマージン）— **FAIL → PASS**

`test_speech_threshold_is_the_one_speech_detector_uses` PASSED。`batch_diagnostic._SPEECH_THRESHOLD_DB` が `SpeechDetector.__init__` の `threshold_db` 既定値と一致することを要求している。

**「既定値を固定して意味があるのか」を独立に確認した。** `grep -rn "SpeechDetector(" src/` の結果、実装側の生成箇所は `main.py:121` の `SpeechDetector(sample_rate=sample_rate)` 1箇所のみで、`threshold_db` は渡されていない。**ストリーミング経路が実際に使っているマージンは既定値そのもの**であり、このテストは正しい値を固定している。

実装側のリテラルが2つあること自体は変わっていないため、「構造的に分岐しえない」状態ではない。しかし約束の内容は「同じマージンを**使う**」＝両者の値が等しいことであり、いま一方を変えれば必ずテストが落ちる。**約束の観測可能な内容は保持されたと判断し、PASS とする。** import による一本化のほうが強いが、それは実装変更を伴う設計判断であり、検証の合否を分ける差ではない。

### 4. `test_pauses_barely_move_srmr` の参照 — **改善を確認（V5a は PASS 継続、根拠が強くなった）**

参照が `apply_reverb(synth_speech(dur=7.0), 0.5)`（RIRシード0・連続信号）から `diagnose(self._clip(burst, **0.0**, dur, seed))`（**同じ RIR シード・同じバースト生成・同じコード経路・gap だけ 0**）に変わった。第2回で指摘した「無音の有無だけでなく部屋の実現値と発話内容も同時に違う」という交絡は解消され、**変数は無音の長さ1つだけ**になった。シードも 1/2/3 の3つになり、docstring と実態の不一致も解消された。

**許容幅10%について判定する。** 比較を公正にした結果、実測最悪値は 5.5% → **7.4%** に上がっている。現在の余裕は 10/7.4 ≒ **1.35倍**で、第2回時点の 10/5.5 ≒ 1.8倍より締まっている。参照側（`gap=0`）も `synth_speech` の4Hz包絡の谷により発話率 0.55〜0.89 にしかならず、完全に無音のない参照はこの生成器から作れない——この限界が docstring と ADR の両方に書かれている。**10%という幅は、この生成器で取りうる最も公正な比較に対する妥当な余裕であり、主張を空洞化させてはいないと判断する。** ただし「7.4%」という数値自体はテストで固定されていない（後述の所見）。

**重要なのは動いた方向である。** 比較を厳密にした結果、数値は著者に**不利な方向**（5.5% → 7.4%）に動いた。それを許容幅の緩和や主張の言い換えで吸収せず、悪化した数値をそのまま ADR と docstring に記録している。第2回で私が警告した「テストを通すために主張を弱める」パターンには**該当しない**。

### 5. `test_sub_100ms_decay_is_not_an_event` の空振り — **解消（D6 は PASS 継続、根拠が強くなった）**

「検出されたイベントを回して長さを見る」形（0件なら無条件に通る）から、`find_decay_events(_decaying_bursts(0.06)) == []` **かつ** `find_decay_events(_decaying_bursts(0.4)) != []` の2本立てになった。**後者が陽性対照として機能し、「何も検出されないから通った」という抜け道を塞いでいる。** 減衰形状も線形ランプから指数減衰に変わり、テスト対象の物理により近くなった。

### 6. ADR「Python層の11件を閉じた」の記述 — **訂正は正確**

「1回目で FAIL 17件」「12件が PASS に変わり、同時に新しい問題が3件見つかった（I4 / D2 / V5）」「いずれも修正済み」という記述は、第2回レポートの判定（FAIL 17 → 12件が PASS、判定を伴う新規問題が I4・D2b・V5b の3件）と一致する。過大な件数主張は解消された。

## 約束ごとの判定（変化のあった行のみ）

| # | 約束 | 第2回 → 第3回 | 根拠 |
|---|------|------|------|
| D2b | 発話閾値は `SpeechDetector` と同じマージン | **FAIL → PASS** | `test_speech_threshold_is_the_one_speech_detector_uses` PASSED。固定対象が既定値であり、かつ `main.py:121` がその既定値で生成していることを確認済み。 |
| I4 | 総合スコア（MOS等）は出さない | **FAIL → PASS** | `test_no_mos_conversion_in_the_source` PASSED。`.py` / `.js` / `.html` を走査し、`rToMos` を含む広いパターンで検査。 |
| V5b | ADR の「表の数値はテストで再現される」 | **FAIL → PASS** | 当該記述は撤回され、「再現される4項目／再現されない2列」に分割。4項目すべてが対応テストと1対1で照合でき、全件 PASSED。 |

上記3件以外の42件（PASS 35件、FAIL 4件、BLOCKED 3件）は判定不変。FAIL 据え置きは **B4 / B5 / B6 / I5**、BLOCKED 据え置きは **I6 / I7 / トレーサビリティ検査**。

## トレーサビリティ検査

`~/dev/.claude/hooks/trace-check.sh` は `docs/items/` が存在しないため **BLOCKED（該当ディレクトリなし）**。3回とも同じ。

## 「閉じた穴の隣に新しい穴を開けていないか」

第2回で私が書いた指摘に対する、今回の最重要の確認点である。変更6件を1件ずつ、**主張が弱められていないか**という観点で見た。

| 変更 | 主張は弱まったか | 判断 |
|---|---|---|
| 測定値を 1.70〜1.83 → 1.70〜1.81 に戻す | いいえ（元に戻しただけ） | 範囲を狭める方向。記録の復元。 |
| 「表の数値は再現される」の撤回 | **主張は狭まった。ただし正しい方向。** | 撤回されたのは**元から成立していなかった主張**。成立していた4項目は残り、テストと照合可能。成立していない2列は「読んではいけない」と明示。虚偽を削るのは弱化ではない。 |
| 本文の「真値付近を出している」削除 | **主張は狭まった。ただし正しい方向。** | 同上。このハーネスで支持不能な精度主張の削除。RT60 精度の担保は V1（平坦バーストharness）に残っており、そちらは12件のテストで ±15% が固定されたまま。 |
| SRMR 参照を `gap=0` に変更 | **いいえ。逆に厳しくなった。** | 交絡を除いた結果、実測最悪値が 5.5% → 7.4% に悪化。許容幅を緩めず、悪化した数値をそのまま記録。 |
| I4 パターン・走査範囲の拡大 | いいえ | 検査対象が広がった。純粋な強化。 |
| `test_sub_100ms` に陽性対照を追加 | いいえ | 抜け道を塞いだ。純粋な強化。 |
| D2b テストの追加 | いいえ | 検査が1つ増えた。 |

**テストを通すために主張を弱めた箇所は見当たらない。** 主張が狭まった2箇所は、いずれも「元から成立していなかった主張を取り下げた」ものであり、取り下げの理由と経緯が ADR に残されている。今回の修正は、第2回で指摘した「閉じた穴の隣に新しい穴を開ける」パターンを**繰り返していない**。

## 所見

### まだ残っている、ごく小さな過大記述（判定は動かさない）

- **ADR の「再現される」リストの中に、テストで固定されていない生の数値が1つ混ざっている。** 「…10%以内に留まること（5条件×3シードでの**実測最悪値 7.4%**）」の 7.4% は、テストが検査しているのは `<= 0.10` であって 7.4% ではない。仮に将来の変更で最悪値が 9% に動いてもテストは通り、ADR の「7.4%」は静かに古くなる。同じ数値が `test_pauses_barely_move_srmr` の docstring にもあり、そちらも同様。これは第2回で指摘した「測定値が ADR に書かれているがテストで固定されていない」構図の**残り香**である。ただし今回は (a) テストの上界の内側にある値であること、(b) 「実測値」と明示されていること、(c) 上界そのものは固定されていること、の3点から、記述として過大とまでは言えない。**唯一、「再現される」と題したリストの中に置かれている点だけが惜しい。**
- **表の「採用イベント」「RT60」2列は数値が残ったままである。** 真値 0.5s に対し 0.558〜0.584 という、見た目には精度の主張に読める数値が、`真値 RT60=0.5s` と書かれた表の中に並んでいる。ADR は太字で「この2列を RT60 の精度の主張として読んではいけない」と禁じており、対応としては十分だが、列そのものに取り消し線なり `（再現不能）` なりの印がない限り、表だけを見た読者は禁止文まで辿り着かない可能性がある。判定には影響しない体裁の指摘である。
- **「参照」という語が、節の中で2つの異なる対象を指している。** 本文（復元された初回測定）の「無音なし連続7秒の参照値 1.819」は連続 `synth_speech` を指し、リストの「同じクリップから無音を抜いた参照」は `gap=0` のクリップ（発話率 0.55〜0.89 で無音は残る）を指す。両者は別物である。ADR はリストの3点目で「絶対値はシードで変わる／テストが見ているのは相対的な主張」と切り分けており誤りではないが、近接する2箇所で同じ語が別の対象を指している。

### 今回の修正で残っていない問題（第2回の所見からの消化状況）

第2回で挙げた9件の所見のうち、判定を伴っていた3件（I4 / D2b / V5b）はすべて解消。判定を伴わない所見のうち、**参照の二重の違い・docstring と実態の不一致・空振りしうるテスト**の3件も解消された。**未消化として残るのは次の2件**（いずれも第2回時点で判定に影響しないと明記したもの）:

- `test_early_to_late_is_the_median_not_the_mean` が実装側の `_isolated_onsets` をテスト内にほぼ再実装している。実装との乖離は検出できるが、実装とテストが同じ勘違いをしている場合は検出できない。
- ADR の V4 節が挙げる具体値（中央値 1.017 / 70% 1.037）はアサートされていない。「例」と明記されているため過大主張ではない。

### 総括

3回の検証を通じて**実装コードは1バイトも変わっていない**。変わったのは、テストが何を保証しているかと、ADR が何を主張しているかの一致度だけである。第1回で FAIL 17件だったものが、第2回で7件、今回4件になった。残る4件（B4 / B5 / B6 / I5）は「ブラウザ JavaScript を実行するテスト基盤が無い」「文章の内容はテスト対象にならない」という、テストを1つ書けば閉じる類のものではない構造的な欠落であり、ADR 自身が未検証領域として明示し、別ADRに切り出すと宣言している。

特筆すべきは、比較を公正にしたら自分に不利な数値（5.5% → 7.4%）が出たときに、それを許容幅の緩和や表現の調整で吸収せず、悪化した数値をそのまま記録した点である。検証に対して数字を合わせにいく動きは、今回の差分には観測されなかった。
