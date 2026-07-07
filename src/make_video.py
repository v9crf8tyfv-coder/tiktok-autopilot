#!/usr/bin/env python3
"""Génère une vidéo TikTok verticale 9:16 à partir d'un script JSON.

Usage : venv/bin/python src/make_video.py chemin/vers/script.json

Schéma du script :
{
  "titre": "identifiant court",
  "voix": "fr-FR-RemyMultilingualNeural",   // optionnel
  "rate": "+12%",                            // optionnel, vitesse TTS
  "scenes": [
    {"texte": "Texte narré. Les mots entre *étoiles* sont surlignés en jaune.", "hue": 265}
  ],
  "caption": "légende TikTok",
  "hashtags": ["#tag1", "#tag2"]
}

Sortie : output/YYYY-MM-DD/<slug>.mp4 + caption.txt
Tout est local et gratuit : edge-tts (voix neurale Microsoft), Pillow (fonds), ffmpeg (montage).
"""
import asyncio
import datetime
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import unicodedata

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter

import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1080, 1920, 30
BG_W, BG_H = 1440, 2560  # surdimensionné pour le zoom
DEFAULT_VOICE = "fr-FR-RemyMultilingualNeural"
DEFAULT_RATE = "+12%"
# Police des sous-titres : Arial Black en local (Mac), configurable en cloud via env.
FONT_NAME = os.environ.get("FONT_NAME", "Arial Black")
FONT_FILE = os.environ.get("FONT_FILE", "/System/Library/Fonts/Supplemental/Arial Black.ttf")


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg a échoué:\n%s" % p.stderr.decode("utf-8", "replace")[-2000:])
    return p


def media_duration(path):
    p = subprocess.run([FFMPEG, "-i", path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    m = re.search(rb"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        raise RuntimeError("durée introuvable pour %s" % path)
    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mn * 60 + s


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "video"


# ---------------------------------------------------------------- TTS

async def tts_scene(text, voice, rate, out_mp3):
    """Synthétise une scène ; renvoie les repères de mots [(mot, début_s, fin_s)]."""
    clean = re.sub(r"\*(.+?)\*", r"\1", text)  # les étoiles ne sont pas lues
    com = edge_tts.Communicate(clean, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                end = start + chunk["duration"] / 1e7
                words.append([chunk["text"], start, end])
    return words


# ---------------------------------------------------------------- Fonds

def make_background(path, hue, seed):
    """Fond dégradé sombre 9:16 avec halos lumineux et vignettage."""
    rng = random.Random(seed)
    img = Image.new("RGB", (BG_W, BG_H))
    top = hsv_rgb(hue, 0.85, 0.32)
    bottom = hsv_rgb((hue + 40) % 360, 0.9, 0.10)
    px = img.load()
    for y in range(BG_H):
        t = y / BG_H
        c = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        for x in range(BG_W):
            px[x, y] = c
    # halos
    glow = Image.new("RGB", (BG_W, BG_H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(4):
        cx, cy = rng.randint(0, BG_W), rng.randint(0, BG_H)
        r = rng.randint(220, 520)
        col = hsv_rgb((hue + rng.randint(-30, 50)) % 360, 0.7, 0.55)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    glow = glow.filter(ImageFilter.GaussianBlur(180))
    img = Image.blend(img, glow, 0.45)
    # vignettage
    vig = Image.new("L", (BG_W, BG_H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-BG_W * 0.35, -BG_H * 0.2, BG_W * 1.35, BG_H * 1.2], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(240))
    black = Image.new("RGB", (BG_W, BG_H), (0, 0, 0))
    img = Image.composite(img, black, vig.point(lambda v: 60 + v * 195 // 255))
    img.save(path, quality=92)


def hsv_rgb(h, s, v):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb((h % 360) / 360.0, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def make_ai_background(path, prompt, seed):
    """Image IA gratuite (Pollinations, sans clé) assombrie pour lisibilité du texte.

    Renvoie True si l'image a bien été récupérée, False sinon (l'appelant garde le dégradé).
    """
    import io
    import urllib.parse
    import requests
    from PIL import ImageOps
    url = ("https://image.pollinations.ai/prompt/%s?width=%d&height=%d&nologo=true&seed=%d"
           % (urllib.parse.quote(prompt[:300]), BG_W, BG_H, seed % 100000))
    try:
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        # recadrage "cover" : on remplit le 9:16 sans JAMAIS déformer (léger cadrage haut)
        img = ImageOps.fit(img, (BG_W, BG_H), method=Image.LANCZOS, centering=(0.5, 0.4))
        # scrim sombre + dégradé bas pour que les sous-titres blancs ressortent
        dark = Image.new("RGB", (BG_W, BG_H), (0, 0, 0))
        img = Image.blend(img, dark, 0.42)
        grad = Image.new("L", (1, BG_H))
        for y in range(BG_H):
            grad.putpixel((0, y), int(210 * (y / BG_H) ** 1.6))
        grad = grad.resize((BG_W, BG_H))
        img = Image.composite(dark, img, grad)
        img.save(path, quality=90)
        return True
    except Exception as e:
        print("   (image IA indisponible: %s → dégradé)" % str(e)[:80])
        return False


# ---------------------------------------------------------------- Sous-titres ASS

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cue,Arial Black,88,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,11,0,5,60,60,880,1
Style: Hook,Arial Black,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,12,0,5,50,50,880,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

YELLOW = r"{\c&H00E5FF&}"
WHITE = r"{\c&HFFFFFF&}"
POP = r"{\fad(60,40)\fscx88\fscy88\t(0,90,\fscx100\fscy100)}"


def ass_time(t):
    t = max(t, 0)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


def build_cues(words, emphasis, max_words=3, max_gap=0.55):
    """Regroupe les mots en cues courtes façon TikTok."""
    cues = []
    cur = []
    for w, s, e in words:
        if cur and (len(cur) >= max_words or s - cur[-1][2] > max_gap):
            cues.append(cur)
            cur = []
        cur.append((w, s, e))
    if cur:
        cues.append(cur)
    out = []
    for i, cue in enumerate(cues):
        start = cue[0][1]
        # chaque cue reste affichée jusqu'au début de la suivante
        end = cues[i + 1][0][1] if i + 1 < len(cues) else cue[-1][2] + 0.4
        parts = []
        for w, _, _ in cue:
            key = re.sub(r"[^\wÀ-ÿ]", "", w).lower()
            color = YELLOW if key in emphasis else WHITE
            parts.append(color + escape_ass(w.upper()))
        out.append((start, min(end, start + 3.5), " ".join(parts)))
    return out


def escape_ass(text):
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def write_ass(path, cues):
    with open(path, "w", encoding="utf-8") as f:
        f.write(ASS_HEADER.replace("Arial Black", FONT_NAME))
        for start, end, text in cues:
            f.write("Dialogue: 0,%s,%s,Cue,,0,0,0,,%s%s\n" % (ass_time(start), ass_time(end), POP, text))


# ---------------------------------------------------------------- Pipeline

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    with open(sys.argv[1], encoding="utf-8") as f:
        script = json.load(f)

    today = datetime.date.today().isoformat()
    slug = slugify(script.get("titre", "video"))
    outdir = os.path.join(ROOT, "output", today)
    work = os.path.join(outdir, "_work")
    os.makedirs(work, exist_ok=True)

    voice = script.get("voix", DEFAULT_VOICE)
    rate = script.get("rate", DEFAULT_RATE)
    scenes = script["scenes"]

    # mots à surligner : entre *étoiles* dans les textes
    stop = {"de", "du", "des", "le", "la", "les", "un", "une", "et", "en", "à", "a", "au", "aux", "ce", "que", "qui"}
    emphasis = set()
    for sc in scenes:
        for m in re.findall(r"\*(.+?)\*", sc["texte"]):
            for w in m.split():
                w = re.sub(r"[^\wÀ-ÿ]", "", w).lower()
                if w and w not in stop:
                    emphasis.add(w)

    # 1) Voix scène par scène + repères de mots
    print("[1/5] Synthèse vocale (%s, %s)..." % (voice, rate))
    all_words, scene_files, scene_durs = [], [], []
    offset = 0.0
    for i, sc in enumerate(scenes):
        mp3 = os.path.join(work, "scene%02d.mp3" % i)
        words = asyncio.run(tts_scene(sc["texte"], voice, rate, mp3))
        dur = media_duration(mp3)
        all_words += [[w, s + offset, e + offset] for w, s, e in words]
        scene_files.append(mp3)
        scene_durs.append(dur)
        offset += dur

    total = sum(scene_durs)
    print("   durée narration: %.1fs" % total)

    # 2) Piste audio : concat + normalisation + musique optionnelle
    print("[2/5] Audio...")
    concat_txt = os.path.join(work, "audio.txt")
    with open(concat_txt, "w") as f:
        for p in scene_files:
            f.write("file '%s'\n" % p)
    narration = os.path.join(work, "narration.m4a")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
         "-af", "loudnorm=I=-15:TP=-1.2:LRA=9", "-c:a", "aac", "-b:a", "160k", narration])

    music_dir = os.path.join(ROOT, "assets", "music")
    musics = [os.path.join(music_dir, m) for m in sorted(os.listdir(music_dir))
              if m.lower().endswith((".mp3", ".m4a", ".wav"))] if os.path.isdir(music_dir) else []
    audio_final = os.path.join(work, "mix.m4a")
    if musics:
        music = random.choice(musics)
        print("   musique: %s" % os.path.basename(music))
        run([FFMPEG, "-y", "-i", narration, "-stream_loop", "-1", "-i", music,
             "-filter_complex",
             "[1:a]volume=0.12,afade=t=in:d=1[a1];[0:a][a1]amix=inputs=2:duration=first:dropout_transition=0[a]",
             "-map", "[a]", "-c:a", "aac", "-b:a", "160k", audio_final])
    else:
        shutil.copy(narration, audio_final)

    # 3) Fonds animés par scène — parfois en images IA, sinon dégradés
    ai_prob = float(script.get("ai_image_prob", os.environ.get("AI_IMAGE_PROB", "0.35")))
    have_prompts = any(sc.get("image") for sc in scenes)
    use_ai = have_prompts and random.random() < ai_prob
    print("[3/5] Fonds animés (%s)..." % ("images IA" if use_ai else "dégradés"))
    seg_files = []
    base_hue = random.randint(0, 359)
    for i, (sc, dur) in enumerate(zip(scenes, scene_durs)):
        hue = sc.get("hue", (base_hue + i * 47) % 360)
        bg = os.path.join(work, "bg%02d.jpg" % i)
        made = False
        if use_ai and sc.get("image"):
            made = make_ai_background(bg, sc["image"], seed=hash(slug) + i * 7919)
        if not made:
            make_background(bg, hue, seed=hash(slug) + i)
        seg = os.path.join(work, "seg%02d.mp4" % i)
        frames = max(int(math.ceil(dur * FPS)), 1)
        zoom_in = i % 2 == 0
        zexpr = ("min(1.0+0.0012*on,1.18)" if zoom_in else "max(1.18-0.0012*on,1.0)")
        vf = ("scale=%d:%d,zoompan=z='%s':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=%dx%d:fps=%d"
              % (BG_W, BG_H, zexpr, W, H, FPS))
        run([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % dur, "-i", bg, "-vf", vf,
             "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "20", "-pix_fmt", "yuv420p", seg])
        seg_files.append(seg)

    concat_v = os.path.join(work, "video.txt")
    with open(concat_v, "w") as f:
        for p in seg_files:
            f.write("file '%s'\n" % p)
    body = os.path.join(work, "body.mp4")
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_v, "-c", "copy", body])

    # 4) Sous-titres
    print("[4/5] Sous-titres...")
    fonts_dir = os.path.join(ROOT, "assets", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    if os.path.exists(FONT_FILE):
        dst = os.path.join(fonts_dir, os.path.basename(FONT_FILE))
        if os.path.abspath(FONT_FILE) != os.path.abspath(dst):
            shutil.copy(FONT_FILE, dst)
    ass = os.path.join(work, "subs.ass")
    write_ass(ass, build_cues(all_words, emphasis))

    # 5) Mux final
    print("[5/5] Export final...")
    final = os.path.join(outdir, slug + ".mp4")
    fade_out = max(total - 0.5, 0)
    run([FFMPEG, "-y", "-i", body, "-i", audio_final,
         "-vf", "subtitles='%s':fontsdir='%s',fade=t=in:st=0:d=0.3,fade=t=out:st=%.2f:d=0.5"
         % (ass.replace("'", r"\'"), fonts_dir, fade_out),
         "-af", "afade=t=out:st=%.2f:d=0.5" % fade_out,
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", final])

    # 6) Calage précis de la durée dans [DUR_MIN, DUR_MAX] (défaut 60-62 s)
    dur_min = float(os.environ.get("DUR_MIN", "60"))
    dur_max = float(os.environ.get("DUR_MAX", "62"))
    target = (dur_min + dur_max) / 2.0
    dur = media_duration(final)
    if not (dur_min <= dur <= dur_max):
        # on accélère/ralentit UNIFORMÉMENT vidéo + audio (sous-titres restent synchro)
        speed = max(0.90, min(1.12, dur / target))
        print("   calage durée: %.1fs → ~%.1fs (x%.3f)" % (dur, dur / speed, speed))
        tmp = os.path.join(work, "final_timed.mp4")
        run([FFMPEG, "-y", "-i", final,
             "-filter_complex", "[0:v]setpts=PTS/%f[v];[0:a]atempo=%f[a]" % (speed, speed),
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
             "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
             "-movflags", "+faststart", tmp])
        os.replace(tmp, final)

    # légende + hashtags prêts à coller
    caption = script.get("caption", "").strip()
    tags = " ".join(script.get("hashtags", []))
    with open(os.path.join(outdir, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(caption + "\n\n" + tags + "\n")
    dst = os.path.join(outdir, "script.json")
    if os.path.abspath(sys.argv[1]) != os.path.abspath(dst):
        shutil.copy(sys.argv[1], dst)

    dur = media_duration(final)
    size = os.path.getsize(final) / 1e6
    print("\n✅ %s  (%.1fs, %.1f Mo)" % (final, dur, size))
    if not dur_min <= dur <= dur_max:
        print("⚠️  Durée %.1fs hors cible %.0f-%.0fs (script trop court/long, calage limité)." % (dur, dur_min, dur_max))
    return 0


if __name__ == "__main__":
    sys.exit(main())
