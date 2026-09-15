# =============================================================
# Vault（Lakehouse ADMIN パスワードを AIDP に渡す secret 用）
# KMS vault → KMS key → Vault secret（初期 version をインライン作成）
# =============================================================

resource "oci_kms_vault" "lab_vault" {
  compartment_id = var.compartment_ocid
  display_name   = "aidp-lab-vault"
  # RM = リージョン全体で使える Vault（VM vault ではない）
  vault_type = "RM"
}

# KMS vault の管理エンドポイント（管理操作: key の作成/参照）
data "oci_kms_vault" "lab_vault" {
  depends_on = [oci_kms_vault.lab_vault]
  vault_id   = oci_kms_vault.lab_vault.id
}

# KMS key はコンパートメント既定の vault に作成される（vault_id は computed のみ）
resource "oci_kms_key" "lab_key" {
  compartment_id      = var.compartment_ocid
  display_name        = "aidp-lab-key"
  management_endpoint = data.oci_kms_vault.lab_vault.management_endpoint
  key_shape {
    # AES256（length はバイト単位）
    algorithm = "AES"
    length    = 32
  }
}

resource "oci_vault_secret" "lakehouse_admin_secret" {
  compartment_id = var.compartment_ocid
  vault_id       = oci_kms_vault.lab_vault.id
  key_id         = oci_kms_key.lab_key.id
  secret_name    = "lakehouse-admin-password"
  description    = "AI Lakehouse ADMIN password for AIDP"

  secret_content {
    content_type = "text/plain"
    content      = var.lakehouse_password
  }
}

# =============================================================
# AI Data Platform Workbench
# ハンズオン 前編 Task 10 に相当。
# 注意:
# - vector_db_id は Lakehouse ADB が必須（Terraform の依存関係で自動作成順）
# - AIDP 標準ポリシー（Standard / Enable object deletion）は
#   Terraform リソースが policies を露出していないため、
#   作成後に AIDP コンソールで手動追加する（README 参照）
# - secret を AIDP が読める IAM ポリシーも Standard ポリシーに含める
# =============================================================

resource "oci_ai_data_platform_ai_data_platform" "lab" {
  compartment_id            = var.compartment_ocid
  display_name              = var.aidp_display_name
  default_workspace_name    = var.aidp_workspace_name
  vector_db_id              = oci_database_autonomous_database.lakehouse.id
  vector_db_admin_secret_id = oci_vault_secret.lakehouse_admin_secret.id
  is_enable_ai_feature      = true
}
