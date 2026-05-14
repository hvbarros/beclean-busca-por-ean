"""
Hub BeClean — Filtrar Pré-Aprovados e analisar produtos item a item.

Uso:
  python3 hub_filtrar_pre_aprovados.py [--marca MARCA] [--fonte FONTE] [--limite N]

Exemplos:
  python3 hub_filtrar_pre_aprovados.py
  python3 hub_filtrar_pre_aprovados.py --marca "L'Oreal" --fonte Mintel --limite 5

Evidências salvas em: evidencias/<MARCA>_<FONTE>/execucao_YYYY-MM-DD-HH-MM/<EAN>/
"""

import argparse
import asyncio
import json
import re
import subprocess
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from playwright.async_api import async_playwright, BrowserContext, Page

# ── Credenciais e URL ────────────────────────────────────────────────────────
EMAIL = "hbarros@baselabs.com.br"
SENHA = "fuz2NJn3"
URL   = "https://hub.beclean.com.br"


def slugify(text: str) -> str:
    """Converte texto para slug: minúsculas, sem acentos, só letras/números/underscore."""
    normalizado = unicodedata.normalize("NFD", text)
    sem_acentos = "".join(c for c in normalizado if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", sem_acentos.lower()).strip("_")


# ══════════════════════════════════════════════════════════════════════════════
# Argumentos de linha de comando
# ══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hub_filtrar_pre_aprovados.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Filtra Pré-Aprovados no Hub BeClean, analisa produtos item a item\n"
            "e gera relatório HTML comparando os dados do Hub com o site oficial."
        ),
        epilog=(
            "exemplos:\n"
            "  python3 hub_filtrar_pre_aprovados.py\n"
            "  python3 hub_filtrar_pre_aprovados.py --marca Nivea --fonte Scrapping --limite 10\n"
            "  python3 hub_filtrar_pre_aprovados.py --marca \"L'Oreal\" --fonte Mintel --limite 5\n"
            "\n"
            "saídas (por execução):\n"
            "  evidencias/<MARCA>_<FONTE>/execucao_YYYY-MM-DD-HH-MM/\n"
            "  ├── 01_login.png … 06_fonte_selecionada.png   fluxo de filtros\n"
            "  ├── <EAN>/\n"
            "  │   ├── 01_modal.png          screenshot do modal\n"
            "  │   ├── 02_pos_link.png       screenshot pós-visita ao link\n"
            "  │   └── resultado.json        comparação do produto\n"
            "  ├── resultados.json           todos os produtos consolidados\n"
            "  └── relatorio.html            relatório comparativo completo\n"
            "\n"
            "scrapers disponíveis: " + ", ".join(sorted(SCRAPERS)) if SCRAPERS else
            "scrapers disponíveis: (nenhum ainda — serão listados após o import)"
        ),
    )
    parser.add_argument("--marca",  default="Nivea",     metavar="MARCA",
                        help='Filtro "Marca Original (Scraping)" (default: Nivea)')
    parser.add_argument("--fonte",  default="Scrapping", metavar="FONTE",
                        help='Filtro "Fonte (Origem)" (default: Scrapping)')
    parser.add_argument("--limite", default=2, type=int, metavar="N",
                        help="Máximo de produtos a processar (default: 2)")
    parser.add_argument("--headless", action="store_true",
                        help="Executa o browser sem interface gráfica")
    parser.add_argument("--publicar", action="store_true",
                        help="Publica o relatório no Cloudflare Pages após a execução")
    return parser.parse_args()


# ══════════════════════════════════════════════════════════════════════════════
# Estrutura de dados
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DadosProduto:
    nome:             str = ""
    ean:              str = ""
    categoria:        str = ""
    subcategoria:     str = ""
    link:             str = ""
    ingredientes:     str = ""   # Original(Scraping)
    ingredientes_db:  str = ""   # Vinculados(DB)
    imagem:           str = ""   # URL da imagem do produto
    fonte:            str = ""   # "hub" | domínio do site externo


@dataclass
class ResultadoAnalise:
    hub:        DadosProduto = field(default_factory=DadosProduto)
    link:       DadosProduto | None = None
    comparacao: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# Registro de scrapers por domínio
# ══════════════════════════════════════════════════════════════════════════════

SCRAPERS: dict[str, Callable] = {}


def _parse_vinculados(txt: str) -> str:
    """Extrai lista de ingredientes do bloco Vinculados(DB) (formato NOME\\nINCI)."""
    linhas = txt.splitlines()
    resultado = []
    for i, linha in enumerate(linhas):
        prox = linhas[i + 1].strip() if i + 1 < len(linhas) else ""
        if prox.upper() == "INCI" and linha.strip() not in {"Vinculados(DB)", "Padronizado", "INCI puro", "INCI"}:
            resultado.append(linha.strip())
    return ", ".join(resultado)


async def baixar_imagem(page: Page, url: str, dest: Path) -> bool:
    """Baixa uma URL de imagem usando a sessão do Playwright e salva em dest."""
    if not url:
        return False
    try:
        resp = await page.request.get(url)
        if resp.ok:
            ext = Path(urlparse(url).path).suffix or ".jpg"
            dest_final = dest.with_suffix(ext)
            dest_final.write_bytes(await resp.body())
            print(f"  📷  {dest_final}")
            return True
    except Exception as e:
        print(f"  ⚠️  Falha ao baixar imagem {url[:60]}: {e}")
    return False


def registrar_scraper(dominio: str):
    """Decorator: associa uma função de scraping a um domínio."""
    def decorator(fn: Callable) -> Callable:
        SCRAPERS[dominio] = fn
        return fn
    return decorator


@registrar_scraper("nivea.com.br")
async def _scrape_nivea(page: Page) -> DadosProduto:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)

    # Aceita cookies se o banner estiver presente
    for sel in [
        "button:has-text('Aceitar')",
        "button:has-text('Aceitar todos')",
        "button:has-text('Accept')",
        "button:has-text('Aceito')",
        "[id*=accept]",
        "[class*=accept]",
    ]:
        btn = page.locator(sel).first
        if await btn.count() and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(800)
            break

    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1500)

    # Nome
    nome = (await page.locator("h1").first.inner_text()).strip()

    # Ingredientes — bloco [class*=ingredient] contendo um <p>
    ing_p = page.locator("[class*=ingredient] p").first
    ingredientes = (await ing_p.inner_text()).strip() if await ing_p.count() else ""

    # Breadcrumb — deduplica e extrai categoria/subcategoria
    crumbs_el = page.locator("[class*=breadcrumb] a, [class*=breadcrumb] span")
    textos: list[str] = []
    for i in range(await crumbs_el.count()):
        t = (await crumbs_el.nth(i).inner_text()).strip()
        if t and t not in textos:
            textos.append(t)

    ignorar = {"Produtos NIVEA", "NIVEA", "Topo da página", nome, nome.upper(), nome.lower()}
    navegacao = [t for t in textos if t not in ignorar]
    categoria    = navegacao[0]  if len(navegacao) > 0 else ""
    subcategoria = navegacao[-1] if len(navegacao) > 1 else ""

    # Imagem principal do produto
    imagem = ""
    for sel in ["[class*=product] img", "[class*=ProductImage] img", "picture img", ".product img"]:
        el = page.locator(sel).first
        if await el.count():
            imagem = (await el.get_attribute("src") or "").strip()
            if imagem:
                break

    return DadosProduto(
        nome=nome,
        categoria=categoria,
        subcategoria=subcategoria,
        ingredientes=ingredientes,
        imagem=imagem,
        fonte="nivea.com.br",
    )


# ══════════════════════════════════════════════════════════════════════════════
# Evidências
# ══════════════════════════════════════════════════════════════════════════════

def _slug(text: str) -> str:
    return re.sub(r"[^\w\-]", "_", text)


def evidencias_dir(marca: str, fonte: str) -> Path:
    ts   = datetime.now().strftime("%Y-%m-%d-%H-%M")
    path = Path("evidencias") / f"{_slug(marca)}_{_slug(fonte)}" / f"execucao_{ts}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def evidencias_produto_dir(ev_dir: Path, ean: str) -> Path:
    path = ev_dir / ean
    path.mkdir(parents=True, exist_ok=True)
    return path


async def screenshot(page: Page, dest_dir: Path, nome: str, full_page: bool = True) -> None:
    dest = dest_dir / f"{nome}.png"
    await page.screenshot(path=str(dest), full_page=full_page)
    print(f"  📸  {dest}")


async def screenshot_modal(page: Page, dest_dir: Path, nome: str) -> None:
    """Screenshot do modal do Hub expandindo o scroll interno para capturar tudo."""
    await page.evaluate("""() => {
        const modal  = document.querySelector('.fixed.inset-0.z-50 .relative');
        const scroll = document.querySelector('.fixed.inset-0.z-50 .overflow-y-auto');
        if (modal)  { modal.style.maxHeight  = 'none'; modal.style.overflow  = 'visible'; }
        if (scroll) { scroll.style.overflow  = 'visible'; scroll.style.flex = 'none'; }
    }""")
    await screenshot(page, dest_dir, nome, full_page=True)
    await page.evaluate("""() => {
        const modal  = document.querySelector('.fixed.inset-0.z-50 .relative');
        const scroll = document.querySelector('.fixed.inset-0.z-50 .overflow-y-auto');
        if (modal)  { modal.style.maxHeight  = ''; modal.style.overflow  = ''; }
        if (scroll) { scroll.style.overflow  = ''; scroll.style.flex = ''; }
    }""")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de extração
# ══════════════════════════════════════════════════════════════════════════════

async def extrair_dados_modal(page: Page) -> DadosProduto:
    modal = ".fixed.inset-0.z-50"

    nome = (await page.locator(f"{modal} h2").first.inner_text()).strip()

    ean = ""
    for s in await page.locator(f"{modal} .flex.items-center.gap-3 span").all():
        t = await s.inner_text()
        if "EAN:" in t:
            ean = t.replace("EAN:", "").strip()
            break

    cat_text = ""
    try:
        cat_span = page.locator(modal).locator(
            "xpath=.//span[normalize-space()='Categoria']/following-sibling::span[1]"
        )
        if await cat_span.count():
            cat_text = (await cat_span.first.inner_text()).strip()
    except Exception:
        pass

    partes       = [p.strip() for p in cat_text.split("/")]
    categoria    = partes[0] if len(partes) > 0 else ""
    subcategoria = partes[1] if len(partes) > 1 else ""

    link = ""
    link_el = page.locator(f"{modal} a[href]").first
    if await link_el.count():
        link = (await link_el.get_attribute("href") or "").strip()

    ingredientes = ""
    for bloco in await page.locator(f"{modal} .bg-slate-50").all():
        txt = (await bloco.inner_text()).strip()
        if "Original" in txt:
            partes_ing   = txt.split("\n\n", 1)
            ingredientes = partes_ing[-1].strip() if partes_ing else txt
            break

    ingredientes_db = ""
    vinc = page.locator(modal).locator("xpath=.//h4[normalize-space()='Vinculados(DB)']/../..")
    if await vinc.count():
        ingredientes_db = _parse_vinculados((await vinc.first.inner_text()).strip())

    imagem = ""
    img_el = page.locator(f"{modal} img.max-w-full").first
    if await img_el.count():
        imagem = (await img_el.get_attribute("src") or "").strip()

    return DadosProduto(
        nome=nome, ean=ean, categoria=categoria, subcategoria=subcategoria,
        link=link, ingredientes=ingredientes, ingredientes_db=ingredientes_db,
        imagem=imagem, fonte="hub",
    )


async def extrair_dados_linha(row) -> tuple[str, str]:
    """Retorna (nome, EAN) a partir de um elemento <tr>."""
    nome = ""
    ean  = ""
    try:
        nome = (await row.locator(".text-sm.font-medium.text-gray-900").first.inner_text()).strip()
    except Exception:
        pass
    try:
        ean_raw = (await row.locator(".text-xs.text-gray-500.truncate.mt-1").first.inner_text()).strip()
        ean = ean_raw.replace("EAN:", "").strip()
    except Exception:
        pass
    return nome, ean


# ══════════════════════════════════════════════════════════════════════════════
# Scraping do link externo
# ══════════════════════════════════════════════════════════════════════════════

async def scrape_link(
    context: BrowserContext, link: str, prod_dir: Path
) -> DadosProduto | None:
    dominio = urlparse(link).netloc.removeprefix("www.")

    scraper_fn = None
    for chave in SCRAPERS:
        if dominio == chave or dominio.endswith("." + chave):
            scraper_fn = SCRAPERS[chave]
            break

    if scraper_fn is None:
        print(f"  ⚠️  Sem scraper cadastrado para '{dominio}' — pulando leitura do link.")
        return None

    nova_pagina = await context.new_page()
    try:
        print(f"  🌐  Abrindo link ({dominio})…")
        await nova_pagina.goto(link, wait_until="domcontentloaded")
        dados = await scraper_fn(nova_pagina)
        await nova_pagina.evaluate("window.scrollTo(0, 0)")
        await screenshot(nova_pagina, prod_dir, "02_site_link", full_page=True)
        return dados
    except Exception as e:
        print(f"  ❌  Erro ao scraping de {link}: {e}")
        return None
    finally:
        await nova_pagina.close()


# ══════════════════════════════════════════════════════════════════════════════
# Comparação
# ══════════════════════════════════════════════════════════════════════════════

def _norm(texto: str) -> str:
    return re.sub(r"\s+", " ", texto.lower().strip())


def comparar(hub: DadosProduto, link: DadosProduto) -> dict:
    resultado = {}

    # Campos simples
    for campo in ["nome", "categoria", "subcategoria"]:
        v_hub  = _norm(getattr(hub,  campo, ""))
        v_link = _norm(getattr(link, campo, ""))
        if not v_link:
            resultado[campo] = {"status": "sem_dados_link", "hub": getattr(hub, campo)}
        elif v_hub == v_link:
            resultado[campo] = {"status": "igual"}
        else:
            resultado[campo] = {"status": "diferente", "hub": getattr(hub, campo), "link": getattr(link, campo)}
        print(f"    {campo:15s} → {resultado[campo]['status']}")

    # Ingredientes: comparação 3 fontes (Scraping × DB × Site) + ordenação
    scraping = hub.ingredientes
    db       = hub.ingredientes_db
    site     = link.ingredientes if link else ""
    cmp_sd   = _cmp_ing(scraping, db)
    cmp_ss   = _cmp_ing(scraping, site)
    cmp_ds   = _cmp_ing(db, site)
    all_igual = cmp_sd["conteudo_igual"] and cmp_sd["ordem_igual"] \
                and cmp_ss["conteudo_igual"] and cmp_ss["ordem_igual"] \
                and cmp_ds["conteudo_igual"] and cmp_ds["ordem_igual"]
    status_ing = "igual" if all_igual else ("sem_dados_link" if not site else "diferente")
    resultado["ingredientes"] = {
        "status":           status_ing,
        "scraping":         scraping,
        "db":               db,
        "site":             site,
        "scraping_vs_db":   cmp_sd,
        "scraping_vs_site": cmp_ss,
        "db_vs_site":       cmp_ds,
    }
    print(f"    {'ingredientes':15s} → {status_ing}")
    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# Relatório HTML
# ══════════════════════════════════════════════════════════════════════════════

def _ing_lista(texto: str) -> list[str]:
    return [re.sub(r"\s+", " ", i.strip().lower()) for i in texto.split(",") if i.strip()]


def _cmp_ing(a: str, b: str) -> dict:
    """Compara duas listas de ingredientes: conteúdo e ordem."""
    la, lb = _ing_lista(a), _ing_lista(b)
    sa, sb = set(la), set(lb)
    comuns = sa & sb
    ordem_a = [i for i in la if i in comuns]
    ordem_b = [i for i in lb if i in comuns]
    return {
        "so_em_a":      sorted(sa - sb),
        "so_em_b":      sorted(sb - sa),
        "ordem_igual":  ordem_a == ordem_b,
        "conteudo_igual": sa == sb,
    }


def _ing_col(titulo: str, texto: str, outras: list[set]) -> str:
    """Renderiza coluna de ingredientes destacando os ausentes nas outras fontes."""
    if not texto:
        return f'<div><strong>{titulo}</strong><p class="sem-dados">—</p></div>'
    uniao_outras: set = set().union(*outras) if outras else set()
    items = [i.strip() for i in texto.split(",") if i.strip()]
    parts = []
    for item in items:
        css = "ing-diff" if item.lower() not in uniao_outras else ""
        parts.append(f'<span class="{css}">{item}</span>' if css else item)
    return f'<div><strong>{titulo}</strong><p>{", ".join(parts)}</p></div>'


def _ing_html(scraping: str, db: str, site: str) -> str:
    """Renderiza 3 colunas de ingredientes com destaque de diferenças e indicador de ordem."""
    ls, ld, lsite = set(_ing_lista(scraping)), set(_ing_lista(db)), set(_ing_lista(site))
    cmp_sd  = _cmp_ing(scraping, db)
    cmp_ss  = _cmp_ing(scraping, site)
    cmp_ds  = _cmp_ing(db, site)

    def _badge_ordem(cmp: dict, label_a: str, label_b: str) -> str:
        if not cmp["conteudo_igual"]:
            return ""
        cor  = "badge-ok" if cmp["ordem_igual"] else "badge-diff"
        txt  = f"ordem igual" if cmp["ordem_igual"] else f"ordem diferente"
        return f'<span class="badge {cor}" style="font-size:.65rem">{label_a}↔{label_b}: {txt}</span> '

    badges = (
        _badge_ordem(cmp_sd,  "Scrap", "DB")
        + _badge_ordem(cmp_ss, "Scrap", "Site")
        + _badge_ordem(cmp_ds, "DB",    "Site")
    )

    col_s  = _ing_col("Original (Scraping)", scraping, [ld, lsite])
    col_d  = _ing_col("Vinculados (DB)",     db,       [ls, lsite])
    col_st = _ing_col("Site",                site,     [ls, ld])

    return (
        f'<div class="ing-badges">{badges}</div>'
        '<div class="ing-grid">'
        f'{col_s}{col_d}{col_st}'
        "</div>"
    )


def gerar_relatorio_html(
    ev_dir: Path,
    resultados: list[dict],
    marca: str,
    fonte: str,
    ts: str,
    tempo_total: str = "",
) -> Path:
    STATUS_BADGE = {
        "igual":          '<span class="badge badge-ok">igual</span>',
        "diferente":      '<span class="badge badge-diff">diferente</span>',
        "sem_dados_link": '<span class="badge badge-nd">sem dados</span>',
    }
    CAMPOS_LABEL = {
        "nome":         "Nome",
        "categoria":    "Categoria",
        "subcategoria": "Subcategoria",
        "ingredientes": "Ingredientes",
    }

    # ── Sumário ──────────────────────────────────────────────────────────────
    contagem = {"igual": 0, "diferente": 0, "sem_dados_link": 0, "sem_link": 0}
    for r in resultados:
        if not r.get("link"):
            contagem["sem_link"] += 1
        else:
            statuses = [v["status"] for v in r.get("comparacao", {}).values()]
            if all(s == "igual" for s in statuses):
                contagem["igual"] += 1
            else:
                contagem["diferente"] += 1

    # ── Cards de produto ─────────────────────────────────────────────────────
    cards_html = ""
    for r in resultados:
        hub  = r["hub"]
        link = r.get("link") or {}
        comp = r.get("comparacao") or {}
        ean  = hub.get("ean", "")

        # Screenshots (caminhos relativos ao ev_dir)
        modal_img = f'{ean}/01_modal.png'   if ean else ""
        link_img  = f'{ean}/02_site_link.png' if ean else ""
        screenshots_links = ""
        if modal_img:
            screenshots_links += f'&ensp;<a href="{modal_img}" target="_blank">📷 Hub</a>'
        if link_img:
            screenshots_links += f'&ensp;<a href="{link_img}" target="_blank">📷 Site</a>'
        img_hub_link  = f'&ensp;<a href="{ean}/produto_hub.jpg"  target="_blank">🖼 Img Hub</a>'  if ean and (ev_dir / ean / "produto_hub.jpg").exists()  else ""
        img_site_link = f'&ensp;<a href="{ean}/produto_site.jpg" target="_blank">🖼 Img Site</a>' if ean and (ev_dir / ean / "produto_site.jpg").exists() else ""

        # Determina status geral do produto
        statuses = [v["status"] for v in comp.values()] if comp else []
        if not link:
            card_cls = "card-nolink"
        elif all(s == "igual" for s in statuses):
            card_cls = "card-ok"
        else:
            card_cls = "card-diff"

        # Linhas da tabela de comparação
        rows = ""
        for campo, label in CAMPOS_LABEL.items():
            c = comp.get(campo, {})
            status = c.get("status", "—")
            badge  = STATUS_BADGE.get(status, f'<span class="badge">{status}</span>')
            v_hub  = hub.get(campo, "")
            v_link = link.get(campo, "") if link else ""

            if campo == "ingredientes":
                valores = _ing_html(
                    c.get("scraping", v_hub),
                    c.get("db", ""),
                    c.get("site", v_link),
                )
            elif status == "diferente":
                valores = (
                    f'<div class="val-pair">'
                    f'<div><small>Hub</small><br>{v_hub}</div>'
                    f'<div><small>Site</small><br>{v_link}</div>'
                    f'</div>'
                )
            else:
                valores = v_hub or v_link or "—"

            rows += (
                f"<tr>"
                f"<td class='campo'>{label}</td>"
                f"<td>{valores}</td>"
                f"<td class='status-col'>{badge}</td>"
                f"</tr>"
            )

        fonte_link = link.get("fonte", "") if link else ""
        link_url   = hub.get("link", "")
        link_tag   = f'<a href="{link_url}" target="_blank">{link_url}</a>' if link_url else "—"
        tempo_s    = r.get("tempo_s", "")
        tempo_tag  = f'&ensp;·&ensp;<span style="font-size:.75rem;color:#94a3b8">⏱ {tempo_s}s</span>' if tempo_s else ""

        cards_html += f"""
<section class="card {card_cls}" onclick="this.classList.toggle('open')">
  <div class="card-header">
    <span class="card-toggle">▶</span>
    <div style="flex:1">
      <h2>{hub.get("nome", "—")}</h2>
      <span class="ean">EAN: {ean}</span>
      {"&ensp;·&ensp;" + f'<span class="fonte-tag">{fonte_link}</span>' if fonte_link else ""}
      {tempo_tag}
    </div>
  </div>
  <div class="card-body">
    <div class="link-row">🔗 {link_tag}{screenshots_links}{img_hub_link}{img_site_link}</div>
    <table>
      <thead><tr><th>Campo</th><th>Valores</th><th>Status</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</section>"""

    # ── Seção de fluxo (screenshots 01–06) ───────────────────────────────────
    _FLOW_LABELS = [
        ("01_login.png",           "01 — Login"),
        ("02_pos_login.png",       "02 — Pós-login"),
        ("03_pre_aprovados.png",   "03 — Pré-Aprovados"),
        ("04_filtros_abertos.png", "04 — Filtros"),
        ("05_marca_selecionada.png","05 — Marca"),
        ("06_fonte_selecionada.png","06 — Fonte"),
    ]
    flow_html = "".join(
        f'<a href="{fname}" target="_blank">📷 {label}</a>'
        for fname, label in _FLOW_LABELS
        if (ev_dir / fname).exists()
    )

    # ── HTML completo ────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório Hub BeClean — {marca}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, sans-serif; background: #f4f6f9; color: #1a1a2e; line-height: 1.5; }}
  a {{ color: #2563eb; word-break: break-all; }}

  /* ── Header ── */
  .header {{ background: #1a1a2e; color: #fff; padding: 2rem; }}
  .header h1 {{ font-size: 1.6rem; margin-bottom: .4rem; }}
  .header .meta {{ opacity: .7; font-size: .9rem; }}
  .summary {{ display: flex; gap: 1rem; margin-top: 1rem; flex-wrap: wrap; }}
  .pill {{ padding: .3rem .8rem; border-radius: 999px; font-size: .8rem; font-weight: 600; }}
  .pill-ok   {{ background: #bbf7d0; color: #166534; }}
  .pill-diff {{ background: #fecaca; color: #991b1b; }}
  .pill-nd   {{ background: #fef9c3; color: #854d0e; }}
  .pill-nl   {{ background: #e2e8f0; color: #475569; }}

  /* ── Cards ── */
  main {{ max-width: 1100px; margin: 2rem auto; padding: 0 1rem; display: flex; flex-direction: column; gap: 1.5rem; }}
  .card {{ background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.08); overflow: hidden; }}
  .card-ok   {{ border-left: 5px solid #22c55e; }}
  .card-diff {{ border-left: 5px solid #ef4444; }}
  .card-nolink {{ border-left: 5px solid #94a3b8; }}

  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; padding: 1.2rem 1.4rem .8rem; gap: 1rem; cursor: pointer; user-select: none; }}
  .card-header h2 {{ font-size: 1.05rem; font-weight: 700; }}
  .card-toggle {{ font-size: .85rem; color: #94a3b8; margin-right: .3rem; transition: transform .2s; flex-shrink: 0; margin-top: .15rem; }}
  .card.open .card-toggle {{ transform: rotate(90deg); }}
  .card-body {{ display: none; }}
  .card.open .card-body {{ display: block; }}
  .screenshots {{ display: flex; gap: .75rem; flex-shrink: 0; align-items: center; }}
  .ean {{ font-size: .8rem; color: #64748b; font-family: monospace; }}
  .fonte-tag {{ background: #dbeafe; color: #1d4ed8; padding: .15rem .5rem; border-radius: 4px; font-size: .75rem; }}
  .link-row {{ padding: .3rem 1.4rem .8rem; font-size: .82rem; color: #64748b; }}

  /* ── Tabela ── */
  table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
  thead th {{ background: #f8fafc; padding: .6rem 1rem; text-align: left; font-size: .75rem; text-transform: uppercase; color: #64748b; letter-spacing: .05em; border-top: 1px solid #e2e8f0; }}
  tbody td {{ padding: .7rem 1rem; vertical-align: top; border-top: 1px solid #f1f5f9; }}
  .campo {{ font-weight: 600; width: 110px; white-space: nowrap; color: #475569; }}
  .status-col {{ width: 110px; }}

  /* ── Badges ── */
  .badge {{ display: inline-block; padding: .2rem .65rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }}
  .badge-ok   {{ background: #dcfce7; color: #166534; }}
  .badge-diff {{ background: #fee2e2; color: #991b1b; }}
  .badge-nd   {{ background: #fef9c3; color: #854d0e; }}

  /* ── Comparação de valores ── */
  .val-pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; }}
  .val-pair small {{ font-size: .7rem; text-transform: uppercase; color: #94a3b8; font-weight: 700; }}

  /* ── Ingredientes ── */
  .ing-badges {{ padding: .5rem 1rem .25rem; display: flex; gap: .4rem; flex-wrap: wrap; }}
  .ing-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: .75rem; padding: 0 1rem .75rem; }}
  .ing-grid strong {{ font-size: .75rem; text-transform: uppercase; color: #94a3b8; letter-spacing: .05em; display: block; margin-bottom: .3rem; }}
  .ing-grid p {{ line-height: 1.7; }}
  .ing-diff {{ background: #fef3c7; border-radius: 3px; padding: 0 2px; }}
  .sem-dados {{ color: #94a3b8; font-style: italic; }}

  footer {{ text-align: center; padding: 2rem; font-size: .8rem; color: #94a3b8; }}

  /* ── Seção de fluxo ── */
  .flow-section {{ max-width: 1100px; margin: 2rem auto 0; padding: 0 1rem; }}
  .flow-section h2 {{ font-size: .85rem; text-transform: uppercase; letter-spacing: .08em; color: #64748b; font-weight: 700; margin-bottom: 1rem; }}
  .flow-grid {{ display: flex; flex-wrap: wrap; gap: .75rem; }}
</style>
</head>
<body>
<div class="header">
  <h1>Relatório Hub BeClean — {marca}</h1>
  <div class="meta">Fonte: {fonte}&ensp;·&ensp;Execução: {ts}&ensp;·&ensp;{len(resultados)} produto(s) analisado(s){"&ensp;·&ensp;⏱ " + tempo_total if tempo_total else ""}</div>
  <div class="summary">
    <span class="pill pill-ok">✓ {contagem["igual"]} totalmente iguais</span>
    <span class="pill pill-diff">✗ {contagem["diferente"]} com diferenças</span>
    <span class="pill pill-nd">{contagem["sem_link"]} sem link externo</span>
  </div>
</div>
<section class="flow-section">
  <h2>Fluxo de execução</h2>
  <div class="flow-grid">
    {flow_html}
  </div>
</section>
<main>
{cards_html}
</main>
<footer>Gerado em {ts} por hub_filtrar_pre_aprovados.py</footer>
</body>
</html>"""

    html_path = ev_dir / f"relatorio_{slugify(marca)}.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de navegação
# ══════════════════════════════════════════════════════════════════════════════

CF_BUCKET      = "propostas"
CF_BASE_URL    = "https://propostas.baselabs.com.br"
CF_PATH_PREFIX = "beclean/robo-validador-produtos/evidencias"

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".json": "application/json",
}


def publicar_cloudflare(ev_dir: Path, marca: str) -> str:
    """Sobe os arquivos da execução atual para o R2 e retorna a URL do relatório."""
    evidencias_root = ev_dir.parent.parent  # evidencias/
    arquivos = [f for f in ev_dir.rglob("*") if f.is_file()]
    print(f"  Enviando {len(arquivos)} arquivo(s) para R2 ({CF_BUCKET})…")

    erros = 0
    for arq in arquivos:
        rel      = arq.relative_to(evidencias_root)
        r2_key   = f"{CF_PATH_PREFIX}/{rel}"
        mime     = _MIME.get(arq.suffix.lower(), "application/octet-stream")
        result   = subprocess.run(
            ["wrangler", "r2", "object", "put", f"{CF_BUCKET}/{r2_key}",
             "--file", str(arq), "--content-type", mime, "--remote"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ⚠️  {r2_key}: {result.stderr.strip()[:120]}")
            erros += 1

    if erros:
        print(f"  ⚠️  {erros} arquivo(s) com falha no upload.")

    url = (f"{CF_BASE_URL}/{CF_PATH_PREFIX}"
           f"/{ev_dir.parent.name}/{ev_dir.name}/relatorio_{slugify(marca)}.html")
    print(f"  ✓  Publicado: {url}")
    return url


async def select_by_label(page: Page, label_text: str, value: str) -> None:
    select = page.locator(f"label:has-text('{label_text}') + select")
    await select.select_option(label=value)
    print(f"  ✓  {label_text!r} → {value!r}")


# ══════════════════════════════════════════════════════════════════════════════
# Fluxo principal
# ══════════════════════════════════════════════════════════════════════════════

async def main(args: argparse.Namespace) -> None:
    t_inicio = datetime.now()
    ts       = t_inicio.strftime("%Y-%m-%d %H:%M")
    ev_dir   = evidencias_dir(args.marca, args.fonte)
    print(f"Evidências em: {ev_dir}")
    resultados: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=args.headless,
            slow_mo=0 if args.headless else 300,
            args=[] if args.headless else ["--start-maximized"],
        )
        context = await browser.new_context(
            no_viewport=not args.headless,
            viewport={"width": 1600, "height": 900} if args.headless else None,
        )
        page    = await context.new_page()

        # ── 1. Login ─────────────────────────────────────────────────────────
        print("Fazendo login…")
        await page.goto(f"{URL}/login")
        await screenshot(page, ev_dir, "01_login")
        await page.fill("input[type=email]",    EMAIL)
        await page.fill("input[type=password]", SENHA)
        await page.click("button[type=submit]")
        await page.wait_for_url(lambda url: "/login" not in url, timeout=15000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)
        print("  ✓  logado")
        await screenshot(page, ev_dir, "02_pos_login")

        # ── 2. Pré-Aprovados ─────────────────────────────────────────────────
        print("Clicando em Pré-Aprovados…")
        await page.get_by_role("button", name="Pré-Aprovados").click()
        await page.wait_for_timeout(1500)
        await screenshot(page, ev_dir, "03_pre_aprovados")

        # ── 3. Filtros ───────────────────────────────────────────────────────
        print("Abrindo painel de Filtros…")
        await page.get_by_role("button", name="Filtros").click()
        await page.wait_for_timeout(1000)
        await screenshot(page, ev_dir, "04_filtros_abertos")

        print("Aplicando filtros…")
        await select_by_label(page, "MARCA ORIGINAL (SCRAPING)", args.marca)
        await page.wait_for_timeout(800)   # dropdown registra visualmente
        await screenshot(page, ev_dir, "05_marca_selecionada")
        await select_by_label(page, "FONTE (ORIGEM)",            args.fonte)
        await page.wait_for_timeout(800)
        await screenshot(page, ev_dir, "06_fonte_selecionada")
        # Aguarda a lista de produtos carregar antes de iterar
        await page.wait_for_selector("tbody tr", timeout=15000)

        # ── 4. Itera produtos (com paginação) ────────────────────────────────
        print(f"\nProcessando até {args.limite} produto(s)…\n")

        processados = 0
        pagina      = 1

        while processados < args.limite:
            await page.wait_for_selector("tbody tr", timeout=10000)
            n_linhas = await page.locator("tbody tr").count()
            if n_linhas == 0:
                print("Nenhuma linha encontrada. Encerrando.")
                break

            info_pag = await page.locator("span:has-text('Página')").first.inner_text()
            print(f"Página {pagina} — {info_pag.strip()} — {n_linhas} linha(s) visíveis\n")

            idx_pagina = 0
            while idx_pagina < n_linhas and processados < args.limite:
                # Usa .nth() com locator fresco para evitar referência stale após fechar modal
                linha = page.locator("tbody tr").nth(idx_pagina)
                nome_linha, ean_linha = await extrair_dados_linha(linha)
                print(f"─── [{processados+1}/{args.limite}] {nome_linha}  |  EAN: {ean_linha}")

                prod_dir = evidencias_produto_dir(ev_dir, ean_linha or f"produto_{processados+1:02d}")

                t0 = datetime.now()
                await page.locator("tbody tr").nth(idx_pagina).get_by_role("button", name="Analisar").click()
                await page.wait_for_timeout(2000)
                await screenshot_modal(page, prod_dir, "01_modal")

                dados_hub = await extrair_dados_modal(page)
                print(f"  nome:         {dados_hub.nome}")
                print(f"  categoria:    {dados_hub.categoria} / {dados_hub.subcategoria}")
                print(f"  link:         {dados_hub.link or '(sem link)'}")
                if dados_hub.imagem:
                    await baixar_imagem(page, dados_hub.imagem, prod_dir / "produto_hub")

                resultado = ResultadoAnalise(hub=dados_hub)

                if dados_hub.link:
                    dados_link = await scrape_link(context, dados_hub.link, prod_dir)
                    if dados_link:
                        if dados_link.imagem:
                            await baixar_imagem(page, dados_link.imagem, prod_dir / "produto_site")
                        resultado.link = dados_link
                        print(f"  → nome (link):         {dados_link.nome}")
                        print(f"  → categoria (link):    {dados_link.categoria} / {dados_link.subcategoria}")
                        print(f"  → ingredientes (link): {dados_link.ingredientes[:80]}…")
                        print("  Comparação:")
                        resultado.comparacao = comparar(dados_hub, dados_link)

                    await screenshot(page, prod_dir, "03_pos_modal")
                else:
                    print("  ⚠️  Produto sem link — nenhuma coleta externa.")

                (prod_dir / "resultado.json").write_text(
                    json.dumps(asdict(resultado), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

                r = asdict(resultado)
                r["tempo_s"] = round((datetime.now() - t0).total_seconds(), 1)
                print(f"  ⏱  {r['tempo_s']}s")
                resultados.append(r)

                await page.locator(".fixed.inset-0.z-50 button.rounded-full").click()
                await page.wait_for_selector(".fixed.inset-0.z-50", state="detached", timeout=5000)
                print()

                idx_pagina += 1
                processados += 1

            if processados >= args.limite:
                break

            # Tenta avançar para a próxima página
            btn_proxima = page.get_by_role("button", name="Próxima")
            if await btn_proxima.count() == 0 or not await btn_proxima.is_enabled():
                print(f"Última página atingida ({processados} produto(s) processado(s)).")
                break

            print(f"Indo para página {pagina + 1}…\n")
            await btn_proxima.click()
            await page.wait_for_timeout(800)
            pagina += 1

        # ── 5. Salva JSON consolidado ─────────────────────────────────────────
        json_path = ev_dir / "resultados.json"
        json_path.write_text(
            json.dumps(resultados, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Resultados salvos em: {json_path}")

        # ── 6. Gera relatório HTML ────────────────────────────────────────────
        tempo_total = str(round((datetime.now() - t_inicio).total_seconds())) + "s"
        html_path = gerar_relatorio_html(ev_dir, resultados, args.marca, args.fonte, ts, tempo_total)
        print(f"Relatório HTML:       {html_path}")
        print(f"Tempo total:          {tempo_total}")
        await browser.close()

    # ── 7. Publica no Cloudflare (fora do bloco do browser) ──────────────────
    if args.publicar:
        publicar_cloudflare(ev_dir, args.marca)


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
