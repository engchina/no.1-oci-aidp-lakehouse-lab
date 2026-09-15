# =============================================================
# 共通（事前に手動作成したリソースの参照情報）
# =============================================================

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

# =============================================================
# ATP（OLTP・ソースシステム）
# =============================================================

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
  default     = "airline-source-atp"
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

# =============================================================
# Autonomous AI Lakehouse（AIDP のベクトル DB / Gold 格納先）
# =============================================================

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
  default     = "aidp-db"
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

variable "db_backup_retention_period_in_days" {
  description = "両 ADB の自動バックアップ保持日数"
  type        = number
  default     = 1
}

variable "license_model" {
  description = "ADB ライセンス種別"
  type        = string
  default     = "LICENSE_INCLUDED"

  validation {
    condition     = contains(["LICENSE_INCLUDED", "BRING_YOUR_OWN_LICENSE"], var.license_model)
    error_message = "license_model は LICENSE_INCLUDED または BRING_YOUR_OWN_LICENSE です。"
  }
}

# =============================================================
# AI Data Platform（AIDP Workbench）
# =============================================================

variable "aidp_display_name" {
  description = "AIDP インスタンスの表示名"
  type        = string
  default     = "aidp-test"
}

variable "aidp_workspace_name" {
  description = "AIDP デフォルトワークスペース名（小文字英数・ダッシュ）"
  type        = string
  default     = "aidp-workspace"
}

# =============================================================
# Oracle Analytics Cloud（OAC）
# =============================================================

variable "oac_name" {
  description = "OAC インスタンス名（テナント内一意、先頭英字、英数字とダッシュのみ。後から変更不可）"
  type        = string
  default     = "aidpoac01"

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

variable "oac_capacity_users" {
  description = "OAC のユーザー数キャパシティ"
  type        = number
  default     = 2
}

# =============================================================
# Object Storage（事前手動作成のバケットを参照）
# =============================================================

variable "bucket_name" {
  description = "AIDP の Delta データ保存先用バケット名（事前手動作成）"
  type        = string
  default     = "aidp-demo-bucket_01"
}

# =============================================================
# Compute（Gradio 設定アプリ）
# =============================================================

variable "instance_display_name" {
  description = "Compute インスタンス名"
  type        = string
  default     = "aidp-lab-instance"
}

variable "instance_image_source_id" {
  description = "Compute OS イメージ（リージョンに応じて選択）"
  type        = string
  default     = "ocid1.image.oc1.ap-osaka-1.aaaaaaaa7sbmd5q54w466eojxqwqfvvp554awzjpt2behuwsiefrxnwomq5a"
}

variable "instance_shape" {
  description = "Compute シェイプ"
  type        = string
  default     = "VM.Standard.E4.Flex"

  validation {
    condition     = contains(["VM.Standard.E4.Flex", "VM.Standard.E5.Flex"], var.instance_shape)
    error_message = "instance_shape は VM.Standard.E4.Flex または VM.Standard.E5.Flex です。"
  }
}

variable "instance_flex_shape_ocpus" {
  description = "Compute OCPU 数"
  type        = number
  default     = 2
}

variable "instance_flex_shape_memory" {
  description = "Compute メモリ（GB）"
  type        = number
  default     = 16
}

variable "instance_boot_volume_size" {
  description = "Compute ブートボリューム（GB）"
  type        = number
  default     = 100
}

variable "instance_boot_volume_vpus" {
  description = "Compute ブートボリューム VPUs/GB（10=Balanced）"
  type        = number
  default     = 10
}

variable "application_port" {
  description = "Gradio アプリ公開ポート"
  type        = number
  default     = 8080

  validation {
    condition     = var.application_port >= 1 && var.application_port <= 65535
    error_message = "application_port は 1〜65535 です。"
  }
}

variable "application_git_tag" {
  description = "デプロイする Git ref（本リポジトリのブランチ・タグ・SHA）"
  type        = string
  default     = "main"
}

variable "github_deploy_key_url" {
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
