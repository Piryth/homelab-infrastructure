# 🏠 Homelab Infrastructure

> A code-driven homelab running on [Proxmox VE](https://www.proxmox.com/), provisioned with **Terraform** and configured with **Ansible**: DNS resolution, reverse proxying, remote access and a media automation stack backed by encrypted cloud storage.

---

## 📋 Overview

This repository contains the Infrastructure-as-Code (IaC) and configuration management for a self-hosted homelab. The stack is designed around **repeatability**, **idempotency** and **security**.

**Key principles:**

- **Declarative and version-controlled**: containers come from Terraform, their configuration from Ansible
- **Vault-encrypted secrets**: sensitive values never appear in plaintext
- **Least privilege**: unprivileged LXC containers with minimal surface area
- **Internal DNS**: ad-blocking and recursive DNSSEC resolution on the LAN
- **Encrypted offsite media**: finished media is stored on 1Fichier through an `rclone crypt` remote

---

## 🏗️ Architecture

![Architecture diagram](assets/architecture.svg)

Everything runs on a single Proxmox node on the **192.168.1.0/24** LAN.

| Host | Hostname | IP | Role | Managed by |
| --- | --- | --- | --- | --- |
| pve01 | `pve-node` | 192.168.1.230 | Proxmox VE hypervisor, `local-lvm` thin pool | manual |
| lxc01 | `docker-ct` | 192.168.1.231 | Docker host: Caddy + LSS media stack, storage pool | Terraform + Ansible |
| lxc02 | `pihole-ct` | 192.168.1.232 | Pi-hole + Unbound DNS | Terraform |
| lxc03 | `wireguard-ct` | 192.168.1.233 | WireGuard remote access, hardened SSH (`:53821`) | Ansible (`lxc_hardening`) |

**Caddy** (lxc01) terminates HTTPS for every web UI under `*.<host>.internal.endignous.fr`, with certificates issued through a Cloudflare **DNS-01** challenge, so certificates work without exposing any service to the internet.

| URL | Upstream |
| --- | --- |
| `pve.pve01.internal.endignous.fr` | Proxmox web UI `192.168.1.230:8006` |
| `pihole.lxc02.internal.endignous.fr` | Pi-hole admin `192.168.1.232:80` |
| `jellyfin.lxc01.internal.endignous.fr` | Jellyfin `:8096` |
| `jellyseerr.lxc01.internal.endignous.fr` | Jellyseerr `:5055` |
| `radarr` / `sonarr` / `lidarr` `.lxc01.internal.endignous.fr` | `:7878` / `:8989` / `:8686` |
| `prowlarr.lxc01.internal.endignous.fr` | Prowlarr `:9696` |
| `qbit.lxc01.internal.endignous.fr` | qBittorrent `:9090` (through gluetun) |
| `flaresolverr.lxc01.internal.endignous.fr` | FlareSolverr `:8191` |

Navidrome (`:4533`) is reached directly on `192.168.1.231:4533`.

---

## 🗂️ Repository Structure

```
homelab-infrastructure/
├── assets/
│   └── architecture.svg          # Architecture diagram (README)
│
├── terraform/                    # Provisions LXC containers on Proxmox VE
│   ├── providers.tf              # bpg/proxmox provider configuration
│   ├── variables.tf              # Input variables
│   ├── lxc01.tf                  # Docker application host
│   ├── lxc02.tf                  # Pi-hole + Unbound DNS host
│   ├── outputs.tf                # IPs, VMIDs, inventory snippet
│   └── terraform.tfvars.example  # Template for local secrets
│
└── ansible/                      # Configures containers post-provisioning
    ├── ansible.cfg               # Inventory, vault password file, SSH key
    ├── inventory/
    │   ├── hosts.yml             # pve, lxc01, lxc02, lxc03
    │   └── group_vars/<group>/vault.yml   # Ansible Vault secrets
    ├── playbooks/
    │   ├── site.yml              # Entry point (see Roadmap)
    │   ├── docker.yml            # lxc01: storage, then Docker stacks
    │   └── lxc_hardening.yml     # lxc03: SSH hardening
    └── roles/
        ├── storage/              # lxc01: rclone crypt mount, mergerfs pool, disk guard
        ├── docker_apps/          # lxc01: Caddy + LSS Docker Compose stacks
        └── lxc_hardening/        # Admin user, key-only SSH on a custom port
```

---

## 💾 lxc01 Storage

Media is downloaded and seeded on a local disk, then moved to **1Fichier** once it no longer needs to be local. A **mergerfs** pool unions both, so every container keeps the same `/data/...` paths wherever a file physically lives.

```
/data/config/                 # rootfs: app configs + SQLite databases (back up with tar)
/data/local/                  # 512G Proxmox mount point = mergerfs branch 1 (RW)
├── torrents/{tv,movies,music}    # qBittorrent downloads + seeding
└── media/{tv,movies,music}       # Library: hardlinks of torrents (music stays local)
/mnt/fichier/                 # rclone mount of fichier-crypt: = mergerfs branch 2 (NC)
/mnt/pool/data/               # mergerfs union, what the containers use
/var/cache/rclone/            # rclone VFS cache (50G cap)
/etc/rclone/rclone.conf       # rclone config (root only, written by Ansible)
```

**How it works:**

1. qBittorrent downloads into `/data/torrents/...` (on the local disk).
2. Radarr / Sonarr / Lidarr import by **hardlink** into `/data/media/...`. Both names live on the local branch, so the import costs no extra space and the torrent keeps seeding.
3. Once a file is done seeding, it is uploaded to `fichier-crypt:media/...` and the local copy is removed. It stays visible at the same path through the pool.
4. Jellyfin and Navidrome read the library through the pool, read-only.

| Component | Setting | Why |
| --- | --- | --- |
| `rclone-fichier.service` | mounts `fichier-crypt:` (→ `fichier:homelab-crypt`), `--vfs-cache-mode full` | Encrypted names and content on 1Fichier, seekable streaming |
| `mergerfs-pool.service` | `create=ff`, branch 2 `=NC` | New files always land on the local disk, never on 1Fichier |
| | `minfreespace=30G` | Writes fail with `ENOSPC` instead of spilling to 1Fichier |
| | `statfs_ignore=nc` | The pool reports local free space only, so the Arrs protect the small disk |
| `docker.service` drop-in | `Requires=` + `After=mergerfs-pool.service` | Containers never bind an empty `/mnt/pool/data` |
| `qbit-diskguard.timer` | every 5 min | Pauses downloads below 40G free, resumes above 80G |

> **Hardlinks never exist on 1Fichier.** rclone mounts do not support them and mergerfs does not emulate them: they only exist on the local branch, during the seeding window.

**Manual rclone commands** must use the config written by Ansible, otherwise rclone falls back to `~/.config/rclone/rclone.conf` and may upload **unencrypted**:

```bash
export RCLONE_CONFIG=/etc/rclone/rclone.conf
rclone copy "$DIR" "fichier-crypt:media/$REL" -P --transfers 2 --tpslimit 4
rclone cryptcheck "$DIR" "fichier-crypt:media/$REL" --one-way
rclone rc vfs/refresh "dir=media/$REL" --rc-addr 127.0.0.1:5572
```

> **Back up `/etc/rclone/rclone.conf` and the Vault crypt password and salt off this server.** Without them, the data on 1Fichier cannot be decrypted.

### Proxmox side

The `/data/local` disk and the `fuse` feature are set by hand on pve01, not by Terraform (bpg replaces the whole container when a disk mount point changes, and `fuse` needs `root@pam`). Both are in `ignore_changes` in `terraform/lxc01.tf`.

```bash
# Back up /data/config first (vzdump of the whole CT does not fit on 'local').
# Stop the LSS stack first so the SQLite databases are consistent.
pct exec 100 -- tar czf /root/lxc01-config.tgz -C /data config
pct pull 100 /root/lxc01-config.tgz /root/lxc01-config-$(date +%F).tgz
# then copy it off pve01, e.g. scp to your workstation

pct shutdown 100
pct config 100                                   # check the current mp0 before deleting it
pct set 100 -delete mp0                          # detach the old /mnt/pool bind mount
pct set 100 -mp0 local-lvm:512,mp=/data/local,mountoptions=discard
pct set 100 -features nesting=1,keyctl=1,fuse=1
pct start 100
```

`local-lvm` is thin: add a weekly `0 3 * * 0 pct fstrim 100` cron on pve01 and keep the `data%` of `pve/data` in `lvs` below 80%.

---

## ⚙️ Tech Stack

| Layer | Tool | Purpose |
| --- | --- | --- |
| **Hypervisor** | Proxmox VE | Bare-metal host running LXC containers |
| **Provisioning** | Terraform + `bpg/proxmox` | Declarative container lifecycle |
| **Configuration** | Ansible | Idempotent post-provisioning setup |
| **Secret Management** | Ansible Vault | API tokens, passwords, WireGuard and crypt keys |
| **Reverse Proxy** | Caddy (+ `caddy-dns/cloudflare`) | Automatic HTTPS with Cloudflare DNS challenge |
| **DNS** | Pi-hole + Unbound | Network-wide ad-blocking + recursive DNSSEC resolver |
| **Remote access** | WireGuard | VPN into the LAN |
| **Container Runtime** | Docker (Docker-in-LXC) | Isolated application stacks |
| **Storage** | rclone (crypt) + mergerfs | Encrypted 1Fichier mount unioned with a local seeding disk |
| **Torrent VPN** | gluetun (ProtonVPN WireGuard) | Kill-switched network namespace for qBittorrent |

---

## 🚀 Services

### 🔒 Network & Security

| Service | Host | Description |
| --- | --- | --- |
| **[Caddy](https://caddyserver.com/)** | lxc01 | Reverse proxy with automatic TLS for every web UI |
| **[Pi-hole](https://pi-hole.net/)** | lxc02 | Network-wide DNS sinkhole for ad-blocking |
| **[Unbound](https://nlnetlabs.nl/projects/unbound/)** | lxc02 | Recursive, validating DNS resolver (DNSSEC), Pi-hole upstream |
| **[WireGuard](https://www.wireguard.com/)** | lxc03 | Remote access VPN, key-only SSH on port 53821 |

### 🎬 Media Automation (LSS Stack, lxc01)

qBittorrent shares **gluetun**'s network namespace, so all torrent traffic goes through the ProtonVPN WireGuard tunnel. Every other service uses the `lss_network` bridge.

| Service | Port | Description |
| --- | --- | --- |
| **[gluetun](https://github.com/qdm12/gluetun)** | publishes `9090`, `6881` | VPN client (ProtonVPN, WireGuard) for qBittorrent |
| **[qBittorrent](https://www.qbittorrent.org/)** | 9090 | Torrent client, `tv` / `movies` / `music` categories |
| **[Prowlarr](https://github.com/Prowlarr/Prowlarr)** | 9696 | Indexer manager, syncs indexers to the Arrs |
| **[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)** | 8191 | Cloudflare challenge solver for Prowlarr |
| **[Radarr](https://radarr.video/)** | 7878 | Movie automation |
| **[Sonarr](https://sonarr.tv/)** | 8989 | TV series automation |
| **[Lidarr](https://lidarr.audio/)** | 8686 | Music automation |
| **[Recyclarr](https://recyclarr.dev/)** | n/a | Syncs TRaSH Guides quality profiles to the Arrs |
| **[Jellyseerr](https://github.com/Fallenbagel/jellyseerr)** | 5055 | Media requests → Radarr / Sonarr |
| **[Jellyfin](https://jellyfin.org/)** | 8096 | Media server (movies, TV) |
| **[Navidrome](https://www.navidrome.org/)** | 4533 | Music streaming server |

---

## 🛠️ Getting Started

### Prerequisites

- A running **Proxmox VE** node (tested on PVE 8.x)
- **Terraform** ≥ 1.5.0
- **Ansible** ≥ 2.15 with the `community.docker` collection
- A **Cloudflare** account (DNS challenge for TLS)
- A **1Fichier** Premium account (API key) and a **ProtonVPN** WireGuard key
- SSH key pair for container access

### 1. Provision containers with Terraform

```bash
cd terraform/

cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your PVE API endpoint, token, IPs, etc.

terraform init
terraform plan
terraform apply
```

Then add the `/data/local` mount point and the `fuse` feature on pve01 (see [Proxmox side](#proxmox-side)).

### 2. Configure containers with Ansible

```bash
cd ansible/

# The vault password is read from ansible/.vault_pass (git-ignored)
ansible-vault edit inventory/group_vars/lxc01/vault.yml
# Add the required secrets (see below)

# lxc01: storage, then Caddy + LSS
ansible-playbook playbooks/docker.yml

# Only one part
ansible-playbook playbooks/docker.yml --tags storage
ansible-playbook playbooks/docker.yml --tags docker_apps

# lxc03: SSH hardening
ansible-playbook playbooks/lxc_hardening.yml
```

Useful extra variables for `docker.yml`:

| Variable | Use |
| --- | --- |
| `-e storage_skip_app_db_check=true` | Fresh install: skip the check that refuses to start the apps when their databases are missing |
| `-e storage_migrate_lss=true` | One-time move of the old `/data/lss` tree into `/data/local`, keeping hardlinks |

---

## 🔐 Required Secrets

Defined in `ansible/inventory/group_vars/<group>/vault.yml` (Ansible Vault encrypted):

| Variable | Description |
| --- | --- |
| `vault_caddy_email` | ACME registration email |
| `vault_cloudflare_token` | Cloudflare API token (DNS challenge) |
| `vault_lss_wg_private_key` | WireGuard private key for the gluetun tunnel |
| `vault_lss_wg_public_key` | WireGuard peer public key |
| `vault_fichier_api_key` | 1Fichier API key |
| `vault_rclone_crypt_password` | rclone crypt password (**back it up offsite**) |
| `vault_rclone_crypt_salt` | rclone crypt salt (**back it up offsite**) |
| `vault_qbittorrent_user` | qBittorrent WebUI user (disk guard) |
| `vault_qbittorrent_password` | qBittorrent WebUI password (disk guard) |

Reserved for the Nextcloud stack (variables defined, stack not deployed yet): `vault_nextcloud_mysql_root_password`, `vault_nextcloud_mysql_password`, `vault_nextcloud_admin_user`, `vault_nextcloud_admin_password`, `vault_nextcloud_smtp_from`, `vault_nextcloud_smtp_user`, `vault_nextcloud_smtp_password`, `vault_onlyoffice_secret`.

Terraform secrets (Proxmox API token, SSH keys) are stored in `terraform/terraform.tfvars`, which is git-ignored. Use `terraform.tfvars.example` as a reference.

---

## 🧭 Roadmap

- [ ] Deploy the media offload script (seed ratio + free-space driven upload to `fichier-crypt:`) as a systemd timer in the `storage` role
- [ ] Add `playbooks/common.yml` and `playbooks/pihole.yml`, imported by `site.yml` but not in the repository yet
- [ ] Bring lxc03 (WireGuard) under Terraform
- [ ] Nextcloud + OnlyOffice stack (variables already defined in `docker_apps`)

---

## 📄 License

This project is open-sourced for portfolio and educational purposes. Feel free to adapt any part of it for your own homelab.
