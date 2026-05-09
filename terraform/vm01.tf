# resource "proxmox_virtual_environment_vm" "vm01" {
#   vm_id     = var.vm01.vm_id
#   name      = var.vm01.name
#   node_name = var.vm01.node

#   cpu {
#     cores = var.vm01.cores
#     type  = "x86-64-v2-AES"
#   }

#   memory {
#     dedicated = var.vm01.memory
#   }

#   # Interface WAN
#   network_device {
#     bridge = var.vm01.wan_bridge
#     model  = "virtio"
#   }

#   serial_device {
#     device = "socket"
#   }


#   # Interface LAN
#   network_device {
#     bridge = var.vm01.lan_bridge
#     model  = "virtio"
#   }

#   disk {
#     datastore_id = "local-lvm"
#     size         = var.vm01.disk_size
#     interface    = "virtio0"
#   }

#   cdrom {
#     file_id = var.vm01.iso
#   }

#   boot_order = ["ide3", "virtio0"]
# }