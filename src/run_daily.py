#!/usr/bin/env python3
"""Orchestrateur quotidien : tendances → script → vidéo → publication.

Une seule commande, utilisée par le cron GitHub Actions ET en local :
  venv/bin/python src/run_daily.py

Chaque étape est isolée : une erreur est journalisée dans logs/ et notifiée
(en local) sans faire tomber le reste.
"""
import datetime
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
TODAY = datetime.date.today().isoformat()


def log(msg):
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg)
    print(line, flush=True)
    with open(os.path.join(ROOT, "logs", "%s.log" % TODAY), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def step(name, args):
    log("▶ %s" % name)
    p = subprocess.run([PY] + args, cwd=ROOT)
    if p.returncode != 0:
        raise RuntimeError("%s a échoué (code %s)" % (name, p.returncode))


def main():
    log("=== Run quotidien %s ===" % TODAY)
    try:
        step("tendances", ["src/trends.py"])
        step("écriture script (cerveau)", ["src/write_script.py"])
        step("génération vidéo", ["src/make_video.py",
                                   os.path.join("output", TODAY, "script.json")])

        vids = sorted(glob.glob(os.path.join(ROOT, "output", TODAY, "*.mp4")),
                      key=os.path.getmtime)
        if not vids:
            raise RuntimeError("aucune vidéo produite")
        video = vids[-1]
        caption_file = os.path.join(ROOT, "output", TODAY, "caption.txt")
        caption = open(caption_file, encoding="utf-8").read().strip() if os.path.exists(caption_file) else ""

        step("publication", ["src/publish_tiktok.py", video, caption])

        # Livraison Discord (bot ou webhook) — toujours, en plus de la publication
        if os.environ.get("DISCORD_BOT_TOKEN") or os.environ.get("DISCORD_WEBHOOK"):
            try:
                step("livraison Discord", ["src/deliver_discord.py", video, caption_file])
            except Exception as e:
                log("livraison Discord ignorée: %s" % e)

        log("✅ Terminé : %s" % os.path.basename(video))
        return 0
    except Exception as e:
        log("❌ ERREUR: %s" % e)
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                            'display notification "Voir logs/%s.log" with title "TikTok Autopilot ❌"' % TODAY])
        return 1


if __name__ == "__main__":
    sys.exit(main())
