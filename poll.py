"""Sınır kapıları public feed'ini kontrol eder; yeni mesajları
DM ekran görüntüsü gibi PNG'ye çevirip Telegram'a foto olarak yollar.

Durum: seen.json içinde en son gönderilen mesaj id'si tutulur (repoya commit'lenir).
İlk çalıştırma sessizdir (eski mesajları spam'lamamak için sadece seed).
"""
import os
import re
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from render import Renderer

SOURCE_URL = os.environ["SOURCE_URL"]  # kaynak sayfa adresi (secret olarak verilir)
SEEN_FILE = Path(__file__).with_name("seen.json")
MAX_SEND_PER_RUN = 10  # uzun kesinti sonrası flood koruması
IST = timezone(timedelta(hours=3))  # Europe/Istanbul
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

BOT = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT = os.environ["TELEGRAM_CHAT_ID"]


def fetch_messages():
    r = requests.get(SOURCE_URL, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=20)
    r.raise_for_status()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        return []
    data = json.loads(m.group(1))
    return data.get("props", {}).get("pageProps", {}).get("initialMessages", []) or []


def load_last_id():
    if SEEN_FILE.exists():
        try:
            return int(json.loads(SEEN_FILE.read_text(encoding="utf-8")).get("last_id", 0)) or None
        except Exception:
            return None
    return None


def save_last_id(value):
    SEEN_FILE.write_text(
        json.dumps({"last_id": str(value)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_photo(png: bytes) -> bool:
    url = f"https://api.telegram.org/bot{BOT}/sendPhoto"
    try:
        r = requests.post(
            url,
            data={"chat_id": CHAT},
            files={"photo": ("dm.png", png, "image/png")},
            timeout=30,
        )
        return r.ok
    except Exception:
        return False


def main():
    msgs = fetch_messages()
    if not msgs:
        print("no messages")
        return

    last_id = load_last_id()

    # İlk çalıştırma: geçmişi göndermeden sadece seed'le.
    if last_id is None:
        mx = max(int(m["message_id"]) for m in msgs)
        save_last_id(mx)
        print(f"seeded at {mx}")
        return

    fresh = sorted(
        (m for m in msgs if int(m["message_id"]) > last_id),
        key=lambda m: int(m["message_id"]),
    )
    if not fresh:
        print("no new messages")
        return

    to_send = fresh[:MAX_SEND_PER_RUN]  # en eskiden başla, hiçbirini atlama
    sent = 0
    new_last = last_id

    with Renderer() as r:
        for m in to_send:
            t = datetime.fromtimestamp(int(m["date"]), IST).strftime("%H:%M")
            body = (m.get("originalText") or m.get("text") or "").strip()
            png = r.render(body, t)
            if not send_photo(png):
                print("send failed, will retry next run")
                break  # watermark ilerlemez → sonraki turda buradan devam
            new_last = int(m["message_id"])
            sent += 1

    if new_last > last_id:
        save_last_id(new_last)

    print(f"sent {sent}, remaining {len(fresh) - sent}")


if __name__ == "__main__":
    main()
