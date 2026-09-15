locals {
  # Compute サブネットがパブリック IP 発行禁止の場合、アクセス IP は private_ip
  compute_subnet_prohibits_public_ip = coalesce(
    data.oci_core_subnet.selected_compute_subnet.prohibit_public_ip_on_vnic,
    false,
  )

  instance_access_ip = local.compute_subnet_prohibits_public_ip ? (
    oci_core_instance.lab_instance.private_ip
    ) : (
    oci_core_instance.lab_instance.public_ip
  )
}
