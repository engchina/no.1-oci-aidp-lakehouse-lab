# no.1-oci-aidp-lakehouse-lab

**OCI AI Data Platform（ATP + Autonomous AI Lakehouse + AIDP Workbench + OAC）のワンクリック lab 環境。**

OCI Resource Manager で 1 回デプロイするだけで、以下のリソースが**正しい順番・正しい依存関係**で作成され、
Terraform では自動化できない初期化（DB ユーザー作成・REST 有効化・サンプルデータ読込・OAC 接続・AIDP 手動設定ガイド）を
Compute 上で動作する **Gradio 設定コンソール**からワンクリックで実行できます。

ベース資料: Qiita「【ハンズオン】AI × データ基盤：OCI AI Data Platform で実現する統合分析パイプラインの構築」（前編・後編）。

---

## アーキテクチャ

```
┌──────────────────────────── OCI (1 compartment) ────────────────────────────┐
│                                                                             │
│  ┌──────────────┐   ┌──────────────────────┐   ┌────────────────────────┐  │
│  │ ATP (OLTP)   │   │ Autonomous AI Lake-  │   │ AIDP Workbench         │  │
│  │ AIRLINESOURCE01│  │ house AIDPDB01       │──▶│ (vector_db = Lakehouse)│  │
│  │ source_01    │   │ gold_01 + vector db  │   │  ポリシー: 手動追加     │  │
│  └──────┬───────┘   └──────────┬───────────┘   └───────────┬────────────┘  │
│         │                      │                           │                │
│         │   ┌──────────────────▼──────────────┐            │                │
│         │   │ KMS vault + secret              │            │                │
│         │   │ (Lakehouse ADMIN パスワード)    │────────────┘                │
│         │   └─────────────────────────────────┘                             │
│         │                                                                   │
│  ┌──────▼───────┐   ┌──────────────────────┐                               │
│  │ Object Storage│   │ OAC (OAC instance)   │◀── gold_01 接続（コンソールから）│
│  │ delta/ バケット│   │ Professional, 2 users │                               │
│  └──────────────┘   └──────────────────────┘                               │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ Compute (E4.2 OCPU) ── Gradio 設定コンソール (port 8080)            │    │
│  │ - Lab DB 初期化（source_01 / gold_01 / REST / サンプルデータ）      │    │
│  │ - AIDP 設定ガイド（手動ステップ + コピー用値）                       │    │
│  │ - OAC 接続（REST API / ウォレットDL）                              │    │
│  │ - ヘルスチェック / 環境設定 / DB管理 / AI チャット（SQL-Assist 由来）│    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Terraform が作成するもの（terraform/stack/）

| ファイル | リソース |
|---|---|
| `adb.tf` | ATP（`db_workload="OLTP"`）+ AI Lakehouse（`db_workload="LH"`）、両ウォレット |
| `aidp.tf` | KMS vault / key / secret（Lakehouse ADMIN パスワード）+ AIDP Workbench |
| `oac.tf` | OAC インスタンス（Professional / USER_COUNT / PUBLIC endpoint） |
| `compute.tf` | Gradio コンソールを実行する Compute インスタンス |
| `vault.tf` | （`aidp.tf` に統合） |
| `bootstrap.template.yaml` | cloud-init: props 書き込み → git clone → `init_script.sh` 実行 |

### Terraform では自動化できないもの（Gradio コンソールが担当）

- DB 内のユーザー（`source_01` / `gold_01`）作成・権限付与・REST（ORDS）有効化
- サンプル航空会社データ 25 件の読込 + `SELECT *` プレビュー
- Gold テーブル `GOLD_01.AIRLINE_SAMPLE_GOLD` の作成（幂等）
- AIDP ポリシー追加（Standard / Enable object deletion）→ コンソールガイド
- AIDP での external catalog / medallion schema / LLM 設定（コンソール上の手動作業）
- AIDP Notebook に貼り付けるコード（Bronze/Silver/Gold/LLM/INSERT）を環境値反映で生成
- OAC へのデータ接続作成（REST API 経由の実験的自動化 + Task 2〜6 の手動手順ガイド）

---

## 全体フロー（フェーズ構成）

```
① Terraform 実行前（手動）  →  ② Terraform 実行（RM デプロイ）  →  ③ Terraform 実行後（手動 + コンソール）
```

| フェーズ | やること | どこでするか |
|---|---|---|
| ① 実行前 | compartment / VCN + サブネット / バケット / IDCS トークン / deploy key PAR URL（下記 5 項目） | OCI コンソール |
| ② 実行 | Stack デプロイ。ATP / AI Lakehouse / KMS vault・secret / AIDP / OAC / Compute を自動作成 | Resource Manager |
| ③ 実行後 | Outputs 確認 → AIDP ポリシー追加 → Gradio コンソール（DB 初期化 / ガイド / Notebook コード / OAC 接続 / ヘルスチェック）→ AIDP notebook → OAC ダッシュボード | OCI コンソール + Gradio + AIDP Workbench |

## ① Terraform 実行前: 手動事前準備（5 項目）

Resource Manager のデプロイ**前**に、以下の 5 項目を手動で用意してください。

1. **Compartment** の作成（`compartment_ocid` 用）
2. **VCN + Compute サブネット**（パブリックサブネット推奨。コンソールに外部からアクセスする場合）
3. **Object Storage バケット**の事前作成（AIDP の Delta データ保存先。既定名 `aidp-lab-bucket_01`）
4. **OAC の IDCS アクセストークン** — Identity and Security → Identity Domains → default → Users →（自分のユーザー）→ Access Tokens で生成し、デプロイフォームに貼り付け
5. **GitHub deploy key（秘密鍵）の Object Storage 事前認証リクエスト（PAR URL）**
   - 本リポジトリに deploy key（読み取り専用で可）を登録し、秘密鍵を Object Storage にアップロード
   - 事前認証リクエスト URL をフォームの `app_github_deploy_key_url` に入力
   - Compute 上で `git clone git@github.com:engchina/no.1-oci-aidp-lakehouse-lab.git` するための鍵

## ② Terraform 実行: Resource Manager デプロイ手順

1. [Resource Manager](https://cloud.oracle.com/iaas/stacks) → Stack → Create stack → **Import stack (from template)**
2. 本リポジトリを指向:
   - Source: `https://github.com/engchina/no.1-oci-aidp-lakehouse-lab`
   - 相対パス: `terraform/stack`
3. フォームに入力（パスワード類は 12〜30 文字・英大文字・英小文字・数字を含む、`admin` 不得、`"` 不得）
4. Stack をデプロイ。AIDP の作成には 20〜40 分程度かかる場合があります（Work Request 待ち）

## ③ Terraform 実行後: 順次実施

1. **Outputs を確認**
   - `atp_connection_string` / `lakehouse_connection_string`（ADMIN 接続文字列）
   - `aidp_instance_ocid` → `https://aidp.oci.oraclecloud.com/?ocid=<この値>`
   - `oac_instance_name` → OAC の URL は OCI コンソールの「アナリティクス・クラウド」から確認
   - `app_url` → Gradio 設定コンソールの URL
   - `ssh_to_instance` → 障害切り分け用
2. **AIDP 標準ポリシーを手動追加**（AIDP インスタンスが作成されてから可能。Terraform は `policies` を設定できないため）
   - AIDP コンソール → インスタンス → Add policies → `Standard` を追加
   - Optional policies から `Enable object deletion` も追加（バケットへの Delta 書き込みに必要）
   - 詳細は Gradio の「AIDP 設定ガイド」Tab 手順 1 を参照
3. **Gradio コンソール**（`app_url`）を開き、ADMIN でログイン（パスワードはフォームの `app_admin_password`）
   1. 「Lab DB 初期化」: `source_01` / `gold_01` を作成 → サンプルデータ読込 → Gold テーブル作成
   2. 「AIDP 設定ガイド」: external catalog（ATP / ADW）→ LLM 設定 → catalog リフレッシュ を順次実施（値はコピー用に表示）
   3. 「AIDP Notebook コード」: 環境値を反映したコードをタスクごとにコピーし、AIDP notebook で順に実行
   4. 「OAC 接続」: OAC Personal Access Token を入力して接続を作成（または UI で手動）→ Task 2〜6 のガイドに従い dataset / ワークブック / OAC Assistant を作成
   5. 「ヘルスチェック」: 各リソースの疎通 + 表行数 + bucket の delta/ パス確認
4. **AIDP の notebook** で後編 Step3（OAC ダッシュボード作成）まで進める

## ローカル開発

```bash
# Terraform
cd terraform/stack
terraform init -backend=false
terraform validate
terraform fmt -check -recursive

# Shell
bash -n init_script.sh

# Python
python3 -m compileall -q main.py utils
```

### コンソールをローカルで実行する場合

```bash
cp .env.example .env   # 値を記入
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./main.sh               # 既定ポート 8080
```

`.env` の重要変数（`init_script.sh` が `/u01/aipoc/props/` から自動埋め合わせします）:

| 変数 | 説明 |
|---|---|
| `ORACLE_26AI_CONNECTION_STRING` | ATP の `admin/<pw>/<db>_high` |
| `ORACLE_LAKEHOUSE_CONNECTION_STRING` | Lakehouse の `admin/<pw>/<db>_high` |
| `WALLET_ATP_DIR` / `WALLET_LH_DIR` | ウォレット展開先（`/u01/aipoc/wallets/{atp,lh}`） |
| `AIDP_OCID` / `OAC_NAME` / `BUCKET_NAME` | 各リソースの識別子 |
| `SOURCE_SCHEMA_PASSWORD` / `GOLD_SCHEMA_PASSWORD` | 「Lab DB 初期化」で保存 |
| `OCI_NAMESPACE` / `BUCKET_NAME` | AIDP の Delta 保存先（ガイド / Notebook コード / ヘルスチェックで使用） |
| `AIDP_LLM_MODEL` | AIDP LLM 設定で登録したモデル名（既定 `xai.grok-4`） |
| `APP_ADMIN_PASSWORD` | Web UI ログインパスワード |

## ファイル構成

```
├── terraform/stack/          # RM stack（schema.yaml フォーム付き）
├── main.py                   # Gradio アプリのエントリポイント
├── utils/                    # UI 各タブ（No.1-SQL-Assist から移植 + lab 固有）
│   ├── lab_setup_util.py     # Lab DB 初期化 / AIDP ガイド / OAC 接続 / ヘルスチェック
│   └── notebook_code_util.py # AIDP Notebook 用コード生成（環境値反映・タスク別コピー）
├── init_script.sh            # Compute 初回起動: 依存パッケージ + .env 生成 + 起動
├── main.sh / restart.sh      # アプリ起動・再起動
├── application_port.sh       # ポート解決（props/application_port.txt、既定 8080）
├── main.cron                 # @reboot 自動起動
├── requirements.txt
├── .env.example
└── sql/sample_data.sql       # サンプルデータ（手動読込用）
```

## 既知の制約

- AIDP の `policies` は Terraform リソースが露出していないため、コンソールでの手動追加が必須。
- OAC のインスタンス URL はリージョンコードの形式が環境により異なるため自動計算せず、Outputs はインスタンス名のみ出力。
- OAC 接続作成 API（`POST /api/public/connections`）は実験的であり、OAC バージョンにより形式が異なる場合がある（失敗時は UI で手動）。
- OAC の dataset / ダッシュボード作成は UI 操作（後編 Step3）。「OAC 接続」タブに Task 2〜6 の完全手順 + OAC Assistant サンプル質問を掲載。
- AIDP の notebook 系操作（Bronze / Silver / Gold 加工、Gold 書き出し）は Workbench 上での手作業。「AIDP Notebook コード」タブが環境値を反映したコードをタスク別に提供。

## 開発規約

[AGENTS.md](AGENTS.md) 参照（Issue → branch → PR → CI → merge のフロー、日本語コメント原則）。
