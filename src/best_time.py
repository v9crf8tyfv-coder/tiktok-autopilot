#!/usr/bin/env python3
"""Meilleures heures de publication (France) — 2 créneaux par jour.

Créneaux à forte activité TikTok FR (midi + soir). Le système publie une vidéo
à chacun de ces créneaux, chaque jour.
"""
import datetime
import json


# Pour chaque jour (0 = lundi) : les heures FR où l'on publie (midi puis soir).
DAILY_SLOTS = {
    0: [12, 18],   # lundi
    1: [12, 18],   # mardi
    2: [12, 18],   # mercredi
    3: [12, 18],   # jeudi
    4: [12, 18],   # vendredi
    5: [11, 18],   # samedi
    6: [12, 19],   # dimanche
}


def daily_slots(day=None):
    day = day if day is not None else datetime.date.today().weekday()
    return DAILY_SLOTS[day]


def best_hour(day=None):
    """Première heure du jour (compat)."""
    return daily_slots(day)[0]


def main():
    today = datetime.date.today()
    slots = daily_slots(today.weekday())
    print(json.dumps({
        "date": today.isoformat(),
        "creneaux_FR": slots,
        "conseil": "Publier à %s (heure de Paris)." % " et ".join("%dh" % h for h in slots),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
