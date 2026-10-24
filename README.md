# WontNote

WontNote is an offline, local-first encrypted desktop note-taking application. Notes are encrypted at rest using authenticated cryptography and stored locally on your machine. There is no cloud sync, telemetry, or remote networking.

## ⬇️ Download

> **Windows 10/11 — No Python required**

[![Latest Release](https://img.shields.io/github/v/release/wiptexbey/WontNote?style=for-the-badge&label=Latest%20Version&color=blue)](https://github.com/wiptexbey/WontNote/releases/latest)
[![Download](https://img.shields.io/badge/Download-.exe-brightgreen?style=for-the-badge&logo=windows)](https://github.com/wiptexbey/WontNote/releases/latest)

1. Open the latest Release from **Download .exe** above
2. Download the `WontNote.exe` asset
3. Run **WontNote.exe** — that's it!

> For Linux or source installation, see the [Installation](#installation) section below.


## Security Architecture

The vault uses authenticated encryption and modern key derivation standards:

- **Symmetric Cipher:** AES-256-GCM (authenticated encryption with 128-bit authentication tag and unique 96-bit nonces per write).
- **Key Derivation (KDF):** Argon2id with memory-hard parameters (64 MB memory, 3 iterations, 4 parallel lanes) and a random 16-byte salt to resist GPU/ASIC brute-force attacks.
- **Subkey Derivation:** HKDF-SHA256 separates the vault encryption key from verification and recovery components.
- **Recovery Key:** A 24-character cryptographically secure token derived via HKDF that allows vault recovery if the master password is forgotten.
- **Zero Network Exposure:** The application makes zero outbound requests. All icons and UI assets are bundled locally.

## Features

- **Local-first Vault:** Notes remain encrypted on disk; plaintext data only resides in process memory while unlocked.
- **Dual Unlock Methods:** Unlock using your master password or the emergency recovery key.
- **Organization:** Categorize notes by folders (Personal, Work & Projects, School & Education, Ideas & Drafts) and pin important notes to the top.
- **Search & Filter:** Instant local full-text search across titles and note contents.
- **Clean Interface:** Compact UI with dark, light, and system theme options, font customization (Inter, Roboto, Monospace, Georgia), and tactile interactions.
- **Trash & Vault Management:** Soft delete with trash recovery, bulk trash purge, password change, recovery key regeneration, and explicit vault reset.

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + N` | Create a new note |
| `Ctrl + F` | Focus note search |
| `Ctrl + L` | Lock vault immediately |
| `Ctrl + ,` | Open Settings |
| `Delete` | Move active note to Trash |
| `Escape` | Close active modal or context menu |

## Installation

### Requirements

- Python 3.10 or higher
- Windows 10/11 (WebView2 runtime is preinstalled on modern Windows) or Linux (WebKit2GTK)

### Setup

1. Clone or download the repository:
   ```bash
   git clone https://github.com/wiptexbey/WontNote.git
   cd WontNote
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Building the Windows release

Install PyInstaller in the environment, then build the bundled application:

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm WontNote.spec
```

The standalone Windows executable with its bundled application icon is written to `dist/WontNote.exe`.

## Usage

Start the application:

```bash
python -m wontnote
```

On first launch, you will be prompted to create a master password (minimum 12 characters). You will then receive a recovery key—store this key in a secure location.

## Data Storage

Vault data is saved to your operating system's standard user data directory via `platformdirs`:

- **Windows:** `%LOCALAPPDATA%\WontNote\vault.wnt`
- **Linux:** `~/.local/share/WontNote/vault.wnt`

## Running Tests

Run the test suite with pytest:

```bash
pytest
```

To run tests with verbose output:

```bash
pytest -v
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
