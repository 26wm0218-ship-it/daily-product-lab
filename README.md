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
