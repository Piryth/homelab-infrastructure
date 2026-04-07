resource "proxmox_virtual_environment_container" "pihole" {
  # -------------------------------------------------------
  # Identity
  # -------------------------------------------------------
  vm_id     = var.pihole_vmid
  node_name = var.pihole_node

  description = "PiHole + Unbound DNS resolver"

  tags = ["dns", "pihole", "infrastructure"]

  # -------------------------------------------------------
  # Template (only used on first create, ignored on import)
  # -------------------------------------------------------
  operating_system {
    template_file_id = var.pihole_template
    type             = "debian"
  }

  # -------------------------------------------------------
  # Compute
  # -------------------------------------------------------
  cpu {
    cores = var.pihole_cores
  }

  memory {
    dedicated = var.pihole_memory
    swap      = var.pihole_swap
  }

  # -------------------------------------------------------
  # Storage
  # -------------------------------------------------------
  disk {
    datastore_id = var.pihole_storage
    size         = var.pihole_disk_size
  }

  # -------------------------------------------------------
  # Network
  # -------------------------------------------------------
  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
  }

  initialization {
    hostname = var.pihole_hostname

    ip_config {
      ipv4 {
        address = "${var.pihole_ip}${var.network_cidr}"
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
