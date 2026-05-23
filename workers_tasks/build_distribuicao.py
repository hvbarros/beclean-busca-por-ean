#!/usr/bin/env python3
"""
Gera build/distribuicao/index.html a partir de distribuicoes/distribuicao.md.
Uso: python3 build_distribuicao.py
"""
import re
import subprocess
from pathlib import Path

ROOT    = Path(__file__).resolve().parent
MD_FILE = ROOT / "distribuicoes" / "distribuicao.md"
OUT_DIR = ROOT / "build" / "distribuicao"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Parse do .md ──────────────────────────────────────────────────────────────

def parse_md(path: Path) -> tuple[str, list[dict]]:
    text = path.read_text(encoding="utf-8")

    # Data de referência
    data_ref = re.search(r"Data de referência:\s*(.+)", text)
    data_referencia = data_ref.group(1).strip() if data_ref else "—"

    # Blocos de worker: separados por "## Nome"
    worker_blocks = re.split(r"\n## ", text)
    workers = []

    for block in worker_blocks[1:]:  # pula o cabeçalho
        lines = block.strip().splitlines()
        nome = lines[0].strip()

        tipo_match = re.search(r"tipo:\s*(\S+)", block)
        tipo = tipo_match.group(1) if tipo_match else "—"

        total_match = re.search(r"total:\s*(\S+)", block)
        total_raw = total_match.group(1) if total_match else None
        total = int(total_raw) if total_raw and total_raw.isdigit() else None

        # Tabela de marcas (só existe quando tipo=Marca)
        marcas = []
        table_rows = re.findall(r"^\|\s*(.+?)\s*\|\s*(\d+)\s*\|", block, re.MULTILINE)
        for marca, qtd in table_rows:
            marcas.append({"nome": marca.strip(), "qtd": int(qtd)})

        if marcas and total is None:
            total = sum(m["qtd"] for m in marcas)

        workers.append({
            "nome":   nome,
            "tipo":   tipo,
            "total":  total,
            "marcas": marcas,
        })

    return data_referencia, workers


# ── Geração da tabela ─────────────────────────────────────────────────────────

def badge(tipo: str) -> str:
    if tipo == "EAN":
        return '<span class="badge-tipo badge-ean">EAN</span>'
    if tipo == "Marca":
        return '<span class="badge-tipo badge-marca">Marca</span>'
    return '<span class="badge-tipo badge-nd">—</span>'


def build_table(workers: list[dict]) -> str:
    rows = ""
    for w in workers:
        nome  = w["nome"]
        tipo  = w["tipo"]
        total = w["total"]
        marcas = w["marcas"]
        total_str = f"{total:,}".replace(",", ".") if total else "—"

        if tipo == "EAN":
            # Uma única linha: worker | EAN | total | —
            rows += f"""
  <tr class="row-worker">
    <td class="col-worker">{nome}</td>
    <td class="col-tipo">{badge(tipo)}</td>
    <td class="col-qtd">{total_str}</td>
    <td class="col-marca">—</td>
  </tr>"""

        elif tipo == "Marca":
            n = len(marcas)
            # Primeira linha: worker com rowspan (marcas + linha de total)
            if marcas:
                first = marcas[0]
                rows += f"""
  <tr class="row-worker">
    <td class="col-worker" rowspan="{n + 1}">{nome}</td>
    <td class="col-tipo">{badge(tipo)}</td>
    <td class="col-qtd">{first["qtd"]}</td>
    <td class="col-marca">{first["nome"]}</td>
  </tr>"""
                for m in marcas[1:]:
                    rows += f"""
  <tr>
    <td class="col-tipo">{badge(tipo)}</td>
    <td class="col-qtd">{m["qtd"]}</td>
    <td class="col-marca">{m["nome"]}</td>
  </tr>"""
                # Linha de total
                rows += f"""
  <tr class="row-subtotal">
    <td class="col-tipo"></td>
    <td class="col-qtd col-total">Total: {total_str}</td>
    <td class="col-marca"></td>
  </tr>"""
            else:
                rows += f"""
  <tr class="row-worker">
    <td class="col-worker">{nome}</td>
    <td class="col-tipo">{badge(tipo)}</td>
    <td class="col-qtd">—</td>
    <td class="col-marca">—</td>
  </tr>"""

        else:
            # Sem atribuição
            rows += f"""
  <tr class="row-sem-atrib">
    <td class="col-worker">{nome}</td>
    <td class="col-tipo">{badge(tipo)}</td>
    <td class="col-qtd">—</td>
    <td class="col-marca">—</td>
  </tr>"""

    return rows


# ── HTML ──────────────────────────────────────────────────────────────────────

CSS = """
:root {
  --bg: #f6f7f9; --bg-1: #ffffff; --bg-2: #eef0f4;
  --fg: #14182a; --fg-2: #404862; --fg-3: #6a7488;
  --brand: #3654ae; --line: #acb8ca; --line-soft: #d1d7e0;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --r-3: 8px;
}
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font-family: var(--mono); font-size: 15px; line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.shell-wide { width: min(1200px, 100% - 48px); margin-inline: auto; }

.site-header {
  position: sticky; top: 0; z-index: 80;
  background: rgba(255,255,255,0.92);
  backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid var(--line-soft);
}
.site-header .row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; height: 64px;
}
.site-header img { height: 28px; }
.site-header .crumbs { font-size: 12px; color: var(--fg-3); letter-spacing: 0.04em; }
.site-header .crumbs a { color: var(--fg-2); text-decoration: none; }
.site-header .crumbs a:hover { color: var(--brand); }

.cover {
  padding: clamp(48px,8vw,80px) 0 clamp(28px,5vw,48px);
  border-bottom: 1px solid var(--line-soft); background: var(--bg-1);
}
.eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--fg-3); letter-spacing: 0.04em;
  text-transform: lowercase; margin-bottom: 20px;
}
.eyebrow .bar { width: 24px; height: 2px; background: var(--brand); display: inline-block; }
.cover h1 {
  font-size: clamp(28px,4.5vw,52px); font-weight: 700;
  line-height: 1.05; letter-spacing: -0.03em; margin: 0 0 20px;
}
.cover h1 em { font-style: italic; font-weight: 400; color: var(--brand); }
.cover .meta { margin-top: 28px; display: flex; gap: 32px; flex-wrap: wrap; font-size: 13px; }
.cover .meta .k { color: var(--fg-3); letter-spacing: 0.04em; }
.cover .meta .v { color: var(--fg); margin-top: 4px; font-weight: 600; }

.content { padding: clamp(40px,6vw,72px) 0 clamp(56px,8vw,100px); }
.section-title {
  font-size: clamp(18px,2.2vw,24px); font-weight: 600;
  letter-spacing: -0.02em; margin: 0 0 8px;
  display: flex; align-items: center; gap: 10px;
}
.section-title::before { content: "//"; color: var(--brand); font-weight: 400; }
.section-desc { font-size: 13px; color: var(--fg-3); margin: 0 0 24px; }

.table-wrap { overflow-x: auto; }
.dist-table {
  width: 100%; border-collapse: collapse; font-size: 13.5px;
  border: 1px solid var(--line-soft); border-radius: var(--r-3);
  overflow: hidden; min-width: 560px;
}
.dist-table thead th {
  text-align: left; padding: 12px 16px;
  background: var(--fg); color: var(--bg-1);
  font-size: 11px; letter-spacing: 0.06em;
  text-transform: uppercase; font-weight: 600;
  border-right: 1px solid rgba(255,255,255,0.08);
  white-space: nowrap;
}
.dist-table thead th:last-child { border-right: 0; }
.dist-table tbody td {
  padding: 10px 16px;
  border-bottom: 1px solid var(--line-soft);
  border-right: 1px solid var(--line-soft);
  vertical-align: middle;
}
.dist-table tbody td:last-child { border-right: 0; }
.dist-table tbody tr:last-child td { border-bottom: 0; }

.row-worker td { border-top: 2px solid var(--line); }
.row-worker:first-child td { border-top: none; }
.row-sem-atrib td { color: var(--fg-3); font-style: italic; border-top: 2px solid var(--line); }
.row-subtotal td {
  background: var(--bg-2);
  border-top: 1px dashed var(--line);
  border-bottom: 2px solid var(--line);
}

.col-worker { font-weight: 600; color: var(--fg); min-width: 200px; vertical-align: top; padding-top: 13px; }
.col-tipo   { width: 90px; }
.col-qtd    { width: 140px; text-align: right; font-variant-numeric: tabular-nums; }
.col-total  { font-weight: 600; color: var(--fg); }
.col-marca  { color: var(--fg-2); }

.badge-tipo {
  display: inline-block; padding: 2px 9px; border-radius: 999px;
  font-size: 10.5px; font-weight: 600; letter-spacing: 0.04em;
}
.badge-ean   { background: #dbeafe; color: #1e40af; }
.badge-marca { background: #fce7f3; color: #9d174d; }
.badge-nd    { background: var(--bg-2); color: var(--fg-3); }

.site-footer {
  border-top: 1px solid var(--line-soft); background: var(--bg-1);
  padding: 40px 0 48px; font-size: 13px; color: var(--fg-3);
}
.site-footer .row {
  display: flex; gap: 24px; flex-wrap: wrap;
  justify-content: space-between; align-items: center;
}
.site-footer img { height: 22px; opacity: 0.85; }
.site-footer a { color: var(--fg-2); text-decoration: none; }
.site-footer a:hover { color: var(--brand); }

@media (max-width: 640px) {
  body { font-size: 14px; }
  .shell-wide { width: min(640px, 100% - 32px); }
  .cover h1 { font-size: 26px; }
}
"""


def render(data_referencia: str, workers: list[dict], table_rows: str,
           n_workers: int, total_eans: int, total_marcas: int) -> str:
    t_eans  = f"{total_eans:,}".replace(",", ".")
    t_marc  = f"{total_marcas:,}".replace(",", ".")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Distribuição de EANs · BeClean · BASE/labs</title>
<meta name="robots" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400;1,500;1,600&display=swap">
<link rel="icon" href="https://propostas.baselabs.com.br/beclean/favicon-32.webp" sizes="32x32" type="image/webp">
<style>{CSS}</style>
</head>
<body>

<header class="site-header">
  <div class="shell-wide row">
    <a href="https://baselabs.com.br/" aria-label="BASE/labs">
      <img src="https://propostas.baselabs.com.br/beclean/logo-azul.webp" alt="BASE/labs">
    </a>
    <div class="crumbs">
      <a href="https://baselabs.com.br/">base/labs</a>
      &nbsp;/&nbsp; beclean &nbsp;/&nbsp; distribuição workers
    </div>
  </div>
</header>

<section class="cover">
  <div class="shell-wide">
    <div class="eyebrow"><span class="bar"></span>uso interno · base/labs</div>
    <h1>Distribuição de<br><em>EANs e Marcas</em></h1>
    <div class="meta">
      <div><div class="k">referência</div><div class="v">{data_referencia}</div></div>
      <div><div class="k">workers</div><div class="v">{n_workers}</div></div>
      <div><div class="k">EANs distribuídos</div><div class="v">{t_eans}</div></div>
      <div><div class="k">marcas distribuídas (qtd)</div><div class="v">{t_marc}</div></div>
    </div>
  </div>
</section>

<main class="content">
  <div class="shell-wide">
    <h2 class="section-title">Distribuição por worker</h2>
    <p class="section-desc">
      <strong>EAN</strong> — total de EANs críticos atribuídos (fonte: planilha).
      &nbsp;·&nbsp;
      <strong>Marca</strong> — marca inteira atribuída com volume esperado (fonte: PDF).
    </p>
    <div class="table-wrap">
      <table class="dist-table">
        <thead>
          <tr>
            <th>Worker</th>
            <th>EAN ou Marca</th>
            <th style="text-align:right">Qtd. Esperada</th>
            <th>Marca</th>
          </tr>
        </thead>
        <tbody>
{table_rows}
        </tbody>
      </table>
    </div>
  </div>
</main>

<footer class="site-footer">
  <div class="shell-wide row">
    <a href="https://baselabs.com.br/" aria-label="BASE/labs">
      <img src="https://propostas.baselabs.com.br/beclean/logo-azul.webp" alt="BASE/labs">
    </a>
    <div>
      <span>© 2026 BASE/labs · uso interno</span>
      &nbsp;·&nbsp;
      <a href="mailto:hbarros@baselabs.com.br">hbarros@baselabs.com.br</a>
    </div>
  </div>
</footer>

</body>
</html>"""


if __name__ == "__main__":
    data_referencia, workers = parse_md(MD_FILE)
    table_rows = build_table(workers)

    # Totais via python3 subprocess (per global rule)
    result = subprocess.run(["python3", "-c", f"""
workers = {repr(workers)}
total_eans   = sum(w['total'] for w in workers if w['tipo'] == 'EAN' and w['total'])
total_marcas = sum(w['total'] for w in workers if w['tipo'] == 'Marca' and w['total'])
n_workers    = len(workers)
print(total_eans, total_marcas, n_workers)
"""], capture_output=True, text=True)
    total_eans, total_marcas, n_workers = map(int, result.stdout.strip().split())

    html = render(data_referencia, workers, table_rows, n_workers, total_eans, total_marcas)
    out = OUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK · build/distribuicao/index.html ({out.stat().st_size:,} bytes)")
    print(f"   Workers: {n_workers} | EANs: {total_eans:,} | Marcas: {total_marcas:,}")
