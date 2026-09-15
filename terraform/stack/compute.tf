# =============================================================
# Compute インスタンス — Gradio 設定アプリのホスト
# No.1-SQL-Assist と同じパターン:
# cloud-init で props を書き込み、init_script.sh が
# 依存パッケージのインストール・アプリ起動まで行う。
# =============================================================

resource "oci_core_instance" "lab_instance" {
  depends_on = [
    oci_database_autonomous_database.atp,
    oci_database_autonomous_database.lakehouse,
    oci_database_autonomous_database_wallet.atp_wallet,
    oci_database_autonomous_database_wallet.lakehouse_wallet,
    data.external.atp_wallet_files,
    data.external.lakehouse_wallet_files,
  ]

  availability_config {
    is_live_migration_preferred = "false"
    recovery_action             = "STOP_INSTANCE"
  }
  availability_domain = var.availability_domain
  compartment_id      = var.compartment_ocid
  create_vnic_details {
    assign_ipv6ip             = "false"
    assign_private_dns_record = "true"
    assign_public_ip          = !local.compute_subnet_prohibits_public_ip
    subnet_id                 = var.subnet_id
  }
  display_name = var.instance_display_name
  instance_options {
    are_legacy_imds_endpoints_disabled = "false"
  }
  metadata = {
    "user_data"           = data.template_cloudinit_config.cloud_init.rendered
    "ssh_authorized_keys" = var.ssh_authorized_keys
  }
  platform_config {
    is_symmetric_multi_threading_enabled = "true"
    type                                 = "AMD_VM"
  }
  shape = var.instance_shape
  shape_config {
    baseline_ocpu_utilization = "BASELINE_1_1"
    memory_in_gbs             = var.instance_flex_shape_memory
    ocpus                     = var.instance_flex_shape_ocpus
  }
  source_details {
    boot_volume_size_in_gbs = var.instance_boot_volume_size
    boot_volume_vpus_per_gb = var.instance_boot_volume_vpus
    source_id               = var.instance_image_source_id
    source_type             = "image"
  }

  lifecycle {
    precondition {
      condition     = trimspace(var.app_admin_password) != ""
      error_message = "app_admin_password must be configured."
    }
  }
}
