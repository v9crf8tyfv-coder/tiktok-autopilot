#!/usr/bin/env python3
"""Meilleures heures de publication (France) — 2 créneaux par jour.

Créneaux à forte activité TikTok FR (midi + soir). Le système publie une vidéo
à chacun de ces créneaux, chaque jour.
"""
import datetime
import json


# Pour chaque jour (0 = lundi) : les heures FR où l'on publie (midi / soir / nuit).
DAILY_SLOTS = {
    0: [12, 18, 21],   # lundi
    1: [12, 18, 21],   # mardi
    2: [12, 18, 21],   # mercredi
    3: [12, 18, 21],   # jeudi
    4: [12, 18, 21],   # vendredi
    5: [11, 18, 21],   # samedi
    6: [12, 19, 21],   # dimanche
}


def daily_slots(day=None):
    day = day if day is not None else datetime.date.today().weekday()
    return DAILY_SLOTS[day]


def best_hour(day=None):
    """Première heure du jour (compat)."""
    return daily_slots(day)[0]


def current_slot(now_dec, done_slots, day=None):
    """Créneau à honorer maintenant. `now_dec` = heure décimale Paris (ex. 20.75 = 20h45).

    Pré-roll de 15 min AVANT le créneau (la création prend ~6 min → la vidéo tombe
    pile à l'heure). Puis fenêtre de tolérance jusqu'à 1h après (retards GitHub).
    On renvoie le créneau actif le plus tardif pas encore fait aujourd'hui, sinon None.
    """
    done = set(int(s) for s in done_slots)
    for s in sorted(daily_slots(day), reverse=True):
        if (s - 0.25) <= now_dec <= (s + 1.0) and s not in done:
            return s
    return None


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
