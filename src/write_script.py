#!/usr/bin/env python3
"""Écrit le script.json du jour à partir des tendances (cerveau du système).

Priorité : Google Gemini (gratuit). Repli : gabarit local si pas de clé/échec.
Anti-répétition via data/history.json. Respecte toutes les règles de PILOT.md.

Usage : venv/bin/python src/write_script.py
Sortie : output/<AAAA-MM-JJ>/script.json  (+ met à jour data/history.json)
"""
import datetime
import glob
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def load_env():
    env = dict(os.environ)
    path = os.path.join(ROOT, "config.env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def latest_trends():
    files = sorted(glob.glob(os.path.join(DATA, "trends-*.json")))
    return json.load(open(files[-1], encoding="utf-8")) if files else {}


def load_history():
    path = os.path.join(DATA, "history.json")
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(hist):
    json.dump(hist, open(os.path.join(DATA, "history.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def trends_digest(trends):
    lines = []
    for t in trends.get("google_trends_fr", [])[:10]:
        if t.get("sujet"):
            ctx = (t.get("contexte") or [""])[0]
            lines.append("- %s (%s) %s" % (t["sujet"], t.get("volume", ""), ctx[:80]))
    for a in trends.get("wikipedia_top_fr", [])[:15]:
        if a.get("article"):
            lines.append("- %s (%s vues Wikipédia)" % (a["article"], a.get("vues", "")))
    return "\n".join(lines)


PROMPT = """Tu es un scénariste TikTok viral francophone expert. Écris le script d'UNE vidéo.

NICHE DU COMPTE : {niche}
DATE : {date}

TENDANCES DU JOUR (choisis-en UNE, la plus virale ET liée à la niche, à faible saturation) :
{digest}

SUJETS DÉJÀ TRAITÉS (INTERDITS, trouve autre chose) :
{history}

RÈGLES STRICTES :
- Format gagnant : "3 faits fous sur…", "Personne ne sait que…", "Le vrai chiffre derrière…", classement, histoire vraie étonnante.
- HOOK < 3 s : la 1re phrase (8-14 mots) doit créer un manque de curiosité. JAMAIS "Bonjour".
- 190 à 220 mots AU TOTAL (pour durer 45-60 s). 4 à 6 scènes, une idée par scène, phrases courtes et orales.
- Mets 2 à 4 mots-clés forts par scène entre *astérisques* (chiffres, noms, mots choc) — jamais de mots-outils (le, la, de, et…).
- Termine par une boucle ou un CTA ("Abonne-toi, un fait comme ça tous les jours à la même heure").
- Évite tout sujet sensible (drames en cours, santé grave, politique clivante, violence).
- Info vérifiable et exacte ; si tu n'es pas sûr d'un chiffre, reste prudent.

RÉPONDS UNIQUEMENT avec ce JSON (aucun texte autour) :
{{
  "titre": "identifiant court en minuscules",
  "sujet": "le sujet en une phrase (pour l'historique)",
  "scenes": [
    {{"texte": "phrase narrée avec des *mots* en avant", "hue": 265}},
    {{"texte": "...", "hue": 210}}
  ],
  "caption": "légende intrigante avec 1 emoji, sans révéler la chute",
  "hashtags": ["#pourtoi", "#fyp", "#sujet", "#niche"]
}}
Le champ "hue" est un entier 0-359 (teinte du fond), varie-le entre scènes."""


def gen_with_llm(env, niche, trends, history):
    prompt = PROMPT.format(
        niche=niche,
        date=datetime.date.today().isoformat(),
        digest=trends_digest(trends) or "(pas de tendances récupérées, choisis un sujet intemporel de la niche)",
        history="\n".join("- %s" % h.get("sujet", "") for h in history[-40:]) or "(aucun)",
    )
    raw = llm.generate(prompt, env=env)
    data = json.loads(raw)
    # validations minimales
    assert data.get("scenes") and 3 <= len(data["scenes"]) <= 7, "nombre de scènes invalide"
    for sc in data["scenes"]:
        assert sc.get("texte"), "scène sans texte"
        sc.setdefault("hue", random.randint(0, 359))
    data.setdefault("voix", env.get("VOICE", "fr-FR-RemyMultilingualNeural"))
    data.setdefault("rate", "+12%")
    data.setdefault("titre", "video-" + datetime.date.today().isoformat())
    data.setdefault("caption", data.get("sujet", ""))
    data.setdefault("hashtags", ["#pourtoi", "#fyp"])
    return data


TEMPLATE_TOPICS = [
    ("le cerveau humain", [
        "Ton *cerveau* consomme *20%* de ton énergie alors qu'il ne pèse que *2%* de ton poids.",
        "Il génère assez d'électricité pour allumer une *petite ampoule*.",
        "Et il ne ressent *aucune douleur* : on peut opérer un cerveau *éveillé*.",
    ]),
]


def gen_template(env, niche, trends, history):
    """Repli minimal si Gemini indisponible : construit un script depuis une tendance."""
    cand = []
    for a in trends.get("wikipedia_top_fr", []):
        s = a.get("article", "")
        if s and not any(s.lower() in h.get("sujet", "").lower() for h in history):
            cand.append(s)
    subject = cand[0] if cand else "un fait surprenant"
    scenes = [
        {"texte": "Personne ne connaît *ces faits* sur *%s*." % subject, "hue": 265},
        {"texte": "C'est l'un des sujets *les plus recherchés* en France *aujourd'hui*.", "hue": 200},
        {"texte": "Et pourtant, la plupart des gens ignorent *l'essentiel*.", "hue": 150},
        {"texte": "Abonne-toi, *un fait* comme ça *chaque jour*.", "hue": 320},
    ]
    return {
        "titre": "fait-du-jour",
        "sujet": "Fait du jour : %s" % subject,
        "voix": env.get("VOICE", "fr-FR-RemyMultilingualNeural"),
        "rate": "+12%",
        "scenes": scenes,
        "caption": "Le fait du jour sur %s 🤯" % subject,
        "hashtags": ["#pourtoi", "#fyp", "#culture", "#lesaviezvous", "#france"],
    }


def main():
    env = load_env()
    niche = env.get("NICHE", "culture et faits surprenants")
    trends = latest_trends()
    history = load_history()

    try:
        data = gen_with_llm(env, niche, trends, history)
        source = "gemini"
    except Exception as e:
        print("⚠️  LLM indisponible (%s) → gabarit local." % e)
        data = gen_template(env, niche, trends, history)
        source = "template"

    today = datetime.date.today().isoformat()
    outdir = os.path.join(ROOT, "output", today)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "script.json")
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    history.append({"date": today, "sujet": data.get("sujet", data.get("titre", "")), "source": source})
    save_history(history)

    print("[cerveau: %s] sujet: %s" % (source, data.get("sujet", data.get("titre"))))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
