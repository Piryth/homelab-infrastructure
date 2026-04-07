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
    pve1 = "192.168.1.20"
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
# LXC: PiHole
# -----------------------------------------------------------------------------
variable "pihole_vmid" {
  description = "VMID for the PiHole LXC container"
  type        = number
}

variable "pihole_node" {
  description = "PVE node hosting PiHole"
  type        = string
}

variable "pihole_ip" {
  description = "Static IP for PiHole container"
  type        = string
  default     = "192.168.1.20"
}

variable "pihole_hostname" {
  description = "Hostname for PiHole container"
  type        = string
  default     = "pihole"
}

variable "pihole_cores" {
  description = "CPU cores for PiHole"
  type        = number
  default     = 1
}

variable "pihole_memory" {
  description = "Memory in MB for PiHole"
  type        = number
  default     = 512
}

variable "pihole_swap" {
  description = "Swap in MB for PiHole"
  type        = number
  default     = 256
}

variable "pihole_disk_size" {
  description = "Root disk size in GB for PiHole"
  type        = number
  default     = 8
}

variable "pihole_storage" {
  description = "PVE storage pool for PiHole root disk"
  type        = string
  default     = "local-lvm"
}

variable "pihole_template" {
  description = "LXC template used for PiHole (for reference, not changed on import)"
  type        = string
  default     = "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
}

# -----------------------------------------------------------------------------
# LXC: Docker Host
# -----------------------------------------------------------------------------
variable "docker_vmid" {
  description = "VMID for the Docker LXC container"
  type        = number
}

variable "docker_node" {
  description = "PVE node hosting the Docker container"
  type        = string
}

variable "docker_ip" {
  description = "Static IP for Docker container"
  type        = string
  default     = "192.168.1.30"
}

variable "docker_hostname" {
  description = "Hostname for Docker container"
  type        = string
  default     = "docker"
}

variable "docker_cores" {
  description = "CPU cores for Docker host"
  type        = number
  default     = 2
}

variable "docker_memory" {
  description = "Memory in MB for Docker host"
  type        = number
  default     = 2048
}

variable "docker_swap" {
  description = "Swap in MB for Docker host"
  type        = number
  default     = 512
}

variable "docker_disk_size" {
  description = "Root disk size in GB for Docker host"
  type        = number
  default     = 32
}

variable "docker_storage" {
  description = "PVE storage pool for Docker root disk"
  type        = string
  default     = "local-lvm"
}

variable "docker_template" {
  description = "LXC template used for Docker host"
  type        = string
  default     = "local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst"
}
