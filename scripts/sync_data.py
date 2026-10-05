#!/usr/bin/env python3
"""
скрипт синхронизации данных с telehack.ru для ci/cd и локального запуска.
обновляет json-файлы в data/ и актуализирует счетчики слотов в readme.md и docs/01-cases.md.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
API_BASE = "https://telehack.ru/api"

# кэш доступности прямого подключения
_direct_accessible: bool | None = None


def fetch_endpoint(endpoint: str, timeout: float = 2.5) -> str | None:
    global _direct_accessible
    url = f"{API_BASE}/{endpoint}/"

    # 1. если прямой доступ еще не проверен или успешен — пробуем
    if _direct_accessible is not False:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _direct_accessible = True
                return resp.read().decode("utf-8")
        except Exception:
            _direct_accessible = False

    # 2. попытка через ssh туннель (если настроен msk)
    if shutil.which("ssh"):
        ssh_target = os.environ.get("SSH_HOST", "msk")
        try:
            res = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", ssh_target, f"curl -sL {url}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return None


def update_data_files() -> list[dict] | None:
    DATA_DIR.mkdir(exist_ok=True)
    endpoints = ["cases", "registration", "program", "faq", "partners", "news"]
    cases_data = None

    for ep in endpoints:
        raw = fetch_endpoint(ep)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            target = DATA_DIR / f"{ep}.json"
            target.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
            if ep == "cases":
                cases_data = parsed
        except Exception as e:
            print(f"предупреждение: ошибка парсинга {ep}: {e}", file=sys.stderr)

    return cases_data


def update_markdown_tables(cases: list[dict]) -> None:
    slot_map: dict[int, tuple[int, int]] = {}
    for c in cases:
        num = c.get("case_number")
        if num is not None:
            max_t = c.get("teams_count", 10)
            reg_t = c.get("registered_teams_count", 0)
            slot_map[num] = (reg_t, max_t)

    # обновление README.md
    readme_path = BASE_DIR / "README.md"
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
        for num, (reg, max_t) in slot_map.items():
            status = f"{reg}/{max_t}"
            pattern = rf"(\|\s*\*\*0?{num}\*\*\s*\|.*?\|.*?\|.*?\|\s*)(.*?)\s*\|"
            content = re.sub(pattern, rf"\g<1>{status} |", content)
        readme_path.write_text(content, encoding="utf-8")

    # обновление docs/01-cases.md
    cases_doc_path = BASE_DIR / "docs" / "01-cases.md"
    if cases_doc_path.exists():
        content = cases_doc_path.read_text(encoding="utf-8")
        for num, (reg, max_t) in slot_map.items():
            pattern = rf"(### кейс 0?{num}:.*?\n\* \*\*партнер:\*\*.*?\n\* \*\*лимит:\*\*).*?(\n)"
            content = re.sub(pattern, rf"\g<1> {reg}/{max_t} команд\g<2>", content)
        cases_doc_path.write_text(content, encoding="utf-8")


def main() -> int:
    cases = update_data_files()
    if not cases:
        print("инфо: не удалось связаться с сервером telehack.ru.")
        return 0

    update_markdown_tables(cases)
    print("данные успешно синхронизированы.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
