#!/usr/bin/env python3
"""Meilleure heure de publication (France), avec apprentissage optionnel.

Base : créneaux à forte activité TikTok FR (source : études d'engagement 2025-2026).
Affinage : si data/perf.json existe (vues par heure de tes propres posts), on
privilégie tes heures qui performent le mieux. 100 % gratuit, aucune API tierce.

perf.json (facultatif, à remplir à la main ou plus tard automatiquement) :
  [{"date": "2026-07-06", "heure": 19, "vues": 2400}, ...]
"""
import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Créneaux FR par jour de semaine (0 = lundi) -> heures conseillées, la 1re = préférée
DEFAULT_SLOTS = {
    0: [18, 12, 20],
    1: [18, 12, 20],
    2: [18, 13, 20],
    3: [18, 12, 21],
    4: [17, 19, 12],   # vendredi : un peu plus tôt
    5: [11, 19, 21],   # samedi
    6: [19, 11, 20],   # dimanche
}


def learned_best_hour():
    path = os.path.join(ROOT, "data", "perf.json")
    if not os.path.exists(path):
        return None
    try:
        rows = json.load(open(path))
        agg = {}
        for r in rows:
            h = int(r["heure"])
            agg.setdefault(h, []).append(float(r.get("vues", 0)))
        if not agg:
            return None
        means = {h: sum(v) / len(v) for h, v in agg.items() if len(v) >= 2}
        return max(means, key=means.get) if means else None
    except Exception:
        return None


def best_hour(day=None):
    day = day if day is not None else datetime.date.today().weekday()
    learned = learned_best_hour()
    if learned is not None:
        return learned
    return DEFAULT_SLOTS[day][0]


def main():
    today = datetime.date.today()
    h = best_hour(today.weekday())
    src = "tes stats (perf.json)" if learned_best_hour() is not None else "créneaux FR par défaut"
    print(json.dumps({
        "date": today.isoformat(),
        "meilleure_heure_locale_FR": h,
        "source": src,
        "conseil": "Publier autour de %dh (heure de Paris)." % h,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
