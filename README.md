# TikTok Autopilot 🎬

Système 100 % local, gratuit et légal qui produit chaque jour une vidéo TikTok
verticale 9:16 (45-60 s) optimisée viralité : analyse de tendances → script IA →
voix neurale → sous-titres animés mot à mot → montage → publication.

## Comment ça marche

```
Tâche planifiée Claude (tous les jours à 11h00)
   │
   ├─ 1. src/trends.py ......... Google Trends FR + Wikipédia top FR (+ recherche web)
   ├─ 2. Claude choisit le sujet et écrit script.json   (aucune API payante :
   │                                                     c'est la session Claude elle-même)
   ├─ 3. src/make_video.py ..... edge-tts (voix neurale gratuite)
   │                             + fonds dégradés animés (Pillow + zoom ffmpeg)
   │                             + sous-titres stylés synchronisés au mot près (libass)
   │                             + musique optionnelle (assets/music/)
   ├─ 4. src/publish_tiktok.py . API officielle TikTok si configurée,
   │                             sinon notification macOS + dossier ouvert (30 s à la main)
   └─ 5. logs/ + data/history.json (anti-répétition de sujets)
```

Le « cerveau » (choix du sujet, écriture du script) est la session Claude planifiée
elle-même — inclus dans l'abonnement Claude, donc **0 € d'API**.
La mission détaillée que suit Claude chaque jour : [PILOT.md](PILOT.md).

## Utilisation manuelle

```bash
cd ~/TikTokAutopilot
./venv/bin/python src/trends.py                          # tendances du jour
./venv/bin/python src/make_video.py output/<date>/script.json   # générer la vidéo
./venv/bin/python src/publish_tiktok.py <video.mp4> "<légende>" # publier
```

La vidéo finie + `caption.txt` (légende + hashtags à coller) sont dans `output/<date>/`.

## Publication automatique (optionnel, gratuit)

Par défaut : mode **semi-auto** (notification, tu postes en 30 s — et tu peux ajouter
un **son en tendance** dans l'app, ce que l'API ne permet pas : c'est mieux pour l'algo).

Pour la publication 100 % auto via l'**API officielle TikTok Content Posting** :
1. Crée une app gratuite sur https://developers.tiktok.com
2. Ajoute le produit « Content Posting API » (scopes `video.publish`, `video.upload`),
   URI de redirection : `https://localhost:8765/callback`
3. Colle `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` dans `config.env`
4. Lance `./venv/bin/python src/publish_tiktok.py --auth` et suis les instructions

⚠️ Limite réelle de TikTok (aucun outil ne peut la contourner légalement) :
tant que ton app n'est pas « auditée » par TikTok, la publication **directe** est
restreinte au mode privé (`SELF_ONLY`). D'où le mode `DRAFT` par défaut : la vidéo
arrive dans ta boîte de réception TikTok et tu valides en 2 taps dans l'app.
Après audit de l'app (gratuit, formulaire), le mode `DIRECT` public devient possible.

## Musique

Dépose des MP3 libres de droits dans `assets/music/` (ex. TikTok Commercial Music
Library, Pixabay Music, YouTube Audio Library) : mixés automatiquement à 12 % sous la voix.
Sinon, ajoute un son en tendance directement dans l'app au moment de poster (recommandé).

## Les 3 architectures possibles (celle installée = C)

| | A. No-code (Make/Zapier) | B. Low-code (Python + cron) | C. Claude pilote + Python (installée) |
|---|---|---|---|
| Coût réel | 20-60 €/mois (Make Pro, HeyGen/Creatomate…) | 0-10 €/mois (API LLM à la demande) | **0 €** (abonnement Claude existant) |
| Difficulté | faible | moyenne (code à maintenir) | faible (déjà monté) |
| Mise en place | 1-2 jours | 2-4 jours | fait |
| Automatisation | 90 % | 95 % | 95 % (100 % avec API TikTok auditée) |
| Limites | coût récurrent, dépendance SaaS, quotas | qualité script si LLM cheap, TTS payant | le Mac doit être allumé à l'heure de la tâche |

L'architecture n8n auto-hébergée est possible aussi (gratuite) mais ajoute un serveur
à maintenir pour le même résultat que C.

## Playbook croissance → 10 000 abonnés

- **Hook** : les 3 premières secondes décident de tout. Curiosity gap + mot fort à l'écran.
- **Rétention** : sous-titres mot à mot (fait), une idée par scène, pas de temps mort,
  chute gardée pour la fin (« le n°1 va te choquer »).
- **Durée** : 45-60 s = sweet spot rétention/watch-time en 2026.
- **Fréquence** : 1/jour minimum, même heure. La régularité bat le talent.
- **Heure** : 18h-20h en France (ou 12h-13h). Teste 2 semaines chaque créneau.
- **SEO TikTok** : le mot-clé du sujet doit être DIT dans les 3 premières secondes,
  écrit à l'écran, dans la légende et en hashtag (TikTok indexe tout).
- **Hashtags** : 5-7 → 2 larges (#pourtoi #fyp) + 3 sujet + 1-2 niche. Jamais 20.
- **Son** : ajouter un son en tendance dans l'app booste la distribution.
- **Série** : un format récurrent reconnaissable (« Le fait du jour ») → abonnements.
- **Itération** : chaque semaine, regarder les 3 meilleures vidéos dans TikTok Studio
  (rétention à 3 s et % vu en entier) et doubler sur ce qui marche.
- Réaliste : 0→10 k abonnés = 2 à 6 mois à 1 vidéo/jour ; c'est souvent 2-3 vidéos
  virales qui font 80 % de la croissance. Le système maximise le nombre d'essais.

## Limites réelles (honnêtes)

- **Publication publique 100 % auto** : impossible sans audit de l'app par TikTok
  (règle TikTok, pas technique). Mode brouillon = 2 taps/jour en attendant.
- **Sons en tendance TikTok** : utilisables uniquement dans l'app (droits musique).
- **Le Mac doit être allumé** (ou en veille programmée) à l'heure de la tâche.
- **TikTok Creative Center** n'a pas d'API publique : couvert via recherche web
  de la session Claude + Google Trends/Wikipédia.
- Visuels = dégradés animés esthétiques. Option gratuite pour des vraies vidéos de
  fond : clé Pexels gratuite dans `config.env` (à brancher si tu la fournis).
