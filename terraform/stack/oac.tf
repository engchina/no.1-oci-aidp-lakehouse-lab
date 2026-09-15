# =============================================================
# Oracle Analytics Cloud（OAC）
# ハンズオン 前編 Task 12 に相当。
# 注意: idcs_access_token は事前に IDCS から生成したアクセストークン。
# =============================================================

resource "oci_analytics_analytics_instance" "oac" {
  compartment_id    = var.compartment_ocid
  name              = var.oac_name
  description       = "AIDP lab OAC instance"
  feature_set       = "SELF_SERVICE_ANALYTICS"
  license_type      = "LICENSE_INCLUDED"
  idcs_access_token = var.oac_idcs_access_token
  state             = "ACTIVE"

  capacity {
    capacity_type  = "USER_COUNT"
    capacity_value = var.oac_user_count
  }

  network_endpoint_details {
    network_endpoint_type = "PUBLIC"
  }
}
