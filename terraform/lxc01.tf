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

  # fuse is REQUIRED for the rclone (1Fichier) and mergerfs mounts.
  # Changing features other than nesting requires root@pam, not an API token:
  # set by hand on pve01 (see README), ignored in lifecycle below.
  features {
    nesting = true
    keyctl  = true
    fuse    = true
  }

  # Local seeding disk (mergerfs branch 1): torrents + hardlinked media.
  # Mounted at /data/local, NOT /data, so /data/config stays on the rootfs.
  # Hard cap for media: a full disk never reaches the OS or the app configs.
  # Created by hand on pve01 (see README): bpg replaces the whole CT when a
  # disk mount point changes, so it is ignored in lifecycle below.
  # discard returns freed blocks to the thin pool (local-lvm).
  mount_point {
    volume = "local-lvm"
    size   = "512G"
    path   = "/data/local"

    mount_options = ["discard"]
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
      # Managed by hand via pct set on pve01 (see comments above)
      mount_point,
      features,
    ]
  }
}
