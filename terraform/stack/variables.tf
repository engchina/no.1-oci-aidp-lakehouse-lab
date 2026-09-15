# =============================================================
# 変数名の命名規則（このスタック全体に統一）:
#   <service prefix>_<attribute>
#   - 共通環境変数: region / compartment_ocid 等（接頭辞なし）
#   - atp_*      : ATP（OLTP・ソースシステム）
#   - lakehouse_*: Autonomous AI Lakehouse
#   - adb_*      : 両 ADB に共通の設定
#   - aidp_*     : AI Data Platform Workbench
#   - oac_*      : Oracle Analytics Cloud
#   - os_*       : Object Storage（事前手動作成のバケット参照）
#   - compute_*  : Compute インスタンス
#   - app_*      : Gradio 設定アプリ
# 表示名デフォルトは "aidp-lab-" プレフィックスで統一し、
# lab 由来のリソースを tenancy 内で識別可能にする。
# =============================================================

# ------------------------------------------------------------
# 共通（事前に手動作成したリソースの参照情報）
# ------------------------------------------------------------

variable "region" {
  description = "リージョン名（例: us-chicago-1）。Resource Manager が自動入力します。"
  type        = string
  default     = ""
}

variable "compartment_ocid" {
  description = "デプロイ先コンパートメントのOCID（事前に手動で作成）"
  type        = string
  default     = ""
}

variable "availability_domain" {
  description = "Compute インスタンス用の Availability Domain。Resource Manager が自動入力します。"
  type        = string
  default     = ""
}

variable "vcn_id" {
  description = "サブネット選択用フィルタとしての VCN OCID（事前作成）"
  type        = string
  default     = ""
}

variable "subnet_id" {
  description = "Compute インスタンス用サブネット OCID。アプリを公网から使う場合はパブリックサブネットを選択"
  type        = string
  default     = ""
}

variable "ssh_authorized_keys" {
  description = "Compute インスタンス用の SSH 公開鍵"
  type        = string
  default     = ""
}

# ------------------------------------------------------------
# atp_* : ATP（OLTP・ソースシステム）
# ------------------------------------------------------------

variable "atp_name" {
  description = "ATP のデータベース名（大文字英数・アンダースコア、先頭は英字、14文字以内）"
  type        = string
  default     = "AIRLINESOURCE01"

  validation {
    condition     = can(regex("^[A-Z][A-Z0-9_]{0,13}$", var.atp_name))
    error_message = "atp_name は大文字英数・アンダースコア、先頭英字、14文字以内で指定してください。"
  }
}

variable "atp_display_name" {
  description = "ATP の表示名"
  type        = string
  default     = "aidp-lab-atp"
}

variable "atp_password" {
  description = "ATP の ADMIN パスワード（小文字・大文字・数字を含む12〜30文字、引用符不可）"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = can(regex("^(?!.*admin)(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?!.*[\"]).{12,30}$", var.atp_password))
    error_message = "atp_password は小文字・大文字・数字を含む12〜30文字で、'admin'・引用符を含むのは禁止です。"
  }
}

variable "atp_compute_count" {
  description = "ATP の ECPU 数"
  type        = number
  default     = 20
}

variable "atp_data_storage_size_in_tbs" {
  description = "ATP のストレージ（TB）"
  type        = number
  default     = 0.05
}

# ------------------------------------------------------------
# lakehouse_* : Autonomous AI Lakehouse（AIDP のベクトル DB / Gold 格納先）
# ------------------------------------------------------------

variable "lakehouse_name" {
  description = "AI Lakehouse のデータベース名"
  type        = string
  default     = "AIDPDB01"

  validation {
    condition     = can(regex("^[A-Z][A-Z0-9_]{0,13}$", var.lakehouse_name))
    error_message = "lakehouse_name は大文字英数・アンダースコア、先頭英字、14文字以内で指定してください。"
  }
}

variable "lakehouse_display_name" {
  description = "AI Lakehouse の表示名"
  type        = string
  default     = "aidp-lab-lakehouse"
}

variable "lakehouse_password" {
  description = "AI Lakehouse の ADMIN パスワード（規則は atp_password と同じ）"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = can(regex("^(?!.*admin)(?=.*[0-9])(?=.*[a-z])(?=.*[A-Z])(?!.*[\"]).{12,30}$", var.lakehouse_password))
    error_message = "lakehouse_password は小文字・大文字・数字を含む12〜30文字で、'admin'・引用符を含むのは禁止です。"
  }
}

variable "lakehouse_compute_count" {
  description = "AI Lakehouse の ECPU 数"
  type        = number
  default     = 8
}

variable "lakehouse_data_storage_size_in_tbs" {
  description = "AI Lakehouse のストレージ（TB）"
  type        = number
  default     = 0.05
}

# ------------------------------------------------------------
# adb_* : 両 ADB に共通の設定
# ------------------------------------------------------------

variable "adb_backup_retention_period_in_days" {
  description = "両 ADB の自動バックアップ保持日数"
  type        = number
  default     = 1
}

variable "adb_license_model" {
  description = "ADB ライセンス種別"
  type        = string
  default     = "LICENSE_INCLUDED"

  validation {
    condition     = contains(["LICENSE_INCLUDED", "BRING_YOUR_OWN_LICENSE"], var.adb_license_model)
    error_message = "adb_license_model は LICENSE_INCLUDED または BRING_YOUR_OWN_LICENSE です。"
  }
}

variable "adb_network_access_type" {
  description = "ADB のネットワークアクセス方式（ATP / AI Lakehouse 両方に共通適用）。PUBLIC = すべての場所からのセキュア・アクセス（パブリック・エンドポイント、既定）、SECURE_ACL = 許可された IP および VCN 限定のセキュア・アクセス（whitelisted_ips 必須）、PRIVATE = プライベート・エンドポイント・アクセスのみ（adb_subnet_id 必須）"
  type        = string
  default     = "PUBLIC"

  validation {
    condition     = contains(["PUBLIC", "SECURE_ACL", "PRIVATE"], var.adb_network_access_type)
    error_message = "adb_network_access_type は PUBLIC / SECURE_ACL / PRIVATE のいずれかで指定してください。"
  }
}

variable "adb_whitelisted_ips" {
  description = "adb_network_access_type = SECURE_ACL の場合のみ使用。許可する接続元（カンマ区切り）。CIDR ブロック（例: 10.0.0.0/24）または VCN OCID（ocid1.vcn.oc1..、VCN 内すべてのサブネットを許可）を混在させられる。Compute インスタンスからアクセスする場合は当該サブネットの CIDR を含めること。"
  type        = string
  default     = ""
}

variable "adb_subnet_id" {
  description = "adb_network_access_type = PRIVATE の場合のみ使用。ADB のプライベート・エンドポイントをアタッチするサブネット OCID（Compute と同じ VCN 内を推奨。セキュリティリスト / NSG で 1522 番ポートの許可が必要な場合あり）"
  type        = string
  default     = ""
}

# ------------------------------------------------------------
# aidp_* : AI Data Platform（AIDP Workbench）
# ------------------------------------------------------------

variable "aidp_display_name" {
  description = "AIDP インスタンスの表示名"
  type        = string
  default     = "aidp-lab-workbench"
}

variable "aidp_workspace_name" {
  description = "AIDP デフォルトワークスペース名（小文字英数・ダッシュ）"
  type        = string
  default     = "aidp-lab-workspace"
}

# ------------------------------------------------------------
# oac_* : Oracle Analytics Cloud
# ------------------------------------------------------------

variable "oac_name" {
  description = "OAC インスタンス名（テナント内一意、先頭英字、英数字とダッシュのみ。後から変更不可）"
  type        = string
  default     = "aidp-lab-oac"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,62}$", var.oac_name))
    error_message = "oac_name は先頭英字の英数字とダッシュのみで指定してください。"
  }
}

variable "oac_idcs_access_token" {
  description = "OAC 作成に必須の IDCS アクセストークン。Identity and Security → Identity Domains → default → Users → 対象ユーザー → Access Tokens から生成して貼り付け"
  type        = string
  sensitive   = true
  default     = ""
}

variable "oac_user_count" {
  description = "OAC のユーザー数キャパシティ（capacity_type=USER_COUNT）"
  type        = number
  default     = 2
}

# ------------------------------------------------------------
# os_* : Object Storage（事前手動作成のバケットを参照）
# ------------------------------------------------------------

variable "os_bucket_name" {
  description = "AIDP の Delta データ保存先用バケット名（事前手動作成）"
  type        = string
  default     = "aidp-lab-bucket_01"
}

# ------------------------------------------------------------
# compute_* : Compute（Gradio 設定アプリのホスト）
# ------------------------------------------------------------

variable "compute_display_name" {
  description = "Compute インスタンス名"
  type        = string
  default     = "aidp-lab-compute"
}

variable "compute_image_id" {
  description = "Compute OS イメージ（リージョンに応じて選択）"
  type        = string
  default     = "ocid1.image.oc1.ap-osaka-1.aaaaaaaa7sbmd5q54w466eojxqwqfvvp554awzjpt2behuwsiefrxnwomq5a"
}

variable "compute_shape" {
  description = "Compute シェイプ"
  type        = string
  default     = "VM.Standard.E4.Flex"

  validation {
    condition     = contains(["VM.Standard.E4.Flex", "VM.Standard.E5.Flex"], var.compute_shape)
    error_message = "compute_shape は VM.Standard.E4.Flex または VM.Standard.E5.Flex です。"
  }
}

variable "compute_ocpus" {
  description = "Compute OCPU 数"
  type        = number
  default     = 2
}

variable "compute_memory_gb" {
  description = "Compute メモリ（GB）"
  type        = number
  default     = 16
}

variable "compute_boot_volume_gb" {
  description = "Compute ブートボリューム（GB）"
  type        = number
  default     = 100
}

variable "compute_boot_volume_vpus" {
  description = "Compute ブートボリューム VPUs/GB（10=Balanced）"
  type        = number
  default     = 10
}

# ------------------------------------------------------------
# app_* : Gradio 設定アプリ
# ------------------------------------------------------------

variable "app_port" {
  description = "Gradio アプリ公開ポート"
  type        = number
  default     = 8080

  validation {
    condition     = var.app_port >= 1 && var.app_port <= 65535
    error_message = "app_port は 1〜65535 です。"
  }
}

variable "app_git_ref" {
  description = "デプロイする Git ref（本リポジトリのブランチ・タグ・SHA）"
  type        = string
  default     = "main"
}

variable "app_github_deploy_key_url" {
  description = "本リポジトリ用 GitHub Deploy Key（秘密鍵）の Object Storage 事前認証リクエストURL（PAR URL）"
  type        = string
  sensitive   = true
  default     = ""
}

variable "app_admin_password" {
  description = "Gradio アプリの ADMIN Web 認証パスワード"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = trimspace(var.app_admin_password) != "" && !can(regex("[\r\n]", var.app_admin_password))
    error_message = "app_admin_password は空以外で改行を含めないでください。"
  }
}
