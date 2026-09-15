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
}
