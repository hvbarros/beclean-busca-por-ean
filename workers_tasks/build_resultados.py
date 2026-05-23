#!/usr/bin/env python3
"""
Gera build/resultados/index.html — página de acompanhamento dos workers.
Usa o mesmo visual do site de instruções, mas sem link na navegação principal.

Uso: python3 build_resultados.py
"""
import subprocess
from pathlib import Path
from datetime import date

ROOT    = Path(__file__).resolve().parent
OUT_DIR = ROOT / "build" / "resultados"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_REFERENCIA = "23 de maio de 2026 às 10:01"

# ── Dados ────────────────────────────────────────────────────────────────────

WORKERS = [
    {
        "rank":          1,
        "nome":          'Camila Teixeira Ferreira',
        "marcas":        'NEW BRAND, NIINA SECRETS, Niina Secrets, NINA RICCI, NIOXIN, Nivea, Novex, Ny Looks, OCÉANE',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '299 produtos, 13 aprovados (4%), resultado 100% preenchido',
        "total":         299,
        "aprovados":     13,
        "revisao":       215,
        "ja_revisado":   71,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 238,
        "notas": [],
    },
    {
        "rank":          2,
        "nome":          'Nicolle Dognini',
        "marcas":        'Adcos, Adidas, Alva, AMACIHAIR, ANTONIO BANDERAS, Aussie, Avène, AZZARO, Baby & Kids, BANDERAS, BANILA CO, Banila Co, BEAUTYCOLOR, BELA&COR, BENETTON, Biocolor, BIODERMA, Bioderma, Boca Rosa, BOCA ROSA, BOSS, BOUCHERON, Bourjois, Bozzano, BRAÉ, BRAÉ HAIR CARE, BRITNEY SPEARS, BRUNA TAVARES, Bruna Tavares, BURBERRY, BVLGARI, CACHAREL, CALVIN KLEIN, CARE Natural Beauty, CAROLINA HERRERA, CARTIER, FELPS, Felps Color, Felps Professional',
        "planilha":      'alerta',
        "evidencias":    'ruim',
        "avaliacao":     '299 produtos, ⚠ 204 sem resultado, 10 aprovados (3%)',
        "total":         299,
        "aprovados":     10,
        "revisao":       85,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 204,
        "com_evidencia": 95,
        "notas": [],
    },
    {
        "rank":          3,
        "nome":          'Paula Machado Alves',
        "marcas":        'Felps professional, Fran By Franciny Ehlke, Gabriela Sabatini, GIORGIO ARMANI, Giovanna Baby, GIVENCHY, Granado, GUCCI, GUERLAIN, HEAD & SHOULDERS, Head & Shoulders, Herbissimo, Herbíssimo, HUGO BOSS, ISSEY MIYAKE, JEAN PAUL GAULTIER, JIMMY CHOO',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '299 produtos, 95 aprovados (32%), resultado 100% preenchido',
        "total":         299,
        "aprovados":     95,
        "revisao":       204,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 368,
        "notas": [],
    },
    {
        "rank":          4,
        "nome":          'Gustavo Norberto',
        "marcas":        'Boticario, Nivea',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '280 produtos, 134 aprovados (48%), resultado 100% preenchido',
        "total":         280,
        "aprovados":     134,
        "revisao":       146,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 274,
        "notas": ['5 EANs sem evidência confirmada'],
    },
    {
        "rank":          5,
        "nome":          'Breno Souza',
        "marcas":        'Revlon',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '138 produtos, resultado 100% preenchido',
        "total":         138,
        "aprovados":     0,
        "revisao":       138,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 135,
        "notas": ['3 EANs sem evidência confirmada'],
    },
    {
        "rank":          6,
        "nome":          'Maria Geane Silva Cardoso',
        "marcas":        'RISQUÉ, Risqué, ROCHAS, Ruby Kisses, RUBY KISSES',
        "planilha":      'alerta',
        "evidencias":    'ruim',
        "avaliacao":     '114 produtos, ⚠ 75 sem resultado, 11 aprovados (10%)',
        "total":         114,
        "aprovados":     11,
        "revisao":       28,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 75,
        "com_evidencia": 53,
        "notas": [],
    },
    {
        "rank":          7,
        "nome":          'Darlan Leal Santos',
        "marcas":        'Sephora',
        "planilha":      'alerta',
        "evidencias":    'ok',
        "avaliacao":     '111 produtos, 25 aprovados (23%), resultado 100% preenchido',
        "total":         111,
        "aprovados":     25,
        "revisao":       86,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 111,
        "notas": [],
    },
    {
        "rank":          8,
        "nome":          'Bruno Felipe Corte',
        "marcas":        'Boticario, Felps, Shiseido',
        "planilha":      'ok',
        "evidencias":    'ok',
        "avaliacao":     '100 produtos, 52 aprovados (52%), resultado 100% preenchido',
        "total":         100,
        "aprovados":     52,
        "revisao":       48,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 100,
        "notas": [],
    },
    {
        "rank":          9,
        "nome":          'Ana Paula Soares Oliveira',
        "marcas":        'Mari Maria Makeup',
        "planilha":      'alerta',
        "evidencias":    'ok',
        "avaliacao":     '93 produtos, 10 aprovados (11%), resultado 100% preenchido',
        "total":         93,
        "aprovados":     10,
        "revisao":       83,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 93,
        "notas": [],
    },
    {
        "rank":          10,
        "nome":          'Rayana Araujo Silva',
        "marcas":        'Lacoste, Lancôme, Leite de Colônia, Listerine, Lola Cosmetics',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '84 produtos, resultado 100% preenchido',
        "total":         84,
        "aprovados":     0,
        "revisao":       80,
        "ja_revisado":   4,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 80,
        "notas": ['4 EANs sem evidência confirmada'],
    },
    {
        "rank":          11,
        "nome":          'Geilson Soares',
        "marcas":        'Volt',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '74 produtos, 17 aprovados (23%), resultado 100% preenchido',
        "total":         74,
        "aprovados":     17,
        "revisao":       57,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 75,
        "notas": [],
    },
    {
        "rank":          12,
        "nome":          'Sherle Daniele',
        "marcas":        'Granado',
        "planilha":      'ok',
        "evidencias":    'alerta',
        "avaliacao":     '73 produtos, 46 aprovados (63%), resultado 100% preenchido',
        "total":         73,
        "aprovados":     46,
        "revisao":       27,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 72,
        "notas": [],
    },
    {
        "rank":          13,
        "nome":          'Marcia Tolentino',
        "marcas":        'Adcos',
        "planilha":      'ok',
        "evidencias":    'ok',
        "avaliacao":     '48 produtos, 2 aprovados (4%), resultado 100% preenchido',
        "total":         48,
        "aprovados":     2,
        "revisao":       46,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 48,
        "notas": [],
    },
    {
        "rank":          14,
        "nome":          'Eduardo Faria',
        "marcas":        'Embelleze',
        "planilha":      'ok',
        "evidencias":    'ok',
        "avaliacao":     '24 produtos, 17 aprovados (71%), resultado 100% preenchido',
        "total":         24,
        "aprovados":     17,
        "revisao":       7,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 24,
        "notas": [],
    },
    {
        "rank":          15,
        "nome":          'Lorrane Fernandes',
        "marcas":        'Eudora',
        "planilha":      'ok',
        "evidencias":    'ok',
        "avaliacao":     '8 produtos, 4 aprovados (50%), resultado 100% preenchido',
        "total":         8,
        "aprovados":     4,
        "revisao":       4,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 8,
        "notas": [],
    },
    {
        "rank":          16,
        "nome":          'Paulo Santini',
        "marcas":        '—',
        "planilha":      'ruim',
        "evidencias":    'ruim',
        "avaliacao":     'Sem produtos registrados ainda',
        "total":         0,
        "aprovados":     0,
        "revisao":       0,
        "ja_revisado":   0,
        "invalido":      0,
        "sem_resultado": 0,
        "com_evidencia": 0,
        "notas": [],
    }
]



















TOTAIS = {
    "total":            sum(w["total"] for w in WORKERS),
    "aprovados":        sum(w["aprovados"] for w in WORKERS),
    "revisao":          sum(w["revisao"] for w in WORKERS),
    "ja_revisado":      sum(w.get("ja_revisado", 0) for w in WORKERS),
    "sem_resultado":    sum(w["sem_resultado"] for w in WORKERS),
    "com_evidencia":    sum(w["com_evidencia"] for w in WORKERS),
}

# ── Helpers de badge ─────────────────────────────────────────────────────────

STATUS_CSS = {"ok": "badge-ok", "alerta": "badge-alerta", "ruim": "badge-ruim"}
STATUS_LABEL = {"ok": "ok", "alerta": "atenção", "ruim": "pendente"}

def badge(status: str) -> str:
    css = STATUS_CSS.get(status, "")
    label = STATUS_LABEL.get(status, status)
    return f'<span class="badge {css}">{label}</span>'

def badge_evidencias(w: dict) -> str:
    """Badge de evidências corrigido: só 'ok' se cobertura for 100%."""
    if w["total"] == 0:
        return badge("ruim")
    pct = round(w["com_evidencia"] / w["total"] * 100)
    if pct == 100:
        return badge("ok")
    elif pct >= 50:
        return badge("alerta")
    else:
        return badge("ruim")

def cob(w: dict) -> str:
    if w["total"] == 0:
        return '<span class="val-nd">—</span>'
    pct = round(w["com_evidencia"] / w["total"] * 100)
    css = "val-ok" if pct == 100 else ("val-alerta" if pct >= 50 else "val-ruim")
    return f'<span class="{css}">{pct}%</span>'

def val(n: int | str, *, ruim_se_zero=False, nd_se_zero=False) -> str:
    if nd_se_zero and n == 0:
        return '<span class="val-nd">—</span>'
    if ruim_se_zero and n == 0:
        return f'<span class="val-ruim">{n}</span>'
    return str(n)

# ── Linhas da tabela ─────────────────────────────────────────────────────────
NCOLS = 11  # número total de colunas da tabela

def tabela_rows() -> str:
    rows = ""
    for w in WORKERS:
        rows += f"""
  <tr>
    <td class="col-rank">#{w["rank"]}</td>
    <td class="col-nome">
      <strong>{w["nome"]}</strong>
      <span class="marcas-tag">{w["marcas"]}</span>
    </td>
    <td class="col-num">{val(w["total"], ruim_se_zero=True)}</td>
    <td class="col-num">{val(w["aprovados"], nd_se_zero=True)}</td>
    <td class="col-num">{val(w["revisao"], nd_se_zero=True)}{' <sup class="badge-invalido" title="+ 1 com resultado inválido">+1 inválido</sup>' if w.get("invalido") else ""}</td>
    <td class="col-num">{val(w.get("ja_revisado", 0), nd_se_zero=True)}</td>
    <td class="col-num">{val(w["sem_resultado"], ruim_se_zero=True, nd_se_zero=False) if w["sem_resultado"] > 0 else val(0, nd_se_zero=True)}</td>
    <td>{badge(w["planilha"])}</td>
    <td>{badge_evidencias(w)}</td>
    <td class="col-num">{val(w["com_evidencia"], ruim_se_zero=True)}</td>
    <td class="col-cob">{cob(w)}</td>
  </tr>"""
        if w["notas"]:
            items = "".join(f"<li>{n}</li>" for n in w["notas"])
            rows += f"""
  <tr class="row-notas">
    <td></td>
    <td colspan="{NCOLS - 1}">
      <ul class="notas-list">{items}</ul>
    </td>
  </tr>"""

    # Linha de totais
    tot_pct = round(TOTAIS["com_evidencia"] / TOTAIS["total"] * 100) if TOTAIS["total"] else 0
    rows += f"""
  <tr class="row-total">
    <td class="col-rank"></td>
    <td class="col-nome"><strong>Total</strong></td>
    <td class="col-num"><strong>{TOTAIS["total"]}</strong></td>
    <td class="col-num"><strong>{TOTAIS["aprovados"]}</strong></td>
    <td class="col-num"><strong>{TOTAIS["revisao"]}</strong></td>
    <td class="col-num"><strong>{TOTAIS["ja_revisado"]}</strong></td>
    <td class="col-num"><strong>{TOTAIS["sem_resultado"]}</strong></td>
    <td>—</td>
    <td>—</td>
    <td class="col-num"><strong>{TOTAIS["com_evidencia"]}</strong></td>
    <td class="col-cob"><strong>{tot_pct}%</strong></td>
  </tr>"""
    return rows


# ── HTML completo ─────────────────────────────────────────────────────────────

HTML = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acompanhamento Workers · BeClean · BASE/labs</title>
<meta name="robots" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400;1,500;1,600&display=swap">
<link rel="icon" href="https://propostas.baselabs.com.br/beclean/favicon-32.webp" sizes="32x32" type="image/webp">
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
  --ok: #166534;
  --ok-bg: #dcfce7;
  --alerta: #854d0e;
  --alerta-bg: #fef9c3;
  --ruim: #991b1b;
  --ruim-bg: #fee2e2;
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
}}
.shell-wide {{ width: min(1200px, 100% - 48px); margin-inline: auto; }}

/* ── Header ── */
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

/* ── Cover ── */
.cover {{
  padding: clamp(48px, 8vw, 80px) 0 clamp(28px, 5vw, 48px);
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
  font-size: clamp(28px, 4.5vw, 52px);
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.03em;
  margin: 0 0 20px;
  color: var(--fg);
}}
.cover h1 em {{ font-style: italic; font-weight: 400; color: var(--brand); }}
.cover .meta {{
  margin-top: 28px;
  display: flex; gap: 32px; flex-wrap: wrap;
  font-size: 13px;
}}
.cover .meta .k {{ color: var(--fg-3); letter-spacing: 0.04em; }}
.cover .meta .v {{ color: var(--fg); margin-top: 4px; }}

/* ── Conteúdo ── */
.content {{ padding: clamp(40px, 6vw, 72px) 0 clamp(56px, 8vw, 100px); }}
.section-title {{
  font-size: clamp(18px, 2.2vw, 24px);
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 24px;
  color: var(--fg);
  display: flex; align-items: center; gap: 10px;
}}
.section-title::before {{ content: "//"; color: var(--brand); font-weight: 400; }}
.section-desc {{ font-size: 14px; color: var(--fg-3); margin: -16px 0 24px; }}

/* ── Tabela principal ── */
.report-wrap {{ overflow-x: auto; margin-bottom: 56px; }}
.report-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
  border-radius: var(--r-3);
  overflow: hidden;
  border: 1px solid var(--line-soft);
  min-width: 920px;
}}
.report-table thead th {{
  text-align: left;
  padding: 12px 14px;
  background: var(--fg);
  color: var(--bg-1);
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-weight: 600;
  border-right: 1px solid rgba(255,255,255,0.08);
  white-space: nowrap;
}}
.report-table thead th:last-child {{ border-right: 0; }}
.report-table tbody tr {{ transition: background 0.1s; }}
.report-table tbody tr:nth-child(odd) {{ background: var(--bg-1); }}
.report-table tbody tr:nth-child(even) {{ background: var(--bg-2); }}
.report-table tbody tr:hover {{ background: #dde1ea; }}
.report-table td {{
  padding: 14px 14px;
  vertical-align: top;
  border-bottom: 1px solid var(--line-soft);
  border-right: 1px solid var(--line-soft);
  line-height: 1.5;
}}
.report-table td:last-child {{ border-right: 0; }}
.report-table tbody tr:last-child td {{ border-bottom: 0; }}

.col-rank {{ width: 36px; text-align: center; color: var(--fg-3); font-size: 12px; }}
.col-nome {{ min-width: 240px; }}
.col-nome strong {{ display: block; color: var(--fg); font-weight: 600; }}
.col-num {{ text-align: center; width: 80px; color: var(--fg); }}
.col-cob {{ text-align: center; width: 80px; font-weight: 600; }}
.marcas-tag {{ font-size: 11px; color: var(--fg-3); display: block; margin-top: 3px; }}

/* linha de totais */
.row-total td {{
  background: var(--bg-2) !important;
  border-top: 2px solid var(--line);
  color: var(--fg);
}}

/* badge de resultado inválido */
sup.badge-invalido {{
  font-size: 10px;
  font-weight: 600;
  background: var(--ruim-bg);
  color: var(--ruim);
  padding: 1px 5px;
  border-radius: 999px;
  vertical-align: middle;
  margin-left: 4px;
  letter-spacing: 0.02em;
  cursor: help;
}}

/* linha de dados seguida por notas: sem borda entre elas */
.report-table tr:has(+ .row-notas) td {{ border-bottom: none; }}

/* ── Linha de notas (colspan) ── */
.row-notas td {{
  padding: 0 14px 14px 14px;
  border-bottom: 1px solid var(--line-soft);
  border-top: none;
  background: inherit;
}}
.notas-list {{
  list-style: none;
  padding: 8px 0 0; margin: 0;
  display: flex; flex-wrap: wrap; gap: 6px 32px;
}}
.notas-list li {{
  font-size: 12px;
  color: var(--fg-3);
  padding-left: 14px;
  position: relative;
  line-height: 1.5;
  min-width: 260px;
  flex: 1 1 280px;
}}
.notas-list li::before {{
  content: "—";
  position: absolute; left: 0;
  color: var(--brand-coral);
}}
.notas-list code {{
  font-family: var(--mono);
  background: var(--bg-2);
  border: 1px solid var(--line-soft);
  border-radius: 3px;
  padding: 0 4px;
  font-size: 11px;
  color: var(--fg);
}}

/* ── Badges ── */
.badge {{
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: lowercase;
}}
.badge-ok     {{ background: var(--ok-bg);     color: var(--ok); }}
.badge-alerta {{ background: var(--alerta-bg); color: var(--alerta); }}
.badge-ruim   {{ background: var(--ruim-bg);   color: var(--ruim); }}

/* ── Valores coloridos ── */
.val-ok    {{ color: var(--ok);    font-weight: 600; }}
.val-alerta{{ color: var(--alerta);font-weight: 600; }}
.val-ruim  {{ color: var(--ruim);  font-weight: 600; }}
.val-nd    {{ color: var(--fg-3); }}

/* ── Critério box ── */
.criterio-box {{
  background: var(--bg-1);
  border: 1px solid var(--line-soft);
  border-left: 3px solid var(--brand);
  border-radius: 0 var(--r-3) var(--r-3) 0;
  padding: 16px 20px;
  font-size: 13.5px;
  color: var(--fg-2);
  margin-bottom: 48px;
}}
.criterio-box ol {{
  margin: 8px 0 0 20px;
  padding: 0;
  display: flex; flex-direction: column; gap: 6px;
}}
.criterio-box ol li {{ color: var(--fg-2); }}
.criterio-box code {{
  font-family: var(--mono);
  background: var(--bg-2);
  border: 1px solid var(--line-soft);
  border-radius: 3px;
  padding: 0 4px;
  font-size: 12px;
  color: var(--fg);
}}

/* ── Footer ── */
.site-footer {{
  border-top: 1px solid var(--line-soft);
  background: var(--bg-1);
  padding: 40px 0 48px;
  font-size: 13px;
  color: var(--fg-3);
}}
.site-footer .row {{
  display: flex; gap: 24px; flex-wrap: wrap;
  justify-content: space-between; align-items: center;
}}
.site-footer img {{ height: 22px; opacity: 0.85; }}
.site-footer a {{ color: var(--fg-2); text-decoration: none; }}
.site-footer a:hover {{ color: var(--brand); }}

@media (max-width: 640px) {{
  body {{ font-size: 14px; }}
  .shell-wide {{ width: min(640px, 100% - 32px); }}
  .cover h1 {{ font-size: 26px; }}
}}
</style>
</head>
<body>

<header class="site-header">
  <div class="shell-wide row">
    <a href="https://baselabs.com.br/" aria-label="BASE/labs">
      <img src="https://propostas.baselabs.com.br/beclean/logo-azul.webp" alt="BASE/labs">
    </a>
    <div class="crumbs">
      <a href="https://baselabs.com.br/">base/labs</a>
      &nbsp;/&nbsp; beclean
      &nbsp;/&nbsp; acompanhamento workers
    </div>
  </div>
</header>

<section class="cover">
  <div class="shell-wide">
    <div class="eyebrow"><span class="bar"></span>uso interno · base/labs</div>
    <h1>Acompanhamento<br><em>Workers BeClean</em></h1>
    <div class="meta">
      <div><div class="k">referência</div><div class="v">{DATA_REFERENCIA}</div></div>
      <div><div class="k">tarefa</div><div class="v">Validação de Scraping (Pré-Aprovados)</div></div>
      <div><div class="k">workers ativos</div><div class="v">{len(WORKERS)}</div></div>
      <div><div class="k">produtos validados</div><div class="v">{TOTAIS["total"]}</div></div>
      <div><div class="k">cobertura de evidências</div><div class="v">{round(TOTAIS["com_evidencia"]/TOTAIS["total"]*100) if TOTAIS["total"] else 0}%</div></div>
    </div>
  </div>
</section>

<main class="content">
  <div class="shell-wide">

    <h2 class="section-title">Tabela de resultados</h2>
    <p class="section-desc">Ordenado por número de produtos validados. Clique nas linhas para expandir as observações.</p>

    <div class="criterio-box">
      <strong>Critério de "evidência correta"</strong> — a pasta do produto no Drive precisa ter:
      <ol>
        <li>Pasta de EAN dentro da pasta da marca correspondente</li>
        <li>Subpasta <code>Screenshots</code> criada dentro da pasta do EAN</li>
        <li>Ao menos 1 arquivo de screenshot dentro de <code>Screenshots</code></li>
      </ol>
    </div>

    <div class="report-wrap">
      <table class="report-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Worker / Marcas / Observações</th>
            <th title="Produtos registrados na planilha">Validados</th>
            <th title="Resultado = Aprovado">Aprovados</th>
            <th title="Resultado = Enviado para revisão">Para revisão</th>
            <th title="Resultado = Já estava revisado">Já revisado</th>
            <th title="Resultado em branco na planilha">Sem resultado</th>
            <th>Planilha</th>
            <th>Evidências</th>
            <th title="Pastas de EAN com subpasta Screenshots não vazia">Com evidência</th>
            <th title="Com evidência correta / Validados">Cobertura</th>
          </tr>
        </thead>
        <tbody>
          {tabela_rows()}
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
    <div class="legal">
      <span>© 2026 BASE/labs · uso interno</span>
      <a href="mailto:hbarros@baselabs.com.br">hbarros@baselabs.com.br</a>
    </div>
  </div>
</footer>

</body>
</html>"""

out = OUT_DIR / "index.html"
out.write_text(HTML, encoding="utf-8")
print(f"OK · build/resultados/index.html ({out.stat().st_size:,} bytes)")
