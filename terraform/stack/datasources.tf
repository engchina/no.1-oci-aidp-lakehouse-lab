# =============================================================
# Data sources: Compute サブネット参照 + cloud-init テンプレート
# =============================================================

data "oci_core_subnet" "selected_compute_subnet" {
  subnet_id = var.subnet_id
}

data "template_file" "cloud_init_file" {
  template = file("${path.module}/cloud_init/bootstrap.template.yaml")

  vars = {
    region                    = var.region
    compartment_id            = var.compartment_ocid
    atp_conn                  = base64gzip("admin/${var.atp_password}@${lower(var.atp_name)}_high")
    atp_password              = base64gzip(var.atp_password)
    lakehouse_conn            = base64gzip("admin/${var.lakehouse_password}@${lower(var.lakehouse_name)}_high")
    lakehouse_password        = base64gzip(var.lakehouse_password)
    atp_name                  = var.atp_name
    lakehouse_name            = var.lakehouse_name
    aidp_ocid                 = oci_ai_data_platform_ai_data_platform.aidp.id
    oac_name                  = var.oac_name
    os_bucket_name            = var.os_bucket_name
    app_admin_password        = base64gzip(var.app_admin_password)
    app_port                  = var.app_port
    app_git_ref               = var.app_git_ref
    app_github_deploy_key_url = var.app_github_deploy_key_url
    atp_wallet_content        = data.external.atp_wallet_files.result.wallet_content
    lakehouse_wallet_content  = data.external.lakehouse_wallet_files.result.wallet_content
  }
}

data "template_cloudinit_config" "cloud_init" {
  gzip          = true
  base64_encode = true

  part {
    filename     = "bootstrap.yaml"
    content_type = "text/cloud-config"
    content      = data.template_file.cloud_init_file.rendered
  }
}
