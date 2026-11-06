# Daily Product Lab

専門研究と実際の事業運営の両方から課題を拾い、AIとソフトウェアで小さく検証する公開実験です。

## 運用リズム

- 毎日: 調査、制作途中、ツール、結果、振り返りのいずれかを公開する
- 毎週: 2つのプロダクトまたはテンプレートを完成させる
- 公開前: Draft PRで本人が事実、動作、権利、導線を確認する
- 4週間後: 顧客反応とブランド反応を分けて評価し、上位領域へ収束する

## 最初の設定

1. このディレクトリをGitHubリポジトリのルートとしてpushする
2. Repository secret `OPENAI_API_KEY` を登録する（ChatGPT契約とは別料金）
3. Settings → Actions → GeneralでActionsによるPR作成を許可する
4. Actionsの `Generate daily draft` を手動実行し、生成されたDraft PRを確認する
5. 安定するまでは定時実行を有効にせず、`workflow_dispatch` で運用する

生成物は `content/drafts/` に置きます。公開先への自動投稿は行いません。

## Codexと変更確認

- Codexでこのリポジトリを開き、`AGENTS.md` と `docs/decisions.md` を作業前に確認します。判断と検証結果は `docs/progress.md` に追記します。
- ローカルではPython 3で `python -m unittest discover -s tests -p 'test_*.py'` と `python scripts/verify.py` を実行します。GitHubの `Verify` ワークフローもPRとmainへのpushで同じ検証を行います。
- 変更はDraft PRで確認します。Codex Code Reviewがリポジトリで有効なら、PRコメントで `@codex review` を依頼します。AIレビューの指摘はテスト結果と差分を照合し、最終判断は人間が行います。

## ローカル反復PoC

`docs/autonomous-loop.json` で目的、編集可能ファイル、最大2回・3分・モデル呼び出し4回・報告トークン25万までを設定しています。Codex CLIは編集可能ファイルの内容と差分をAI推論のためOpenAIへ送ります。今後の実行は `allow_codex_context_transmission` を初期値の `false` で停止します。送信するファイルと内容を本人が確認・承認した場合だけ `true` に変更してください。ブランチ `codex/autonomous-loop-*` 上で、設定変更をコミットして作業ツリーを空にしてから `python scripts/autonomous_loop.py` を実行します。Codex CLIへのログインと、動作するPython 3が必要です。

AIは次の作業指示とファイル全体の修正案をJSONで返します。スクリプトが編集範囲と元ファイルのハッシュを検査して適用し、10件の単体テスト、既存の構造チェック、`git diff --check` を実行します。テスト前後に作業ツリーと保護対象ファイルを照合します。合格後に別のCodexセッションが差分をレビューします。失敗時は最大回数まで再提案し、範囲違反、AI・レビュー不能、時間・回数・トークン上限では停止します。実行ログは `.loop-logs/latest.jsonl` に保存し、過去のログは `.loop-logs/history/` に残します。担当者は検証後に結論を `docs/progress.md` に追記します。

料金の厳密な金額上限はこのスクリプトでは保証できません。モデルごとの課金条件や1回の呼び出し中のトークン数を事前に固定できないためです。呼び出し回数、経過時間、呼び出し後の報告トークンで次の呼び出しを止めます。実行前に `codex login status` でChatGPT契約かAPIキーかを確認し、単発実行後に利用状況を確認してください。APIキー利用は契約内の利用枠とは別料金です。GitHubへのpush、PR作成、公開、外部連絡はスクリプトにありません。

Codexの読み取り専用設定は、読めるファイルを編集可能ファイルだけに限定するものではありません。また、タイムアウト時の子プロセス終了は可能な範囲で試みますが、完全な停止保証ではありません。研究データや認証情報のある環境へ広げる前に、専用の隔離コピーと権限設定が必要です。現在の設定は `false` のままなので通常のAI実行は停止します。

