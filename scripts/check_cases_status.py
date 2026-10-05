#!/usr/bin/env python3
"""
скрипт мониторинга занятости кейсов всероссийского хакатона связи 2026.
работает из коробки на стандартной библиотеке python без внешних зависимостей.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

API_URL = "https://telehack.ru/api/cases/"


def fetch_cases_direct(timeout: float = 3.5) -> list[dict]:
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_cases_fallback_ssh() -> list[dict] | None:
    if not shutil.which("ssh"):
        return None
    try:
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", "msk", f"curl -sL {API_URL}"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass
    return None


def fetch_cases() -> list[dict]:
    # 1. стандартный прямой запрос (для работы из РФ без VPN)
    try:
        return fetch_cases_direct()
    except Exception:
        pass

    # 2. резервный канал (если на хосте настроен алиас туннеля)
    data = fetch_cases_fallback_ssh()
    if data is not None:
        return data

    raise RuntimeError(
        "не удалось подключиться к telehack.ru.\n"
        "если у вас включен VPN — отключите его (сервер хакатона блокирует зарубежные IP-адреса)."
    )


def main() -> int:
    try:
        cases = fetch_cases()
    except Exception as e:
        print(f"ошибка: {e}", file=sys.stderr)
        return 1

    print("=" * 72)
    print("  вхс 2026 — мониторинг занятости кейсов (telehack.ru)")
    print("=" * 72)
    print(f"{'№':<3} | {'уровень':<11} | {'партнер':<18} | {'места':<10} | {'кейс'}")
    print("-" * 72)

    for c in sorted(cases, key=lambda x: x.get("case_number", 0)):
        num = c.get("case_number")
        lvl = c.get("level", "")
        partner = c.get("partner_name", "")
        max_teams = c.get("teams_count", 0)
        reg_teams = c.get("registered_teams_count", 0)
        name = c.get("name", "")

        slots = f"{reg_teams}/{max_teams}"
        status = " (заполнен!)" if reg_teams >= max_teams else ""
        print(f"{num:<3} | {lvl:<11} | {partner:<18} | {slots:<10} | {name}{status}")

    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
