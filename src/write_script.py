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


PROMPT = """Tu es un STRATÈGE VIRAL TikTok de génie (pas un simple rédacteur). Ta seule obsession :
maximiser la RÉTENTION (que les gens regardent jusqu'au bout et re-regardent), les PARTAGES et les
COMMENTAIRES. Tu connais parfaitement ce qui performe sur TikTok en ce moment : hooks choc,
storytelling à tension, montage ultra-rythmé, boucles ouvertes. Tu écris le script d'UNE vidéo.

CONTEXTE MARCHÉ : {niche}
DATE : {date}
SUJET (très tendance aujourd'hui) : {subject}

SOURCE FIABLE (Wikipédia) — TU NE PEUX UTILISER QUE DES FAITS PRÉSENTS ICI :
\"\"\"
{source}
\"\"\"

=== STRATÉGIE VIRALE OBLIGATOIRE ===

1) LE HOOK (2 PREMIÈRES SECONDES = 80% du succès)
- La 1re scène est UNE phrase choc de 6 à 12 mots qui crée une curiosité BRÛLANTE ou une émotion forte.
- INTERDIT : toute intro classique ("Bonjour", "Aujourd'hui on va parler de", "Saviez-vous que").
- Techniques : promesse folle, chiffre choc, contradiction, question qui dérange, "Personne ne te dira
  que…", "Ce que tu vois n'est pas…", ouvrir une boucle qu'on ne referme qu'à la fin.
- La 1re phrase doit rendre IMPOSSIBLE de scroller.

2) STRUCTURE = HISTOIRE (début → montée en tension → chute satisfaisante)
- Après le hook : on relance la curiosité à CHAQUE scène (on donne un bout, on en promet un autre).
- Montée en tension progressive, puis une révélation / chute qui récompense celui qui est resté.
- Garde une INFO forte pour la toute fin ("et le plus dingue arrive maintenant").

3) RYTHME ULTRA-DYNAMIQUE (RÈGLE STRICTE)
- La scène 1 (hook) = UNE SEULE phrase de 6 à 12 mots. RIEN d'autre.
- Ensuite MINIMUM 8 scènes (idéal 9 à 11). CHAQUE scène = UNE phrase courte (10 à 20 mots), 1 seule idée.
- INTERDIT de mettre plusieurs phrases dans une même scène. Plus il y a de scènes, plus le montage est dynamique.
- Total ≈ 220-250 mots (≈ 60 s). Rythme rapide, zéro temps mort, zéro remplissage.

4) SOUS-TITRES : 2 à 3 mots-clés par scène entre *astérisques* (chiffres, noms propres, mots choc).

5) FIN QUI DÉCLENCHE COMMENTAIRES (JAMAIS "abonne-toi")
- Termine par une phrase qui donne envie de commenter ou de regarder une autre vidéo :
  une question ouverte, un avis à trancher, une mini-énigme, un "à ton avis, …?".

6) VÉRITÉ : chaque fait DOIT venir de la SOURCE. N'invente JAMAIS un chiffre/date/nom/citation.
   Dans le doute reste général. Un fait vrai bien raconté > un faux fait spectaculaire.

7) INTERDIT : remplissage ("oups", "c'est du lourd", "oui oui"), onomatopées, répétitions.

=== CHOIX ADAPTATIF DU FORMAT ===
Ne te limite PAS à un format fixe. Choisis LE format le plus viral pour CE sujet (compte à rebours,
révélation, "la vérité cachée", storytime, "ce que personne ne remarque", face-à-face, mythe vs réalité…)
et indique-le dans "format".

RÉPONDS UNIQUEMENT avec ce JSON (aucun texte autour) :
{{
  "titre": "identifiant court en minuscules",
  "sujet": "le sujet en une phrase (pour l'historique)",
  "format": "le format viral choisi (2-4 mots)",
  "ambiance": "un mot parmi: epique, mystere, hype, emotion, choc, fun",
  "scenes": [
    {{"texte": "HOOK de 6-12 mots", "image": "vivid cinematic ENGLISH visual, vertical, dramatic lighting", "hue": 265}},
    {{"texte": "phrase courte avec *mots* forts", "image": "...", "hue": 210}}
  ],
  "caption": "légende qui intrigue + finit par une question qui appelle un commentaire, 1 emoji",
  "hashtags": ["#pourtoi", "#fyp", "#sujet"]
}}
- 8 à 11 scènes. "image" = description visuelle EN ANGLAIS, cinématographique, DIFFÉRENTE à chaque scène
  (pour des changements de plan fréquents). "hue" = entier 0-359, varie-le. "ambiance" sert à choisir
  la musique et les effets sonores."""


def _wordcount(data):
    return sum(len(re.findall(r"\w+", sc.get("texte", ""))) for sc in data.get("scenes", []))


def _limit_emphasis(text, max_spans=3):
    """Garde au plus max_spans mots surlignés par scène ; déballe le surplus."""
    spans = list(re.finditer(r"\*(.+?)\*", text))
    for m in spans[max_spans:]:
        text = text.replace(m.group(0), m.group(1), 1)
    return text


def _clean(data, env):
    assert data.get("scenes") and 4 <= len(data["scenes"]) <= 12, "nombre de scènes invalide"
    for sc in data["scenes"]:
        assert sc.get("texte"), "scène sans texte"
        sc["texte"] = _limit_emphasis(sc["texte"].strip())
        sc.setdefault("hue", random.randint(0, 359))
    # INTERDIT : tout CTA d'abonnement (on veut des commentaires, pas "abonne-toi")
    last = data["scenes"][-1]
    last["texte"] = re.sub(
        r"[^.!?]*\b(abonne[-\s]?toi|abonnez[-\s]?vous|subscribe|même heure|chaque jour)\b[^.!?]*[.!?]?",
        "", last["texte"], flags=re.I).strip()
    if len(re.findall(r"\w+", last["texte"])) < 4:
        last["texte"] = "Et toi, t'en penses quoi en *commentaire* ?"
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
        _now = datetime.datetime.now(ZoneInfo("Europe/Paris"))
    except Exception:
        off = 2 if 4 <= datetime.datetime.utcnow().month <= 10 else 1
        _now = datetime.datetime.utcnow() + datetime.timedelta(hours=off)
    now_dec = _now.hour + _now.minute / 60.0
    # on enregistre le CRÉNEAU honoré (12 ou 18…), pas l'heure brute (retards GitHub)
    import best_time as _bt
    done = [int(h["heure"]) for h in history if h.get("date") == today and "heure" in h]
    heure = _bt.current_slot(now_dec, done) or _now.hour
    history.append({"date": today, "heure": heure,
                    "sujet": data.get("sujet", data.get("titre", "")), "source": source})
    save_history(history)

    print("[cerveau: %s] sujet: %s" % (source, data.get("sujet", data.get("titre"))))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
