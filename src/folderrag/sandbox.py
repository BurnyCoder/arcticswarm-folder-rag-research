"""Set up the WSL2 tool sandbox and sync corpora into it.

Global context: ArcticSwarm agents run ``bash`` / ``python_execute`` inside a
dedicated WSL2 distro (``exec_backend: wsl``), where they are root and may install
any apt/PyPI package, while being unable to see Windows drives or launch Windows
programs. This module (1) configures that distro once (idempotent ``setup``) and
(2) copies each target folder into its ext4 filesystem before every run
(``sync_corpus``), verifying with SHA-256 manifests that the sandbox copy is
byte-identical to the canonical copy on D:.

Local design: all commands are piped to ``wsl.exe -d <distro> -u root -- bash -s``
as bytes (no Windows quoting / CRLF translation issues); corpora are streamed as a
tar archive to ``tar -x`` over stdin, which works even with automount disabled.
"""

from __future__ import annotations

import hashlib
import io
import logging
import subprocess
import tarfile
from pathlib import Path

from folderrag.settings import SANDBOX_DISTRO

log = logging.getLogger(__name__)

# /etc/wsl.conf for the sandbox: no Windows drive mounts, no Windows interop, root default.
# Docs: https://learn.microsoft.com/windows/wsl/wsl-config (automount / interop / user sections).
WSL_CONF = """[automount]
enabled=false
mountFsTab=false
[interop]
enabled=false
appendWindowsPath=false
[user]
default=root
"""

SETUP_SCRIPT = r"""
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ripgrep fd-find jq poppler-utils pandoc sqlite3 tree file git \
    build-essential python3-venv python3-pip ca-certificates curl unzip
ln -sf /usr/bin/fdfind /usr/local/bin/fd
# Parallel agents queue on the dpkg lock instead of failing.
echo 'DPkg::Lock::Timeout "300";' > /etc/apt/apt.conf.d/90arcticswarm-lock
if [ ! -x /opt/agent-venv/bin/python ]; then python3 -m venv /opt/agent-venv; fi
/opt/agent-venv/bin/pip install -q --upgrade pip uv
/opt/agent-venv/bin/uv pip install --python /opt/agent-venv/bin/python -q \
    pandas numpy pypdf markitdown bm25s scikit-learn
# With automount off the old drive mount points remain as empty dirs; remove them.
for d in /mnt/[a-z]; do mountpoint -q "$d" || rmdir "$d" 2>/dev/null || true; done
mkdir -p /corpus /work
echo SETUP_OK
"""


def wsl(script: str, *, distro: str = SANDBOX_DISTRO, timeout: int = 1800, stdin: bytes | None = None,
        argv_tail: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run a bash script (or ``argv_tail`` via --exec) as root in the sandbox."""
    if argv_tail is not None:
        argv = ["wsl.exe", "-d", distro, "-u", "root", "--exec", *argv_tail]
        data = stdin
    else:
        argv = ["wsl.exe", "-d", distro, "-u", "root", "--", "bash", "-s"]
        data = script.encode("utf-8")
    return subprocess.run(argv, input=data, capture_output=True, timeout=timeout)


def _out(p: subprocess.CompletedProcess) -> str:
    return (p.stdout + p.stderr).decode("utf-8", errors="replace")


def setup(distro: str = SANDBOX_DISTRO) -> None:
    """Configure the sandbox distro (idempotent). Requires the distro to be installed."""
    p = wsl(f"cat > /etc/wsl.conf <<'EOF'\n{WSL_CONF}EOF\necho CONF_OK", distro=distro)
    if b"CONF_OK" not in p.stdout:
        raise RuntimeError(f"writing wsl.conf failed: {_out(p)}")
    # Restart the distro so automount/interop settings take effect.
    subprocess.run(["wsl.exe", "--terminate", distro], capture_output=True)
    p = wsl(SETUP_SCRIPT, distro=distro, timeout=3600)
    if b"SETUP_OK" not in p.stdout:
        raise RuntimeError(f"sandbox setup failed:\n{_out(p)[-4000:]}")
    log.info("sandbox %s configured", distro)


def check_isolation(distro: str = SANDBOX_DISTRO) -> dict[str, bool]:
    """Verify the isolation properties the experiment relies on."""
    p = wsl(
        # A drive is reachable only if /mnt/c is a mountpoint or has content.
        "(mountpoint -q /mnt/c || [ -n \"$(ls -A /mnt/c 2>/dev/null)\" ]) && echo MNT_C || echo NO_MNT_C\n"
        "(cmd.exe /c echo hi >/dev/null 2>&1 && echo INTEROP) || echo NO_INTEROP\n"
        "env | grep -qi anthropic && echo KEYS || echo NO_KEYS\n"
        "command -v rg >/dev/null && echo RG\n"
        "/opt/agent-venv/bin/python -c 'import pandas, bm25s, pypdf; print(\"VENV_OK\")'\n",
        distro=distro, timeout=120,
    )
    o = _out(p)
    return {
        "no_windows_drives": "NO_MNT_C" in o,
        "no_interop": "NO_INTEROP" in o,
        "no_api_keys": "NO_KEYS" in o,
        "ripgrep": "RG" in o,
        "agent_venv": "VENV_OK" in o,
    }


def manifest(root: Path) -> dict[str, str]:
    """SHA-256 of every file under ``root`` keyed by POSIX relative path."""
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in corpus_files(root)}


def corpus_files(root: Path) -> list[Path]:
    """Files that make up the corpus: everything except VCS metadata (``.git``).

    A blobless clone's ``.git`` also holds commits made *after* the pinned
    benchmark commit, so it is never copied into the sandbox.
    """
    return [p for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.relative_to(root).parts]


def sync_corpus(src: Path, dest: str, distro: str = SANDBOX_DISTRO) -> None:
    """Replace ``dest`` in the sandbox with an exact copy of ``src`` and verify hashes."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for p in corpus_files(src):
            tar.add(p, arcname=p.relative_to(src).as_posix(), recursive=False)
    p = wsl(f"rm -rf '{dest}' && mkdir -p '{dest}' && echo READY", distro=distro)
    if b"READY" not in p.stdout:
        raise RuntimeError(f"cannot prepare {dest}: {_out(p)}")
    p = wsl("", distro=distro, argv_tail=["tar", "-x", "-C", dest], stdin=buf.getvalue(), timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"tar extract into {dest} failed: {_out(p)}")
    verify_corpus(src, dest, distro)


def verify_corpus(src: Path, dest: str, distro: str = SANDBOX_DISTRO) -> None:
    """Raise if the sandbox copy differs from ``src`` (missing, extra or changed files)."""
    p = wsl(f"cd '{dest}' && find . -type f -print0 | xargs -0 -r sha256sum", distro=distro, timeout=1800)
    remote = {}
    for line in p.stdout.decode("utf-8", errors="replace").splitlines():
        digest, _, rel = line.partition("  ")
        remote[rel[2:] if rel.startswith("./") else rel] = digest
    local = manifest(src)
    if remote != local:
        missing = sorted(set(local) - set(remote))[:5]
        extra = sorted(set(remote) - set(local))[:5]
        changed = sorted(k for k in set(local) & set(remote) if local[k] != remote[k])[:5]
        raise RuntimeError(f"sandbox corpus mismatch at {dest}: missing={missing} extra={extra} changed={changed}")
    log.info("sandbox corpus %s verified (%d files)", dest, len(local))
