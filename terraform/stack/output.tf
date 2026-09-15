# =============================================================
# Outputs — デプロイ結果のまとめ
# =============================================================

output "atp_connection_string" {
  description = "ATP の ADMIN 接続文字列（user/password@dsn、high）"
  value       = "admin/${var.atp_password}@${lower(var.atp_name)}_high"
  sensitive   = true
}

output "atp_db_ocid" {
  description = "ATP Autonomous Database OCID"
  value       = oci_database_autonomous_database.atp.id
}

output "lakehouse_connection_string" {
  description = "AI Lakehouse の ADMIN 接続文字列（user/password@dsn、high）"
  value       = "admin/${var.lakehouse_password}@${lower(var.lakehouse_name)}_high"
  sensitive   = true
}

output "lakehouse_db_ocid" {
  description = "AI Lakehouse Autonomous Database OCID"
  value       = oci_database_autonomous_database.lakehouse.id
}

output "aidp_instance_ocid" {
  description = "AIDP Workbench インスタンス OCID。コンソール: https://aidp.oci.oraclecloud.com/?ocid=<この値>"
  value       = oci_ai_data_platform_ai_data_platform.aidp.id
}

output "oac_instance_name" {
  description = "OAC インスタンス名。URL は OCI コンソールの「アナリティクス・クラウド」から確認（形式: https://<name>.analytics.oc<リージョンコード>.oraclecloud.com）"
  value       = var.oac_name
}

output "app_url" {
  description = "Gradio 設定アプリのURL（パブリックサブネットの場合）"
  value       = "http://${local.compute_access_ip}:${var.app_port}"
}

output "ssh_to_instance" {
  description = "Compute インスタンスへの SSH コマンド"
  value       = "ssh -o ServerAliveInterval=10 ubuntu@${oci_core_instance.compute.public_ip}"
}

output "object_storage_bucket" {
  description = "AIDP Delta データ保存バケット名（namespace はコンソールで確認）"
  value       = var.os_bucket_name
}
