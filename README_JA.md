<div align="center"><a name="readme-top"></a>

[![][image-head]][hanggent-site]

[![][image-seperator]][hanggent-site]

### Hanggent: 卓越した生産性を実現するオープンソースのコワークデスクトップ

<!-- SHIELD GROUP -->

[![][download-shield]][hanggent-download]
[![][github-star]][hanggent-github]
[![][social-x-shield]][social-x-link]
[![][discord-image]][discord-url]<br>
[![][join-us-image]][join-us]

</div>

<hr/>
<div align="center">

[English](./README.md) · [Português](./README_PT-BR.md) · [简体中文](./README_CN.md) · **日本語** · [公式サイト][hanggent-site] · [ドキュメント][docs-site] · [フィードバック][github-issue-link]

</div>
<br/>

**Hanggent**は、オープンソースのコワークデスクトップアプリケーションです。複雑なワークフローを自動化タスクに変換できるカスタムAIワークフォースを構築、管理、デプロイする力を提供します。

**マルチエージェントワークフォース**を導入し、並列実行、カスタマイズ、プライバシー保護を通じて**生産性を向上**させます。

### ⭐ 100%オープンソース - 🥇 ローカルデプロイメント - 🏆 MCP統合

- ✅ **ゼロセットアップ** - 技術的な設定は不要
- ✅ **マルチエージェント連携** - 複雑なマルチエージェントワークフローを処理
- ✅ **エンタープライズ機能** - SSO/アクセス制御
- ✅ **ローカルデプロイメント**
- ✅ **オープンソース**
- ✅ **カスタムモデルサポート**
- ✅ **MCP統合**

<br/>

[![][image-join-us]][join-us]

<details>
<summary><kbd>目次</kbd></summary>

#### TOC

- [🚀 はじめに](#-はじめに)
  - [🏠 ローカルデプロイメント（推奨）](#-ローカルデプロイメント推奨)
  - [⚡ クイックスタート（クラウド接続）](#-クイックスタートクラウド接続)
  - [🏢 エンタープライズ](#-エンタープライズ)
  - [☁️ クラウドバージョン](#️-クラウドバージョン)
- [✨ 主な機能](#-主な機能)
  - [🏭 ワークフォース](#-ワークフォース)
  - [🧠 包括的なモデルサポート](#-包括的なモデルサポート)
  - [🔌 MCPツール統合](#-mcpツール統合)
  - [✋ ヒューマンインザループ](#-ヒューマンインザループ)
  - [👐 100%オープンソース](#-100オープンソース)
- [🧩 ユースケース](#-ユースケース)
- [🛠️ 技術スタック](#️-技術スタック)
  - [バックエンド](#バックエンド)
  - [フロントエンド](#フロントエンド)
- [🌟 最新情報を入手](#最新情報を入手)
- [🗺️ ロードマップ](#️-ロードマップ)
- [📖 コントリビューション](#-コントリビューション)
- [エコシステム](#エコシステム)
- [📄 オープンソースライセンス](#-オープンソースライセンス)
- [🌐 コミュニティ & お問い合わせ](#-コミュニティ--お問い合わせ)

####

<br/>

</details>

## **🚀 はじめに**

> **🔓 オープンに開発** — Hanggentは初日から**100%オープンソース**です。すべての機能、すべてのコミット、すべての決定が透明です。最高のAIツールは、閉じられたドアの後ろではなく、コミュニティと共にオープンに構築されるべきだと信じています。

### 🏠 ローカルデプロイメント（推奨）

Hanggentを実行する推奨方法 — データを完全に制御でき、クラウドアカウント不要で完全にスタンドアロンで動作します。

👉 **[ローカルデプロイメント完全ガイド](./server/README_EN.md)**

このセットアップには以下が含まれます：
- 完全なAPIを備えたローカルバックエンドサーバー
- ローカルモデル統合（vLLM、Ollama、LM Studioなど）
- クラウドサービスからの完全な分離
- 外部依存ゼロ

### ⚡ クイックスタート（クラウド接続）

クラウドバックエンドを使用した簡単なプレビュー — 数秒で開始できます：

#### 前提条件

- Node.js（バージョン18-22）およびnpm

#### 手順

```bash
git clone https://github.com/hanggent-ai/hanggent.git
cd hanggent
npm install
npm run dev
```

> 注：このモードはHanggentクラウドサービスに接続し、アカウント登録が必要です。完全にスタンドアロンで使用する場合は、代わりに[ローカルデプロイメント](#-ローカルデプロイメント推奨)を使用してください。

### 🏢 エンタープライズ

最大限のセキュリティ、カスタマイズ、制御を必要とする組織向け：

- **限定機能**（SSO & カスタム開発など）
- **スケーラブルなエンタープライズデプロイメント**
- **交渉可能なSLA** & 導入サービス

📧 詳細については、[redpanda321@gmail.com](mailto:redpanda321@gmail.com) までお問い合わせください。

### ☁️ クラウドバージョン

マネージドインフラストラクチャを好むチーム向けに、クラウドプラットフォームも提供しています。セットアップの複雑さなしにHanggentのマルチエージェントAI機能を体験する最速の方法です。モデル、API、クラウドストレージをホストし、Hanggentがシームレスに動作することを保証します。

- **即時アクセス** - 数分でマルチエージェントワークフローの構築を開始。
- **マネージドインフラストラクチャ** - スケーリング、更新、メンテナンスを私たちが処理。
- **プレミアムサポート** - サブスクリプションでエンジニアリングチームからの優先サポートを受けられます。

<br/>

[![image-public-beta]][hanggent-download]

<div align="right">
<a href="https://www.hangent.com/download">Hangent.comで始める →</a>
</div>

## **✨ 主な機能**
Hanggentの強力な機能で卓越した生産性の可能性を最大限に引き出しましょう — シームレスな統合、よりスマートなタスク実行、無限の自動化のために構築されています。

### 🏭 ワークフォース
複雑なタスクを解決するために協力する専門AIエージェントのチームを活用します。Hanggentは動的にタスクを分解し、複数のエージェントを**並列で**動作させます。

Hanggentは以下のエージェントワーカーを事前定義しています：

- **Developer Agent:** コードを書いて実行し、ターミナルコマンドを実行します。
- **Browser Agent:** ウェブを検索し、コンテンツを抽出します。
- **Document Agent:** ドキュメントを作成・管理します。
- **Multi-Modal Agent:** 画像と音声を処理します。

![Workforce](https://hanggent-ai.github.io/.github/assets/gif/feature_dynamic_workforce.gif)

<br/>

### 🧠 包括的なモデルサポート
お好みのモデルでHanggentをローカルにデプロイできます。

![Model](https://hanggent-ai.github.io/.github/assets/gif/feature_local_model.gif)

<br/>

### 🔌 MCPツール統合
Hanggentには大規模な組み込み**Model Context Protocol（MCP）**ツール（ウェブブラウジング、コード実行、Notion、Google suite、Slackなど）が付属しており、**独自のツールをインストール**することもできます。エージェントにシナリオに適したツールを装備させ、内部APIやカスタム関数を統合して機能を強化できます。

![MCP](https://hanggent-ai.github.io/.github/assets/gif/feature_add_mcps.gif)

<br/>

### ✋ ヒューマンインザループ
タスクが行き詰まったり不確実性に遭遇した場合、Hanggentは自動的に人間の入力を要求します。

![Human-in-the-loop](https://hanggent-ai.github.io/.github/assets/gif/feature_human_in_the_loop.gif)

<br/>

### 👐 100%オープンソース
Hanggentは完全にオープンソースです。コードをダウンロード、検査、修正でき、透明性を確保し、マルチエージェントイノベーションのためのコミュニティ主導のエコシステムを育成します。

![Opensource][image-opensource]

<br/>

## 🧩 ユースケース

### 1. パームスプリングステニス旅行の旅程とSlackサマリー [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTM0MzUxNTEzMzctNzExMyI.aIeysw.MUeG6ZcBxI1GqvPDvn4dcv-CDWw__1753435151337-7113)

<details>
<summary><strong>プロンプト:</strong> <kbd>私たちは2人のテニスファンで、パームスプリングス2026のテニストーナメントを見に行きたいです...</kbd></summary>
<br>
私たちは2人のテニスファンで、パームスプリングス2026のテニストーナメントを見に行きたいです。私はサンフランシスコに住んでいます。準決勝/決勝の時期に合わせて、3日間のフライト、ホテル、アクティビティを含む詳細な旅程を準備してください。私たちはハイキング、ヴィーガン料理、スパが好きです。予算は5,000ドルです。旅程は、時間、アクティビティ、コスト、その他の詳細、および該当する場合はチケット購入/予約リンクを含む詳細なタイムラインにしてください。スパへのアクセスはあれば嬉しいですが、必須ではありません。このタスクが完了したら、この旅行に関するHTMLレポートを生成し、計画の要約とレポートHTMLリンクをSlackの#tennis-trip-sfチャンネルに送信してください。
</details>

<br>

### 2. CSVバンクデータからQ2レポートを生成 [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTM1MjY4OTE4MDgtODczOSI.aIjJmQ.WTdoX9mATwrcBr_w53BmGEHPo8U__1753526891808-8739)

<details>
<summary><strong>プロンプト:</strong> <kbd>銀行振込記録ファイルに基づいてQ2財務諸表を準備してください...</kbd></summary>
<br>
デスクトップにあるbank_transacation.csvの銀行振込記録ファイルに基づいて、投資家向けに支出額をチャート付きHTMLレポートにまとめたQ2財務諸表を準備してください。
</details>

<br>

### 3. 英国ヘルスケア市場調査レポートの自動化 [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTMzOTM1NTg3OTctODcwNyI.aIey-Q.Jh9QXzYrRYarY0kz_qsgoj3ewX0__1753393558797-8707)

<details>
<summary><strong>プロンプト:</strong> <kbd>次の会社の計画をサポートするために、英国のヘルスケア業界を分析してください...</kbd></summary>
<br>
次の会社の計画をサポートするために、英国のヘルスケア業界を分析してください。現在のトレンド、成長予測、関連規制を含む包括的な市場概要を提供してください。市場内の主要な機会、ギャップ、またはサービスが行き届いていないセグメントのトップ5-10を特定してください。すべての調査結果を、よく構成されたプロフェッショナルなHTMLレポートで提示してください。その後、タスクが完了したらSlackの#hanggentr-product-testチャンネルにメッセージを送信し、チームメイトとレポート内容を共有してください。
</details>

<br>

### 4. ドイツの電動スケートボード市場実現可能性調査 [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTM2NTI4MjY3ODctNjk2Ig.aIjGiA.t-qIXxk_BZ4ENqa-yVIm0wMVyXU__1753652826787-696)

<details>
<summary><strong>プロンプト:</strong> <kbd>私たちは高級電動スケートボードを製造する会社で、ドイツ市場への参入を検討しています...</kbd></summary>
<br>
私たちは高級電動スケートボードを製造する会社で、ドイツ市場への参入を検討しています。詳細な市場参入実現可能性レポートを準備してください。レポートは以下の側面をカバーする必要があります：
1. 市場規模と規制：ドイツにおける個人用軽量電動車両（PLEV）の市場規模、年間成長率、主要プレーヤー、市場シェアを調査してください。同時に、ABE認証などの認証要件や保険ポリシーを含む、公道での電動スケートボード使用に関するドイツの法律と規制の詳細な内訳と要約を提供してください。
2. 消費者プロファイル：潜在的なドイツの消費者のプロファイルを分析してください。年齢、収入レベル、主な使用シナリオ（通勤、レクリエーション）、主な購買決定要因（価格、性能、ブランド、デザイン）、情報収集に使用するチャネル（フォーラム、ソーシャルメディア、オフライン小売店）を含めてください。
3. チャネルと流通：ドイツの主流オンライン電子機器販売プラットフォーム（Amazon.de、MediaMarkt.deなど）と高級スポーツ用品オフライン小売チェーンを調査してください。潜在的なオンラインおよびオフライン流通パートナーのトップ5をリストアップし、可能であれば購買部門の連絡先情報を見つけてください。
4. コストと価格設定：デスクトップのProduct_Cost.csvファイルにある製品コスト構造に基づき、ドイツの関税、付加価値税（VAT）、物流・倉庫コスト、潜在的なマーケティング費用を考慮して、メーカー希望小売価格（MSRP）を見積もり、市場での競争力を分析してください。
5. 包括的なレポートとプレゼンテーション：すべての調査結果をHTMLレポートファイルにまとめてください。内容にはデータチャート、主要な調査結果、最終的な市場参入戦略の推奨（推奨/非推奨/条件付き推奨）を含めてください。
</details>

<br>

### 5. Workforce Multiagentローンチ向けSEO監査 [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTM2OTk5NzExNDQtNTY5NiI.aIex0w.jc_NIPmfIf9e3zGt-oG9fbMi3K4__1753699971144-5696)

<details>
<summary><strong>プロンプト:</strong> <kbd>新しいWorkforce Multiagent製品のローンチをサポートするために...</kbd></summary>
<br>
新しいWorkforce Multiagent製品のローンチをサポートするために、公式ウェブサイト（https://www.hangent.com）で徹底的なSEO監査を実行し、実行可能な推奨事項を含む詳細な最適化レポートを提供してください。
</details>

<br>

### 6. ダウンロード内の重複ファイルを特定 [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTM3NjAzODgxNzEtMjQ4Ig.aIhKLQ.epOG--0Nj0o4Bqjtdqm9OZdaqRQ__1753760388171-248)

<details>
<summary><strong>プロンプト:</strong> <kbd>Documentsディレクトリにmydocsというフォルダがあります...</kbd></summary>
<br>
Documentsディレクトリにmydocsというフォルダがあります。スキャンして、完全一致または類似した重複ファイルをすべて特定してください — ファイル名や拡張子が異なっていても、同一のコンテンツ、ファイルサイズ、または形式を持つファイルを含みます。類似性でグループ化して明確にリストしてください。
</details>

<br>

### 7. PDFに署名を追加 [リプレイ ▶️](https://www.hangent.com/download?share_token=IjE3NTQwOTU0ODM0NTItNTY2MSI.aJCHrA.Mg5yPOFqj86H_GQvvRNditzepXc__1754095483452-5661)

<details>
<summary><strong>プロンプト:</strong> <kbd>この署名画像をPDFの署名エリアに追加してください...</kbd></summary>
<br>
この署名画像をPDFの署名エリアに追加してください。このタスクを完了するために、CLIツール'tesseract'（OCRを介した'署名エリア'の信頼性の高い位置特定に必要）をインストールできます。
</details>

<br>

## 🛠️ 技術スタック

### バックエンド
- **フレームワーク:** FastAPI
- **パッケージマネージャー:** uv
- **非同期サーバー:** Uvicorn
- **認証:** OAuth 2.0、Passlib
- **マルチエージェントフレームワーク:** CAMEL

### フロントエンド

- **フレームワーク:** React
- **デスクトップアプリフレームワーク:** Electron
- **言語:** TypeScript
- **UI:** Tailwind CSS、Radix UI、Lucide React、Framer Motion
- **状態管理:** Zustand
- **フローエディター:** React Flow

## 🌟 最新情報を入手

> \[!IMPORTANT]
>
> **Hanggentにスター**を付けると、GitHubからすべてのリリース通知を遅延なく受け取れます ⭐️

![][image-star-us]

## 🗺️ ロードマップ

| トピック | 課題 | Discordチャンネル |
| ------------------------ | -- |-- |
| **コンテキストエンジニアリング** | - プロンプトキャッシング<br> - システムプロンプト最適化<br> - ツールキットdocstring最適化<br> - コンテキスト圧縮 | [**Discordに参加 →**](https://discord.gg/D2e3rBWD) |
| **マルチモーダル強化** | - ブラウザ使用時のより正確な画像理解<br> - 高度な動画生成 | [**Discordに参加 →**](https://discord.gg/kyapNCeJ) |
| **マルチエージェントシステム** | - 固定ワークフローをサポートするワークフォース<br> - マルチラウンド変換をサポートするワークフォース | [**Discordに参加 →**](https://discord.gg/bFRmPuDB) |
| **ブラウザツールキット** | - BrowseComp統合<br> - ベンチマーク改善<br> - 繰り返しページ訪問の禁止<br> - 自動キャッシュボタンクリック | [**Discordに参加 →**](https://discord.gg/NF73ze5v) |
| **ドキュメントツールキット** | - 動的ファイル編集のサポート | [**Discordに参加 →**](https://discord.gg/4yAWJxYr) |
| **ターミナルツールキット** | - ベンチマーク改善<br> - Terminal-Bench統合 | [**Discordに参加 →**](https://discord.gg/FjQfnsrV) |
| **環境 & RL** | - 環境設計<br> - データ生成<br> - RLフレームワーク統合（VERL、TRL、OpenRLHF） | [**Discordに参加 →**](https://discord.gg/MaVZXEn8) |


## [🤝 コントリビューション][contribution-link]

私たちは信頼を築き、あらゆる形式のオープンソースコラボレーションを歓迎することを信じています。あなたの創造的な貢献が`Hanggent`のイノベーションを推進します。GitHubのissuesとプロジェクトを探索して、あなたの力を見せてください 🤝❤️ [コントリビューションガイドライン][contribution-link]

## Contributors

<a href="https://github.com/hanggent-ai/hanggent/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=hanggent-ai/hanggent" />
</a>

Made with [contrib.rocks](https://contrib.rocks).


<!-- LINK GROUP -->
<!-- Social -->
[discord-url]: https://discord.com/invite/CNcNpquyDc
[discord-image]: https://img.shields.io/discord/1082486657678311454?logo=discord&labelColor=%20%235462eb&logoColor=%20%23f5f5f5&color=%20%235462eb

[hanggent-github]: https://github.com/hanggent-ai/hanggent
[github-star]: https://img.shields.io/github/stars/hanggent-ai?color=F5F4F0&labelColor=gray&style=plastic&logo=github

[contribution-link]: https://github.com/hanggent-ai/hanggent/blob/main/CONTRIBUTING.md

[social-x-link]: https://x.com/Hanggent_AI
[social-x-shield]: https://img.shields.io/badge/-%40Hanggent_AI-white?labelColor=gray&logo=x&logoColor=white&style=plastic

[hanggent-download]: https://www.hangent.com/download
[download-shield]: https://img.shields.io/badge/Download%20Hanggent-363AF5?style=plastic

[join-us]: https://www.hangent.com/careers
[join-us-image]: https://img.shields.io/badge/Join%20Us-yellow?style=plastic

[hanggent-site]: https://www.hangent.com
[docs-site]: https://www.hangent.com/docs
[github-issue-link]: https://github.com/hanggent-ai/hanggent/issues

<!-- marketing -->
[image-seperator]: https://hanggent-ai.github.io/.github/assets/seperator.png
[image-head]: https://hanggent-ai.github.io/.github/assets/head.png
[image-public-beta]: https://hanggent-ai.github.io/.github/assets/banner.png
[image-star-us]: https://hanggent-ai.github.io/.github/assets/star-us.gif
[image-opensource]: https://hanggent-ai.github.io/.github/assets/opensource.png
[image-wechat]: https://hanggent-ai.github.io/.github/assets/wechat.png
[image-join-us]: https://hanggent-ai.github.io/.github/assets/join_us.png

<!-- feature -->
[image-workforce]: https://hanggent-ai.github.io/.github/assets/feature_dynamic_workforce.gif
[image-human-in-the-loop]: https://hanggent-ai.github.io/.github/assets/feature_human_in_the_loop.gif
[image-customise-workers]: https://hanggent-ai.github.io/.github/assets/feature_customise_workers.gif
[image-add-mcps]: https://hanggent-ai.github.io/.github/assets/feature_add_mcps.gif
[image-local-model]: https://hanggent-ai.github.io/.github/assets/feature_local_model.gif
