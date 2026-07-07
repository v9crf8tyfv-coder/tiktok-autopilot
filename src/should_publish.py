#!/usr/bin/env python3
"""Décide s'il faut générer+publier MAINTENANT (un des 2 créneaux du jour).

Robuste aux retards de GitHub Actions : chaque créneau reste "actif" pendant 2h
(voir best_time.current_slot). Un créneau déjà honoré aujourd'hui n'est pas refait.

Sortie : code 0 = on y va / code 1 = pas maintenant.  FORCE=1 → toujours 0.
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


def done_slots_today():
    p = os.path.join(ROOT, "data", "history.json")
    if not os.path.exists(p):
        return []
    try:
        hist = json.load(open(p, encoding="utf-8"))
        today = datetime.date.today().isoformat()
        return [int(h["heure"]) for h in hist if h.get("date") == today and "heure" in h]
    except Exception:
        return []


def main():
    if os.environ.get("FORCE") == "1":
        print("FORCE : publication immédiate.")
        return 0
    now = paris_now()
    slot = best_time.current_slot(now.hour, done_slots_today(), now.weekday())
    if slot is None:
        print("Aucun créneau actif à %dh (Paris) → on saute." % now.hour)
        return 1
    print("Créneau %dh actif (il est %dh Paris) → on publie." % (slot, now.hour))
    return 0


if __name__ == "__main__":
    sys.exit(main())
