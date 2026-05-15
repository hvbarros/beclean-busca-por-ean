#!/usr/bin/env python3
"""
Renderiza Tarefas_Workers_BeClean_v1.5.md em três páginas HTML estáticas
no estilo de novosite.baselabs.com.br e grava em build/.

Páginas geradas:
  build/index.html                → Início
  build/tarefa-1/index.html       → Tarefa 1 (Validação de Scraping)
  build/tarefa-2/index.html       → Tarefa 2 (Coleta de Rua)

A numeração das seções é reescrita por página (cada página começa em 1).

Uso: python3 build.py
"""
import subprocess
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MD_FILE = ROOT / "Tarefas_Workers_BeClean_v1.5.md"
XLSX_CAT = ROOT / "Categorias e subcategorias Be Clean v2 - Vertical.xlsx"
OUT_DIR = ROOT / "build"
BASE_URL = "/beclean/instrucoes_workers/"

OUT_DIR.mkdir(exist_ok=True)

# ── 1. Convert .md to full HTML body ──────────────────────────────────────
full_body = subprocess.run(
    [
        "pandoc",
        str(MD_FILE),
        "-f", "markdown-smart",  # preserva aspas retas (necessário pro match das captions)
        "-t", "html5",
        "--syntax-highlighting=none",
    ],
    check=True,
    capture_output=True,
    text=True,
).stdout

# Strip header (everything before first <hr/>)
full_body = re.split(r'<hr\s*/?>', full_body, maxsplit=1)[1].lstrip()

# ── Mapeamento caption (regex) → imagem extraída do PDF ──────────────────
# As regexes batem contra o texto após o slot ID (ex.: "1.1:"). A primeira
# regex que casar é usada. Slots sem match ficam como placeholder de texto.
SCREENSHOT_IMAGES = [
    (r'Revisão de imagens.*filtros',                   'hub-revisao-imagens-filtros.png'),
    (r'fora do padrão.*revisão',                       'hub-foto-fora-padrao.png'),
    (r'Pré-Aprovados.*filtros',                        'hub-pre-aprovados-filtros.png'),
    (r'quantidade total do lote',                      'hub-listagem-quantidade-total.png'),
    (r'link da loja aberto',                           'hub-ficha-produto.png'),
    (r'nome do Hub vs\.\s*nome no site',               'hub-ficha-produto.png'),
    (r'área da imagem na ficha',                       'hub-ficha-produto.png'),
    (r'campo de categoria/subcategoria',               'hub-ficha-produto.png'),
    (r'Editar categoria.*Salvar classificação',        'hub-ficha-produto.png'),
    (r'três quadrantes',                               'hub-ingredientes-quadrantes.png'),
    (r'botão "Aprovar Produto"',                       'hub-botao-aprovar-produto.png'),
    (r'toast.*"Produto pronto para produção"',         'hub-toast-pronto-producao.png'),
    (r'Observação com o ícone do lápis',               'hub-observacao-lapis.png'),
    (r'Observação preenchido',                         'hub-observacao-preenchida.png'),
    (r'lista de motivos existentes',                   'hub-observacao-preenchida.png'),
    (r'"Confirmar Revisão".*"Produto marcado',         'hub-confirmar-revisao.png'),
    (r'Revisão/Rejeitar/Aprovar destacados',           'hub-lote-checkboxes.png'),
    (r'"Selecionar todos os produtos"',                'hub-lote-checkboxes.png'),
    (r'Match Down.*Rejeitados',                        'hub-toast-lote.png'),
]


def transform_screenshot(m):
    # Pandoc quebra captions longas com \n — normaliza pra um espaço
    raw = re.sub(r'\s+', ' ', m.group(1)).strip()
    # Extract slot ID like "1.1", "3.a", "3.f.1" if present
    id_match = re.match(r'([0-9]+(?:\.[a-z0-9]+)+):\s*(.*)', raw)
    if id_match:
        slot_id = id_match.group(1)
        caption = id_match.group(2).strip()
    else:
        slot_id = ""
        caption = raw.lstrip(":").strip()

    img_file = None
    for pat, fname in SCREENSHOT_IMAGES:
        if re.search(pat, caption):
            img_file = fname
            break

    tag_label = f"// screenshot {slot_id}" if slot_id else "// screenshot"

    if img_file:
        img_src = f"{BASE_URL}img/{img_file}"
        return (
            f'<figure class="screenshot-slot has-img">'
            f'<figcaption class="ss-cap"><span class="ss-tag">{tag_label}</span>'
            f'<span class="ss-text">{caption}</span></figcaption>'
            f'<img src="{img_src}" alt="{caption}" loading="lazy">'
            f'</figure>'
        )
    return (
        f'<div class="screenshot-slot">'
        f'<span class="ss-tag">{tag_label}</span>'
        f'<span class="ss-text">{caption}</span>'
        f'</div>'
    )


# Convert screenshot placeholders to styled slots (com imagem quando bate o match)
full_body = re.sub(
    r'<blockquote>\s*<p><em>\[ESPAÇO PARA SCREENSHOT([^<]*)\]</em></p>\s*</blockquote>',
    transform_screenshot,
    full_body,
)

# Convert "> **Nota:**" blockquotes to coral callouts
full_body = re.sub(
    r'<blockquote>\s*<p><strong>Nota:</strong>([^<]*(?:<[^/][^>]*>[^<]*</[^>]+>[^<]*)*)</p>\s*</blockquote>',
    lambda m: f'<div class="note-callout"><span class="nc-tag">// nota</span><div class="nc-body">{m.group(1).strip()}</div></div>',
    full_body,
)

# Convert "> **Evidência:**" blockquotes to evidence callouts
full_body = re.sub(
    r'<blockquote>\s*<p><strong>Evidência:</strong>(.*?)</p>\s*</blockquote>',
    lambda m: f'<div class="evidence-callout"><span class="ev-tag">// evidência esperada</span><div class="ev-body">{m.group(1).strip()}</div></div>',
    full_body,
    flags=re.DOTALL,
)

# Convert "> **Aviso:**" blockquotes to navigation-hint callouts (yellow, bold)
full_body = re.sub(
    r'<blockquote>\s*<p><strong>Aviso:</strong>(.*?)</p>\s*</blockquote>',
    lambda m: f'<div class="aviso-callout"><span class="av-tag">// aviso</span><div class="av-body">{m.group(1).strip()}</div></div>',
    full_body,
    flags=re.DOTALL,
)

# Convert "> **Atenção:**" blockquotes to warning callouts
full_body = re.sub(
    r'<blockquote>\s*<p><strong>Atenção:</strong>(.*?)</p>\s*</blockquote>',
    lambda m: f'<div class="warning-callout"><span class="wn-tag">// atenção</span><div class="wn-body">{m.group(1).strip()}</div></div>',
    full_body,
    flags=re.DOTALL,
)

# ── 1b. Build categories table HTML from xlsx ─────────────────────────────
def build_categories_body() -> str:
    import openpyxl as _xl
    wb = _xl.load_workbook(str(XLSX_CAT))
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))  # skip header

    # Group by category for the TOC and section headers
    from collections import OrderedDict
    cats: "OrderedDict[str, list]" = OrderedDict()
    for cat, sub, ex in rows:
        if cat not in cats:
            cats[cat] = []
        cats[cat].append((sub or "", ex or ""))

    parts = [
        '<div class="cat-filter-wrap">'
        '<input class="cat-filter" type="search" placeholder="Filtrar por categoria ou subcategoria…" aria-label="Filtrar categorias">'
        '</div>\n'
    ]
    for cat, subcats in cats.items():
        slug = re.sub(r'[^a-z0-9]+', '-', cat.lower()).strip('-')
        parts.append(
            f'<h2 id="cat-{slug}" class="cat-heading">{cat}</h2>\n'
            f'<table class="cat-table">\n'
            f'<thead><tr><th>Subcategoria</th><th>Exemplos</th></tr></thead>\n'
            f'<tbody>\n'
        )
        for sub, ex in subcats:
            ex_html = f'<span class="cat-examples">{ex}</span>' if ex else ''
            parts.append(f'<tr><td class="cat-sub">{sub}</td><td>{ex_html}</td></tr>\n')
        parts.append('</tbody></table>\n')

    return "".join(parts)


# ── 2. Split full body into sections keyed by H2 id ───────────────────────
SECTION_RE = re.compile(r'(<h2\s+id="([^"]+)"[^>]*>.*?)(?=<h2\s+id=|<hr\s*/?>|\Z)', re.DOTALL)
sections = {m.group(2): m.group(1).rstrip() for m in SECTION_RE.finditer(full_body)}

# Strip stray <hr/> between sections
for k, v in sections.items():
    sections[k] = re.sub(r'<hr\s*/?>\s*$', '', v).rstrip()

# ── 3. Page configuration ─────────────────────────────────────────────────
PAGES = [
    {
        "slug": "",
        "nav_title": "Início",
        "cover_eyebrow": "manual operacional · beclean",
        "cover_title": 'Tarefas para <em>Workers</em>.<br>Projeto BeClean.',
        "show_meta": True,
        "sections": ["publico", "sec-introducao", "sec-duvidas"],
        # mapping de numeração original (no .md) → numeração local na página
        "renumber": {"1": "1", "5": "2"},
    },
    {
        "slug": "regras",
        "nav_title": "Regras",
        "cover_eyebrow": "regras gerais de execução",
        "cover_title": '<em>Regras</em><br>Gerais de Execução.',
        "show_meta": False,
        "sections": ["sec-regras", "sec-drive", "sec-planilha"],
        "renumber": {"3": "1", "4": "2", "6": "3"},
    },
    {
        "slug": "tarefa-1",
        "nav_title": "Tarefa 1",
        "cover_eyebrow": "tarefa 1 · validação de scraping",
        "cover_title": '<em>Tarefa 1</em><br>Validação de Scraping.',
        "show_meta": False,
        "sections": ["sec-tarefa-1"],
        "renumber": {"7": "1"},
    },
    {
        "slug": "categorias",
        "nav_title": "Categorias",
        "cover_eyebrow": "referência · categorias e subcategorias",
        "cover_title": '<em>Categorias</em><br>e Subcategorias.',
        "show_meta": False,
        "sections": [],
        "renumber": {},
        "custom_body": "categories",
    },
    {
        "slug": "problemas",
        "nav_title": "FAQ",
        "cover_eyebrow": "referência · perguntas frequentes",
        "cover_title": '<em>FAQ</em><br>Perguntas e Problemas Frequentes.',
        "show_meta": False,
        "sections": ["sec-troubleshooting"],
        "renumber": {"8": "1"},
    },
    {
        "slug": "tarefa-2",
        "nav_title": "Tarefa 2",
        "cover_eyebrow": "tarefa 2 · validação de coleta de rua",
        "cover_title": '<em>Tarefa 2</em><br>Coleta de Rua.',
        "show_meta": False,
        "sections": ["sec-tarefa-2"],
        "renumber": {"9": "1"},
        "hidden": True,
    },
    {
        "slug": "racional",
        "nav_title": "Racional",
        "cover_eyebrow": "anexo interno · gestor de contratos",
        "cover_title": '<em>Racional</em><br>Estimativas de tempo.',
        "show_meta": False,
        "sections": ["sec-racional"],
        "renumber": {"11": "1"},
        "hidden": True,
    },
]


def renumber_body(body: str, mapping: dict) -> str:
    """Reescreve numeração de H2/H3 e referências textuais conforme mapping."""
    if not mapping:
        return body

    def renum_h2(m):
        prefix = m.group(1)
        orig_num = m.group(2)
        new_num = mapping.get(orig_num, orig_num)
        return f'{prefix}{new_num}.'
    body = re.sub(r'(<h2[^>]*>)(\d+)\.', renum_h2, body)

    def renum_h3(m):
        prefix = m.group(1)
        orig_num = m.group(2)
        sub = m.group(3)
        new_num = mapping.get(orig_num, orig_num)
        return f'{prefix}{new_num}.{sub}.'
    body = re.sub(r'(<h3[^>]*>)(\d+)\.(\d+)\.', renum_h3, body)

    # "seção N" ou "seção N.M"
    def renum_secao(m):
        prefix = m.group(1)
        orig = m.group(2)
        rest = m.group(3) or ""
        new = mapping.get(orig)
        if new is None:
            return m.group(0)
        return f'{prefix}{new}{rest}'
    body = re.sub(r'(seção )(\d+)(\.\d+)?', renum_secao, body)

    # "ver N.M" ou "ver N.M.x"
    def renum_ver(m):
        prefix = m.group(1)
        orig = m.group(2)
        rest = m.group(3)
        new = mapping.get(orig)
        if new is None:
            return m.group(0)
        return f'{prefix}{new}{rest}'
    body = re.sub(r'(ver )(\d+)(\.\d+(?:\.[a-z])?)', renum_ver, body)

    return body


def extract_toc(body: str):
    """Extract H2 + H3 + H4 from a body fragment as a flat list of (level, id, title)."""
    items = []
    for hm in re.finditer(r'<h([234])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', body, re.DOTALL):
        level = int(hm.group(1))
        sid = hm.group(2)
        title = re.sub(r'<[^>]+>', '', hm.group(3)).strip()
        items.append((level, sid, title))
    return items


def render_toc(items):
    """Render TOC list HTML with H3s/H4s nested under their parent."""
    parts = []
    for lvl, sid, title in items:
        cls = {2: "toc-h2", 3: "toc-h3", 4: "toc-h4"}.get(lvl, "toc-h3")
        parts.append(
            f'<li class="{cls}"><a href="#{sid}"><span class="t">{title}</span></a></li>'
        )
    return "\n        ".join(parts)


def render_top_nav(active_slug: str):
    items = []
    for p in PAGES:
        if p.get("hidden"):
            continue
        href = BASE_URL + (p["slug"] + "/" if p["slug"] else "")
        cls = "active" if p["slug"] == active_slug else ""
        items.append(f'<li><a href="{href}" class="{cls}">{p["nav_title"]}</a></li>')
    return "\n      ".join(items)


def render_meta_block():
    return """
    <div class="meta">
      <div>
        <div class="k">// gestor de contrato</div>
        <div class="v">Hugo Barros · <a href="mailto:hbarros@baselabs.com.br">hbarros@baselabs.com.br</a></div>
      </div>
      <div>
        <div class="k">// pontos focais</div>
        <div class="v">Marina da Costa Miranda · Elaine da Silva (BeClean)</div>
      </div>
      <div>
        <div class="k">// versão</div>
        <div class="v">1.5 — 11/05/2026</div>
      </div>
    </div>
"""


# ── 4. HTML template ──────────────────────────────────────────────────────
TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title} · Instruções para Workers — BeClean · BASE/labs</title>
<meta name="description" content="Manual operacional dos workers BASE/labs alocados ao projeto BeClean — validação no Hub.">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400;1,500;1,600&display=swap">
<link rel="icon" href="https://novosite.baselabs.com.br/favicon-32.webp" sizes="32x32" type="image/webp">
<style>
:root {{
  --bg: #f6f7f9;
  --bg-1: #ffffff;
  --bg-2: #eef0f4;
  --fg: #14182a;
  --fg-2: #404862;
  --fg-3: #6a7488;
  --brand: #3654ae;
  --brand-2: #2a4490;
  --brand-coral: #ff6e5a;
  --line: #acb8ca;
  --line-soft: #d1d7e0;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --r-3: 8px;
}}
*, *::before, *::after {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--mono);
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}}
.shell {{ width: min(960px, 100% - 48px); margin-inline: auto; }}
.shell-wide {{ width: min(1200px, 100% - 48px); margin-inline: auto; }}

/* Header */
.site-header {{
  position: sticky; top: 0; z-index: 80;
  background: rgba(255,255,255,0.92);
  backdrop-filter: saturate(140%) blur(8px);
  -webkit-backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid var(--line-soft);
}}
.site-header .row {{
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; height: 64px;
}}
.site-header img {{ height: 28px; width: auto; }}
.site-header .crumbs {{ font-size: 12px; color: var(--fg-3); letter-spacing: 0.04em; }}
.site-header .crumbs a {{ color: var(--fg-2); text-decoration: none; }}
.site-header .crumbs a:hover {{ color: var(--brand); }}

/* Page nav (top tabs) */
.page-nav {{
  position: sticky; top: 64px; z-index: 70;
  background: var(--bg-1);
  border-bottom: 1px solid var(--line-soft);
}}
.page-nav ul {{
  display: flex; gap: 0;
  margin: 0; padding: 0;
  list-style: none;
  overflow-x: auto;
  scrollbar-width: none;
}}
.page-nav ul::-webkit-scrollbar {{ display: none; }}
.page-nav li {{ flex-shrink: 0; }}
.page-nav li::before {{ content: none; }}
.page-nav a {{
  display: block;
  padding: 14px 24px;
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--fg-3);
  text-decoration: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
}}
.page-nav a:hover {{ color: var(--fg-2); }}
.page-nav a.active {{ color: var(--brand); border-bottom-color: var(--brand); }}

/* Cover */
.cover {{
  padding: clamp(48px, 8vw, 88px) 0 clamp(28px, 5vw, 56px);
  border-bottom: 1px solid var(--line-soft);
  background: var(--bg-1);
}}
.eyebrow {{
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--fg-3); letter-spacing: 0.04em;
  text-transform: lowercase; margin-bottom: 20px;
}}
.eyebrow .bar {{ width: 24px; height: 2px; background: var(--brand); display: inline-block; }}
.cover h1 {{
  font-family: var(--mono);
  font-size: clamp(32px, 5.4vw, 60px);
  font-weight: 700;
  line-height: 1.0;
  letter-spacing: -0.03em;
  margin: 0 0 24px;
  color: var(--fg);
  max-width: 22ch;
}}
.cover h1 em {{ font-style: italic; font-weight: 400; color: var(--brand); }}
.cover .meta {{
  margin-top: 36px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px 32px;
  font-size: 13px;
}}
.cover .meta .k {{ color: var(--fg-3); text-transform: lowercase; letter-spacing: 0.04em; }}
.cover .meta .v {{ color: var(--fg); margin-top: 4px; }}
.cover .meta a {{ color: var(--brand); text-decoration: none; }}
.cover .meta a:hover {{ text-decoration: underline; }}

/* Content + sidebar layout */
.content {{ padding: clamp(40px, 6vw, 80px) 0 clamp(56px, 8vw, 120px); }}
.content-grid {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: 64px;
  align-items: start;
}}
.content-body {{ min-width: 0; }}

/* Content typography */
.content-body h1 {{ display: none; }}
.content-body h2 {{
  font-family: var(--mono);
  font-size: clamp(22px, 2.6vw, 30px);
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin: 64px 0 20px;
  padding-top: 16px;
  border-top: 1px solid var(--line-soft);
  color: var(--fg);
  scroll-margin-top: 130px;
}}
.content-body > h2:first-of-type {{ margin-top: 0; border-top: 0; padding-top: 0; }}
.content-body h3 {{
  font-family: var(--mono);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 36px 0 12px;
  color: var(--fg);
  scroll-margin-top: 130px;
}}
.content-body h3::before {{ content: "// "; color: var(--brand); font-weight: 400; }}
.content-body h4 {{
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 600;
  text-transform: lowercase;
  letter-spacing: 0.02em;
  color: var(--fg-2);
  margin: 24px 0 8px;
  scroll-margin-top: 130px;
}}
.content-body p, .content-body li {{ font-size: 15px; color: var(--fg-2); line-height: 1.7; }}
.content-body p {{ margin: 12px 0; }}
.content-body ul, .content-body ol {{ padding-left: 24px; margin: 12px 0; }}
.content-body ul li {{ list-style: none; position: relative; }}
.content-body ul li::before {{ content: "—"; position: absolute; left: -22px; color: var(--brand); }}
.content-body ol {{ padding-left: 28px; }}
.content-body ol li {{ padding-left: 4px; }}
.content-body ol li::marker {{ color: var(--brand); font-weight: 500; }}
.content-body strong {{ color: var(--fg); font-weight: 600; }}
.content-body em {{ color: var(--fg); font-style: italic; }}
.content-body a {{
  color: var(--brand); text-decoration: underline;
  text-decoration-thickness: 1px; text-underline-offset: 2px;
}}
.content-body a:hover {{ color: var(--brand-2); }}
.content-body code {{
  font-family: var(--mono);
  background: var(--bg-2);
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 0.92em;
  color: var(--fg);
}}
.content-body pre {{
  background: #0e1224;
  border: 1px solid var(--brand-2);
  border-radius: var(--r-3);
  padding: 18px 22px;
  overflow-x: auto;
  margin: 20px 0;
  position: relative;
}}
.content-body pre::before {{
  content: "// prompt";
  position: absolute; top: -10px; left: 16px;
  background: #0e1224;
  padding: 0 8px;
  font-size: 11px;
  color: #9edc37;
  letter-spacing: 0.06em;
}}
.content-body pre code {{
  background: transparent; border: 0; padding: 0;
  color: #d1d7e0; font-size: 13px; line-height: 1.65;
  white-space: pre-wrap;
}}
.content-body hr {{ display: none; }}
.content-body blockquote {{
  border-left: 2px solid var(--brand);
  background: var(--bg-1);
  padding: 14px 20px;
  margin: 16px 0;
  color: var(--fg-2);
  border-radius: 0 var(--r-3) var(--r-3) 0;
}}
.content-body blockquote p {{ margin: 0; }}

/* Screenshot slots (text placeholder) */
.screenshot-slot {{
  margin: 12px 0;
  padding: 14px 18px;
  background: var(--bg-1);
  border: 1px dashed var(--line);
  border-radius: var(--r-3);
  display: flex; gap: 14px; align-items: baseline;
  font-size: 13px;
}}
.screenshot-slot .ss-tag {{ color: var(--brand); font-weight: 500; letter-spacing: 0.04em; flex-shrink: 0; }}
.screenshot-slot .ss-text {{ color: var(--fg-3); font-style: italic; }}

/* Screenshot slots (with image) */
figure.screenshot-slot.has-img {{
  display: block;
  margin: 20px 0;
  padding: 0;
  background: var(--bg-1);
  border: 1px solid var(--line-soft);
  border-radius: var(--r-3);
  overflow: hidden;
}}
figure.screenshot-slot.has-img .ss-cap {{
  display: flex;
  gap: 12px;
  align-items: baseline;
  padding: 12px 16px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--line-soft);
  font-size: 12.5px;
}}
figure.screenshot-slot.has-img .ss-cap .ss-tag {{
  color: var(--brand); font-weight: 500;
  letter-spacing: 0.04em; flex-shrink: 0;
}}
figure.screenshot-slot.has-img .ss-cap .ss-text {{
  color: var(--fg-2); font-style: normal;
}}
figure.screenshot-slot.has-img img {{
  display: block;
  width: 100%;
  height: auto;
  background: #fff;
}}

/* Note callouts */
.note-callout {{
  display: flex; gap: 16px;
  padding: 14px 18px;
  margin: 16px 0;
  background: #fff8f3;
  border-left: 3px solid var(--brand-coral);
  border-radius: 0 var(--r-3) var(--r-3) 0;
}}
.note-callout .nc-tag {{
  color: var(--brand-coral); font-size: 12px;
  letter-spacing: 0.04em; flex-shrink: 0; padding-top: 2px;
}}
.note-callout .nc-body {{ color: var(--fg-2); font-size: 14px; line-height: 1.6; }}

/* Aviso callouts (navigation hint — yellow, bold) */
.aviso-callout {{
  display: flex; gap: 16px;
  padding: 14px 18px;
  margin: 24px 0 8px;
  background: #fffbe6;
  border-left: 3px solid #e6a800;
  border-radius: 0 var(--r-3) var(--r-3) 0;
}}
.aviso-callout .av-tag {{
  color: #b37f00; font-size: 12px;
  letter-spacing: 0.04em; flex-shrink: 0; padding-top: 2px; font-weight: 500;
}}
.aviso-callout .av-body {{ color: var(--fg); font-size: 14px; line-height: 1.6; font-weight: 600; }}

/* Warning callouts */
.warning-callout {{
  display: flex; gap: 16px;
  padding: 14px 18px;
  margin: 16px 0;
  background: #fff2f2;
  border-left: 3px solid #d93025;
  border-radius: 0 var(--r-3) var(--r-3) 0;
}}
.warning-callout .wn-tag {{
  color: #d93025; font-size: 12px;
  letter-spacing: 0.04em; flex-shrink: 0; padding-top: 2px; font-weight: 500;
}}
.warning-callout .wn-body {{ color: var(--fg); font-size: 14px; line-height: 1.6; font-weight: 500; }}

/* Evidence callouts */
.evidence-callout {{
  display: flex; gap: 16px;
  padding: 14px 18px;
  margin: 24px 0 8px;
  background: #fffbe6;
  border-left: 3px solid #e6a800;
  border-radius: 0 var(--r-3) var(--r-3) 0;
}}
.evidence-callout .ev-tag {{
  color: #b37f00; font-size: 12px;
  letter-spacing: 0.04em; flex-shrink: 0; padding-top: 2px; font-weight: 500;
}}
.evidence-callout .ev-body {{ color: var(--fg-2); font-size: 14px; line-height: 1.6; }}

/* Side TOC */
.toc-side {{
  position: sticky;
  top: 140px;
  align-self: start;
  font-size: 13px;
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  padding-right: 4px;
}}
.toc-side .toc-side-inner > .eyebrow {{ margin-bottom: 12px; }}
.toc-side ol, .toc-side ul {{ list-style: none; padding: 0; margin: 0; }}
.toc-side li {{ margin: 0; padding: 0; }}
.toc-side li::before {{ content: none; }}
.toc-side a {{
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 0 6px 12px;
  margin-left: -12px;
  border-left: 2px solid transparent;
  color: var(--fg-3);
  text-decoration: none;
  line-height: 1.45;
  transition: color 0.15s ease, border-color 0.15s ease;
}}
.toc-side a:hover {{ color: var(--fg-2); }}
.toc-side a.active {{ color: var(--brand); border-left-color: var(--brand); }}
.toc-side .toc-h2 > a {{ font-weight: 500; color: var(--fg-2); }}
.toc-side .toc-h2 > a.active {{ color: var(--brand); }}
.toc-side .toc-h3 > a {{
  padding-left: 28px;
  margin-left: -12px;
  font-size: 12.5px;
}}
.toc-side .toc-h4 > a {{
  padding-left: 44px;
  margin-left: -12px;
  font-size: 12px;
  color: var(--fg-3);
}}
.toc-side .toc-top {{
  display: inline-block;
  margin-top: 20px;
  font-size: 12px;
  color: var(--fg-3);
  text-decoration: none;
  letter-spacing: 0.04em;
}}
.toc-side .toc-top:hover {{ color: var(--brand); }}

/* Footer */
.site-footer {{
  border-top: 1px solid var(--line-soft);
  background: var(--bg-1);
  padding: 48px 0 56px;
  font-size: 13px;
  color: var(--fg-3);
}}
.site-footer .row {{
  display: flex; gap: 24px; flex-wrap: wrap;
  justify-content: space-between; align-items: center;
}}
.site-footer img {{ height: 22px; opacity: 0.85; }}
.site-footer .legal {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.site-footer a {{ color: var(--fg-2); text-decoration: none; }}
.site-footer a:hover {{ color: var(--brand); }}

/* Page footer nav (prev/next) */
.page-footer-nav {{
  margin-top: 80px;
  padding-top: 32px;
  border-top: 1px solid var(--line-soft);
  display: flex; gap: 16px;
  justify-content: space-between; flex-wrap: wrap;
}}
.page-footer-nav a {{
  text-decoration: none;
  color: var(--fg-2);
  font-size: 13px;
  display: flex; flex-direction: column; gap: 4px;
  padding: 12px 16px;
  border: 1px solid var(--line-soft);
  border-radius: var(--r-3);
  background: var(--bg-1);
  min-width: 200px;
  transition: border-color 0.15s ease, color 0.15s ease;
}}
.page-footer-nav a:hover {{ border-color: var(--brand); color: var(--brand); }}
.page-footer-nav .pfn-k {{ font-size: 11px; color: var(--fg-3); letter-spacing: 0.04em; }}
.page-footer-nav .pfn-prev {{ text-align: left; }}
.page-footer-nav .pfn-next {{ text-align: right; margin-left: auto; }}
.page-footer-nav .pfn-next .pfn-k {{ text-align: right; }}

/* Categories table */
.cat-heading {{
  font-size: clamp(18px, 2vw, 24px);
  font-weight: 600;
  letter-spacing: -0.01em;
  margin: 56px 0 14px;
  padding-top: 16px;
  border-top: 1px solid var(--line-soft);
  color: var(--fg);
  scroll-margin-top: 130px;
}}
.content-body > .cat-heading:first-of-type {{ margin-top: 0; border-top: 0; padding-top: 0; }}
.cat-filter-wrap {{
  margin-bottom: 32px;
}}
.cat-filter {{
  width: 100%;
  max-width: 420px;
  padding: 10px 14px;
  font-family: var(--mono);
  font-size: 13px;
  background: var(--bg-1);
  border: 1px solid var(--line);
  border-radius: var(--r-3);
  color: var(--fg);
  outline: none;
  transition: border-color 0.15s;
}}
.cat-filter:focus {{ border-color: var(--brand); }}
.cat-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 8px;
}}
.cat-table thead th {{
  text-align: left;
  padding: 8px 14px;
  background: var(--bg-2);
  border: 1px solid var(--line-soft);
  font-size: 11px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--fg-3);
  font-weight: 500;
}}
.cat-table tbody tr {{ transition: background 0.1s; }}
.cat-table tbody tr:hover {{ background: var(--bg-2); }}
.cat-table td {{
  padding: 9px 14px;
  border: 1px solid var(--line-soft);
  vertical-align: top;
  line-height: 1.55;
}}
.cat-sub {{
  width: 220px;
  font-weight: 500;
  color: var(--fg);
  white-space: nowrap;
}}
.cat-examples {{ color: var(--fg-3); }}
.cat-hidden {{ display: none; }}

/* Generic content tables (e.g. Problemas Comuns) */
.content-body table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  margin: 24px 0 32px;
  border-radius: var(--r-3);
  overflow: hidden;
  border: 1px solid var(--line-soft);
}}
.content-body table thead th {{
  text-align: left;
  padding: 12px 18px;
  background: var(--fg);
  color: var(--bg-1);
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 600;
  border-bottom: 2px solid var(--brand);
}}
.content-body table tbody tr:nth-child(odd) {{
  background: var(--bg-1);
}}
.content-body table tbody tr:nth-child(even) {{
  background: var(--bg-2);
}}
.content-body table tbody tr:hover {{
  background: #dde1ea;
}}
.content-body table td {{
  padding: 14px 18px;
  vertical-align: top;
  line-height: 1.65;
  border-bottom: 1px solid var(--line-soft);
  color: var(--fg);
}}
.content-body table td:first-child {{
  font-weight: 600;
  color: var(--brand-2);
  white-space: nowrap;
  width: 28%;
}}
.content-body table tbody tr:last-child td {{
  border-bottom: none;
}}

@media (max-width: 1024px) {{
  .content-grid {{ grid-template-columns: 1fr; gap: 0; }}
  .toc-side {{ display: none; }}
  .page-nav {{ top: 64px; }}
  .content-body h2, .content-body h3 {{ scroll-margin-top: 130px; }}
}}
@media (max-width: 640px) {{
  body {{ font-size: 14px; }}
  .shell, .shell-wide {{ width: min(640px, 100% - 32px); }}
  .cover h1 {{ font-size: 30px; }}
  .content-body h2 {{ font-size: 21px; margin-top: 48px; }}
  .content-body h3 {{ font-size: 16px; }}
  .page-nav a {{ padding: 12px 16px; }}
}}
@media print {{
  .site-header, .page-nav, .site-footer, .toc-side, .page-footer-nav {{ display: none; }}
  .content-grid {{ grid-template-columns: 1fr; }}
  body {{ background: white; }}
  .content-body pre {{ background: #f3f4f8; color: #14182a; border-color: var(--line-soft); }}
  .content-body pre::before {{ background: #f3f4f8; color: var(--brand-2); }}
  .content-body pre code {{ color: #14182a; }}
}}
</style>
</head>
<body>
<header class="site-header">
  <div class="shell-wide row">
    <a href="https://novosite.baselabs.com.br/" aria-label="BASE/labs">
      <img src="https://novosite.baselabs.com.br/logo-azul.webp" alt="BASE/labs">
    </a>
    <div class="crumbs">
      <a href="https://novosite.baselabs.com.br/">base/labs</a>
      &nbsp;/&nbsp; beclean
      &nbsp;/&nbsp; instruções workers
    </div>
  </div>
</header>
<nav class="page-nav" aria-label="Páginas do manual">
  <div class="shell-wide">
    <ul>
      {top_nav}
    </ul>
  </div>
</nav>
<section class="cover">
  <div class="shell-wide">
    <div class="eyebrow"><span class="bar"></span>{cover_eyebrow}</div>
    <h1>{cover_title}</h1>
    {meta_block}
  </div>
</section>
<main class="content">
  <div class="shell-wide content-grid">
    <article class="content-body">
{body}
{page_footer_nav}
    </article>
    <aside class="toc-side" aria-label="Sumário lateral">
      <div class="toc-side-inner">
        <div class="eyebrow"><span class="bar"></span>nesta página</div>
        <ol class="toc-list">
        {toc_side}
        </ol>
        <a href="#" class="toc-top" aria-label="Voltar ao topo">↑ topo</a>
      </div>
    </aside>
  </div>
</main>
<footer class="site-footer">
  <div class="shell-wide row">
    <a href="https://novosite.baselabs.com.br/" aria-label="BASE/labs">
      <img src="https://novosite.baselabs.com.br/logo-azul.webp" alt="BASE/labs">
    </a>
    <div class="legal">
      <span>© 2026 BASE/labs · Braço de IA da BASE2</span>
      <a href="mailto:hbarros@baselabs.com.br">Dúvidas: hbarros@baselabs.com.br</a>
    </div>
  </div>
</footer>
<script>
// Category filter
(() => {{
  const input = document.querySelector('.cat-filter');
  if (!input) return;
  input.addEventListener('input', () => {{
    const q = input.value.trim().toLowerCase();
    document.querySelectorAll('.cat-heading').forEach(h2 => {{
      const table = h2.nextElementSibling;
      if (!table) return;
      const catMatch = !q || h2.textContent.toLowerCase().includes(q);
      let visibleRows = 0;
      table.querySelectorAll('tbody tr').forEach(tr => {{
        const match = catMatch || tr.textContent.toLowerCase().includes(q);
        tr.classList.toggle('cat-hidden', !match);
        if (match) visibleRows++;
      }});
      const hide = q && !catMatch && visibleRows === 0;
      h2.classList.toggle('cat-hidden', hide);
      table.classList.toggle('cat-hidden', hide);
    }});
  }});
}})();

(() => {{
  const headings = document.querySelectorAll('.content-body h2[id], .content-body h3[id], .content-body h4[id]');
  const links = document.querySelectorAll('.toc-side a[href^="#"]');
  if (!headings.length || !links.length) return;
  const linkByHref = {{}};
  links.forEach(a => {{ linkByHref[a.getAttribute('href')] = a; }});
  let activeId = null;
  const setActive = (id) => {{
    if (id === activeId) return;
    activeId = id;
    links.forEach(a => a.classList.remove('active'));
    const link = linkByHref['#' + id];
    if (link) link.classList.add('active');
  }};
  const visible = new Map();
  const io = new IntersectionObserver((entries) => {{
    entries.forEach(e => {{
      if (e.isIntersecting) visible.set(e.target.id, e.target);
      else visible.delete(e.target.id);
    }});
    const ids = [...visible.values()].sort((a,b) => a.offsetTop - b.offsetTop).map(el => el.id);
    if (ids.length) setActive(ids[0]);
  }}, {{ rootMargin: '-130px 0px -70% 0px' }});
  headings.forEach(h => io.observe(h));
}})();
</script>
</body>
</html>
"""


def render_page_footer_nav(page_idx: int):
    """Render prev/next links between pages. Hidden pages don't get prev/next, and don't appear as targets."""
    current = PAGES[page_idx]
    if current.get("hidden"):
        return ""

    visible = [(i, p) for i, p in enumerate(PAGES) if not p.get("hidden")]
    pos = next(i for i, (idx, _) in enumerate(visible) if idx == page_idx)

    parts = []
    if pos > 0:
        prev = visible[pos - 1][1]
        prev_href = BASE_URL + (prev["slug"] + "/" if prev["slug"] else "")
        parts.append(
            f'<a href="{prev_href}" class="pfn-prev"><span class="pfn-k">← anterior</span><span class="pfn-v">{prev["nav_title"]}</span></a>'
        )
    else:
        parts.append('<span></span>')
    if pos < len(visible) - 1:
        nxt = visible[pos + 1][1]
        nxt_href = BASE_URL + (nxt["slug"] + "/" if nxt["slug"] else "")
        parts.append(
            f'<a href="{nxt_href}" class="pfn-next"><span class="pfn-k">próxima →</span><span class="pfn-v">{nxt["nav_title"]}</span></a>'
        )
    return f'<div class="page-footer-nav">{"".join(parts)}</div>'


# ── 5. Render each page ───────────────────────────────────────────────────
generated = []
for idx, page in enumerate(PAGES):
    if page.get("custom_body") == "categories":
        body = build_categories_body()
    else:
        body_parts = []
        for sid in page["sections"]:
            if sid not in sections:
                raise RuntimeError(f'Section "{sid}" not found in {MD_FILE.name}')
            body_parts.append(sections[sid])
        body = "\n".join(body_parts)
        body = renumber_body(body, page.get("renumber", {}))

    toc_items = extract_toc(body)
    toc_html = render_toc(toc_items)
    nav_html = render_top_nav(page["slug"])
    meta_html = render_meta_block() if page["show_meta"] else ""
    pfn_html = render_page_footer_nav(idx)

    html = TEMPLATE.format(
        page_title=page["nav_title"],
        cover_eyebrow=page["cover_eyebrow"],
        cover_title=page["cover_title"],
        meta_block=meta_html,
        top_nav=nav_html,
        body=body,
        toc_side=toc_html,
        page_footer_nav=pfn_html,
    )

    out_path = OUT_DIR / (page["slug"] if page["slug"] else "") / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    generated.append((page["nav_title"], out_path))

print("OK · páginas geradas:")
for title, path in generated:
    print(f"  · {title:10s} → {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")
