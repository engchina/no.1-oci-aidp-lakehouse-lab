# AGENTS.md — no.1-oci-aidp-lakehouse-lab

> このファイルは **dsh CLI・Claude Code・Codex が参照する正本（single source of truth）** です。
> `CLAUDE.md` を併用する場合は `@AGENTS.md` でこのファイルを取り込むこと。ルールを変更する際は **必ずこのファイルを編集**してください。

## 開発ワークフロー / GitHub 運用

- **`main` ブランチへ直接 commit / push / 変更しない。** すべての変更は GitHub Issue を先に作成し、Issue に紐づく作業ブランチで行う。
- 作業ブランチ名は既定で `<agent>/<issue-number>-<short-topic>` とする（`agent` は実際に作業するエージェント/CLI の名前、例: `dsh` / `claude` / `codex`）。既存 ref との衝突などで使用できない場合も、Issue 番号と作業内容が分かる名前を使う。
- 変更後は Pull Request を作成し、関連 Issue、変更内容、検証結果を PR description に明記する。
- **変更・必要な検証・PR 本文の更新が完了し、PR の最新 commit に対する CI/checks が成功したら、追加のユーザ確認を求めず自動で `main` へ merge する。** PR 作成や CI 成功の報告だけで作業を終了しない。必須 CI が存在しない場合は、PR 上で checks 状態を確認し、成功した代替検証を PR 本文に明記してから merge する。
- CI/checks の失敗や merge conflict がある場合は、原因を修正・解消し、最新 commit を再検証してから merge する。branch protection を迂回した強制 merge は行わない。解消できない場合は原因と未完了の操作を明示する。
- **merge 後はローカルブランチを必ず `main` に切り替え、`origin/main` へ fast-forward 同期してから完了を報告する。** PR の merge 状態、ローカルブランチ、同期状態を確認する。ユーザの未保存変更を破棄する `reset --hard` 等は使わず、変更を保持したまま安全に同期する。同期できない場合は理由と残作業を明示する。
- docs-only の小さな変更や緊急修正も原則として同じ Issue → branch → PR → CI/checks → main merge の流れに従う。例外が必要な場合は、理由を添えてユーザ確認を取る。

### GitHub Issue / Pull Request の記述規約

#### 共通

- Issue / PR のタイトルと本文は**原則として日本語**で記述する。code identifier、API path、file path、command、製品・ライブラリの固有名詞は英語のままでよい。
- タイトルは対象と事象が分かる具体的な文にする。「不具合」「修正」「対応」だけの曖昧なタイトルにしない。
- 本文は Markdown 見出しで構造化し、確認した事実と推測を区別する。未調査・未確定の項目は断定せず「調査中」「未確認」と明記し、判明後に本文を更新する。
- 変更の再現値・実行したコマンド・検証結果など、調査・レビュー・回帰に必要な具体情報を記載する。secret、token、個人情報、実 credential は記載しない。

#### Issue

- Issue の種別にかかわらず、最低でも `問題`、`症状`、`原因`、`修正方針` の4項目を含める。初回登録時に原因が未確定でも `原因` を省略せず、現時点の仮説または「調査中」と記載する。

```markdown
## 問題

何が問題なのかを記載する。

## 症状

どのような入力や条件で何が起きるのかを、観測事実に基づいて記載する。

## 原因

どの構成、スクリプト、または設計が原因と考えられるかを記載する。未確定の場合は仮説と未確認事項を区別する。

## 修正方針

どこを、どのような考え方で修正するかを、責務境界と変更しない範囲を含めて記載する。
```

- 可能であれば `影響範囲`、`再現手順`、`関連ファイル`、`必要なテスト` も追加する。必要に応じて `期待動作`、`完了条件`、`補足`、`ログ`、`代替案` を追加する。
- feature / docs / refactor / investigation Issue では、`問題` に背景や現在の不足、`症状` に現状の制約や具体例、`原因` に設計上の理由または調査対象を記載し、4項目を Issue の性質に合わせて具体化する。
- `完了条件`は「対応する」のような作業表現だけにせず、期待状態と必要な検証（terraform validate / bash -n 等）を判定可能な形で列挙する。

#### Pull Request

- PR title は原則として `<type>: <日本語の要約> (#<issue-number>)` とする。`type` は変更内容に合わせて `feat` / `fix` / `docs` / `test` / `refactor` / `chore` 等を使用する。
- PR 本文は原則として次の見出しを使用する。

```markdown
## 関連 Issue

Closes #<issue-number>

## 背景 / 原因

Issue の要点と、この変更が必要な理由を記載する。bug fix では根因を記載する。

## 変更内容

- 変更した構成・挙動を具体的に記載する
- 既存環境への影響（既存 stack / state / 設定への破壊的変更の有無）を記載する

## 検証結果

- `<実行した command>` — pass / fail / skip と件数
- 手動確認した内容（OCI 上で検証できない場合は理由を明記）

## 既知の制約・残課題

- 未対応範囲、既知の制約、follow-up Issue を記載する。なければ「なし」と記載する。
```

- `関連 Issue` には、merge で完了する Issue は `Closes #N`、参照のみは `Refs #N` と記載する。複数ある場合はすべて列挙する。
- `変更内容` は commit の羅列ではなく、reviewer が挙動差分と責務境界を判断できる粒度で記載する。変更していない重要範囲や既存環境との互換性も必要に応じて明記する。
- `検証結果` には実行した正確な command と結果を記載する。失敗・skip・未実行を隠さず、今回の変更によるものか既存問題かを分ける。実行できない検証がある場合は理由と代替確認を記載する。
- docs-only など CI 対象外の場合も `検証結果` を省略せず、実施できた検証の結果と、実施しなかった検証の理由を記載する。
- PR 作成後に追加修正や検証結果の変化があった場合は、コメントだけで済ませず PR 本文を最終状態へ更新してから merge する。

## プロジェクト概要

**ATP (OLTP)、Autonomous AI Lakehouse、Oracle Analytics Cloud 等の OCI AI Data Platform 向けワンクリック lab 環境。**

本プロジェクトは Terraform とシェルスクリプトにより、OCI 上で AI Data Platform の検証用環境を構築する lab を提供する。

### 技術スタック（確定）

| 用途 | 採用 | 重要な制約 |
|---|---|---|
| インフラ定義 | **Terraform**（`hashicorp/oci` provider） | `terraform fmt` 準拠。backend は lab 用途で既定 `local` |
| 構築・運用スクリプト | **Bash** | `bash -n` 必須。set -euo pipefail を推奨 |
| 補助 CLI | **OCI CLI** / **oci-setup** | ローカル運用用。認証はキーファイル・env 経由 |

## 言語・ローカライズ方針

- **コメント・ドキュメント・説明文は原則として日本語**で記述する。
  - Terraform / Shell のコメント、README / docs、Issue / PR の記述、CI の日本語メッセージを含む。
- 識別子（HCL の resource / variable name、スクリプトの変数・関数名、ブランチ名など）は**英語**。
- OCI / Oracle の製品・サービス名（ATP、ADW、OAC、compartment、bucket 等）は英語の正式名称を維持する。

## 検証済みコマンド

```bash
# Terraform
terraform init -backend=false
terraform fmt -check -recursive
terraform validate

# Shell スクリプト
bash -n <script.sh>
```

## CI

- `.github/workflows/ci.yml` が **PR と main への push** で実行される。
- チェック項目:
  1. `terraform fmt -check -recursive`
  2. `.tf` がある各ディレクトリで `terraform init -backend=false` + `terraform validate`
  3. 全 `.sh` に対して `bash -n`（構文チェック）
- `.tf` / `.sh` ファイルが存在しない段階では該当チェックはスキップして成功とする（リポジトリ初期段階を踏まえた設計）。
- **`main` ブランチには branch protection が有効**（必須 CI = `CI` job 的成功、PR 経由の merge 必須、直接 push 禁止、管理者も適用）。

## コーディング規約・重要ルール

1. HCL は `terraform fmt` の出力に合わせる。手動整形で逸脱させない。
2. Shell スクリプトは `bash -n` を通過させること。エラー時は `set -euo pipefail` を推奨する。
3. シークレット（OCI 認証・DB password 等）は `.tfvars` / environment variable 経由。**ハードコード禁止**、コミットしない（`.gitignore` 参照）。
4. `.terraform/`、`.tfstate*`、`*.tfvars` 等は git にコミットしない。
5. Terraform 構成を変更した場合は、関連するスクリプト・ドキュメント・README も同じ変更で追従更新し、PR の `検証結果` に記載する。
6. 既存 lab 環境（state 上にあるリソース）を破壊的に変える変更は、`変更内容` に破壊的変更の明示と移行手順を含むこと。
7. このスタック（Terraform + Bash + OCI）から外れる提案（別 IaC ツール、別言語のスクリプト等）をする場合は、必ず理由を添えてユーザに確認する。

## テスト / 検証方針

- 変更後は該当範囲の `terraform fmt -check` / `terraform validate` / `bash -n` を実行し、完了報告に実行結果を明記する。
- OCI 上で実構築できる場合は、`terraform plan` / 手動デプロイで検証し PR に結果を記載する。実行できない場合は理由と代替確認（例: `terraform plan` のみ、構文チェックのみ）を明記する。
