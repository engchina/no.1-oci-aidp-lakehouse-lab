# =============================================================
# ATP（OLTP）— 航空会社運航データのソースシステム
# ハンズオン 前編 Task 2〜5 に相当。source_01 スキーマ等の
# DB 内オブジェクトは Gradio アプリの「Lab DB 初期化」タブで作成。
# =============================================================

resource "oci_database_autonomous_database" "atp" {
  admin_password                                 = var.atp_password
  autonomous_maintenance_schedule_type           = "REGULAR"
  backup_retention_period_in_days                = var.adb_backup_retention_period_in_days
  character_set                                  = "AL32UTF8"
  compartment_id                                 = var.compartment_ocid
  compute_count                                  = var.atp_compute_count
  compute_model                                  = "ECPU"
  data_storage_size_in_tbs                       = var.atp_data_storage_size_in_tbs
  db_name                                        = var.atp_name
  db_version                                     = "26ai"
  db_workload                                    = "OLTP"
  display_name                                   = var.atp_display_name
  is_auto_scaling_enabled                        = true
  is_auto_scaling_for_storage_enabled            = true
  is_dedicated                                   = "false"
  is_mtls_connection_required                    = true
  is_preview_version_with_service_terms_accepted = "false"
  license_model                                  = var.adb_license_model
  ncharacter_set                                 = "AL16UTF16"
  # ネットワークアクセス（nl2sql 参照の導出）:
  #   PUBLIC     → 両者 unset（パブリック・エンドポイント）
  #   SECURE_ACL → whitelisted_ips
  #   PRIVATE    → subnet_id
  subnet_id       = local.adb_private_endpoint_enabled ? var.adb_subnet_id : null
  whitelisted_ips = local.adb_secure_acl_enabled ? local.adb_whitelisted_ip_entries : null

  lifecycle {
    precondition {
      condition     = !(local.adb_private_endpoint_enabled && trimspace(var.adb_subnet_id) == "")
      error_message = "adb_network_access_type = PRIVATE の場合、adb_subnet_id を指定してください。"
    }
    precondition {
      condition     = !(local.adb_secure_acl_enabled && length(local.adb_whitelisted_ip_entries) == 0)
      error_message = "adb_network_access_type = SECURE_ACL の場合、adb_whitelisted_ips を指定してください。"
    }
  }
}

# ATP 用インスタンスウォレット（アプリの oracledb 接続・OAC 接続で使う）
resource "oci_database_autonomous_database_wallet" "atp_wallet" {
  autonomous_database_id = oci_database_autonomous_database.atp.id
  password               = var.atp_password
  base64_encode_content  = "true"
  generate_type          = "SINGLE"
}

resource "local_file" "atp_wallet_zip" {
  content_base64 = oci_database_autonomous_database_wallet.atp_wallet.content
  filename       = "${path.module}/wallet_atp.zip"
}

# ウォレットから不要ファイルを除去した base64 を cloud-init に渡す
data "external" "atp_wallet_files" {
  depends_on = [local_file.atp_wallet_zip]
  program    = ["bash", "${path.module}/extract_wallet.sh", "${path.module}/wallet_atp.zip"]
}

# =============================================================
# Autonomous AI Lakehouse — AIDP のベクトル DB / Gold 格納先
# ハンズオン 前編 Task 6〜9 に相当。gold_01 スキーマ等の
# DB 内オブジェクトは Gradio アプリの「Lab DB 初期化」タブで作成。
# =============================================================

resource "oci_database_autonomous_database" "lakehouse" {
  admin_password                                 = var.lakehouse_password
  autonomous_maintenance_schedule_type           = "REGULAR"
  backup_retention_period_in_days                = var.adb_backup_retention_period_in_days
  character_set                                  = "AL32UTF8"
  compartment_id                                 = var.compartment_ocid
  compute_count                                  = var.lakehouse_compute_count
  compute_model                                  = "ECPU"
  data_storage_size_in_tbs                       = var.lakehouse_data_storage_size_in_tbs
  db_name                                        = var.lakehouse_name
  db_version                                     = "26ai"
  db_workload                                    = "LH"
  display_name                                   = var.lakehouse_display_name
  is_auto_scaling_enabled                        = true
  is_auto_scaling_for_storage_enabled            = true
  is_dedicated                                   = "false"
  is_mtls_connection_required                    = true
  is_preview_version_with_service_terms_accepted = "false"
  license_model                                  = var.adb_license_model
  ncharacter_set                                 = "AL16UTF16"
  # ネットワークアクセス（ATP と同じ方式が共通適用される）
  subnet_id       = local.adb_private_endpoint_enabled ? var.adb_subnet_id : null
  whitelisted_ips = local.adb_secure_acl_enabled ? local.adb_whitelisted_ip_entries : null

  lifecycle {
    precondition {
      condition     = !(local.adb_private_endpoint_enabled && trimspace(var.adb_subnet_id) == "")
      error_message = "adb_network_access_type = PRIVATE の場合、adb_subnet_id を指定してください。"
    }
    precondition {
      condition     = !(local.adb_secure_acl_enabled && length(local.adb_whitelisted_ip_entries) == 0)
      error_message = "adb_network_access_type = SECURE_ACL の場合、adb_whitelisted_ips を指定してください。"
    }
  }
}

# Lakehouse 用インスタンスウォレット
resource "oci_database_autonomous_database_wallet" "lakehouse_wallet" {
  autonomous_database_id = oci_database_autonomous_database.lakehouse.id
  password               = var.lakehouse_password
  base64_encode_content  = "true"
  generate_type          = "SINGLE"
}

resource "local_file" "lakehouse_wallet_zip" {
  content_base64 = oci_database_autonomous_database_wallet.lakehouse_wallet.content
  filename       = "${path.module}/wallet_lh.zip"
}

data "external" "lakehouse_wallet_files" {
  depends_on = [local_file.lakehouse_wallet_zip]
  program    = ["bash", "${path.module}/extract_wallet.sh", "${path.module}/wallet_lh.zip"]
}
