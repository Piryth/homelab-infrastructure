resource "proxmox_virtual_environment_container" "lxc01" {
  # -------------------------------------------------------
  # Identity
  # -------------------------------------------------------
  vm_id     = var.lxc01_vmid
  node_name = var.lxc01_node

  description = "Docker application host"

  tags = ["docker", "apps"]

  # -------------------------------------------------------
  # Template
  # -------------------------------------------------------
  operating_system {
    template_file_id = var.lxc01_template
    type             = "debian"
  }

  # -------------------------------------------------------
  # Compute
  # -------------------------------------------------------
  cpu {
    cores = var.lxc01_cores
  }

  memory {
    dedicated = var.lxc01_memory
    swap      = var.lxc01_swap
  }

  # -------------------------------------------------------
  # Storage
  # -------------------------------------------------------
  disk {
    datastore_id = var.lxc01_storage
    size         = var.lxc01_disk_size
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
    hostname = var.lxc01_hostname

    ip_config {
      ipv4 {
        address = "${var.lxc01_ip}${var.network_cidr}"
        gateway = var.network_gateway
      }
    }

    dns {
      servers = [var.lxc02_ip, var.network_gateway]
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
  shared = true
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
