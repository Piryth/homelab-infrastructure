# 🏠 Homelab Infrastructure

> A fully code-driven homelab running on [Proxmox VE](https://www.proxmox.com/), provisioned with **Terraform** and configured with **Ansible** — covering DNS resolution, reverse proxying, media automation, and self-hosted productivity tools.

---

## 📋 Overview

This repository contains all the Infrastructure-as-Code (IaC) and configuration management for a self-hosted homelab environment. The stack is designed around **repeatability**, **idempotency**, and **security** — every component can be destroyed and rebuilt from a single command sequence.

**Key principles:**

- **No manual steps** — everything is declarative and version-controlled
- **Vault-encrypted secrets** — sensitive values never appear in plaintext
- **Least privilege** — unprivileged LXC containers with minimal surface area
- **Internal DNS** — split-horizon DNS with ad-blocking and DNSSEC validation

---

## 🏗️ Architecture

![Architecture diagram](assets/architecture.drawio.svg)

All containers run on a **192.168.1.0/24** LAN. Caddy handles HTTPS termination with automatic TLS via Cloudflare DNS challenge, exposing all services under the `*.docker.endignous.fr` wildcard domain.

---

## 🗂️ Repository Structure

```
homelab/
├── terraform/          # Provisions LXC containers on Proxmox VE
│   ├── providers.tf    # bpg/proxmox provider configuration
│   ├── variables.tf    # All input variables with descriptions
│   ├── lxc01.tf        # Docker application host container
│   ├── lxc02.tf        # Pi-hole + Unbound DNS container
│   ├── outputs.tf      # Exported values (IPs, hostnames…)
│   └── terraform.tfvars.example  # Template for local secrets
│
├── ansible/            # Configures containers post-provisioning
│   ├── ansible.cfg
│   ├── inventory/      # Host definitions
│   ├── group_vars/     # Vars + Ansible Vault secrets per group
│   ├── playbooks/
│   │   ├── site.yml    # Entry point – runs all playbooks
│   │   ├── docker.yml  # Deploys Docker stacks on lxc01
│   │   └── pve.yml     # Configures Proxmox host storage
│   └── roles/
│       ├── docker_apps/  # Manages all Docker Compose stacks
│       └── pve_storage/  # Configures PVE storage pools
│
└── lxc01/              # Static configs managed outside Ansible
    ├── compose/        # Reference Docker Compose files
    │   ├── caddy/
    │   ├── lss/        # LSS media stack
    │   └── openclaw/
    └── dns/
        └── unbound/    # Unbound recursive resolver config
```

---

## ⚙️ Tech Stack

| Layer                 | Tool                      | Purpose                                              |
| --------------------- | ------------------------- | ---------------------------------------------------- |
| **Hypervisor**        | Proxmox VE                | Bare-metal host running LXC containers               |
| **Provisioning**      | Terraform + `bpg/proxmox` | Declarative container lifecycle                      |
| **Configuration**     | Ansible                   | Idempotent post-provisioning setup                   |
| **Secret Management** | Ansible Vault             | Encrypts API tokens, passwords, WireGuard keys       |
| **Reverse Proxy**     | Caddy                     | Automatic HTTPS with Cloudflare DNS challenge        |
| **DNS**               | Pi-hole + Unbound         | Network-wide ad-blocking + recursive DNSSEC resolver |
| **Container Runtime** | Docker (Docker-in-LXC)    | Isolated application stacks                          |

---

## 🚀 Services

### 🔒 Network & Security

| Service                                               | Description                                                          |
| ----------------------------------------------------- | -------------------------------------------------------------------- |
| **[Caddy](https://caddyserver.com/)**                 | Reverse proxy with automatic TLS, routing all public subdomains      |
| **[Pi-hole](https://pi-hole.net/)**                   | Network-wide DNS sinkhole for ad-blocking                            |
| **[Unbound](https://nlnetlabs.nl/projects/unbound/)** | Recursive, validating DNS resolver (DNSSEC) used as Pi-hole upstream |

### ☁️ Productivity

| Service                                       | Description                                       |
| --------------------------------------------- | ------------------------------------------------- |
| **[Nextcloud](https://nextcloud.com/)**       | Self-hosted cloud storage and collaboration suite |
| **[OnlyOffice](https://www.onlyoffice.com/)** | Online office suite integrated with Nextcloud     |

### 🎬 Media Automation (LSS Stack)

The media stack runs behind a **WireGuard VPN tunnel** for private torrent traffic.

| Service                                                          | Description                               |
| ---------------------------------------------------------------- | ----------------------------------------- |
| **[Jellyfin](https://jellyfin.org/)**                            | Open-source media server                  |
| **[Jellyseerr](https://github.com/Fallenbagel/jellyseerr)**      | Media request management                  |
| **[Sonarr](https://sonarr.tv/)**                                 | TV series automation                      |
| **[Radarr](https://radarr.video/)**                              | Movie automation                          |
| **[Lidarr](https://lidarr.audio/)**                              | Music automation                          |
| **[Bazarr](https://www.bazarr.media/)**                          | Subtitle automation                       |
| **[Prowlarr](https://github.com/Prowlarr/Prowlarr)**             | Indexer manager                           |
| **[qBittorrent](https://www.qbittorrent.org/)**                  | Torrent client (routed through WireGuard) |
| **[Notifiarr](https://notifiarr.com/)**                          | Notifications hub                         |
| **[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)** | Cloudflare bypass for Prowlarr            |

---

## 🛠️ Getting Started

### Prerequisites

- A running **Proxmox VE** node (tested on PVE 8.x)
- **Terraform** ≥ 1.5.0
- **Ansible** ≥ 2.15
- A **Cloudflare** account (for automatic TLS DNS challenge)
- SSH key pair for container access

### 1 — Provision containers with Terraform

```bash
cd terraform/

# Copy and fill in your credentials
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your PVE API endpoint, token, IPs, etc.

terraform init
terraform plan
terraform apply
```

### 2 — Configure containers with Ansible

```bash
cd ansible/

# Decrypt / create your vault file
ansible-vault create group_vars/lxc01/vault.yml
# Add required secrets (see Variables section below)

# Run the full site playbook
ansible-playbook playbooks/site.yml
```

---

## 🔐 Required Secrets

The following secrets must be defined in `ansible/group_vars/<group>/vault.yml` (Ansible Vault encrypted):

| Variable                              | Description                                  |
| ------------------------------------- | -------------------------------------------- |
| `vault_caddy_email`                   | ACME registration email                      |
| `vault_cloudflare_token`              | Cloudflare API token (for DNS challenge)     |
| `vault_lss_wg_private_key`            | WireGuard private key for the VPN tunnel     |
| `vault_lss_wg_public_key`             | WireGuard peer public key                    |
| `vault_nextcloud_mysql_root_password` | MariaDB root password                        |
| `vault_nextcloud_mysql_password`      | Nextcloud DB user password                   |
| `vault_nextcloud_admin_user`          | Nextcloud admin username                     |
| `vault_nextcloud_admin_password`      | Nextcloud admin password                     |
| `vault_nextcloud_smtp_from`           | SMTP sender address (via Proton Mail Bridge) |
| `vault_nextcloud_smtp_user`           | SMTP username                                |
| `vault_nextcloud_smtp_password`       | SMTP password                                |
| `vault_onlyoffice_secret`             | OnlyOffice JWT secret                        |

Terraform secrets (Proxmox API token, SSH keys) are stored in `terraform/terraform.tfvars`, which is git-ignored. Use `terraform.tfvars.example` as a reference.

---

## 📄 License

This project is open-sourced for portfolio and educational purposes. Feel free to adapt any part of it for your own homelab.
