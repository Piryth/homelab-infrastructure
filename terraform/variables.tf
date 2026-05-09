# -----------------------------------------------------------------------------
# Proxmox connection
# -----------------------------------------------------------------------------
variable "pve_api_url" {
  description = "Proxmox API endpoint"
  type        = string
}

variable "pve_api_token" {
  description = "Proxmox API token"
  type        = string
  sensitive   = true
}

variable "pve_insecure" {
  description = "Skip TLS verification for self-signed certs"
  type        = bool
  default     = true
}

variable "pve_ssh_user" {
  description = "SSH user for PVE node operations (template uploads, etc.)"
  type        = string
  default     = "root"
}

# -----------------------------------------------------------------------------
# PVE nodes
# -----------------------------------------------------------------------------
variable "pve_nodes" {
  description = "Map of PVE node names to their IPs"
  type        = map(string)
  default = {
    pve01 = "192.168.1.20"
    #pve2 = "192.168.1.233"
  }
}

# -----------------------------------------------------------------------------
# Network
# -----------------------------------------------------------------------------
variable "network_gateway" {
  description = "Default gateway for all containers"
  type        = string
  default     = "192.168.1.1"
}

variable "network_cidr" {
  description = "CIDR suffix for container IPs"
  type        = string
  default     = "/24"
}

# -----------------------------------------------------------------------------
# SSH
# -----------------------------------------------------------------------------
variable "ssh_public_keys" {
  description = "SSH public keys to inject into containers"
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# LXC01 : Docker Host
# -----------------------------------------------------------------------------
variable "lxc01" {
  type = object({
    vm_id        = number
    node        = string
    ip          = string
    hostname    = string
    cores       = number
    memory      = number
    disk_size   = number
    swap        = number
    storage     = string
    template    = string
  })
}

# -----------------------------------------------------------------------------
# LXC: PiHole
# -----------------------------------------------------------------------------

variable "lxc02" {
  type = object({
    vm_id       = number
    node        = string
    ip          = string
    hostname    = string
    cores       = number
    memory      = number
    disk_size   = number
    swap        = number
    storage     = string
    template    = string
  })
}

# -----------------------------------------------------------------------------
# LXC 03: Wireguard
# -----------------------------------------------------------------------------

variable "lxc03" {
  type = object({
    vm_id       = number
    node        = string
    ip          = string
    hostname    = string
    cores       = number
    memory      = number
    disk_size   = number
    swap        = number
    storage     = string
    template    = string
  })
}

# -----------------------------------------------------------------------------
# VM01 - OPNSense
# -----------------------------------------------------------------------------

# variable "vm01" {
#   type = object({
#     vm_id       = number
#     name        = string
#     node        = string
#     iso         = string
#     cores       = number
#     memory      = number
#     disk_size   = number
#     wan_bridge  = string
#     lan_bridge  = string
#   })
# }