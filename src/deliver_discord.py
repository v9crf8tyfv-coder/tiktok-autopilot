#!/usr/bin/env python3
"""Envoie la vidéo du jour + la légende dans un salon Discord via webhook.

Le webhook (gratuit) se crée dans Discord : Paramètres du salon → Intégrations →
Webhooks → Nouveau webhook → Copier l'URL. À mettre dans le secret DISCORD_WEBHOOK.

Usage : venv/bin/python src/deliver_discord.py <video.mp4> <caption.txt>
"""
import os
import sys

import requests


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK", "").strip()
    if not webhook:
        print("DISCORD_WEBHOOK absent : livraison Discord ignorée.")
        return 0
    if len(sys.argv) < 2:
        print("Usage: deliver_discord.py <video> [caption_file]")
        return 1
    video = sys.argv[1]
    caption = ""
    if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
        caption = open(sys.argv[2], encoding="utf-8").read().strip()

    content = "🎬 **Vidéo TikTok du jour prête !**\nCopie la légende ci-dessous, télécharge la vidéo et poste 👇\n\n" + caption
    with open(video, "rb") as f:
        r = requests.post(webhook, data={"content": content[:1900]},
                          files={"file": (os.path.basename(video), f, "video/mp4")}, timeout=120)
    if r.status_code in (200, 204):
        print("✅ Vidéo envoyée sur Discord.")
        return 0
    print("Discord a répondu %s: %s" % (r.status_code, r.text[:200]))
    return 0  # ne bloque pas le pipeline


if __name__ == "__main__":
    sys.exit(main())
