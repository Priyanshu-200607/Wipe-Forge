<<<<<<< HEAD
# Wipe-Forge
A secure, TUI-based Linux utility for the permanent and unrecoverable destruction of data on NVMe,   SSD, HDD, and USB drives.
=======
# ⚡ Wipe-Forge

> **Permanent. Unrecoverable. Deliberate.**  
> A safety-first disk destruction utility for Linux, built for people who mean it.

---

```
██╗    ██╗██╗██████╗ ███████╗      ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
██║    ██║██║██╔══██╗██╔════╝      ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
██║ █╗ ██║██║██████╔╝█████╗  █████╗█████╗  ██║   ██║██████╔╝██║  ███╗█████╗  
██║███╗██║██║██╔═══╝ ██╔══╝  ╚════╝██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  
╚███╔███╔╝██║██║     ███████╗      ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
 ╚══╝╚══╝ ╚═╝╚═╝     ╚══════╝      ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
```

---

## What Is This?

Wipe-Forge is a **secure disk destruction tool** for Linux. It wraps the raw, unforgiving power of `nvme format`, `hdparm`, and `dd` inside a structured Terminal UI (TUI) that keeps you from making an irreversible mistake — while making sure that when you *do* want to destroy something, it's actually destroyed.

It is built for:
- IT administrators decommissioning hardware
- Security-conscious individuals wiping drives before resale or disposal
- Anyone who needs evidence-grade erasure, not just a format

---

## Why Not Just Run `dd` or `hdparm` Yourself?

You can. People do. And sometimes they wipe the wrong disk.

Wipe-Forge exists because:
- **Raw commands have no guard rails.** One typo and `/dev/sda` becomes `/dev/sdb`.
- **Not all drives are equal.** Running `dd` on an NVMe is slow and incomplete; a cryptographic erase is instant and total.
- **Destruction needs an audit trail.** Compliance isn't just about *doing* the wipe — it's about *proving* it.

---

## Features

### 🔍 Intelligent Device Detection
Automatically scans all attached block devices and categorizes each one as **SAFE** (eligible to wipe) or **BLOCKED** (protected), based on whether it contains active system mounts.

### 🛡️ Strict Safety Guardrails
Drives containing `/`, `/boot`, or any currently mounted partition are **hard-blocked**. You cannot select them. There is no override flag. That's intentional.

### 🧠 Context-Aware Wipe Strategies
Wipe-Forge analyzes the drive type and applies the right protocol automatically:

| Drive Type | Method | Why |
|---|---|---|
| **NVMe** | `nvme format --ses=1` (Cryptographic Erase) | Instantly destroys the encryption key; all data is irrecoverable in microseconds |
| **SATA SSD** | `hdparm --security-erase` (ATA Secure Erase) | Instructs the drive's own firmware to wipe every flash cell |
| **HDD / USB** | `dd if=/dev/zero` (Bit-by-Bit Overwrite) | Reliable full-surface zero-fill for magnetic and generic block devices |

### 🔒 State Locking & Pre-Execution Verification
Just before the wipe begins, a `DeviceLock` mechanism re-confirms the target drive's **serial number**, **model**, and **size**. If the device path has silently shifted (e.g., a USB was unplugged and re-enumerated as `/dev/sdb` instead of `/dev/sdc`), the operation is **aborted**.

### ⏱️ Multi-Stage Confirmation
To execute a wipe, you must:
1. Select the drive
2. Type a specific confirmation string
3. Wait out a countdown timer

None of these steps can be skipped.

### 📊 Live Progress Feedback
The wipe runs in a background process via Python `multiprocessing`. The TUI receives live progress updates without blocking or freezing — you see exactly what's happening in real time.

### 📝 Audit Logging
Every action — device scan, selection, confirmation, wipe start, and completion — is written to `wipeforge.log`. Because accountability matters.

---

## Architecture

```
Wipe-Forge/
├── scripts/
│   └── wipeforge              # Bash entry-point wrapper
├── wipeforge/
│   ├── __main__.py            # Module entry point
│   ├── main.py                # Pre-flight checks (root, missing binaries)
│   ├── core/
│   │   ├── detection.py       # pyudev/psutil — scans & categorizes drives
│   │   ├── lock.py            # DeviceLock — prevents wiping the wrong drive
│   │   └── models.py          # Data classes (DeviceInfo, etc.)
│   ├── engine/
│   │   ├── decision.py        # Maps device type → WipeStrategy
│   │   ├── verify.py          # Post-wipe verification logic
│   │   └── wipe.py            # Subprocess wrappers: dd, nvme format, hdparm
│   ├── tui/
│   │   └── app.py             # Textual TUI — screens, UI, event handling
│   ├── utils/
│   │   └── logger.py          # Audit and application logging
│   └── worker/
│       └── process.py         # Background multiprocessing wipe worker
└── pyproject.toml
```

**The separation is deliberate.** The `core` layer knows about hardware. The `engine` layer knows about destruction. The `tui` layer knows about display. They do not bleed into each other.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| TUI Framework | [Textual](https://github.com/Textualize/textual) |
| Hardware Discovery | `pyudev` |
| Mount Detection | `psutil` |
| System Execution | `subprocess`, `multiprocessing` |
| Required Binaries | `nvme` (nvme-cli), `hdparm`, `dd` (coreutils) |
| Packaging | `pyproject.toml` + `setuptools` |

---

## Installation

### Prerequisites

Ensure the required system binaries are installed:

```bash
# Debian / Ubuntu
sudo apt install nvme-cli hdparm coreutils

# Arch
sudo pacman -S nvme-cli hdparm coreutils

# Fedora / RHEL
sudo dnf install nvme-cli hdparm coreutils
```

### Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/wipe-forge.git
cd wipe-forge

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Wipe-Forge
pip install .
```

---

## Usage

### Standard (Production)

Wipe-Forge requires root to access raw block devices:

```bash
sudo .venv/bin/python3 -m wipeforge
```

### Development Mode (No Root, No Real Wipes)

Set the `WIPEFORGE_DEV=1` environment variable to run the TUI safely without hardware access:

```bash
WIPEFORGE_DEV=1 python3 -m wipeforge
```

Use this for UI development, testing, and demos.

---

## Safety Model

Wipe-Forge is built around a **defense-in-depth** philosophy. Every layer assumes the previous one could fail:

```
Layer 1 — Detection:   Is this drive safe to target?
Layer 2 — Locking:     Has the device path changed since selection?
Layer 3 — Confirmation: Did the user explicitly consent to destruction?
Layer 4 — Strategy:    Is the right wipe method being used for this hardware?
Layer 5 — Logging:     Is there a record of everything that happened?
```

All five layers must pass before data destruction begins.

---

## ⚠️ Warning

**This tool permanently destroys data. Correctly wiped drives cannot be recovered — not by you, not by a data recovery lab, not by anyone.**

- Always double-check the target device before confirming
- Never run on a system where the target drive might be in active use
- Test in `WIPEFORGE_DEV=1` mode if you are unfamiliar with the tool

The authors accept no responsibility for data loss caused by misuse.

---

## License

[MIT](LICENSE)

---

## Contributing

Pull requests are welcome. For significant changes, please open an issue first to discuss the proposed direction.

When contributing, please respect the existing module boundaries — keep hardware logic in `core`, destruction logic in `engine`, and display logic in `tui`.

---

*Built for the people who understand that a deleted file is not a destroyed file.*
>>>>>>> 2cd085a (Base Version)
