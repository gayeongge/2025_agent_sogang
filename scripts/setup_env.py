
#!/usr/bin/env python3
"""가상환경 생성 및 활성화를 자동화하는 스크립트."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def resolve_venv_path(project_root: Path) -> Path:
    """기존 가상환경 경로를 우선 탐색하고, 없으면 기본 경로를 반환한다."""
    preferred = project_root / "venv"
    fallback = project_root / ".venv"

    if preferred.exists():
        return preferred
    if fallback.exists():
        return fallback
    return fallback


def ensure_venv(venv_path: Path) -> bool:
    """가상환경이 없으면 생성하고, 있으면 재사용한다.

    Returns:
        bool: 새로 생성했으면 True, 기존 것을 재사용하면 False.
    """
    if venv_path.exists():
        print(f"[INFO] 기존 가상환경을 재사용합니다: {venv_path}")
        return False

    print(f"[INFO] 가상환경을 생성합니다: {venv_path}")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
    return True


def install_requirements(python_bin: Path, requirements: Path) -> None:
    subprocess.check_call([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python_bin), "-m", "pip", "install", "-r", str(requirements)])


def determine_interpreter(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def spawn_shell(venv_path: Path) -> None:
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv_path)
    bin_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONHOME", None)

    if os.name == "nt":
        shell = env.get("COMSPEC", "cmd.exe")
        print("[INFO] 가상환경이 활성화된 새 CMD 세션을 실행합니다.")
        os.execve(shell, [shell], env)
    else:
        shell = env.get("SHELL", "/bin/bash")
        print("[INFO] 가상환경이 활성화된 새 셸을 실행합니다. 작업이 끝나면 'exit'으로 종료하세요.")
        os.execve(shell, [shell, "-l"], env)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    venv_path = resolve_venv_path(project_root)
    requirements = project_root / "requirements.txt"

    if not requirements.exists():
        print(f"[ERROR] requirements.txt를 찾을 수 없습니다: {requirements}", file=sys.stderr)
        sys.exit(1)

    ensure_venv(venv_path)
    python_bin = determine_interpreter(venv_path)
    install_requirements(python_bin, requirements)
    spawn_shell(venv_path)


if __name__ == "__main__":
    main()
