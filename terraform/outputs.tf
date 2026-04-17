# Outputs used by Ansible and for quick reference after apply.

output "lxc02_ip" {
  description = "PiHole container IP"
  value       = var.lxc02_ip
}

output "lxc02_vmid" {
  description = "PiHole container VMID"
  value       = proxmox_virtual_environment_container.lxc02.vm_id
}

output "lxc01_ip" {
  description = "Docker host container IP"
  value       = var.lxc01_ip
}

output "lxc01_vmid" {
  description = "Docker host container VMID"
  value       = proxmox_virtual_environment_container.lxc01.vm_id
}

output "ansible_inventory" {
  description = "Quick inventory snippet for Ansible"
  value = <<-EOT
    # Auto-generated from Terraform outputs
    [pihole]
    ${var.lxc02_hostname} ansible_host=${var.lxc02_ip}

    [lxc01_hosts]
    ${var.lxc01_hostname} ansible_host=${var.lxc01_ip}

    [lxc:children]
    pihole
    lxc01_hosts
  EOT
}
