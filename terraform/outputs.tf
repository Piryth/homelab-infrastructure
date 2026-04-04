# Outputs used by Ansible and for quick reference after apply.

output "pihole_ip" {
  description = "PiHole container IP"
  value       = var.pihole_ip
}

output "pihole_vmid" {
  description = "PiHole container VMID"
  value       = proxmox_virtual_environment_container.pihole.vm_id
}

output "docker_ip" {
  description = "Docker host container IP"
  value       = var.docker_ip
}

output "docker_vmid" {
  description = "Docker host container VMID"
  value       = proxmox_virtual_environment_container.docker.vm_id
}

output "ansible_inventory" {
  description = "Quick inventory snippet for Ansible"
  value = <<-EOT
    # Auto-generated from Terraform outputs
    [pihole]
    ${var.pihole_hostname} ansible_host=${var.pihole_ip}

    [docker_hosts]
    ${var.docker_hostname} ansible_host=${var.docker_ip}

    [lxc:children]
    pihole
    docker_hosts
  EOT
}
