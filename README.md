# Flatback

This is a simple script utility to back up and restore Flatpak applications for offline transfer.

Packages a Flatpak app together with its runtime into a single `.tar.gz` archive (or directory), including a YAML manifest. Ideal for moving apps to offline computers or preserving deprecated packages.

## Install

```sh
pip install flatback
```

Requires `flatpak` to be installed on the system.

## Usage

### Backup

```sh
flatback backup org.popular.emulator
flatback backup org.popular.emulator -o emulator-backup.tar.gz
flatback backup com.slack.Slack --no-tar
flatback backup com.google.Chrome --system
flatback backup org.popular.emulator --data
```

### Restore

```sh
flatback restore org.popular.emulator.tar.gz
flatback restore emulator-backup.tar.gz
flatback restore com.slack.Slack/
flatback restore com.google.Chrome.tar.gz --system
flatback restore org.popular.emulator.tar.gz --data
flatback restore org.popular.emulator.tar.gz --no-data
```

## How It Works

**Backup** bundles the app and its runtime into `.flatpak` files using `flatpak build-bundle`, then packages everything with a `flatback.yml` manifest into a `.tar.gz`.

**Restore** extracts the archive, reads the manifest, and installs the runtime and app bundles using `flatpak install --bundle`.

> **Only restore backups you created or trust.** A backup installs software and can replace `~/.var/app/<app_id>`. As a safeguard, restore rejects manifests whose bundle names are not plain files inside the backup or whose `app_id` is not a valid Flatpak ID, and skips user-data symlinks that point outside `~/.var/app/<app_id>`.

### Manifest Example (`flatback.yml`)

```yaml
app:
  app_id: org.popular.emulator
  arch: x86_64
  branch: stable
  installation: user
  origin: flathub
app_bundle: app_org.popular.emulator_x86_64_stable.flatpak
flatback_version: '1.0'
has_data: true
runtime:
  app_id: org.kde.Platform
  arch: x86_64
  branch: 5.15-23.08
  installation: user
  origin: flathub
runtime_bundle: runtime_org.kde.Platform_x86_64_5.15-23.08.flatpak
version: mainline-0-1734
```

## Arguments

### `flatback backup`

| Argument | Description |
|-|-|
| `app_id` | Flatpak application ID (e.g. `org.popular.emulator`) |
| `-o`, `--output` | Output path (default: `<app_id>.tar.gz`) |
| `--no-tar` | Save as directory instead of tar.gz |
| `--data` | Include user data (`~/.var/app/<app_id>`) in backup |
| `--system` | Use system installation instead of user |

### `flatback restore`

| Argument | Description |
|-|-|
| `source` | Path to backup `.tar.gz` or directory |
| `--data` | Restore user data without prompting |
| `--no-data` | Skip user data restore without prompting |
| `--system` | Install to system instead of user |
