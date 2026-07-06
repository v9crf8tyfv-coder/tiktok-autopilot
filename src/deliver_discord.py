#!/usr/bin/env python3
"""Poste la vidéo du jour dans un salon Discord via un BOT.

Message = ping d'un rôle + Embed (sujet, hashtags) + vidéo attachée
          + bouton "⬇️ Télécharger" (bouton-lien, aucun bot allumé requis).

Variables (secrets GitHub / config.env) :
  DISCORD_BOT_TOKEN   token du bot dédié
  DISCORD_CHANNEL_ID  salon cible
  DISCORD_ROLE_ID     rôle à ping (optionnel)

Repli : si DISCORD_BOT_TOKEN absent mais DISCORD_WEBHOOK présent → mode webhook simple.

Usage : venv/bin/python src/deliver_discord.py <video.mp4> [caption.txt]
"""
import json
import os
import sys

import requests

API = "https://discord.com/api/v10"


def parse_caption(caption_file):
    sujet, tags = "Vidéo du jour", ""
    if caption_file and os.path.exists(caption_file):
        txt = open(caption_file, encoding="utf-8").read().strip()
        parts = [p for p in txt.split("\n") if p.strip()]
        if parts:
            sujet = parts[0][:240]
        tags = " ".join(p for p in parts if p.strip().startswith("#"))
    return sujet, tags


def post_via_bot(video, sujet, tags):
    token = os.environ["DISCORD_BOT_TOKEN"]
    channel = os.environ["DISCORD_CHANNEL_ID"]
    role = os.environ.get("DISCORD_ROLE_ID", "").strip()
    headers = {"Authorization": "Bot " + token}

    content = ("🔔 <@&%s>\n" % role if role else "") + "🎬 **Nouvelle vidéo TikTok prête !**"
    embed = {
        "title": sujet,
        "description": (tags + "\n\n" if tags else "") + "Télécharge-la et publie-la quand tu veux 👇",
        "color": 0xFE2C55,
        "footer": {"text": "TikTok Autopilot • générée automatiquement"},
    }
    payload = {
        "content": content,
        "embeds": [embed],
        "allowed_mentions": {"parse": [], "roles": [role] if role else []},
        "attachments": [{"id": 0, "filename": os.path.basename(video)}],
    }
    with open(video, "rb") as f:
        r = requests.post(
            "%s/channels/%s/messages" % (API, channel),
            headers=headers,
            data={"payload_json": json.dumps(payload)},
            files={"files[0]": (os.path.basename(video), f, "video/mp4")},
            timeout=300,
        )
    if r.status_code not in (200, 201):
        print("Erreur envoi Discord: %s %s" % (r.status_code, r.text[:300]))
        return 1
    msg = r.json()

    # bouton-lien "Télécharger" vers l'URL de la vidéo attachée (pas besoin de bot allumé)
    att = (msg.get("attachments") or [{}])[0]
    url = att.get("url")
    if url:
        comp = [{"type": 1, "components": [
            {"type": 2, "style": 5, "label": "⬇️ Télécharger", "url": url}
        ]}]
        pr = requests.patch(
            "%s/channels/%s/messages/%s" % (API, channel, msg["id"]),
            headers={**headers, "Content-Type": "application/json"},
            json={"components": comp}, timeout=30,
        )
        if pr.status_code != 200:
            print("(bouton non ajouté: %s)" % pr.text[:150])
    print("✅ Vidéo postée dans le salon Discord (message %s)." % msg.get("id"))
    return 0


def post_via_webhook(video, sujet, tags):
    webhook = os.environ["DISCORD_WEBHOOK"].strip()
    role = os.environ.get("DISCORD_ROLE_ID", "").strip()
    content = ("<@&%s> " % role if role else "") + "🎬 **%s**\n%s" % (sujet, tags)
    with open(video, "rb") as f:
        r = requests.post(webhook, data={"content": content[:1900],
                          "allowed_mentions": json.dumps({"roles": [role] if role else []})},
                          files={"file": (os.path.basename(video), f, "video/mp4")}, timeout=300)
    print("✅ Webhook Discord ok." if r.status_code in (200, 204) else "Webhook: %s" % r.text[:200])
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: deliver_discord.py <video> [caption]")
        return 1
    video = sys.argv[1]
    sujet, tags = parse_caption(sys.argv[2] if len(sys.argv) > 2 else None)
    if os.environ.get("DISCORD_BOT_TOKEN"):
        return post_via_bot(video, sujet, tags)
    if os.environ.get("DISCORD_WEBHOOK"):
        return post_via_webhook(video, sujet, tags)
    print("Aucun canal Discord configuré : livraison ignorée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
