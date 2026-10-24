# 生成AI 設計書レビュー支援システム

システム設計書をアップロードし、生成AIが不足・曖昧さ・矛盾・異常処理・入出力・セキュリティ・境界条件などをレビューする、個人開発のPoCです。結果は重要度別の構造化データとして返し、日本語のWeb画面に表示します。

APIキーを設定しなくても固定結果を返すデモモードで、画面と一連の操作を確認できます。

> **Status: PoC v1.0**
>
> 現在の `backend/app/prompts.py`、Expected Issues、Review Scope、ヒューリスティック評価、人工Adjudicationをv1.0評価基準として固定しています。以降のPromptや評価基準の変更は、この基準との差分として扱います。

**公開データに関する声明:** 本リポジトリで使用している設計書および評価データは、すべて本PoC用に作成した架空データです。実在する企業・顧客・業務案件とは関係ありません。

## 開発背景

設計書レビューでは、観点のばらつきや確認漏れが起こりやすく、レビュー担当者の負担も大きくなります。本プロジェクトは、生成AIを最終判断者ではなく「確認観点を提示する支援ツール」として利用し、レビューの初動を効率化できるかを検証するために作成しました。

## 主な機能

- PDF / DOCX / TXT / Markdown形式の設計書アップロード
- アップロードデータを保存せず、メモリ上でテキスト抽出
- OpenAI Responses APIとPydantic Structured Outputsによる型付きレビュー結果
- 問題と追加確認事項の区別
- High / Medium / Low別の指摘件数と詳細表示
- APIキーがない環境向けの明示的なデモモード
- 10MBのアップロード上限、ファイル形式・空ファイル検証
- スキャンPDFに対する明確なエラー表示（OCRは未対応）

## システム構成

```text
Browser (Next.js / localhost:3000)
        |
        | multipart/form-data: POST /review
        v
FastAPI (localhost:8000)
        |
        +-- Document Parser (TXT / MD / DOCX / PDF)
        |
        +-- Demo Review Service (APIキーなし)
        |
        +-- OpenAI Review Service (APIキーあり)
                 |
                 +-- Responses API / Structured Outputs
```

OpenAI APIの呼び出しはバックエンドだけで行います。フロントエンドへAPIキーを渡す処理はありません。

## 技術スタック

| 区分 | 技術 |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic |
| AI | OpenAI Python SDK, Responses API, Structured Outputs |
| Document | pypdf, python-docx |
| Frontend | Next.js, React, TypeScript, CSS |
| Test | pytest, FastAPI TestClient |

## ディレクトリ構成

```text
.
├── backend
│   ├── app
│   │   ├── config.py           # 環境変数と設定
│   │   ├── document_parser.py  # 文書テキスト抽出
│   │   ├── main.py             # FastAPIとエンドポイント
│   │   ├── prompts.py          # 日本語レビューPrompt
│   │   ├── review_service.py   # OpenAI / Demoレビュー
│   │   └── schemas.py          # Pydanticデータモデル
│   ├── tests                   # Backend自動テスト
│   ├── .env.example
│   └── requirements.txt
├── frontend
│   ├── app                     # Next.js App Router
│   ├── .env.example
│   └── package.json
├── evaluation
│   ├── adjudication            # Extra Issueの人手判定
│   ├── expected_*.json         # 人手定義した期待指摘
│   ├── evaluate_review.py      # ヒューリスティック評価
│   ├── run_review.py           # 実レビュー結果保存CLI
│   ├── results                 # モデル別レビュー結果
│   └── tests                   # 評価ロジックのテスト
├── samples
│   ├── sample_good_design.md
│   ├── sample_problematic_design.md
│   └── sample_reference_design.md
├── pytest.ini
└── README.md
```

## 環境要件

- macOS（ほかのOSでも同等のコマンドで動作可能）
- Python 3.11以上
- Node.js 20以上
- npm
- 実際のAIレビューを行う場合のみOpenAI APIキー

## セットアップと起動

### Backend

プロジェクトルートで以下を実行します。

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

起動後の確認先:

- API: <http://localhost:8000/>
- Swagger UI: <http://localhost:8000/docs>

### Frontend

別のターミナルで、プロジェクトルートから実行します。

```bash
cd frontend
npm install
npm run dev
```

ブラウザで <http://localhost:3000> を開きます。

バックエンドURLを変更する場合は、`frontend/.env.local` を作成します。

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Demoモード

`OPENAI_API_KEY` が未設定または空の場合、自動的にDemoモードになります。OpenAI APIへ接続せず、入力内容にかかわらずUI確認用の固定レビュー結果を返します。画面には次の注意を表示します。

> デモモード：この結果は生成AIによる実際のレビュー結果ではありません。

動作確認には `samples/sample_problematic_design.md` または `samples/sample_good_design.md` を利用できます。

### 実際のOpenAI APIを使用する場合

実際の生成AIレビューを利用する場合は、サンプルをコピーしてバックエンド用の `.env` を作成します。

```bash
cp backend/.env.example backend/.env
```

`backend/.env` に値を設定します。

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.6-terra
```

`OPENAI_MODEL` はStructured Outputs対応モデルへ変更できます。`.env` はGit管理対象外です。APIキーはフロントエンドの環境変数へ設定しないでください。

## Screenshots / Demo

本PoCはローカル環境で動作します。BackendとFrontendを起動し、http://localhost:3000 から操作できます。

### 設計書アップロード画面

![image-20261024113214757](/Users/shawn/Library/Application Support/typora-user-images/image-20261024113214757.png)

### AIレビュー結果

![image-20261024113238965](/Users/shawn/Library/Application Support/typora-user-images/image-20261024113238965.png)

1. `samples/sample_problematic_design.md` などの架空サンプルを選択する。
2. 「レビューを実行」を押す。
3. ファイル名、重要度別件数、AI要約、指摘一覧を確認する。

APIキーを設定しなければDemoモードで安全に画面と操作フローを確認できます。実際のAIレビュー結果を確認する場合のみ、Backendの `.env` に自身のAPIキーを設定してください。

## AI Review Evaluation

### Review Scope

現在のPoCが対象とする文書レベルは **基本設計書** です。レビューでは、基本設計段階で確定すべき業務フロー、権限原則、データ整合性、トランザクション、重大な異常処理・セキュリティ上の問題と、詳細設計・インターフェース設計・運用設計で具体化できる実装詳細を区別します。

後続工程で補完できるHTTPエラーコードの細部、ヘッダー形式、サービス間認証方式、同期プロトコル、組織マスタ展開方法などは、基本設計自体が成立しない場合を除いてHighのIssueにはしません。追加資料や後続設計を確認しないと判断できない事項は、構造化出力上では `finding_type: Confirmation`（要確認）として扱い、`severity` は原則 `Low` とします。

### 評価の目的

モデル、Prompt、レビュー規則を変更したときに、既知の問題をどの程度検出できたか、追加の指摘がどの程度増えたかを同じ基準で比較するためのPoC評価機構です。単純な指摘件数ではなく、人手で定義したExpected IssuesとAIの各指摘を対応付けて評価します。

評価対象は「AIが問題を見つけたか」だけではありません。その指摘が現在の文書レベルに属するか、実際の欠陥か、詳細設計など後続工程で確認すべき事項かも人手で判定します。

### 評価用サンプル

| サンプル | 位置付け | Expected Issues |
| --- | --- | ---: |
| `sample_problematic_design.md` | 意図的に権限、入力、矛盾、異常処理、セキュリティ等の問題を含む | 11 |
| `sample_good_design.md` | 比較的良好だが、業務処理、状態遷移、API定義等に改善余地がある | 5 |
| `sample_reference_design.md` | 状態、API、境界条件、主要異常処理まで補った高品質基準 | 0 |

`evaluation/expected_*.json` が人手で事前に定義した期待指摘です。各項目はID、カテゴリ、説明、重要度、Review Scope、照合用キーワードを持ちます。Expected Issuesは既知問題の集合であり、設計書に存在するすべての問題を網羅する保証はありません。Referenceは既知のHigh / Medium問題を0件とし、AIが出した指摘は人手で内容を確認します。

Review Scopeは次の3種類です。

- `BASIC_DESIGN_CORE`: 基本設計で必須となる業務規則、実装方針、整合性、安全性、または受入条件
- `BASIC_DESIGN_CONFIRMATION`: 基本設計で確認が望ましいが、関連文書や後続工程でも補完可能な事項
- `DETAIL_DESIGN`: 詳細設計、インターフェース設計、実装設計で定義する事項

### Evaluation Results

PoC v1.0のPromptと評価基準を使用し、同一モデル `gpt-5.6-terra` で各サンプルを1回ずつレビューした結果です。

| Sample | Basic Design Core Expected | Matched | Core Recall | Extra |
| --- | ---: | ---: | ---: | ---: |
| Problematic | 11 | 9 | 0.82 | 0 |
| Good | 3 | 2 | 0.67 | 1 |
| Reference | 0 | N/A | N/A | 4 |

ReferenceはCore Expectedが0件のため、Recall、Precision、F1を計算しません。4件のExtraは人によるAdjudicationが必要であり、Extraであることだけを理由にFalse Positiveとは判定しません。

この結果を読む際は、次の制約を考慮する必要があります。

- LLMの出力には試行ごとのばらつきがあり、同一モデルとPromptでも結果が変わる可能性があります。
- Extra Issueは、Valid New Finding、False Positive、Needs Confirmation、または基本設計の対象外のいずれにもなり得ます。
- 本評価はExpected Issuesとの文字列・カテゴリ照合を用いるPoCレベルのヒューリスティック評価です。
- サンプルは3件のみであり、この数値をモデル一般の正解率や汎用的な性能指標として解釈することはできません。
- 評価結果JSONはすべて上記の架空サンプルから生成しており、APIキーや実在する企業・顧客データを含みません。

### 実AIレビュー結果の保存

上記のOpenAI API設定を完了した後、プロジェクトルートで実行します。

```bash
source backend/.venv/bin/activate
python -m evaluation.run_review samples/sample_problematic_design.md
```

結果はモデル名を含むファイル名で保存されます。

```text
evaluation/results/problematic_gpt-4o-mini.json
```

APIキーがない場合、このCLIはDemo結果を実レビューとして保存せず終了します。APIキーそのものは結果JSONへ出力しません。

モデルを変更して個別に実行する例:

```bash
OPENAI_MODEL=model-a python -m evaluation.run_review samples/sample_problematic_design.md
OPENAI_MODEL=model-b python -m evaluation.run_review samples/sample_problematic_design.md
```

複数モデルを自動実行する機能はなく、各コマンドの実行時にだけOpenAI API料金が発生します。同じ文書・モデル名の既存結果は上書きされます。

### 評価の実行

Expected Issuesと保存済みレビュー結果を指定します。

```bash
python -m evaluation.evaluate_review \
  evaluation/expected_problematic.json \
  evaluation/results/problematic_gpt-4o-mini.json
```

出力にはExpected件数、AI件数、Matched、Missed、Extra、Recall、Precision、F1に加え、Basic Design CoreのExpected、Matched、Missed、Recallと、対応したIDおよび照合根拠が含まれます。Core Recallには `DETAIL_DESIGN` と `BASIC_DESIGN_CONFIRMATION` の未検出を含めません。

Extra Issueの人手判定を併せて表示する場合は、独立したadjudicationファイルを指定します。AIレビュー結果JSONは変更されません。

```bash
python -m evaluation.evaluate_review \
  evaluation/expected_reference.json \
  evaluation/results/reference_gpt-5.6-terra.json \
  --adjudication evaluation/adjudication/reference_gpt-5.6-terra.json
```

`evaluation/adjudication/reference_gpt-5.6-terra.json` は、PoC v1.0のreferenceレビュー4件を収録した初期テンプレートです。自動判定を避けるため、すべて `NEEDS_CONFIRMATION` から開始し、担当者が `status` と `comment` を更新します。

### マッチング方法

1. カテゴリ、指摘箇所、該当原文、問題点をUnicode NFKCで正規化し、英字の大小と空白・記号の差を除去する。
2. Expectedのキーワードが2個以上一致した場合を候補とする。
3. カテゴリが部分一致する場合は、キーワード1個以上で候補とする。
4. Expectedの説明とAIの問題点・原文の文字列類似度が0.58以上の場合も候補とする。
5. キーワード数、カテゴリ、説明類似度、重要度一致から得点を計算し、高得点順に一対一で対応付ける。

一つのAI指摘を複数のExpected Issuesへ重複計上しないため、広すぎる一つの指摘でRecallが過大になることを防ぎます。

### 指標

- **Recall**: Expected IssuesのうちAIが検出できた割合。見逃しが少ないほど高くなります。
- **Precision**: AI IssuesのうちExpected Issuesと対応した割合。余分な指摘が少ないほど高くなります。
- **F1**: RecallとPrecisionの調和平均で、検出と余分な指摘のバランスを表します。
- **Basic Design Core Recall**: `BASIC_DESIGN_CORE` に分類されたExpected Issuesのうち、AIが検出できた割合です。

Expected Issuesが0件の場合は正解集合に対する検出率を定義できないため、Recall、Precision、F1をすべて `N/A` と表示します。AI指摘は件数と詳細をExtraとして表示しますが、自動的にFalse Positiveとは判定しません。

Extra issueは人手で次のいずれかに分類します。

1. **VALID_NEW_FINDING**: Expected Issuesには未登録だが、設計書に根拠がある新しい有効指摘
2. **FALSE_POSITIVE**: 設計書に根拠がない、または既に十分定義されている誤指摘
3. **NEEDS_CONFIRMATION**: 文書の前提や関連資料を確認しなければ妥当性を判断できない事項
4. **OUT_OF_SCOPE_FOR_BASIC_DESIGN**: 詳細設計、インターフェース設計、運用設計などで定義すべき事項

**Extra Issue ≠ False Positive** です。Expected Issuesは事前に把握した問題の集合にすぎず、設計書に存在するすべての問題を網羅しません。したがってExtra Issueは、文書レベルと根拠を確認したうえで人手判定する必要があります。

### Lessons Learned / 検証で得られた知見

- 初期Promptでは、基本設計書に対して詳細設計・インターフェース設計レベルの不足を強く指摘する傾向がありました。
- Basic Design Review Scopeを導入し、基本設計で確認すべき核心事項と後続工程で補完できる事項を分離しました。
- Expected Issuesを `BASIC_DESIGN_CORE`、`BASIC_DESIGN_CONFIRMATION`、`DETAIL_DESIGN` に分類し、文書レベルに合ったRecallを確認できるようにしました。
- Extra Issueを自動的に誤検知とせず、人が根拠と文書スコープを確認するAdjudicationを導入しました。
- Referenceの指摘件数を0にすること自体を目標にするとPromptが特定サンプルへ過学習するため、合理的な新規指摘を残して人手判定する方針としました。

### 評価機構の制限

- PoCレベルの決定的なヒューリスティック照合であり、絶対的・客観的なAI品質スコアではありません。
- 同義語、複合指摘、表現差によって誤マッチまたは未マッチが発生します。
- Expected Issues自体が人手判断に依存し、設計書の唯一の正解ではありません。
- Expected Issuesに未登録であることだけを理由に、Extraを誤検知とは判定できません。
- 重要度の妥当性や修正案の実行可能性を詳細には採点しません。
- Referenceに対するLow / Confirmationの妥当性は人手確認が必要です。
- LLM-as-a-judgeは使用せず、評価処理からOpenAI APIを呼び出しません。

## テスト方法

プロジェクトルートでBackendとEvaluationの全テストを実行します。

```bash
source backend/.venv/bin/activate
python -m pytest -q
```

Frontendの本番ビルド確認:

```bash
cd frontend
npm run build
```

## 対応ファイル

| 形式 | 拡張子 | 抽出方法 |
| --- | --- | --- |
| Text | `.txt` | UTF-8テキストとして読込 |
| Markdown | `.md` | UTF-8テキストとして読込 |
| Word | `.docx` | 段落・表のテキストを抽出 |
| PDF | `.pdf` | PDF内のテキストレイヤーを抽出 |

最大ファイルサイズは10MBです。アップロードファイルは永久保存しません。

## セキュリティとプライバシー

- OpenAI APIキーはバックエンドの環境変数からのみ読み込みます。
- `.env` と `.env.local` は `.gitignore` の対象です。
- 設計書全文をアプリケーションログへ出力しません。
- アップロードファイルはディスクへ保存しません。
- 設計書本文は信頼できないレビュー対象データとしてPromptへ渡し、本文中の命令でシステム指示を上書きしないよう明示しています。
- OpenAI API利用時のデータ取り扱いは、利用組織のポリシーとOpenAIの最新規約を確認してください。

## 現在の制限

- 画像だけのスキャンPDFはテキストを抽出できません。
- レイアウト、図、画像、表の視覚的な意味はレビュー対象外です。
- 大規模文書の分割処理やトークン数の事前見積もりは未実装です。
- AIの指摘は誤りを含む可能性があり、人による最終確認が必要です。
- データベース、ユーザー認証、レビュー履歴、クラウドデプロイは含みません。

## 今後の拡張候補

- OCRによるスキャン文書対応
- RAGによる社内標準・過去事例の参照
- 企業ごとのレビュー規則とチェックリスト
- レビュー履歴と差分比較
- Excel形式での結果出力
