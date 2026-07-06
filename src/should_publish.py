#!/usr/bin/env python3
"""Décide s'il faut générer+publier MAINTENANT (un des 2 créneaux du jour).

Le workflow se déclenche à plusieurs heures ; ce garde-fou (stdlib seulement)
laisse passer UNIQUEMENT aux 2 créneaux optimaux du jour, une fois par créneau.

Sortie : code 0 = on y va / code 1 = pas maintenant.
FORCE=1 → toujours 0 (lancement manuel).
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
        off = 2 if 4 <= datetime.datetime.utcnow().month <= 10 else 1
        return datetime.datetime.utcnow() + datetime.timedelta(hours=off)


def slot_done_today(hour):
    """Vrai si une vidéo a déjà été faite pour ce créneau (cette heure) aujourd'hui."""
    p = os.path.join(ROOT, "data", "history.json")
    if not os.path.exists(p):
        return False
    try:
        hist = json.load(open(p, encoding="utf-8"))
        today = datetime.date.today().isoformat()
        return any(h.get("date") == today and int(h.get("heure", -1)) == hour for h in hist)
    except Exception:
        return False


def main():
    if os.environ.get("FORCE") == "1":
        print("FORCE : publication immédiate.")
        return 0
    now = paris_now()
    slots = best_time.daily_slots(now.weekday())
    if now.hour not in slots:
        print("Heure de Paris %dh ≠ créneaux du jour %s → on saute." % (now.hour, slots))
        return 1
    if slot_done_today(now.hour):
        print("Créneau %dh déjà fait aujourd'hui → on saute." % now.hour)
        return 1
    print("Créneau optimal %dh (Paris) → on publie." % now.hour)
    return 0


if __name__ == "__main__":
    sys.exit(main())
