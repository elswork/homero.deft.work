#!/usr/bin/env python3
"""
GENERADOR DE VIDEOLIBROS — LA ODISEA DE LA .IA
Renderiza capítulos como vídeos MP4 Full HD (1920x1080) con:
1. Telón de inicio (Intro): Portada oficial con animación Ken Burns y título.
2. Lectura karaoke: Letra grande centrada, palabras iluminadas en oro con subtítulos ASS.
3. Telón de cierre (Outro): Códigos QR de la web y red social, email y créditos oficiales.
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def to_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    cs = int(round((s - int(s)) * 100))
    s = int(s)
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_subtitles(cap: dict, ass_path: Path):
    full_html = " ".join([
        cap.get("title_html", ""),
        cap.get("subtitle_html", ""),
        cap.get("author_html", ""),
        cap.get("html", "")
    ])
    pattern = re.compile(r"<span[^>]*data-w=\"(\d+)\"[^>]*>(.*?)</span>", re.DOTALL)
    words_by_id = {}
    for wid, wtext in pattern.findall(full_html):
        words_by_id[int(wid)] = re.sub(r"<[^>]+>", "", wtext).strip()

    sync_data = cap["sync"]
    words_by_s = {}
    for w in sync_data["words"]:
        words_by_s.setdefault(w["s"], []).append(w)

    ass_lines = [
        "[Script Info]",
        "Title: La Odisea de la .IA - Videolibro",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Karaoke,DejaVu Sans,44,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,5,160,160,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    for s in sync_data["sentences"]:
        s_idx = s["s"]
        start_t = s["start"]
        end_t = s["end"]
        s_words = words_by_s.get(s_idx, [])
        if not s_words:
            continue
        k_parts = []
        curr = start_t
        for w in s_words:
            w_start = w["start"]
            w_end = w["end"]
            gap = max(0, int(round((w_start - curr) * 100)))
            dur = max(1, int(round((w_end - w_start) * 100)))
            w_text = words_by_id.get(w["w"], "")
            if gap > 0:
                k_parts.append(f"{{\\k{gap}}}")
            k_parts.append(f"{{\\kf{dur}}}{w_text} ")
            curr = w_end
        k_str = "".join(k_parts).strip()
        ass_lines.append(f"Dialogue: 0,{to_ass_time(start_t)},{to_ass_time(end_t)},Karaoke,,0,0,0,,{k_str}")

    ass_path.write_text("\n".join(ass_lines), encoding="utf-8")


def generate_frames(book_dir: Path, cap: dict, intro_path: Path, bg_path: Path, outro_path: Path):
    W, H = 1920, 1080
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font_title = font_sub = font_badge = font_small = ImageFont.load_default()

    # 1. Intro
    intro_img = Image.new("RGB", (W, H), color=(7, 10, 16))
    draw_in = ImageDraw.Draw(intro_img)
    cover_path = book_dir / "img/portada-la-odisea-de-la-ia.jpg"
    if cover_path.exists():
        cover = Image.open(cover_path).convert("RGB").resize((620, 620), Image.Resampling.LANCZOS)
        intro_img.paste(cover, (160, 230))
        draw_in.rectangle([158, 228, 160 + 622, 230 + 622], outline=(255, 215, 0), width=3)

    draw_in.text((860, 320), "🏛️ ECI(2026)000012 · DECISIÓN C(2026) 7098 FINAL", font=font_badge, fill=(255, 215, 0))
    draw_in.text((860, 370), "La Odisea de la .IA", font=font_title, fill=(255, 255, 255))
    draw_in.text((860, 450), f"Capítulo {cap.get('capitulo', 0)}: {cap.get('title', '')}", font=font_sub, fill=(147, 197, 253))
    draw_in.text((860, 520), "Por Eloy López Sánchez", font=font_small, fill=(148, 163, 184))
    draw_in.text((860, 580), "Relato Oficial y Audiolibro Neuronal con Karaoke Inverso", font=font_small, fill=(100, 116, 139))
    draw_in.text((860, 660), "https://odisea.deft.work", font=font_small, fill=(255, 215, 0))
    intro_img.save(intro_path)

    # 2. Main Background
    bg_img = Image.new("RGB", (W, H), color=(8, 12, 19))
    draw_bg = ImageDraw.Draw(bg_img)
    draw_bg.rectangle([0, 0, W, 80], fill=(13, 19, 30))
    draw_bg.line([0, 80, W, 80], fill=(30, 41, 59), width=2)
    draw_bg.text((60, 25), "🏛️ LA ODISEA DE LA .IA", font=font_badge, fill=(255, 215, 0))
    draw_bg.text((450, 27), f"·  Capítulo {cap.get('capitulo', 0)}: {cap.get('title', '')}", font=font_small, fill=(148, 163, 184))
    draw_bg.text((W - 320, 27), "odisea.deft.work", font=font_small, fill=(100, 116, 139))
    bg_img.save(bg_path)

    # 3. Outro
    outro_img = Image.new("RGB", (W, H), color=(7, 10, 16))
    draw_out = ImageDraw.Draw(outro_img)
    draw_out.text((W // 2 - 200, 140), "🏛️ FIN DEL CAPÍTULO", font=font_badge, fill=(255, 215, 0))
    draw_out.text((W // 2 - 320, 180), "La Odisea de la .IA", font=font_title, fill=(255, 255, 255))
    draw_out.text((W // 2 - 400, 260), "Por la Soberanía Digital Europea · Iniciativa Ciudadana ECI(2026)000012", font=font_small, fill=(148, 163, 184))

    qr1_path = book_dir / "img/qrcode_odisea.deft.work.png"
    if qr1_path.exists():
        q1 = Image.open(qr1_path).convert("RGB").resize((220, 220))
        outro_img.paste(q1, (W // 2 - 320, 340))
        draw_out.rectangle([W // 2 - 322, 338, W // 2 - 320 + 222, 340 + 222], outline=(255, 255, 255), width=2)
        draw_out.text((W // 2 - 350, 580), "odisea.deft.work", font=font_small, fill=(255, 215, 0))
        draw_out.text((W // 2 - 380, 615), "Leer y escuchar la obra", font=font_small, fill=(148, 163, 184))

    qr2_path = book_dir / "img/etiqueta-PVQ0M.png"
    if qr2_path.exists():
        q2 = Image.open(qr2_path).convert("RGB").resize((220, 220))
        outro_img.paste(q2, (W // 2 + 100, 340))
        draw_out.rectangle([W // 2 + 98, 338, W // 2 + 100 + 222, 340 + 222], outline=(255, 255, 255), width=2)
        draw_out.text((W // 2 + 90, 580), "free.deft.work/PVQ0M", font=font_small, fill=(255, 215, 0))
        draw_out.text((W // 2 + 80, 615), "Comentar en la red social", font=font_small, fill=(148, 163, 184))

    draw_out.text((W // 2 - 250, 720), "Contacto: Eloy López · elswork@mypublicinbox.email", font=font_sub, fill=(255, 255, 255))
    draw_out.text((W // 2 - 230, 790), "6 de Abril de 2027 · Apertura de la Urna Oficial Europea", font=font_small, fill=(255, 215, 0))
    outro_img.save(outro_path)


def render_chapter_video(book_dir: Path, chapter_idx: int = 0, lang: str = "es", output_mp4: Path = None):
    bundle_path = book_dir / "homero-bundle.js"
    if not bundle_path.exists():
        raise FileNotFoundError(f"No se encuentra {bundle_path}")

    bundle_text = bundle_path.read_text(encoding="utf-8").strip()
    if bundle_text.startswith("window.HOMERO_BOOK = "):
        bundle_text = bundle_text[len("window.HOMERO_BOOK = "):]
    if bundle_text.endswith(";"):
        bundle_text = bundle_text[:-1]

    data = json.loads(bundle_text)
    lang_data = data["idiomas"].get(lang, data["idiomas"]["es"])
    chapters = lang_data["chapters"]
    if chapter_idx >= len(chapters):
        raise IndexError(f"El capítulo {chapter_idx} no existe en el idioma {lang}.")

    cap = chapters[chapter_idx]
    audio_path = book_dir / cap["audio_url"]
    if not audio_path.exists():
        raise FileNotFoundError(f"No se encuentra el audio en {audio_path}")

    sync_data = cap["sync"]
    duration = cap.get("duration", sync_data.get("duration", 60.0))

    if output_mp4 is None:
        out_dir = book_dir / "videos"
        out_dir.mkdir(exist_ok=True)
        slug = cap.get("slug", f"capitulo_{chapter_idx:02d}")
        output_mp4 = out_dir / f"videolibro_{slug}_{lang}.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ass_path = tmp / "subtitles.ass"
        intro_path = tmp / "intro.png"
        bg_path = tmp / "bg.png"
        outro_path = tmp / "outro.png"

        print(f"[1/3] Generando subtítulos ASS con Karaoke para capítulo {chapter_idx} ({lang})...")
        build_ass_subtitles(cap, ass_path)

        print("[2/3] Generando telones gráficos de Intro, Fondo y Outro con QR...")
        generate_frames(book_dir, cap, intro_path, bg_path, outro_path)

        outro_dur = 6.0
        total_dur = duration + outro_dur

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(total_dur), "-i", str(bg_path),
            "-i", str(audio_path),
            "-loop", "1", "-t", "3.2", "-i", str(intro_path),
            "-loop", "1", "-t", str(outro_dur), "-i", str(outro_path),
            "-filter_complex",
            f"[0:v]ass={ass_path}[vmain];"
            f"[vmain][2:v]overlay=0:0:enable='between(t,0,3.2)'[vintro];"
            f"[vintro][3:v]overlay=0:0:enable='gte(t,{duration})'[vout]",
            "-map", "[vout]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_mp4)
        ]

        print(f"[3/3] Codificando videolibro MP4 con FFmpeg en {output_mp4}...")
        subprocess.run(cmd, check=True)
        size_mb = os.path.getsize(output_mp4) / (1024 * 1024)
        print(f"\n✅ [ÉXITO] Videolibro listo: {output_mp4} ({size_mb:.2f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Generador de Videolibros MP4 para La Odisea de la .IA")
    parser.add_argument("--book-dir", default=".", help="Ruta al libro (por defecto: .)")
    parser.add_argument("--chapter", type=int, default=0, help="Número de capítulo (por defecto: 0)")
    parser.add_argument("--lang", default="es", help="Idioma (por defecto: es)")
    parser.add_argument("--output", default=None, help="Ruta de salida del archivo .mp4")
    parser.add_argument("--all", action="store_true", help="Generar vídeos para todos los capítulos")

    args = parser.parse_args()
    b_dir = Path(args.book_dir).resolve()

    if args.all:
        bundle_path = b_dir / "homero-bundle.js"
        text = bundle_path.read_text(encoding="utf-8").strip()[len("window.HOMERO_BOOK = "):-1]
        data = json.loads(text)
        total = len(data["idiomas"][args.lang]["chapters"])
        for idx in range(total):
            render_chapter_video(b_dir, chapter_idx=idx, lang=args.lang)
    else:
        out = Path(args.output).resolve() if args.output else None
        render_chapter_video(b_dir, chapter_idx=args.chapter, lang=args.lang, output_mp4=out)


if __name__ == "__main__":
    main()
