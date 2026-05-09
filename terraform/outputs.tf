# Outputs used by Ansible and for quick reference after apply.


output "lxc01_ip" {
  description = "Docker host container IP"
  value       = var.lxc01.ip
}

output "lxc01_vmid" {
  description = "Docker host container VMID"
  value       = proxmox_virtual_environment_container.lxc01.vm_id
}

output "lxc02_ip" {
  description = "PiHole container IP"
  value       = var.lxc02.ip
}

output "lxc02_vmid" {
  description = "PiHole container VMID"
  value       = proxmox_virtual_environment_container.lxc02.vm_id
}

output "lxc03_ip" {
  description = "WG host container IP"
  value       = var.lxc03.ip
}

output "lxc03_vmid" {
  description = "WG host container VMID"
  value       = proxmox_virtual_environment_container.lxc03.vm_id
}

output "ansible_inventory" {
  description = "Quick inventory snippet for Ansible"
  value = <<-EOT
    # Auto-generated from Terraform outputs
    [lxc01_hosts]
    ${var.lxc01.hostname} ansible_host=${var.lxc01.ip}
    
    [pihole]
    ${var.lxc02.hostname} ansible_host=${var.lxc02.ip}

    [lxc03]
    ${var.lxc03.hostname} ansible_host=${var.lxc03.ip}

    [lxc:children]
    pihole
    lxc01_hosts
    lxc03
  EOT
}
