resource "proxmox_virtual_environment_container" "lxc02" {
  # -------------------------------------------------------
  # Identity
  # -------------------------------------------------------
  vm_id     = var.lxc02.vm_id
  node_name = var.lxc02.node

  description = "PiHole + Unbound DNS resolver"

  tags = ["dns", "pihole", "infrastructure"]

  # -------------------------------------------------------
  # Template (only used on first create, ignored on import)
  # -------------------------------------------------------
  operating_system {
    template_file_id = var.lxc02.template
    type             = "debian"
  }

  # -------------------------------------------------------
  # Compute
  # -------------------------------------------------------
  cpu {
    cores = var.lxc02.cores
  }

  memory {
    dedicated = var.lxc02.memory
    swap      = var.lxc02.swap
  }

  # -------------------------------------------------------
  # Storage
  # -------------------------------------------------------
  disk {
    datastore_id = var.lxc02.storage
    size         = var.lxc02.disk_size
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
    hostname = var.lxc02.hostname

    ip_config {
      ipv4 {
        address = "${var.lxc02.ip}${var.network_cidr}"
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
