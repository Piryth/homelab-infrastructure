resource "proxmox_virtual_environment_container" "lxc01" {
  # -------------------------------------------------------
  # Identity
  # -------------------------------------------------------
  vm_id     = var.lxc01.vm_id
  node_name = var.lxc01.node

  description = "Docker application host"

  tags = ["docker", "apps"]

  # -------------------------------------------------------
  # Template
  # -------------------------------------------------------
  operating_system {
    template_file_id = var.lxc01.template
    type             = "debian"
  }

  # -------------------------------------------------------
  # Compute
  # -------------------------------------------------------
  cpu {
    cores = var.lxc01.cores
  }

  memory {
    dedicated = var.lxc01.memory
    swap      = var.lxc01.swap
  }

  # -------------------------------------------------------
  # Storage
  # -------------------------------------------------------
  disk {
    datastore_id = var.lxc01.storage
    size         = var.lxc01.disk_size
  }

  # -------------------------------------------------------
  # Network
  # -------------------------------------------------------
  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
    firewall = true
  }

  initialization {
    hostname = var.lxc01.hostname
    ip_config {
      ipv4 {
        address = "${var.lxc01.ip}${var.network_cidr}"
        gateway = var.network_gateway
      }
    }

    dns {
      servers = [var.lxc02.ip, var.network_gateway]
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
    keyctl  = true 
  }

  mount_point {
  volume = "/mnt/pool"
  path   = "/mnt/pool"
  shared = false
  }

console {
  enabled   = true
  tty_count = 2
  type      = "tty"
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
