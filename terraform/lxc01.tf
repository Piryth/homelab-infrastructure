resource "proxmox_virtual_environment_container" "docker" {
  # -------------------------------------------------------
  # Identity
  # -------------------------------------------------------
  vm_id     = var.docker_vmid
  node_name = var.docker_node

  description = "Docker application host"

  tags = ["docker", "apps"]

  # -------------------------------------------------------
  # Template
  # -------------------------------------------------------
  operating_system {
    template_file_id = var.docker_template
    type             = "debian"
  }

  # -------------------------------------------------------
  # Compute
  # -------------------------------------------------------
  cpu {
    cores = var.docker_cores
  }

  memory {
    dedicated = var.docker_memory
    swap      = var.docker_swap
  }

  # -------------------------------------------------------
  # Storage
  # -------------------------------------------------------
  disk {
    datastore_id = var.docker_storage
    size         = var.docker_disk_size
  }

  # -------------------------------------------------------
  # Network
  # -------------------------------------------------------
  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
  }

  initialization {
    hostname = var.docker_hostname

    ip_config {
      ipv4 {
        address = "${var.docker_ip}${var.network_cidr}"
        gateway = var.network_gateway
      }
    }

    dns {
      servers = [var.pihole_ip, var.network_gateway]
      domain  = "lan"
    }

    user_account {
      keys = var.ssh_public_keys
    }
  }

  # -------------------------------------------------------
  # Options — nesting REQUIRED for Docker-in-LXC
  # -------------------------------------------------------
  started       = true
  start_on_boot = true
  unprivileged  = true

  features {
    nesting = true
    keyctl  = true   # required by Docker for key management
  }

  # -------------------------------------------------------
  # Lifecycle
  # -------------------------------------------------------
  lifecycle {
    prevent_destroy = true

    ignore_changes = [
      operating_system,
      initialization,
    ]
  }
}
