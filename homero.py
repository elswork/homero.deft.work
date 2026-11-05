#!/usr/bin/env python3
"""
HOMERO — Motor de publicación editorial, audiolibro neuronal con Karaoke Inverso
(Read-Along) y exportación multiformato (Web, EPUB, PDF, MP3) para GitHub Pages.
"""

import argparse
import asyncio
import datetime
import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

import edge_tts
import yaml
from fpdf import FPDF


LANG_MAP = {
    "en": "en",
    "es": "es",
}


def translate_text(text: str, sl: str = "es", tl: str = "en") -> str:
    """Traduce texto plano preservando saltos de línea."""
    if not text or not text.strip():
        return text
    target = LANG_MAP.get(tl, tl)
    source = LANG_MAP.get(sl, sl)
    if source == target:
        return text
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source}&tl={target}&dt=t&q={urllib.parse.quote(text)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return "".join([part[0] for part in data[0] if part[0]])


def translate_markdown_file(source_content: str, sl: str, tl: str) -> str:
    """
    Traduce un archivo Markdown completo preservando frontmatter YAML y sintaxis.
    """
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", source_content, re.DOTALL)
    if not fm_match:
        return translate_text(source_content, sl, tl)

    fm_raw, body = fm_match.groups()
    source_hash = hashlib.sha256(source_content.encode("utf-8")).hexdigest()[:16]

    out_fm_lines = []
    has_source_hash = False
    for line in fm_raw.splitlines():
        if line.startswith("titulo:"):
            val = line.split("titulo:", 1)[1].strip().strip("\"'")
            tr_val = translate_text(val, sl, tl).replace('"', '\\"')
            out_fm_lines.append(f'titulo: "{tr_val}"')
        elif line.startswith("subtitulo:"):
            val = line.split("subtitulo:", 1)[1].strip().strip("\"'")
            tr_val = translate_text(val, sl, tl).replace('"', '\\"')
            out_fm_lines.append(f'subtitulo: "{tr_val}"')
        elif line.startswith("fuente_hash:"):
            out_fm_lines.append(f'fuente_hash: "{source_hash}"')
            has_source_hash = True
        else:
            out_fm_lines.append(line)

    if not has_source_hash:
        out_fm_lines.append(f'fuente_hash: "{source_hash}"')

    paras = body.split("\n\n")
    tr_paras = []
    for p in paras:
        p_strip = p.strip()
        if not p_strip:
            continue
        if p_strip.startswith("## "):
            h_text = p_strip[3:].strip()
            tr_paras.append(f"## {translate_text(h_text, sl, tl)}")
        elif p_strip.startswith("### "):
            h_text = p_strip[4:].strip()
            tr_paras.append(f"### {translate_text(h_text, sl, tl)}")
        elif p_strip.startswith("> "):
            q_text = p_strip[2:].strip()
            tr_paras.append(f"> {translate_text(q_text, sl, tl)}")
        elif p_strip.startswith("---") or p_strip.startswith("***"):
            tr_paras.append(p_strip)
        else:
            lines = p_strip.splitlines()
            if any(re.match(r"^\d+\.\s+", l) for l in lines):
                tr_lines = []
                for l in lines:
                    m = re.match(r"^(\d+\.\s+)(.*)$", l)
                    if m:
                        tr_lines.append(f"{m.group(1)}{translate_text(m.group(2), sl, tl)}")
                    else:
                        tr_lines.append(translate_text(l, sl, tl))
                tr_paras.append("\n".join(tr_lines))
            else:
                tr_paras.append(translate_text(p_strip, sl, tl))

    new_fm = "---\n" + "\n".join(out_fm_lines) + "\n---\n\n"
    return new_fm + "\n\n".join(tr_paras) + "\n"


def auto_translate_book(book_dir: Path, source_lang: str = "es"):
    """
    Traduce automáticamente los capítulos desde el idioma fuente a todos los idiomas
    definidos en libro.yaml si no existen o si el archivo fuente ha cambiado.
    """
    cfg_path = book_dir / "libro.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"No se encontró {cfg_path}")

    book_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    idiomas_cfg = book_cfg.get("idiomas", {})

    source_dir = book_dir / "capitulos" / source_lang
    if not source_dir.exists():
        print(f"[TRADUCCIÓN] Directorio fuente {source_dir} no existe.")
        return

    source_files = sorted(source_dir.glob("*.md"))
    if not source_files:
        print(f"[TRADUCCIÓN] No hay capítulos en {source_dir}.")
        return

    for target_lang, linfo in idiomas_cfg.items():
        if target_lang == source_lang:
            continue

        target_dir = book_dir / "capitulos" / target_lang
        target_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[TRADUCCIÓN] Sincronizando idioma [{target_lang.upper()}] ({linfo.get('nombre', target_lang)})...")
        for s_file in source_files:
            t_file = target_dir / s_file.name
            s_content = s_file.read_text(encoding="utf-8")
            s_hash = hashlib.sha256(s_content.encode("utf-8")).hexdigest()[:16]

            needs_trans = True
            if t_file.exists():
                try:
                    t_content = t_file.read_text(encoding="utf-8")
                    t_meta, _ = parse_frontmatter_and_body(t_content)
                    if t_meta.get("fuente_hash") == s_hash:
                        needs_trans = False
                except Exception:
                    pass

            if needs_trans:
                print(f"  -> Traduciendo {s_file.name} ({source_lang} -> {target_lang})...")
                translated_md = translate_markdown_file(s_content, source_lang, target_lang)
                t_file.write_text(translated_md, encoding="utf-8")
            else:
                print(f"  -> {s_file.name} [{target_lang}] actualizado (caché OK).")


def normalize_word(w: str) -> str:
    """Extrae únicamente caracteres alfanuméricos en minúscula para alinear palabras."""
    return re.sub(r"[^\w]", "", w.lower(), flags=re.UNICODE)


def parse_frontmatter_and_body(md_text: str):
    """Separa el frontmatter YAML del cuerpo Markdown."""
    meta = {}
    body = md_text
    if md_text.startswith("---"):
        parts = md_text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
    return meta, body


def clean_inline_markdown_to_plain(text: str) -> str:
    """Convierte inline markdown a texto limpio para hablar/PDF."""
    s = re.sub(r"\*\*`([^`]+)`\*\*", r"\1", text)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    # Limpiar cualquier marcador residual o huérfano
    s = s.replace("**", "").replace("*", "").replace("`", "").replace("«", '"').replace("»", '"')
    return s.strip()


def split_into_sentences(text: str):
    """Divide un párrafo en frases manteniendo signos de puntuación."""
    parts = re.split(r"(?<=[.?!])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def format_word_html(raw_token: str, w_id: int, s_id: int) -> str:
    """Formatea un token de palabra con formato inline básico y su span de karaoke."""
    display = html.escape(raw_token)
    display = re.sub(r"\*\*`([^`]+)`\*\*", r"<strong><code>\1</code></strong>", display)
    display = re.sub(r"`([^`]+)`", r"<code>\1</code>", display)
    display = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", display)
    display = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", display)
    return f'<span class="hm-word" id="w-{w_id}" data-w="{w_id}" data-s="{s_id}">{display}</span>'


def compile_markdown_for_karaoke(
    md_body: str,
    chapter_num: int,
    chapter_title: str,
    chapter_subtitle: str,
    author: str,
    lang: str,
):
    """
    Convierte el título, subtítulo, autoría y cuerpo Markdown en:
    - HTML interactivo con frases (.hm-sentence) y palabras (.hm-word) numeradas
    - Lista de frases y palabras para alinear con el motor TTS
    - Lista de bloques limpios para EPUB y PDF
    """
    lines = md_body.splitlines()
    blocks = []
    current_para = []
    in_list = False
    list_items = []

    def flush_para():
        nonlocal current_para
        if current_para:
            joined = " ".join(current_para).strip()
            if joined:
                blocks.append(("p", joined))
            current_para = []

    def flush_list():
        nonlocal in_list, list_items
        if list_items:
            blocks.append(("ol", list_items[:]))
            list_items = []
        in_list = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_para()
            flush_list()
            continue
        if line == "---":
            flush_para()
            flush_list()
            blocks.append(("hr", ""))
            continue
        if line.startswith("# "):
            # El H1 ya se muestra en la cabecera del capítulo
            flush_para()
            flush_list()
            continue
        if line.startswith("### Sé parte") or line.startswith("### Be Part"):
            # El cierre CTA ya lo renderiza la caja interactiva de Homero
            flush_para()
            flush_list()
            break
        if line.startswith("## ") or line.startswith("### "):
            flush_para()
            flush_list()
            heading_text = re.sub(r"^#{2,3}\s+", "", line).strip()
            blocks.append(("h2", heading_text))
            continue
        m_ol = re.match(r"^\d+\.\s+(.*)$", line)
        if m_ol:
            flush_para()
            in_list = True
            list_items.append(m_ol.group(1).strip())
            continue
        if line.startswith("* "):
            flush_para()
            in_list = True
            list_items.append(line[2:].strip())
            continue

        if in_list:
            flush_list()
        current_para.append(line)

    flush_para()
    flush_list()

    sentences_meta = []
    words_meta = []
    html_parts = []
    clean_blocks = []

    s_counter = 0
    w_counter = 0

    def register_sentence(raw_sentence: str):
        nonlocal s_counter, w_counter
        s_id = s_counter
        s_counter += 1
        tokens = [t for t in raw_sentence.split(" ") if t]
        word_spans = []
        s_word_ids = []
        for tok in tokens:
            w_id = w_counter
            w_counter += 1
            plain_tok = clean_inline_markdown_to_plain(tok)
            norm_tok = normalize_word(plain_tok)
            words_meta.append({
                "w": w_id,
                "s": s_id,
                "text": plain_tok,
                "norm": norm_tok,
                "start": 0.0,
                "end": 0.0,
            })
            s_word_ids.append(w_id)
            word_spans.append(format_word_html(tok, w_id, s_id))

        plain_sentence = clean_inline_markdown_to_plain(raw_sentence)
        sentences_meta.append({
            "s": s_id,
            "text": plain_sentence,
            "words": s_word_ids,
            "start": 0.0,
            "end": 0.0,
        })
        inner_html = " ".join(word_spans)
        return f'<span class="hm-sentence" id="s-{s_id}" data-s="{s_id}">{inner_html}</span>'

    # 1. El audiolibro y el karaoke comienzan con el Título del capítulo
    prefix_cap = f"Capítulo {chapter_num}: " if lang == "es" else f"Chapter {chapter_num}: "
    title_full = f"{prefix_cap}{chapter_title}"
    title_html = register_sentence(title_full)

    # 2. Subtítulo explicativo
    subtitle_html = ""
    if chapter_subtitle:
        sub_sents = split_into_sentences(chapter_subtitle)
        subtitle_html = " ".join(register_sentence(st) for st in sub_sents)

    # 3. Datos adicionales de autoría
    author_prefix = f"Por {author}." if lang == "es" else f"By {author}."
    author_html = register_sentence(author_prefix)

    # 4. Cuerpo de párrafos, listas y encabezados
    for btype, bcontent in blocks:
        if btype == "hr":
            html_parts.append('<hr class="chapter-divider">')
            clean_blocks.append(("hr", ""))
        elif btype == "h2":
            s_html = register_sentence(bcontent)
            html_parts.append(f"<h2>{s_html}</h2>")
            clean_blocks.append(("h2", clean_inline_markdown_to_plain(bcontent)))
        elif btype == "ol":
            li_htmls = []
            clean_items = []
            for item in bcontent:
                sents = split_into_sentences(item)
                rendered_sents = [register_sentence(st) for st in sents]
                li_htmls.append(f"<li>{' '.join(rendered_sents)}</li>")
                clean_items.append(clean_inline_markdown_to_plain(item))
            html_parts.append(f"<ol>{''.join(li_htmls)}</ol>")
            clean_blocks.append(("ol", clean_items))
        elif btype == "p":
            sents = split_into_sentences(bcontent)
            rendered_sents = [register_sentence(st) for st in sents]
            html_parts.append(f"<p>{' '.join(rendered_sents)}</p>")
            clean_blocks.append(("p", clean_inline_markdown_to_plain(bcontent)))

    return title_html, subtitle_html, author_html, "\n".join(html_parts), sentences_meta, words_meta, clean_blocks


async def synthesize_and_align(
    sentences_meta,
    words_meta,
    voice: str,
    rate: str,
    mp3_path: Path,
    sync_path: Path,
    text_hash: str,
    force: bool = False,
):
    """
    Genera el archivo MP3 con edge-tts y alinea al milisegundo cada palabra y frase
    usando los eventos WordBoundary.
    """
    if not force and mp3_path.exists() and sync_path.exists():
        try:
            existing = json.loads(sync_path.read_text(encoding="utf-8"))
            if existing.get("text_hash") == text_hash:
                print(f"  [CACHÉ OK] {mp3_path.name} sin cambios.")
                return existing
        except Exception:
            pass

    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    spoken_text = " ".join(s["text"] for s in sentences_meta)

    print(f"  [TTS] Generando audiolibro y marcas de tiempo ({voice}) -> {mp3_path.name}...")
    tts_words = []
    active_voice = voice
    for attempt in range(2):
        try:
            communicate = edge_tts.Communicate(
                spoken_text,
                voice=active_voice,
                rate=rate,
                boundary="WordBoundary",
            )
            tts_words = []
            with open(mp3_path, "wb") as audio_file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start_sec = round(chunk["offset"] / 10_000_000.0, 3)
                        dur_sec = round(chunk["duration"] / 10_000_000.0, 3)
                        end_sec = round(start_sec + max(dur_sec, 0.08), 3)
                        tts_words.append({
                            "text": chunk["text"],
                            "norm": normalize_word(chunk["text"]),
                            "start": start_sec,
                            "end": end_sec,
                        })
            if tts_words:
                break
        except Exception as err:
            if attempt == 0:
                fallback_voice = "ru-RU-SvetlanaNeural" if "ru-RU" in active_voice else "en-US-AriaNeural"
                print(f"  [AVISO TTS] Falló voz {active_voice} ({err}). Reintentando con voz alternativa {fallback_voice}...")
                active_voice = fallback_voice
            else:
                print(f"  [ERROR TTS] No se pudo generar audio para {mp3_path.name}: {err}")

    # Mapear la posición de caracteres de cada palabra del DOM en spoken_text
    w_cursor = 0
    for w_obj in words_meta:
        w_text = w_obj["text"]
        idx = spoken_text.find(w_text, w_cursor)
        if idx == -1:
            idx = spoken_text.lower().find(w_text.lower(), w_cursor)
        if idx != -1 and idx - w_cursor < 35:
            w_obj["char_start"] = idx
            w_obj["char_end"] = idx + len(w_text)
            w_cursor = w_obj["char_end"]
        else:
            w_obj["char_start"] = w_cursor
            w_obj["char_end"] = w_cursor + len(w_text)
            w_cursor = w_obj["char_end"]

    # Mapear la posición de caracteres de cada chunk devuelto por TTS
    t_cursor = 0
    for chunk in tts_words:
        c_text = chunk["text"]
        idx = spoken_text.lower().find(c_text.lower(), t_cursor)
        if idx != -1 and idx - t_cursor < 50:
            chunk["char_start"] = idx
            chunk["char_end"] = idx + len(c_text)
            t_cursor = chunk["char_end"]
        else:
            chunk["char_start"] = t_cursor
            chunk["char_end"] = t_cursor + len(c_text)
            t_cursor = chunk["char_end"]

    if tts_words:
        # Alineación precisa basada en superposición de caracteres y marcas de tiempo TTS
        for w_obj in words_meta:
            overlapping = [
                c for c in tts_words
                if not (c["char_end"] <= w_obj["char_start"] or c["char_start"] >= w_obj["char_end"])
            ]
            if overlapping:
                w_obj["start"] = overlapping[0]["start"]
                w_obj["end"] = overlapping[-1]["end"]
            else:
                nearest = min(tts_words, key=lambda c: abs(c["char_start"] - w_obj["char_start"]))
                w_obj["start"] = nearest["start"]
                w_obj["end"] = nearest["end"]

        # Garantizar monotonía temporal limpia (el audio solo avanza en el tiempo)
        cur_t = 0.0
        for w_obj in words_meta:
            if w_obj["start"] < cur_t:
                w_obj["start"] = cur_t
            if w_obj["end"] < w_obj["start"]:
                w_obj["end"] = round(w_obj["start"] + 0.1, 3)
            cur_t = w_obj["start"]
        last_time = max((w_obj["end"] for w_obj in words_meta), default=0.0)
    else:
        # Fallback sintético si no hubo eventos de WordBoundary
        last_time = 0.0
        for w_obj in words_meta:
            w_obj["start"] = round(last_time, 3)
            w_obj["end"] = round(last_time + 0.18, 3)
            last_time = w_obj["end"]

    # Calcular inicio y fin de cada frase a partir de sus palabras
    for s_obj in sentences_meta:
        w_ids = s_obj["words"]
        if w_ids:
            first_w = words_meta[w_ids[0]]
            last_w = words_meta[w_ids[-1]]
            s_obj["start"] = first_w["start"]
            s_obj["end"] = last_w["end"]

    sync_payload = {
        "text_hash": text_hash,
        "voice": voice,
        "duration": round(last_time, 3),
        "sentences": [
            {"s": s["s"], "start": s["start"], "end": s["end"]}
            for s in sentences_meta
        ],
        "words": [
            {"w": w["w"], "s": w["s"], "start": w["start"], "end": w["end"]}
            for w in words_meta
        ],
    }

    sync_path.write_text(json.dumps(sync_payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return sync_payload


def generate_epub(book_cfg: dict, lang: str, chapters_data: list, out_path: Path):
    """Genera un archivo EPUB 3 estándar y válido."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    book_title = book_cfg["libro"]["titulo"]
    author = book_cfg["libro"]["autor"]
    book_uid = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, f'odisea.deft.work/{lang}')}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. mimetype debe ir primero y sin comprimir
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        # 2. META-INF/container.xml
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )

        # 3. OEBPS/styles.css
        zf.writestr(
            "OEBPS/styles.css",
            """body { font-family: Georgia, serif; line-height: 1.65; margin: 5%; color: #1c1e21; }
h1 { font-size: 1.8em; color: #003399; margin-bottom: 0.2em; }
h2 { font-size: 1.3em; margin-top: 1.6em; color: #1c1e21; }
.subtitle { font-style: italic; color: #5c5f66; margin-bottom: 1.8em; }
hr { border: 0; border-top: 1px solid #ccc; margin: 1.5em 0; }
""",
        )

        manifest_items = [
            '<item id="css" href="styles.css" media-type="text/css"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]
        spine_items = []
        nav_links = []

        for idx, ch in enumerate(chapters_data, start=1):
            fname = f"chapter_{idx:02d}.xhtml"
            item_id = f"ch{idx:02d}"
            manifest_items.append(
                f'<item id="{item_id}" href="{fname}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{item_id}"/>')
            nav_links.append(f'<li><a href="{fname}">{html.escape(ch["title"])}</a></li>')

            body_elems = []
            for btype, bcontent in ch["clean_blocks"]:
                if btype == "hr":
                    body_elems.append("<hr/>")
                elif btype == "h2":
                    body_elems.append(f"<h2>{html.escape(bcontent)}</h2>")
                elif btype == "ol":
                    items_xml = "".join(f"<li>{html.escape(it)}</li>" for it in bcontent)
                    body_elems.append(f"<ol>{items_xml}</ol>")
                elif btype == "p":
                    body_elems.append(f"<p>{html.escape(bcontent)}</p>")

            ch_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">
<head>
  <meta charset="UTF-8"/>
  <title>{html.escape(ch["title"])}</title>
  <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
  <h1>{html.escape(ch["title"])}</h1>
  <p class="subtitle">{html.escape(ch["subtitle"])}</p>
  {"".join(body_elems)}
</body>
</html>"""
            zf.writestr(f"OEBPS/{fname}", ch_xhtml)

        # 4. OEBPS/nav.xhtml
        nav_xhtml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head>
  <meta charset="UTF-8"/>
  <title>{html.escape(book_title)}</title>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{html.escape(book_title)}</h1>
    <ol>
      {"".join(nav_links)}
    </ol>
  </nav>
</body>
</html>"""
        zf.writestr("OEBPS/nav.xhtml", nav_xhtml)

        # 5. OEBPS/content.opf
        opf_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{book_uid}</dc:identifier>
    <dc:title>{html.escape(book_title)}</dc:title>
    <dc:creator>{html.escape(author)}</dc:creator>
    <dc:language>{lang}</dc:language>
    <meta property="dcterms:modified">{now_iso}</meta>
  </metadata>
  <manifest>
    {"".join(manifest_items)}
  </manifest>
  <spine>
    {"".join(spine_items)}
  </spine>
</package>"""
        zf.writestr("OEBPS/content.opf", opf_xml)

    print(f"  [EPUB] Generado -> {out_path.name}")


def find_font_for_lang(lang: str) -> tuple[str, str]:
    """Busca fuentes TrueType/OpenType adecuadas según el sistema de escritura del idioma."""
    candidates = []
    if lang == "zh":
        candidates = [
            ("/usr/share/fonts/chromeos/notocjk/NotoSansCJK-Regular.ttc", "/usr/share/fonts/chromeos/notocjk/NotoSansCJK-Bold.ttc"),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"),
        ]
    elif lang == "ar":
        candidates = [
            ("/usr/share/fonts/chromeos/noto/NotoSansArabic-Regular.ttf", "/usr/share/fonts/chromeos/noto/NotoSansArabic-Bold.ttf"),
            ("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"),
        ]
    elif lang == "hi":
        candidates = [
            ("/usr/share/fonts/chromeos/noto/NotoSansDevanagari-Regular.ttf", "/usr/share/fonts/chromeos/noto/NotoSansDevanagari-Bold.ttf"),
            ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"),
        ]

    for reg, bld in candidates:
        if os.path.exists(reg):
            bold_file = bld if os.path.exists(bld) else reg
            return reg, bold_file

    default_candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/chromeos/noto/NotoSerif-Regular.ttf", "/usr/share/fonts/chromeos/noto/NotoSerif-Bold.ttf"),
    ]
    for reg, bld in default_candidates:
        if os.path.exists(reg):
            bold_file = bld if os.path.exists(bld) else reg
            return reg, bold_file

    return "", ""


def generate_pdf(book_cfg: dict, lang: str, chapters_data: list, out_path: Path):
    """Genera un archivo PDF maquetado con soporte Unicode completo."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(22, 22, 22)

    font_reg, font_bold = find_font_for_lang(lang)
    if font_reg:
        pdf.add_font("BookSerif", style="", fname=font_reg)
        pdf.add_font("BookSerif", style="B", fname=font_bold)
    else:
        pdf.set_font("Helvetica", "", 11)

    for ch in chapters_data:
        pdf.add_page()
        pdf.set_font("BookSerif", "B", 10)
        pdf.set_text_color(0, 51, 153)
        pdf.cell(
            0,
            7,
            f"{book_cfg['libro']['titulo']} · {book_cfg['libro']['expediente_ue']}",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.ln(3)
        pdf.set_font("BookSerif", "B", 18)
        pdf.set_text_color(28, 30, 33)
        pdf.multi_cell(0, 9, ch["title"])

        pdf.ln(2)
        pdf.set_font("BookSerif", "", 11)
        pdf.set_text_color(92, 95, 102)
        pdf.multi_cell(0, 6.5, ch["subtitle"])
        pdf.ln(5)

        pdf.set_text_color(28, 30, 33)
        for btype, bcontent in ch["clean_blocks"]:
            if btype == "hr":
                pdf.ln(3)
            elif btype == "h2":
                pdf.ln(4)
                pdf.set_font("BookSerif", "B", 13)
                pdf.multi_cell(0, 7.5, bcontent)
                pdf.ln(2)
            elif btype == "ol":
                pdf.set_font("BookSerif", "", 11)
                for idx_li, it in enumerate(bcontent, start=1):
                    pdf.multi_cell(0, 6.8, f"  {idx_li}. {it}")
                    pdf.ln(1.5)
                pdf.ln(2)
            elif btype == "p":
                pdf.set_font("BookSerif", "", 11)
                pdf.multi_cell(0, 6.8, bcontent)
                pdf.ln(3.5)

    pdf.output(str(out_path))
    print(f"  [PDF]  Generado -> {out_path.name}")


async def build_book(
    book_dir: Path,
    force_tts: bool = False,
    translate: bool = False,
    source_lang: str = "es",
):
    cfg_path = book_dir / "libro.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"No se encontró {cfg_path}")

    if translate:
        auto_translate_book(book_dir, source_lang=source_lang)

    book_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    idiomas_cfg = book_cfg.get("idiomas", {})
    compiled_bundle = {
        "libro": book_cfg["libro"],
        "patrocinio": book_cfg.get("patrocinio", {}),
        "idiomas": {},
    }

    for lang, linfo in idiomas_cfg.items():
        lang_dir = book_dir / "capitulos" / lang
        if not lang_dir.exists():
            continue

        md_files = sorted(lang_dir.glob("*.md"))
        if not md_files:
            continue

        print(f"\n=== Procesando idioma [{lang.upper()}] ({linfo['nombre']}) ===")
        chapters_out = []
        chapters_for_docs = []

        for md_file in md_files:
            raw_md = md_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter_and_body(raw_md)
            slug = md_file.stem
            ch_num = meta.get("capitulo", 1)
            ch_title = meta.get("titulo", slug)
            ch_subtitle = meta.get("subtitulo", "")
            reading_time = meta.get("tiempo_lectura", "4 min")

            author_name = book_cfg["libro"]["autor"]
            title_html, subtitle_html, author_html, html_body, s_meta, w_meta, clean_blocks = (
                compile_markdown_for_karaoke(
                    body, ch_num, ch_title, ch_subtitle, author_name, lang
                )
            )

            spoken_text = " ".join(s["text"] for s in s_meta)
            text_hash = hashlib.sha256(f"{linfo['voz_tts']}::{spoken_text}".encode("utf-8")).hexdigest()[:16]

            mp3_rel = f"audio/{lang}/{slug}.mp3"
            sync_rel = f"audio/{lang}/{slug}.sync.json"
            mp3_path = book_dir / mp3_rel
            sync_path = book_dir / sync_rel

            sync_data = await synthesize_and_align(
                sentences_meta=s_meta,
                words_meta=w_meta,
                voice=linfo["voz_tts"],
                rate=linfo.get("velocidad_tts", "+0%"),
                mp3_path=mp3_path,
                sync_path=sync_path,
                text_hash=text_hash,
                force=force_tts,
            )

            chapters_out.append({
                "capitulo": ch_num,
                "slug": slug,
                "title": ch_title,
                "title_html": title_html,
                "subtitle": ch_subtitle,
                "subtitle_html": subtitle_html,
                "author_html": author_html,
                "reading_time": reading_time,
                "audio_url": mp3_rel,
                "duration": sync_data["duration"],
                "html": html_body,
                "sync": {
                    "sentences": sync_data["sentences"],
                    "words": sync_data["words"],
                },
            })

            chapters_for_docs.append({
                "title": f"Capítulo {ch_num}: {ch_title}" if lang == "es" else f"Chapter {ch_num}: {ch_title}",
                "subtitle": ch_subtitle,
                "clean_blocks": clean_blocks,
            })

        epub_rel = f"descargas/odisea-ia-{lang}.epub"
        pdf_rel = f"descargas/odisea-ia-{lang}.pdf"
        generate_epub(book_cfg, lang, chapters_for_docs, book_dir / epub_rel)
        generate_pdf(book_cfg, lang, chapters_for_docs, book_dir / pdf_rel)

        compiled_bundle["idiomas"][lang] = {
            "nombre": linfo["nombre"],
            "bandera": linfo["bandera"],
            "epub_url": epub_rel,
            "pdf_url": pdf_rel,
            "chapters": chapters_out,
        }

    bundle_js_path = book_dir / "homero-bundle.js"
    bundle_json = json.dumps(compiled_bundle, ensure_ascii=False, separators=(",", ":"))
    bundle_js_path.write_text(
        f"window.HOMERO_BOOK = {bundle_json};\n",
        encoding="utf-8",
    )
    print(f"\n[OK] Bundle interactivo escrito en {bundle_js_path}")


def main():
    parser = argparse.ArgumentParser(description="Homero — Compilador de libros interactivos y audiolibros")
    sub = parser.add_subparsers(dest="cmd")

    # Comando build
    b_parser = sub.add_parser("build", help="Compila los capítulos Markdown, el audiolibro y los formatos descargables")
    b_parser.add_argument("--book-dir", default=".", help="Ruta al directorio del libro")
    b_parser.add_argument("--force-tts", action="store_true", help="Regenerar audios aunque no haya cambiado el texto")
    b_parser.add_argument("--translate", action="store_true", help="Auto-traducir capítulos ausentes o modificados antes de compilar")
    b_parser.add_argument("--source-lang", default="es", help="Idioma maestro fuente (por defecto: es)")

    # Comando translate
    t_parser = sub.add_parser("translate", help="Auto-traduce capítulos desde el idioma fuente a los idiomas de libro.yaml")
    t_parser.add_argument("--book-dir", default=".", help="Ruta al directorio del libro")
    t_parser.add_argument("--source-lang", default="es", help="Idioma maestro fuente (por defecto: es)")

    args = parser.parse_args()
    if args.cmd == "build":
        asyncio.run(build_book(
            Path(args.book_dir).resolve(),
            force_tts=args.force_tts,
            translate=args.translate,
            source_lang=args.source_lang,
        ))
    elif args.cmd == "translate":
        auto_translate_book(Path(args.book_dir).resolve(), source_lang=args.source_lang)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

