resource "proxmox_virtual_environment_container" "lxc03" {
  # -------------------------------------------------------
  # Identity
  # -------------------------------------------------------
  vm_id     = var.lxc03.vm_id
  node_name = var.lxc03.node

  description = "PiHole + Unbound DNS resolver"

  tags = ["dns", "pihole", "infrastructure"]

  # -------------------------------------------------------
  # Template (only used on first create, ignored on import)
  # -------------------------------------------------------
  operating_system {
    template_file_id = var.lxc03.template
    type             = "debian"
  }

  # -------------------------------------------------------
  # Compute
  # -------------------------------------------------------
  cpu {
    cores = var.lxc03.cores
  }

  memory {
    dedicated = var.lxc03.memory
    swap      = var.lxc03.swap
  }

  # -------------------------------------------------------
  # Storage
  # -------------------------------------------------------
  disk {
    datastore_id = var.lxc03.storage
    size         = var.lxc03.disk_size
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
    hostname = var.lxc03.hostname

    ip_config {
      ipv4 {
        address = "${var.lxc03.ip}${var.network_cidr}"
        gateway = var.network_gateway
      }
    }

    dns {
      servers = ["127.0.0.1", var.network_gateway]
      domain  = "lan"
    }

    user_account {
      keys = var.ssh_public_keys
    }
  }

  # -------------------------------------------------------
  # Options
  # -------------------------------------------------------
  started       = true
  start_on_boot = true
  unprivileged  = true

  features {
    nesting = false
  }

  console {
  enabled   = true
  tty_count = 2
  type      = "tty"
  }

  # -------------------------------------------------------
  # Lifecycle — prevent accidental destruction
  # -------------------------------------------------------
  lifecycle {
    prevent_destroy = true

    # Ignore changes that PVE may drift on, or that we manage
    # outside Terraform during the initial import phase.
    ignore_changes = [
      operating_system,
      initialization,
    ]
  }
}
