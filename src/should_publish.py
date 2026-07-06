#!/usr/bin/env python3
"""Décide s'il faut lancer la publication MAINTENANT (heure optimale du jour).

Le workflow se déclenche à plusieurs créneaux ; ce garde-fou (stdlib seulement)
ne laisse passer que le meilleur créneau du jour, une seule fois par jour.

Sortie : code 0 = « c'est l'heure, on y va » / code 1 = « pas maintenant, on saute ».
FORCE=1 (ex. lancement manuel) → toujours 0.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import best_time  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def paris_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Paris"))
    except Exception:
        # repli : Paris = UTC+2 en été (avr-oct), +1 sinon
        off = 2 if 4 <= datetime.datetime.utcnow().month <= 10 else 1
        return datetime.datetime.utcnow() + datetime.timedelta(hours=off)


def already_posted_today():
    p = os.path.join(ROOT, "data", "history.json")
    if not os.path.exists(p):
        return False
    try:
        hist = json.load(open(p, encoding="utf-8"))
        today = datetime.date.today().isoformat()
        return any(h.get("date") == today for h in hist)
    except Exception:
        return False


def main():
    if os.environ.get("FORCE") == "1":
        print("FORCE : publication immédiate.")
        return 0
    now = paris_now()
    target = best_time.best_hour(now.weekday())
    if already_posted_today():
        print("Déjà publié aujourd'hui → on saute.")
        return 1
    if now.hour != target:
        print("Heure de Paris %dh ≠ heure optimale %dh → on saute." % (now.hour, target))
        return 1
    print("Heure optimale (%dh Paris) → on publie." % target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
