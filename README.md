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






# 🏠 Homelab Infrastructure

![Last Updated](https://img.shields.io/badge/Last_Updated-July_2026-brightgreen?style=for-the-badge)
![Terraform](https://img.shields.io/badge/terraform-%235835CC.svg?style=for-the-badge&logo=terraform&logoColor=white)
![Ansible](https://img.shields.io/badge/ansible-%231A1918.svg?style=for-the-badge&logo=ansible&logoColor=white)
![Proxmox](https://img.shields.io/badge/Proxmox-%23E57000.svg?style=for-the-badge&logo=proxmox&logoColor=white)

A fully code-driven homelab running on a single-node Proxmox VE, provisioned with Terraform and configured with Ansible. It covers DNS resolution, reverse proxying, media automation, and self-hosted productivity tools.

## 📋 Context & Overview

This repository contains all the Infrastructure-as-Code (IaC) and configuration management for my self-hosted homelab. 

More than just a deployment script, this project is an **exercise in building resilient architecture under strict constraints**:
* **Hardware Limitations:** Running on a recycled Intel Core i7 laptop (8GB RAM). The battery was purposefully removed to safely allow 24/7 operation and prevent hardware damage (swollen battery risk).
* **Network Constraints:** Deployed on a flat domestic ISP network (`192.168.1.0/24`) with no hardware VLAN support. Network segmentation and security are entirely handled at the software and OS levels.
* **Storage Instability:** Previous reliance on aging hard drives and a faulty DAS, requiring strict statelessness for compute nodes.

### 🎯 Key Design Principles
* **No manual steps:** Everything is declarative and version-controlled. The entire stack can be destroyed and rebuilt from a single command sequence.
* **Vault-encrypted secrets:** Sensitive values (API tokens, DB passwords) never appear in plaintext.
* **Least privilege & Software Security:** Unprivileged LXC containers with minimal surface area, hardened SSH, UFW, and fail2ban to compensate for the lack of hardware network segmentation.
* **Internal DNS:** Split-horizon DNS with ad-blocking and DNSSEC validation.

---

## 🏗️ Architecture & Hardware

*(Insert Architecture Diagram Here)*

**Hardware Setup:**
* **Hypervisor:** Recycled Laptop (Intel i7, 8GB RAM) running Proxmox VE.
* **External Node:** Raspberry Pi 5 (16GB RAM) used for out-of-cluster debugging and side-projects.
* **Network Access:** All containers run on the flat LAN. External secure access is provided via a **Tailscale** zero-trust tunnel. Caddy handles HTTPS termination with automatic TLS via Cloudflare DNS challenge, exposing services under the `*.docker.endignous.fr` wildcard domain.

---

## 🗂️ Repository Structure

```text
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
    └── dns/            # Unbound recursive resolver config

## ⚙️ Tech Stack

| Layer | Tool | Purpose |
| :--- | :--- | :--- |
| **Hypervisor** | Proxmox VE | Bare-metal host running LXC containers |
| **Provisioning** | Terraform + bpg/proxmox | Declarative container lifecycle |
| **Configuration** | Ansible | Idempotent post-provisioning setup |
| **Secret Management** | Ansible Vault | Encrypts API tokens, passwords, WireGuard keys |
| **Reverse Proxy** | Caddy | Automatic HTTPS with Cloudflare DNS challenge |
| **DNS** | Pi-hole + Unbound | Network-wide ad-blocking + recursive DNSSEC resolver |
| **Container Runtime** | Docker (in LXC) | Isolated application stacks |

## 🚀 Services

### 🔒 Network & Security

| Service | Description |
| :--- | :--- |
| **Caddy** | Reverse proxy with automatic TLS, routing all public subdomains |
| **Tailscale** | Zero-Trust Network Access (ZTNA) for remote administration |
| **Pi-hole** | Network-wide DNS sinkhole for ad-blocking |
| **Unbound** | Recursive, validating DNS resolver (DNSSEC) used as Pi-hole upstream |

☁️ Productivity & Media (Arr Stack)

The media stack runs behind a WireGuard VPN tunnel for private torrent traffic.
| Service | Description |
| :--- | :--- |
| **Nextcloud & OnlyOffice** | Self-hosted cloud storage and collaboration suite |
| **Jellyfin / Jellyseerr** | Open-source media server and request management |
| **The *Arr Stack** | Sonarr, Radarr, Lidarr, Bazarr, Prowlarr |
| **qBittorrent** | Torrent client (routed strictly through WireGuard) |

## 💥 Incident Post-Mortem & Lessons Learned

A significant challenge in this project was dealing with hardware failures, specifically a 4-bay DAS (IcyBox) that caused severe infrastructure instability.

+ Incident: The Proxmox cluster experienced multiple kernel panics, and data corruption occurred on the external Raspberry Pi node.
+ Investigation: Debugging kernel traces (dmesg / syslog) revealed massive I/O errors pointing to electrical interference and unstable power delivery from the DAS controller.
+ Mitigation: Attempted to isolate the failing hardware by connecting the DAS to the Raspberry Pi and sharing the storage via Samba. The hardware remained completely unstable.
+ Resolution: Complete decommissioning of the DAS to protect the host compute node. This highlighted the importance of treating storage as an untrusted dependency in low-budget homelabs.

## 🛣️ Roadmap

This infrastructure is a living project. Current plans include:

+ Storage Refactoring: Acquiring a reliable NAS to relaunch the Media Stack and deploy a Bitcoin Full Node.
+ Observability: Implementing Prometheus & Grafana to proactively monitor host metrics and detect hardware anomalies before they cause kernel panics.
+ CI/CD Pipeline: Moving towards a full GitOps strategy (e.g., automated Terraform applies via GitHub Actions).

## 🛠️ Getting Started

### Prerequisites

+ A running Proxmox VE node (tested on PVE 8.x)
+ Terraform ≥ 1.5.0
+ Ansible ≥ 2.15
+ A Cloudflare account (for automatic TLS DNS challenge)
+ SSH key pair for container access

#### 1 — Provision containers with Terraform

```sh
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your PVE API endpoint, token, IPs, etc.

terraform init
terraform plan
terraform apply
```

#### 2 — Configure containers with Ansible

```sh
cd ansible/
ansible-vault create group_vars/lxc01/vault.yml

# Run the full site playbook
ansible-playbook playbooks/site.yml
```

### 🔐 Required Secrets

The following secrets must be defined in ansible/group_vars/<group>/vault.yml (Ansible Vault encrypted):

| Variable | Description |
| :--- | :--- |
| `vault_caddy_email` | ACME registration email |
| `vault_cloudflare_token` | Cloudflare API token (for DNS challenge) |
| `vault_lss_wg_private_key` | WireGuard private key for the VPN tunnel |
| `vault_lss_wg_public_key` | WireGuard peer public key |
| `vault_nextcloud_mysql_root_password` | MariaDB root password |
| `vault_nextcloud_mysql_password` | Nextcloud DB user password |
| `vault_nextcloud_admin_user` | Nextcloud admin username |
| `vault_nextcloud_admin_password` | Nextcloud admin password |
| `vault_nextcloud_smtp_from` | SMTP sender address (via Proton Mail Bridge) |
| `vault_nextcloud_smtp_user` | SMTP username |
| `vault_nextcloud_smtp_password` | SMTP password |
| `vault_onlyoffice_secret` | OnlyOffice JWT secret |

Terraform secrets (Proxmox API token, SSH keys) are stored in terraform/terraform.tfvars, which is git-ignored. Use terraform.tfvars.example as a reference.

## 📄 License

This project is open-sourced for portfolio and educational purposes. Feel free to adapt any part of it for your own homelab.
