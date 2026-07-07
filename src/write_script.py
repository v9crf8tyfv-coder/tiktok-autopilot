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

import requests

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


def wiki_extract(title):
    """Intro de l'article Wikipédia FR (faits vérifiés) pour ancrer le script."""
    try:
        r = requests.get("https://fr.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
            "redirects": 1, "titles": title, "format": "json", "exchars": 1500,
        }, headers={"User-Agent": "TikTokAutopilot/1.0"}, timeout=20)
        pages = r.json()["query"]["pages"]
        for _, page in pages.items():
            txt = page.get("extract", "").strip()
            if len(txt) >= 200:
                return re.sub(r"\s+", " ", txt)
    except Exception:
        pass
    return None


def pick_grounded_subject(trends, history):
    """Choisit le sujet le plus tendance non encore traité + sa source Wikipédia.

    Le marché décide (ordre des tendances) ; l'historique évite les doublons exacts ;
    Wikipédia fournit les faits pour empêcher l'IA d'inventer.
    """
    done = " ".join(h.get("sujet", "").lower() for h in history)
    candidates = [a["article"] for a in trends.get("wikipedia_top_fr", []) if a.get("article")]
    candidates += [t["sujet"] for t in trends.get("google_trends_fr", []) if t.get("sujet")]
    for cand in candidates:
        if cand.lower() in done:
            continue
        extract = wiki_extract(cand)
        if extract:
            return cand, extract
    return (candidates[0] if candidates else None), None


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
SUJET IMPOSÉ (choisi car très tendance aujourd'hui) : {subject}

SOURCE FIABLE (Wikipédia) — TU NE PEUX UTILISER QUE DES FAITS PRÉSENTS ICI :
\"\"\"
{source}
\"\"\"

RÈGLES STRICTES :
- ANCRAGE ABSOLU : chaque fait énoncé DOIT provenir de la SOURCE ci-dessus. Si une info n'y est
  pas, tu ne l'écris pas. INTERDICTION TOTALE d'inventer un chiffre, une date, un nom, une citation.
  Mieux vaut un fait simple mais VRAI qu'un fait spectaculaire mais faux.
- Format gagnant : "3 faits fous sur…", "Personne ne sait que…", "Le vrai chiffre derrière…", classement, histoire vraie étonnante.
- HOOK < 3 s : la 1re phrase (8-14 mots) doit créer un manque de curiosité. JAMAIS "Bonjour".
- LONGUEUR IMPÉRATIVE : la vidéo doit durer environ 60 SECONDES à l'oral → écris 235 à 255 mots
  AU TOTAL. 5 à 6 scènes, CHAQUE scène = 2 à 3 phrases (45 à 55 mots par scène). Une vidéo
  trop courte est un ÉCHEC : remplis bien chaque scène.
- EXACTEMENT 2 à 3 mots-clés par scène entre *astérisques*, uniquement sur des CHIFFRES ou des NOMS PROPRES.
  Jamais d'astérisques sur des mots de remplissage.
- INTERDIT : le langage de remplissage ("oups", "oui oui", "c'est du lourd", "promis", "la folie"),
  les onomatopées, les répétitions. Ton clair, fluide, crédible, comme un bon documentaire punchy.
- Termine par une boucle ou un CTA ("Abonne-toi, un fait comme ça tous les jours à la même heure").
- Évite tout sujet sensible (drames en cours, santé grave, politique clivante, violence).
- EXACTITUDE ABSOLUE : n'invente JAMAIS de chiffre, de record, de citation ou d'événement.
  Utilise uniquement des faits largement connus et vérifiables. Dans le doute, reste général
  (ex. "des dizaines de millions" plutôt qu'un chiffre précis faux). Pas de comparaisons absurdes.

RÉPONDS UNIQUEMENT avec ce JSON (aucun texte autour) :
{{
  "titre": "identifiant court en minuscules",
  "sujet": "le sujet en une phrase (pour l'historique)",
  "scenes": [
    {{"texte": "phrase narrée avec des *mots* en avant", "hue": 265, "image": "short vivid ENGLISH visual description of the scene, cinematic, vertical"}},
    {{"texte": "...", "hue": 210, "image": "..."}}
  ],
  "caption": "légende intrigante avec 1 emoji, sans révéler la chute",
  "hashtags": ["#pourtoi", "#fyp", "#sujet", "#niche"]
}}
- "hue" : entier 0-359 (teinte du fond de secours), varie-le entre scènes.
- "image" : description visuelle EN ANGLAIS, concrète et cinématographique (le système
  décidera lui-même s'il l'utilise en image IA ou garde un fond dégradé)."""


def _wordcount(data):
    return sum(len(re.findall(r"\w+", sc.get("texte", ""))) for sc in data.get("scenes", []))


def _limit_emphasis(text, max_spans=3):
    """Garde au plus max_spans mots surlignés par scène ; déballe le surplus."""
    spans = list(re.finditer(r"\*(.+?)\*", text))
    for m in spans[max_spans:]:
        text = text.replace(m.group(0), m.group(1), 1)
    return text


def _clean(data, env):
    assert data.get("scenes") and 3 <= len(data["scenes"]) <= 7, "nombre de scènes invalide"
    for sc in data["scenes"]:
        assert sc.get("texte"), "scène sans texte"
        sc["texte"] = _limit_emphasis(sc["texte"].strip())
        sc.setdefault("hue", random.randint(0, 359))
    data.setdefault("voix", env.get("VOICE", "fr-FR-RemyMultilingualNeural"))
    data.setdefault("rate", "+12%")
    data.setdefault("titre", "video-" + datetime.date.today().isoformat())
    # les astérisques ne servent qu'aux sous-titres, pas à la légende
    data["caption"] = re.sub(r"\*", "", data.get("caption") or data.get("sujet", "")).strip()
    data.setdefault("hashtags", ["#pourtoi", "#fyp"])
    return data


UNGROUNDED = """Tu es un scénariste TikTok viral francophone expert. Écris le script d'UNE vidéo.

NICHE : {niche}
DATE : {date}
SUJET IMPOSÉ (très tendance aujourd'hui) : {subject}

Aucune source fournie : utilise UNIQUEMENT des faits très largement connus et incontestables
sur ce sujet. N'invente AUCUN chiffre/date/citation précis ; dans le doute, reste général.
"""


def gen_with_llm(env, niche, subject, source, history):
    today = datetime.date.today().isoformat()
    if source:
        base = PROMPT.format(niche=niche, date=today, subject=subject, source=source)
    else:
        # tronc commun : on réutilise les règles de PROMPT après l'en-tête ancré
        rules = PROMPT.split("RÈGLES STRICTES :", 1)[1]
        base = UNGROUNDED.format(niche=niche, date=today, subject=subject) + "\nRÈGLES STRICTES :" + rules
    best = None
    # jusqu'à 3 essais : on garde le script le plus long tant qu'il n'atteint pas la cible
    for attempt in range(3):
        prompt = base if attempt == 0 else base + (
            "\n\nATTENTION : ta version précédente ne faisait que %d mots. "
            "Refais-la BEAUCOUP plus longue : 210-240 mots, 2-3 phrases par scène." % _wordcount(best)
        )
        data = _clean(json.loads(llm.generate(prompt, env=env)), env)
        if best is None or _wordcount(data) > _wordcount(best):
            best = data
        if _wordcount(best) >= 190:
            break
    return best


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


PRESENT_PROMPT = """Tu écris une courte vidéo TikTok de PRÉSENTATION d'un compte.

COMPTE : {name} ({handle})
NICHE : {niche}

But : présenter le compte à de nouveaux spectateurs et donner envie de s'abonner.
RÈGLES : hook <3s, 150-190 mots, 4-5 scènes, phrases orales courtes, énergie,
mots-clés forts entre *astérisques*, CTA d'abonnement clair à la fin.

RÉPONDS UNIQUEMENT avec ce JSON :
{{
  "titre": "presentation-compte",
  "sujet": "Présentation du compte {handle}",
  "scenes": [{{"texte": "...", "hue": 300, "image": "short english cinematic visual"}}],
  "caption": "légende de bienvenue avec 1 emoji",
  "hashtags": ["#pourtoi", "#fyp", "#presentation"]
}}"""


def is_presentation_day(env, history):
    every = int(env.get("PRESENT_EVERY_DAYS", "0") or 0)
    if every <= 0:
        return False
    last = None
    for h in history:
        if h.get("source") == "presentation" or "présentation" in h.get("sujet", "").lower():
            last = h.get("date")
    if last is None:
        return len(history) >= every  # première présentation après N vidéos
    try:
        delta = (datetime.date.today() - datetime.date.fromisoformat(last)).days
        return delta >= every
    except Exception:
        return False


def gen_presentation(env, niche):
    prompt = PRESENT_PROMPT.format(
        name=env.get("ACCOUNT_NAME", "ce compte"),
        handle=env.get("ACCOUNT_HANDLE", ""),
        niche=niche,
    )
    data = json.loads(llm.generate(prompt, env=env))
    data.setdefault("voix", env.get("VOICE", "fr-FR-RemyMultilingualNeural"))
    data.setdefault("rate", "+10%")
    for sc in data.get("scenes", []):
        sc.setdefault("hue", random.randint(0, 359))
    return data


def main():
    env = load_env()
    niche = env.get("NICHE", "culture et faits surprenants")
    trends = latest_trends()
    history = load_history()

    present = is_presentation_day(env, history)
    try:
        prov = (llm.active_provider(env) or {}).get("name", "llm")
        if present:
            data = gen_presentation(env, niche)
            source = "presentation"
        else:
            subject, src_text = pick_grounded_subject(trends, history)
            if not subject:
                raise RuntimeError("aucun sujet tendance exploitable")
            print("   sujet imposé: %s (%s)" % (subject, "ancré Wikipédia" if src_text else "sans source"))
            data = gen_with_llm(env, niche, subject, src_text, history)
            data.setdefault("sujet", subject)
            source = prov + ("+wiki" if src_text else "")
    except Exception as e:
        print("⚠️  LLM indisponible (%s) → gabarit local." % e)
        data = gen_template(env, niche, trends, history)
        source = "template"

    today = datetime.date.today().isoformat()
    outdir = os.path.join(ROOT, "output", today)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "script.json")
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    try:
        from zoneinfo import ZoneInfo
        ph = datetime.datetime.now(ZoneInfo("Europe/Paris")).hour
    except Exception:
        off = 2 if 4 <= datetime.datetime.utcnow().month <= 10 else 1
        ph = (datetime.datetime.utcnow() + datetime.timedelta(hours=off)).hour
    # on enregistre le CRÉNEAU honoré (12 ou 18…), pas l'heure brute (retards GitHub)
    import best_time as _bt
    done = [int(h["heure"]) for h in history if h.get("date") == today and "heure" in h]
    heure = _bt.current_slot(ph, done) or ph
    history.append({"date": today, "heure": heure,
                    "sujet": data.get("sujet", data.get("titre", "")), "source": source})
    save_history(history)

    print("[cerveau: %s] sujet: %s" % (source, data.get("sujet", data.get("titre"))))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
