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
import uuid
import zipfile
from pathlib import Path

import edge_tts
import yaml
from fpdf import FPDF


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
    return s.strip()


def split_into_sentences(text: str):
    """Divide un párrafo en frases manteniendo signos de puntuación."""
    parts = re.split(r"(?<=[.?!:;])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def format_word_html(raw_token: str, w_id: int, s_id: int) -> str:
    """Formatea un token de palabra con formato inline básico y su span de karaoke."""
    display = html.escape(raw_token)
    display = re.sub(r"\*\*`([^`]+)`\*\*", r"<strong><code>\1</code></strong>", display)
    display = re.sub(r"`([^`]+)`", r"<code>\1</code>", display)
    display = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", display)
    display = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", display)
    return f'<span class="hm-word" id="w-{w_id}" data-w="{w_id}" data-s="{s_id}">{display}</span>'


def compile_markdown_for_karaoke(md_body: str, chapter_title: str, chapter_subtitle: str):
    """
    Convierte el cuerpo Markdown en:
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

    # Incluir título y subtítulo como frase 0 y frase 1 narradas o empezar desde el cuerpo:
    # Empezamos en el cuerpo del relato para que el lector vea iluminarse directamente el primer párrafo.
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

    return "\n".join(html_parts), sentences_meta, words_meta, clean_blocks


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
    communicate = edge_tts.Communicate(
        spoken_text,
        voice=voice,
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

    # Alineación secuencial con ventana de búsqueda corta para emparejar cada token del DOM
    tts_idx = 0
    num_tts = len(tts_words)
    last_time = 0.0

    for w_obj in words_meta:
        target_norm = w_obj["norm"]
        matched = None
        if target_norm and tts_idx < num_tts:
            # Buscar coincidencia exacta o prefijo dentro de una ventana de 6 tokens
            for lookahead in range(min(6, num_tts - tts_idx)):
                cand = tts_words[tts_idx + lookahead]
                if (
                    cand["norm"] == target_norm
                    or (cand["norm"] and target_norm.startswith(cand["norm"]))
                    or (cand["norm"] and cand["norm"].startswith(target_norm))
                ):
                    matched = cand
                    tts_idx = tts_idx + lookahead + 1
                    break

        if matched is None and tts_idx < num_tts:
            matched = tts_words[tts_idx]
            tts_idx += 1

        if matched is not None:
            w_obj["start"] = matched["start"]
            w_obj["end"] = matched["end"]
            last_time = matched["end"]
        else:
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


def generate_pdf(book_cfg: dict, lang: str, chapters_data: list, out_path: Path):
    """Genera un archivo PDF maquetado con soporte Unicode completo."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(22, 22, 22)

    font_reg = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
    if not os.path.exists(font_reg):
        font_reg = "/usr/share/fonts/chromeos/noto/NotoSerif-Regular.ttf"
        font_bold = "/usr/share/fonts/chromeos/noto/NotoSerif-Bold.ttf"

    pdf.add_font("BookSerif", style="", fname=font_reg)
    pdf.add_font("BookSerif", style="B", fname=font_bold)

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


async def build_book(book_dir: Path, force_tts: bool = False):
    cfg_path = book_dir / "libro.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"No se encontró {cfg_path}")

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
            text_hash = hashlib.sha256(raw_md.encode("utf-8")).hexdigest()[:16]
            meta, body = parse_frontmatter_and_body(raw_md)
            slug = md_file.stem
            ch_num = meta.get("capitulo", 1)
            ch_title = meta.get("titulo", slug)
            ch_subtitle = meta.get("subtitulo", "")
            reading_time = meta.get("tiempo_lectura", "4 min")

            html_body, s_meta, w_meta, clean_blocks = compile_markdown_for_karaoke(
                body, ch_title, ch_subtitle
            )

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
                "subtitle": ch_subtitle,
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
    b_parser = sub.add_parser("build", help="Compila los capítulos Markdown, el audiolibro y los formatos descargables")
    b_parser.add_argument("--book-dir", default=".", help="Ruta al directorio del libro")
    b_parser.add_argument("--force-tts", action="store_true", help="Regenerar audios aunque no haya cambiado el texto")

    args = parser.parse_args()
    if args.cmd == "build":
        asyncio.run(build_book(Path(args.book_dir).resolve(), force_tts=args.force_tts))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
