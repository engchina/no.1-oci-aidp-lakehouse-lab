locals {
  # Compute サブネットがパブリック IP 発行禁止の場合、アクセス IP は private_ip
  compute_subnet_prohibits_public_ip = coalesce(
    data.oci_core_subnet.selected_compute_subnet.prohibit_public_ip_on_vnic,
    false,
  )

  compute_access_ip = local.compute_subnet_prohibits_public_ip ? (
    oci_core_instance.compute.private_ip
    ) : (
    oci_core_instance.compute.public_ip
  )

  # ---------------------------------------------------------------
  # ADB ネットワークアクセス方式（参照: no.1-production-ready-nl2sql）
  # adb_network_access_type から subnet_id / whitelisted_ips を導出する
  # ---------------------------------------------------------------
  adb_private_endpoint_enabled = var.adb_network_access_type == "PRIVATE"
  adb_secure_acl_enabled       = var.adb_network_access_type == "SECURE_ACL"
  adb_public_access_enabled    = var.adb_network_access_type == "PUBLIC"

  # SECURE_ACL のホワイトリストエントリ（カンマ区切り → リスト、空白のみを除外）
  adb_whitelisted_ip_entries = local.adb_secure_acl_enabled ? [
    for entry in split(",", var.adb_whitelisted_ips) : trimspace(entry)
    if trimspace(entry) != ""
  ] : []
}
