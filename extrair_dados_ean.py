"""
FASE 1 — Extração de dados por EAN.
Fontes: Bing Search → loja → scraping | Mercado Livre fallback
Salva em mintel.db, tabela enriquecimento_ean.
Retomável: EANs já processados são pulados.
"""

import argparse
import asyncio
import csv
import mimetypes
import random
import sqlite3
import subprocess
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

CDP_URL = "http://localhost:9222"
CHROME_BIN = "google-chrome"

CSV_PATH = "falta_enriquecimento.csv"
DB_PATH = "mintel.db"
IMG_DIR = Path("imagens")
DELAY_MIN = 2.5
DELAY_MAX = 4.5


# ── DB ───────────────────────────────────────────────────────────────────────

def setup_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS enriquecimento_ean (
            ean          TEXT PRIMARY KEY,
            nome         TEXT,
            nome_fonte   TEXT,
            imagem_url   TEXT,
            imagem_local TEXT,
            descricao    TEXT,
            desc_fonte   TEXT,
            produto_url  TEXT,
            buscador     TEXT,
            status       TEXT,
            processado   TEXT
        )
    """)
    cols = {r[1] for r in con.execute("PRAGMA table_info(enriquecimento_ean)")}
    for col, tipo in [
        ("nome_fonte", "TEXT"), ("desc_fonte", "TEXT"),
        ("produto_url", "TEXT"), ("buscador", "TEXT"),
        ("imagem_local", "TEXT"), ("origem", "TEXT"),
    ]:
        if col not in cols:
            con.execute(f"ALTER TABLE enriquecimento_ean ADD COLUMN {col} {tipo}")
    con.execute("""
        CREATE TABLE IF NOT EXISTS busca_tentativa (
            ean  TEXT,
            loja TEXT,
            data TEXT,
            PRIMARY KEY (ean, loja)
        )
    """)
    con.commit()


def ja_tentou(con: sqlite3.Connection, ean: str, loja: str) -> bool:
    return con.execute(
        "SELECT 1 FROM busca_tentativa WHERE ean = ? AND loja = ?", (ean, loja)
    ).fetchone() is not None


def marcar_tentativa(con: sqlite3.Connection, ean: str, loja: str):
    from datetime import datetime
    con.execute(
        "INSERT OR REPLACE INTO busca_tentativa (ean, loja, data) VALUES (?, ?, ?)",
        (ean, loja, datetime.now().isoformat()),
    )
    con.commit()


def load_pending(con: sqlite3.Connection, reprocessar: bool = False) -> list[str]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        all_eans = [row["ean"].strip() for row in csv.DictReader(f) if row["ean"].strip()]

    if reprocessar:
        return all_eans

    ok_set = {r[0] for r in con.execute("SELECT ean FROM enriquecimento_ean WHERE status = 'ok'").fetchall()}
    return [e for e in all_eans if e not in ok_set]


def save_result(con: sqlite3.Connection, ean: str, **kwargs):
    kwargs["ean"] = ean
    kwargs["processado"] = datetime.now().isoformat()
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" * len(kwargs))
    con.execute(
        f"INSERT OR REPLACE INTO enriquecimento_ean ({cols}) VALUES ({placeholders})",
        list(kwargs.values()),
    )
    con.commit()


# ── Download de imagem ───────────────────────────────────────────────────────

# Hashes MD5 de imagens placeholder conhecidas (sem conteúdo real de produto)
PLACEHOLDER_HASHES = {
    "83b748414c62a9b2a981bc979d0cac68",  # farmaciasapp: imagem genérica sem foto
}

PLACEHOLDER = object()  # sentinel: download ok mas imagem é placeholder


def download_image(url: str, ean: str):
    import hashlib
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=15)
        r.raise_for_status()
        if hashlib.md5(r.content).hexdigest() in PLACEHOLDER_HASHES:
            print(f"    ↳ imagem placeholder ignorada")
            return PLACEHOLDER
        ct = r.headers.get("content-type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(ct) or Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
        ext = ext.replace(".jpe", ".jpg")
        dest = IMG_DIR / f"{ean}{ext}"
        dest.write_bytes(r.content)
        return str(dest)
    except Exception as e:
        print(f"    ↳ download falhou: {e}")
        return None


# ── Extração da página do produto ────────────────────────────────────────────

async def safe_goto_blank(page: Page):
    # Wait for any pending navigation (e.g. chrome-error) to settle before navigating away.
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
    except Exception:
        pass
    for _ in range(2):
        try:
            await page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
            return
        except Exception:
            await asyncio.sleep(0.3)


async def extract_product(page: Page) -> dict:
    return await page.evaluate("""() => {
        const g = (sel, attr) => document.querySelector(sel)?.getAttribute(attr) ?? null;

        // Nome: h1 é o mais limpo; og:title como fallback
        const h1 = document.querySelector('h1')?.innerText?.trim() ?? null;
        const og_title = g('meta[property="og:title"]', 'content');
        const nome = h1 || og_title;
        const nome_fonte = h1 ? 'h1' : (og_title ? 'og:title' : null);

        // Imagem: og:image → schema.org
        let imagem = g('meta[property="og:image"]', 'content');
        if (!imagem) {
            try {
                for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
                    const d = JSON.parse(s.textContent);
                    const obj = Array.isArray(d) ? d[0] : d;
                    if (obj?.image) {
                        const i = Array.isArray(obj.image) ? obj.image[0] : obj.image;
                        imagem = typeof i === 'string' ? i : (i?.url ?? null);
                        if (imagem) break;
                    }
                }
            } catch {}
        }

        // Descrição: schema.org → meta description → og:description
        let descricao = null, desc_fonte = null;
        try {
            for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
                const d = JSON.parse(s.textContent);
                const obj = Array.isArray(d) ? d[0] : d;
                if (obj?.description) {
                    descricao = obj.description;
                    desc_fonte = 'schema.org';
                    break;
                }
            }
        } catch {}
        if (!descricao) {
            const meta = g('meta[name="description"]', 'content');
            if (meta) { descricao = meta; desc_fonte = 'meta:description'; }
        }
        if (!descricao) {
            const og = g('meta[property="og:description"]', 'content');
            if (og) { descricao = og; desc_fonte = 'og:description'; }
        }

        return { nome, nome_fonte, imagem, descricao, desc_fonte };
    }""")


# ── Google ───────────────────────────────────────────────────────────────────

async def search_google(page: Page, ean: str) -> list[str]:
    await page.goto(
        f"https://www.google.com.br/search?q={ean}&hl=pt-BR",
        wait_until="domcontentloaded", timeout=20000,
    )
    await page.wait_for_timeout(random.randint(800, 1400))

    links = await page.evaluate("""() => {
        // Contêineres de shopping/anúncios do Google a ignorar
        const SHOPPING_SELETORES = [
            '#tvcap',           // carrossel de shopping no topo
            '#commercial-unit', // unidade comercial lateral
            '.commercial-unit-desktop-top',
            '.cu-container',
            '[data-attrid="organic"] a',
        ];
        const excludedEls = new Set(
            SHOPPING_SELETORES.flatMap(s => Array.from(document.querySelectorAll(s)))
        );
        const isExcluded = el => {
            let cur = el;
            while (cur) {
                if (excludedEls.has(cur)) return true;
                cur = cur.parentElement;
            }
            return false;
        };
        return Array.from(document.querySelectorAll('#search a[href], #rso a[href]'))
            .filter(a => !isExcluded(a))
            .map(a => a.href)
            .filter(h => h.startsWith('http') && !h.includes('google'));
    }""")
    return [l for l in links if not any(ig in l for ig in BLACKLIST)]


# ── Blacklist de sites a ignorar ─────────────────────────────────────────────

BLACKLIST = {
    "cosmos.bluesoft.com.br",
    "mercadolivre.com.br",
    "mercadolibre.com",
    "digit-eyes.com",
    "magazineluiza.com.br",
    "bimdistribuidora.com.br",
    "mercadomake.com.br",
    "dite.com.br",
    "drogariapolvilho.com.br",
    "parfum1.kyte.site",
}


# ── Lojas de farmácia e cosméticos ────────────────────────────────────────────

LOJAS_FALLBACK = [
    # ordenado por histórico de sucessos (OK)
    {
        "nome":             "farmaciasapp",       # 59 OK
        "url":              "https://www.farmaciasapp.com.br/busca?q={ean}",
        "seletor":          "a[href*='farmaciasapp.com.br/'], .product-card a, h2 a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "amazon",             # 59 OK
        "url":              "https://www.amazon.com.br/s?k={ean}",
        "seletor":          "[data-component-type='s-search-result'] h2 a, a.a-link-normal[href*='/dp/']",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}') || document.body.innerText.includes('Nenhum resultado para sua consulta')",
    },
    {
        "nome":             "consultaremedios",   # 21 OK
        "url":              "https://consultaremedios.com.br/busca?q={ean}",
        "seletor":          "a[href$='/p'], .product-card a, h2 a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "drogaraia",          # 16 OK
        "url":              "https://www.drogaraia.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "mercadolivre",       # 11 OK
        "url":              "https://lista.mercadolivre.com.br/{ean}",
        "seletor":          "a.poly-component__title, .ui-search-item__group--title a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "drogariavenancio",   # 11 OK
        "url":              "https://www.drogariavenancio.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, a[href$='/p'], .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "drogasil",           # 7 OK
        "url":              "https://www.drogasil.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "ultrafarma",         # 1 OK
        "url":              "https://www.ultrafarma.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, .product-name a, .product-card a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":            "panvel",     # 1 OK
        "url":             "https://www.panvel.com/panvel/buscarProduto.do?termoPesquisa={ean}",
        "seletor":         "lib-card-item-v2-vertical a",
        "wait_until":      "networkidle",
        "extra_wait":      5000,
        "seletor_timeout": 15000,
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "araujo",
        "url":              "https://www.araujo.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, a[href$='/p'], .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "drogariasaopaulo",
        "url":              "https://www.drogariasaopaulo.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, a[href$='/p'], .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "drogal",
        "url":              "https://www.drogal.com.br/busca?q={ean}",
        "seletor":          "a.product-item-link, a[href$='/p'], .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
    {
        "nome":             "belezanaweb",        # 0 OK
        "url":              "https://www.belezanaweb.com.br/busca/?q={ean}",
        "seletor":          "a.showcase-item, [data-testid='product-card'] a, .product-name a",
        "sem_resultado_js": "() => !document.body.innerText.includes('{ean}')",
    },
]


async def search_lojas(
    page: Page, ean: str,
    lojas: list | None = None,
    con: sqlite3.Connection | None = None,
    reprocessar: bool = False,
    sites_pausados: set | None = None,
) -> tuple[str | None, str | None]:
    for loja in (lojas or LOJAS_FALLBACK):
        nome_loja = loja["nome"]
        if any(b in loja["url"] for b in BLACKLIST):
            continue
        if sites_pausados and nome_loja in sites_pausados:
            print(f"    → {nome_loja}... pulado (timeout nesta execução)")
            continue
        if con and not reprocessar and ja_tentou(con, ean, nome_loja):
            print(f"    → {nome_loja}... pulado (já tentado)")
            continue
        print(f"    → {nome_loja}...", end=" ", flush=True)
        try:
            await page.goto(loja["url"].format(ean=ean), wait_until=loja.get("wait_until", "domcontentloaded"), timeout=20000)
            extra_wait = loja.get("extra_wait", random.randint(800, 1200))
            await page.wait_for_timeout(extra_wait)
            seletor_timeout = loja.get("seletor_timeout", 5000)
            try:
                el = await page.wait_for_selector(loja["seletor"], timeout=seletor_timeout, state="attached")
            except PWTimeout:
                el = None
            # Se a loja definiu verificação JS de "sem resultado", executa antes de aceitar
            # O campo suporta {ean} como placeholder para checagens dinâmicas (ex: EAN ausente da página)
            if el and loja.get("sem_resultado_js"):
                js = loja["sem_resultado_js"].format(ean=ean)
                sem_resultado = await page.evaluate(js)
                if sem_resultado:
                    print("sem resultado real para este EAN (verificação JS)")
                    if con:
                        marcar_tentativa(con, ean, nome_loja)
                    continue

            if not el:
                if loja.get("clicar"):
                    titulo = await page.title()
                    links = await page.evaluate("""() =>
                        Array.from(document.querySelectorAll('a[href]'))
                            .map(a => ({ texto: a.innerText.trim().slice(0, 50), href: a.href, cls: a.className }))
                            .filter(a => a.href.includes('panvel.com'))
                            .slice(0, 20)
                    """)
                    print(f"não achou\n      título: {titulo}")
                    for lk in links:
                        print(f"      a.{lk['cls'][:30]} | {lk['texto']} | {lk['href'][:80]}")
                else:
                    print("não achou")
                if con:
                    marcar_tentativa(con, ean, nome_loja)
                continue

            if loja.get("clicar"):
                texto = (await el.inner_text()).strip()[:60]
                href_dbg = await el.get_attribute("href") or "(sem href)"
                print(f"\n      elemento: '{texto}' | href: {href_dbg}")
                url_antes = page.url
                await el.scroll_into_view_if_needed()
                await el.click()
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                except PWTimeout:
                    pass
                await page.wait_for_timeout(500)
                url_depois = page.url.split("?")[0]
                if url_depois != url_antes.split("?")[0]:
                    print(f"      → {url_depois}")
                    print("    achou", end=" ")
                    return url_depois, loja["nome"]
                print("não navegou")

            href = await el.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = urllib.parse.urljoin(page.url, href)
                print("achou")
                return href.split("?")[0], loja["nome"]
            print("não achou")
            if con:
                marcar_tentativa(con, ean, nome_loja)
        except PWTimeout:
            print(f"timeout — pausando {nome_loja} nesta execução")
            if sites_pausados is not None:
                sites_pausados.add(nome_loja)
            await safe_goto_blank(page)
            continue
        except Exception as e:
            print(f"erro: {e}")
            await safe_goto_blank(page)
            continue
    return None, None


# ── Processamento de um EAN ───────────────────────────────────────────────────

NOMES_GENERICOS = (
    "o resumo do produto apresenta as principais informações",
    "os códigos de barras começam com",
    "não encontramos essa página",
    "page not found",
    "404",
)


async def extract_product_amazon(page: Page) -> dict:
    return await page.evaluate("""() => {
        // Nome: #productTitle é o elemento canônico da Amazon
        const tituloEl = document.querySelector('#productTitle');
        const nome = tituloEl?.innerText?.trim() ?? null;

        // Imagem: data-old-hires (alta res) → src do landingImage
        const img = document.querySelector('#landingImage');
        const imagem = img?.getAttribute('data-old-hires') || img?.getAttribute('src') || null;

        // Descrição: bullets de features → descrição do produto
        const bullets = Array.from(
            document.querySelectorAll('#feature-bullets .a-list-item')
        ).map(el => el.innerText.trim()).filter(t => t).join(' ');
        const descDiv = document.querySelector('#productDescription p, #productDescription');
        const descricao = bullets || descDiv?.innerText?.trim() || null;

        return {
            nome,
            nome_fonte: nome ? 'amazon:#productTitle' : null,
            imagem,
            descricao,
            desc_fonte: bullets ? 'amazon:feature-bullets' : (descricao ? 'amazon:productDescription' : null),
        };
    }""")


async def extract_product_farmaciasapp(page: Page) -> dict:
    return await page.evaluate("""() => {
        const g = (sel, attr) => document.querySelector(sel)?.getAttribute(attr) ?? null;

        const h1 = document.querySelector('h1')?.innerText?.trim() ?? null;
        const og_title = g('meta[property="og:title"]', 'content');
        const nome = h1 || og_title;

        // Imagem: img[alt^="product-"] é o elemento canônico da farmaciasapp
        const imgEl = document.querySelector('img[alt^="product-"]');
        const imagem = imgEl?.getAttribute('src') || null;

        let descricao = null, desc_fonte = null;
        const meta = g('meta[name="description"]', 'content');
        if (meta) { descricao = meta; desc_fonte = 'meta:description'; }

        return {
            nome,
            nome_fonte: h1 ? 'h1' : (og_title ? 'og:title' : null),
            imagem,
            descricao,
            desc_fonte,
        };
    }""")


async def extract_product_salvadosvirtual(page: Page) -> dict:
    return await page.evaluate("""() => {
        const g = (sel, attr) => document.querySelector(sel)?.getAttribute(attr) ?? null;

        const h1 = document.querySelector('h1')?.innerText?.trim() ?? null;
        const og_title = g('meta[property="og:title"]', 'content');
        const nome = h1 || og_title;

        // Imagem: src contendo /media/resize/ ou /produto/
        const imgEl = document.querySelector('img[src*="/media/resize/"], img[src*="/produto/"]');
        const imagem = imgEl?.getAttribute('src') || null;

        let descricao = null, desc_fonte = null;
        const meta = g('meta[name="description"]', 'content');
        if (meta) { descricao = meta; desc_fonte = 'meta:description'; }

        return {
            nome,
            nome_fonte: h1 ? 'h1' : (og_title ? 'og:title' : null),
            imagem,
            descricao,
            desc_fonte,
        };
    }""")


async def navigate_and_extract(page: Page, url: str) -> dict | None:
    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
    await page.wait_for_timeout(random.randint(700, 1300))
    if "amazon.com" in url:
        info = await extract_product_amazon(page)
    elif "farmaciasapp.com.br" in url:
        info = await extract_product_farmaciasapp(page)
    elif "salvadosvirtual.com.br" in url:
        info = await extract_product_salvadosvirtual(page)
    else:
        info = await extract_product(page)
    if info["nome"]:
        nome_lower = info["nome"].strip().lower()
        if any(g in nome_lower for g in NOMES_GENERICOS):
            return None
    return info


def mintel_info(ean: str, con: sqlite3.Connection) -> str:
    import re
    row = con.execute(
        "SELECT marca, produto, descricao_produto_pt FROM produtos WHERE codigo_barras = ?",
        (ean,),
    ).fetchone()
    if not row:
        return "(não encontrado no Mintel)"
    marca, produto, desc = row
    nome_en = " ".join(filter(None, [marca, produto]))
    nome_pt = None
    if desc:
        for frase in re.split(r"\.\s+", desc):
            m = re.match(r"^(.+?)\s+(?:já está disponível|foi relançado|está disponível)", frase)
            if m:
                nome_pt = m.group(1).strip()
                break
    partes = [nome_en]
    if nome_pt and nome_pt.lower() != nome_en.lower():
        partes.append(f"({nome_pt})")
    return "  ".join(partes)


def dominio(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().lstrip("www.")
    return host.split(".")[0]


def lojas_ordenadas(ean: str, con: sqlite3.Connection) -> list:
    row = con.execute(
        "SELECT marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    nome = " ".join(filter(None, row or [])).lower()
    if "panvel" in nome:
        panvel = next(l for l in LOJAS_FALLBACK if l["nome"] == "panvel")
        resto = [l for l in LOJAS_FALLBACK if l["nome"] != "panvel"]
        return [panvel] + resto
    return LOJAS_FALLBACK


def _tokens(texto: str) -> set[str]:
    """Normaliza texto e retorna conjunto de tokens relevantes."""
    import unicodedata, re
    STOP = {
        # português
        'de', 'da', 'do', 'das', 'dos', 'e', 'o', 'a', 'os', 'as', 'com',
        'para', 'em', 'um', 'uma', 'por', 'ao', 'aos', 'na', 'no', 'nos',
        'nas', 'se', 'que', 'ou', 'ja', 'esta', 'sao',
        # inglês
        'the', 'and', 'for', 'of', 'with', 'in', 'is', 'a', 'an', 'to',
        'by', 'at', 'it', 'its', 'be',
        # unidades
        'ml', 'g', 'kg', 'l', 'mg', 'gr',
    }
    nfkd = unicodedata.normalize('NFKD', texto)
    ascii_str = nfkd.encode('ASCII', 'ignore').decode('ASCII').lower()
    ascii_str = re.sub(r'[^a-z0-9\s]', ' ', ascii_str)
    return {t for t in ascii_str.split() if t not in STOP and len(t) > 1}


def similaridade_nome(nome_encontrado: str | None, ean: str, con: sqlite3.Connection) -> float:
    """
    Calcula sobreposição de tokens entre o nome encontrado na loja e o nome Mintel.
    Retorna coeficiente de sobreposição [0, 1]: interseção / mínimo dos dois conjuntos.
    Retorna 1.0 se não há dados Mintel (sem base para rejeitar).
    """
    if not nome_encontrado:
        return 1.0
    row = con.execute(
        "SELECT marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    if not row:
        return 1.0
    nome_mintel = " ".join(filter(None, row))
    t_encontrado = _tokens(nome_encontrado)
    t_mintel = _tokens(nome_mintel)
    if not t_encontrado or not t_mintel:
        return 1.0
    intersec = t_encontrado & t_mintel
    return len(intersec) / min(len(t_encontrado), len(t_mintel))


def _tentar_download(info: dict, ean: str, fonte: str, con: sqlite3.Connection) -> tuple:
    """Tenta baixar a imagem. Retorna (imagem_local, placeholder_detectado)."""
    if not info.get("imagem"):
        return None, False
    resultado = download_image(info["imagem"], ean)
    if resultado is PLACEHOLDER:
        print(f"    ↳ placeholder detectado em {fonte}, marcando como tentado")
        marcar_tentativa(con, ean, fonte)
        return None, True
    return resultado, False


async def process_ean(page: Page, ean: str, con: sqlite3.Connection, fonte: str | None = None, reprocessar: bool = False, sites_pausados: set | None = None):
    print(f"  {ean}  {mintel_info(ean, con)}")
    produto_url, buscador, info, origem, imagem_local = None, None, None, None, None

    # Google — tenta cada link retornado até encontrar um válido
    if not fonte or fonte == "google":
        try:
            google_links = await search_google(page, ean)
            if not google_links:
                print(f"    → Google... não achou")
            else:
                for url in google_links:
                    try:
                        result = await navigate_and_extract(page, url)
                        if result is None:
                            print(f"    → Google [{dominio(url)}]... sem dados úteis, tentando próximo")
                            continue
                        img, placeholder = _tentar_download(result, ean, dominio(url), con)
                        if placeholder:
                            print(f"    → Google [{dominio(url)}]... placeholder, tentando próximo")
                            continue
                        print(f"    → Google [{dominio(url)}]... achou")
                        produto_url, buscador, info, origem, imagem_local = url, dominio(url), result, "google", img
                        break
                    except PWTimeout:
                        print(f"    → Google [{dominio(url)}]... timeout, tentando próximo")
                        await safe_goto_blank(page)
                    except Exception as e:
                        print(f"    → Google [{dominio(url)}]... erro: {e}, tentando próximo")
                        await safe_goto_blank(page)
        except Exception as e:
            print(f"    → Google... erro: {e}")
            await safe_goto_blank(page)

    # Lojas — loop até encontrar ou esgotar todas as opções
    if not produto_url:
        if fonte and fonte != "google":
            lojas = [l for l in LOJAS_FALLBACK if l["nome"] == fonte]
        else:
            lojas = lojas_ordenadas(ean, con)
        try:
            while True:
                url, loja = await search_lojas(page, ean, lojas, con=con, reprocessar=reprocessar, sites_pausados=sites_pausados)
                if not url:
                    break
                try:
                    result = await navigate_and_extract(page, url)
                    if result is None:
                        print(f"    → nome genérico, marcando {loja} como tentado")
                        marcar_tentativa(con, ean, loja)
                        continue
                    img, placeholder = _tentar_download(result, ean, loja, con)
                    if placeholder:
                        continue
                    produto_url, buscador, info, origem, imagem_local = url, loja, result, "loja_direta", img
                    break
                except PWTimeout:
                    print(f"    → timeout em {loja}, tentando próxima loja")
                    marcar_tentativa(con, ean, loja)
                    if sites_pausados is not None:
                        sites_pausados.add(loja)
                    await safe_goto_blank(page)
                except Exception as e:
                    print(f"    → erro em {loja}: {e}, tentando próxima loja")
                    marcar_tentativa(con, ean, loja)
                    await safe_goto_blank(page)
        except Exception as e:
            print(f"    → Lojas erro: {e}")
            await safe_goto_blank(page)

    if not produto_url:
        save_result(con, ean, status="sem_resultado")
        print(f"    → sem resultado")
        return

    # Verifica similaridade com o nome Mintel antes de aceitar
    LIMIAR_SIMILARIDADE = 0.20
    sim = similaridade_nome(info["nome"], ean, con)
    if sim < LIMIAR_SIMILARIDADE:
        print(f"    ↳ nome incompatível com Mintel (similaridade {sim:.0%}) — descartado como falso positivo")
        print(f"        encontrado : {(info['nome'] or '')[:70]}")
        row = con.execute("SELECT marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)).fetchone()
        print(f"        mintel     : {' '.join(filter(None, row or []))[:70]}")
        if buscador:
            marcar_tentativa(con, ean, buscador)
        return

    if imagem_local:
        status = "ok"
    elif info["imagem"]:
        status = "download_falhou"
    else:
        status = "sem_imagem"

    save_result(
        con, ean,
        nome=info["nome"], nome_fonte=info["nome_fonte"],
        imagem_url=info["imagem"], imagem_local=imagem_local,
        descricao=info["descricao"], desc_fonte=info["desc_fonte"],
        produto_url=produto_url, buscador=buscador,
        origem=origem, status=status,
    )

    flag = "✓" if imagem_local else "✗"
    sim_str = f"{sim:.0%}" if sim < 1.0 else ""
    print(f"  {ean} [{flag}] [{buscador}] [{info['nome_fonte']}] {sim_str} {(info['nome'] or '')[:55]}")


# ── Main ──────────────────────────────────────────────────────────────────────

def reordenar_lojas(con: sqlite3.Connection):
    global LOJAS_FALLBACK
    counts = {r[0]: r[1] for r in con.execute(
        "SELECT buscador, COUNT(*) FROM enriquecimento_ean WHERE status = 'ok' GROUP BY buscador"
    ).fetchall()}
    LOJAS_FALLBACK = sorted(LOJAS_FALLBACK, key=lambda l: counts.get(l["nome"], 0), reverse=True)
    print("Ordem de busca direta (atualizada):")
    for loja in LOJAS_FALLBACK:
        ok = counts.get(loja["nome"], 0)
        bl = " [blacklist]" if any(b in loja["url"] for b in BLACKLIST) else ""
        print(f"  {loja['nome']:<25} {ok:>5} OK{bl}")
    print()


def print_resumo_buscadores(con: sqlite3.Connection):
    rows = con.execute("""
        SELECT
            origem,
            buscador,
            SUM(CASE WHEN status = 'ok'              THEN 1 ELSE 0 END) as ok,
            SUM(CASE WHEN status = 'sem_imagem'      THEN 1 ELSE 0 END) as sem_imagem,
            SUM(CASE WHEN status = 'download_falhou' THEN 1 ELSE 0 END) as download_falhou
        FROM enriquecimento_ean
        WHERE status IN ('ok', 'sem_imagem', 'download_falhou')
        GROUP BY origem, buscador
        HAVING ok + sem_imagem + download_falhou > 0
        ORDER BY ok DESC, sem_imagem DESC, download_falhou DESC
    """).fetchall()
    total_ok  = sum(r[2] for r in rows)
    total_si  = sum(r[3] for r in rows)
    total_dl  = sum(r[4] for r in rows)
    print(f"\n{'Origem':<14} {'Buscador':<30} {'OK':>6} {'Sem img':>8} {'Dl falhou':>10}")
    print("-" * 72)
    for origem, buscador, ok, sem_img, dl in rows:
        print(f"{(origem or 'NULL'):<14} {(buscador or 'NULL'):<30} {ok:>6} {sem_img:>8} {dl:>10}")
    print("-" * 72)
    print(f"{'TOTAL':<14} {'':<30} {total_ok:>6} {total_si:>8} {total_dl:>10}\n")


PROFILE_DIR = Path(".browser_profile")
CHROME_LOG  = Path("chrome.log")


def iniciar_chrome() -> subprocess.Popen:
    """Lança o Chrome com porta de debug. Log zerado a cada chamada."""
    log_file = CHROME_LOG.open("w")
    return subprocess.Popen(
        [
            CHROME_BIN,
            "--remote-debugging-port=9222",
            f"--user-data-dir={PROFILE_DIR.resolve()}",
            "--no-first-run",
            "--no-default-browser-check",
            "--lang=pt-BR",
        ],
        stdout=log_file,
        stderr=log_file,
    )


def encerrar_chrome(proc: subprocess.Popen):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def cmd_setup():
    """Abre o Chrome real para login e aguarda confirmação do usuário."""
    PROFILE_DIR.mkdir(exist_ok=True)
    print("Abrindo Chrome para configuração de sessão...\n")
    proc = iniciar_chrome()

    try:
        print("[ 1/2 ] Google")
        print("        Faça login na sua conta Google no Chrome que abriu.")
        input("        Quando terminar, pressione ENTER aqui... ")

        print("\n[ 2/2 ] Mercado Livre")
        print("        Acesse mercadolivre.com.br e faça login.")
        input("        Quando terminar, pressione ENTER aqui... ")
    finally:
        proc.terminate()

    print("\nSessão salva em .browser_profile/ — pode rodar a extração agora.")


async def cmd_extrair(args):
    IMG_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    setup_db(con)
    print_resumo_buscadores(con)
    reordenar_lojas(con)
    pending = load_pending(con, reprocessar=args.reprocessar)
    sites_pausados: set = set()

    if not pending:
        print("Nenhum EAN pendente.")
        con.close()
        return

    if args.limite:
        pending = pending[:args.limite]
        print(f"Limitado a {args.limite} EANs.")

    print(f"Iniciando Chrome... (log em {CHROME_LOG})")
    chrome = iniciar_chrome()
    await asyncio.sleep(2)

    start = time.time()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            print(f"Conectado. Iniciando extração de {len(pending)} EANs...\n")

            for i, ean in enumerate(pending, 1):
                await process_ean(page, ean, con, fonte=args.fonte, reprocessar=args.reprocessar, sites_pausados=sites_pausados)
                await page.wait_for_timeout(int(random.uniform(DELAY_MIN, DELAY_MAX) * 1000))

                if i % 50 == 0:
                    elapsed = time.time() - start
                    rate = i / elapsed
                    remaining = (len(pending) - i) / rate if rate > 0 else 0
                    print(f"\n  >>> {i}/{len(pending)} | {rate:.2f}/s | ~{remaining/60:.0f} min restantes\n")

            await page.close()
    finally:
        encerrar_chrome(chrome)
        print("Chrome encerrado.")

    LEGENDA = {
        "ok":              "✓ Imagem baixada com sucesso",
        "sem_resultado":   "✗ EAN não encontrado",
        "sem_imagem":      "✗ Página encontrada, mas sem imagem",
        "download_falhou": "✗ Imagem encontrada, mas falhou ao baixar",
        "timeout":         "✗ Página demorou demais para carregar",
        "erro_pagina":     "✗ Erro ao acessar a página do produto",
    }

    elapsed = time.time() - start
    print(f"\nConcluído em {elapsed/60:.1f} min.\n")
    print(f"{'Status':<20} {'Descrição':<45} {'Qtd':>6}")
    print("-" * 75)
    for status, count in con.execute(
        "SELECT status, COUNT(*) FROM enriquecimento_ean GROUP BY status ORDER BY 2 DESC"
    ):
        descricao = LEGENDA.get(status, status)
        print(f"  {status:<18} {descricao:<45} {count:>6}")
    print("-" * 75)
    total = con.execute("SELECT COUNT(*) FROM enriquecimento_ean").fetchone()[0]
    ok = con.execute("SELECT COUNT(*) FROM enriquecimento_ean WHERE status='ok'").fetchone()[0]
    print(f"  {'Total processado':<18} {'':<45} {total:>6}")
    print(f"  {'Taxa de sucesso':<18} {'':<45} {ok/total*100:>5.1f}%")
    con.close()


def _coletar_eans_buscador(con: sqlite3.Connection, buscador: str) -> list[str]:
    """Retorna EANs de loja_direta/ok para o buscador e remove-os do banco."""
    eans = [r[0] for r in con.execute(
        "SELECT ean FROM enriquecimento_ean WHERE buscador = ? AND origem = 'loja_direta' AND status = 'ok'",
        (buscador,),
    ).fetchall()]
    if eans:
        ph = ",".join("?" * len(eans))
        con.execute(f"DELETE FROM enriquecimento_ean WHERE ean IN ({ph})", eans)
        con.execute(f"DELETE FROM busca_tentativa WHERE loja = ? AND ean IN ({ph})", [buscador] + eans)
        con.commit()
    return eans


async def _rebuscar_lista(page, con: sqlite3.Connection, eans: list[str], buscador: str, sites_pausados: set, start: float, total: int, offset: int):
    """Processa uma lista de EANs num buscador específico usando a página já aberta."""
    for i, ean in enumerate(eans, 1):
        await process_ean(page, ean, con, fonte=buscador, sites_pausados=sites_pausados)
        await page.wait_for_timeout(int(random.uniform(DELAY_MIN, DELAY_MAX) * 1000))
        pos = offset + i
        if pos % 50 == 0:
            elapsed = time.time() - start
            rate = pos / elapsed
            remaining = (total - pos) / rate if rate > 0 else 0
            print(f"\n  >>> {pos}/{total} | {rate:.2f}/s | ~{remaining/60:.0f} min restantes\n")


async def cmd_rebuscar_buscador(args):
    """Refaz a busca completa para EANs encontrados por um buscador específico."""
    IMG_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    setup_db(con)

    if args.rebuscar_buscador not in [l["nome"] for l in LOJAS_FALLBACK]:
        print(f"Buscador '{args.rebuscar_buscador}' não encontrado em LOJAS_FALLBACK.")
        con.close()
        return

    eans = _coletar_eans_buscador(con, args.rebuscar_buscador)
    if not eans:
        print(f"Nenhum EAN com buscador='{args.rebuscar_buscador}' e origem='loja_direta' e status='ok'.")
        con.close()
        return

    print(f"{len(eans)} EANs para re-buscar via '{args.rebuscar_buscador}'")

    sites_pausados: set = set()
    print(f"Iniciando Chrome... (log em {CHROME_LOG})")
    chrome = iniciar_chrome()
    await asyncio.sleep(2)

    start = time.time()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            print(f"Conectado. Re-buscando {len(eans)} EANs em '{args.rebuscar_buscador}'...\n")
            await _rebuscar_lista(page, con, eans, args.rebuscar_buscador, sites_pausados, start, len(eans), 0)
            await page.close()
    finally:
        encerrar_chrome(chrome)
        print("Chrome encerrado.")

    elapsed = time.time() - start
    ok = con.execute(
        "SELECT COUNT(*) FROM enriquecimento_ean WHERE buscador = ? AND status = 'ok'",
        (args.rebuscar_buscador,),
    ).fetchone()[0]
    print(f"\nConcluído em {elapsed/60:.1f} min. {ok}/{len(eans)} confirmados.")
    con.close()


async def cmd_rebuscar_todos(args):
    """Refaz a busca completa para todos os buscadores loja_direta numa única sessão do Chrome."""
    IMG_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    setup_db(con)

    nomes_lojas = {l["nome"] for l in LOJAS_FALLBACK}
    buscadores = [r[0] for r in con.execute(
        "SELECT DISTINCT buscador FROM enriquecimento_ean WHERE origem = 'loja_direta' AND status = 'ok' AND buscador IS NOT NULL"
    ).fetchall() if r[0] in nomes_lojas]

    if not buscadores:
        print("Nenhum buscador loja_direta com status='ok' encontrado no banco.")
        con.close()
        return

    # Coleta e remove todos os EANs de uma vez (antes de abrir o Chrome)
    agenda: list[tuple[str, list[str]]] = []
    for buscador in buscadores:
        eans = _coletar_eans_buscador(con, buscador)
        if eans:
            agenda.append((buscador, eans))
            print(f"  {buscador:<30} {len(eans):>4} EANs")

    total = sum(len(e) for _, e in agenda)
    if not total:
        print("Nada a reprocessar.")
        con.close()
        return

    print(f"\nTotal: {total} EANs em {len(agenda)} buscadores\n")

    sites_pausados: set = set()
    print(f"Iniciando Chrome... (log em {CHROME_LOG})")
    chrome = iniciar_chrome()
    await asyncio.sleep(2)

    start = time.time()
    offset = 0
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            print(f"Conectado.\n")

            for buscador, eans in agenda:
                print(f"\n{'='*60}")
                print(f"  {buscador} — {len(eans)} EANs")
                print(f"{'='*60}\n")
                await _rebuscar_lista(page, con, eans, buscador, sites_pausados, start, total, offset)
                offset += len(eans)

            await page.close()
    finally:
        encerrar_chrome(chrome)
        print("\nChrome encerrado.")

    elapsed = time.time() - start
    print(f"\nConcluído em {elapsed/60:.1f} min.")
    print_resumo_buscadores(con)
    con.close()


async def cmd_rescrape_buscador(args):
    """Re-faz apenas o scraping (sem nova busca) para EANs de um buscador específico."""
    IMG_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    setup_db(con)
    print_resumo_buscadores(con)
    reordenar_lojas(con)

    rows = con.execute(
        "SELECT ean, produto_url, buscador, origem FROM enriquecimento_ean WHERE buscador = ? AND status != 'ok'",
        (args.rescrape_buscador,),
    ).fetchall()

    if not rows:
        print(f"Nenhum EAN pendente para buscador '{args.rescrape_buscador}'.")
        con.close()
        return

    print(f"Iniciando Chrome... (log em {CHROME_LOG})")
    chrome = iniciar_chrome()
    await asyncio.sleep(2)

    start = time.time()

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            print(f"Conectado. Re-scraping {len(rows)} EANs do buscador '{args.rescrape_buscador}'...\n")

            for i, (ean, url, buscador, origem) in enumerate(rows, 1):
                print(f"  {ean}  {url[:70]}", end=" ")
                try:
                    result = await navigate_and_extract(page, url)
                    if result is None or not result.get("imagem"):
                        print("✗ sem imagem")
                        continue

                    imagem_local = download_image(result["imagem"], ean)
                    status = "ok" if imagem_local else ("download_falhou" if result["imagem"] else "sem_imagem")
                    save_result(
                        con, ean,
                        nome=result["nome"], nome_fonte=result["nome_fonte"],
                        imagem_url=result["imagem"], imagem_local=imagem_local,
                        descricao=result["descricao"], desc_fonte=result["desc_fonte"],
                        produto_url=url, buscador=buscador,
                        origem=origem, status=status,
                    )
                    flag = "✓" if imagem_local else "✗"
                    print(f"{flag} {status}")
                except PWTimeout:
                    print("✗ timeout")
                    await safe_goto_blank(page)
                except Exception as e:
                    print(f"✗ erro: {e}")
                    await safe_goto_blank(page)

                await page.wait_for_timeout(int(random.uniform(DELAY_MIN, DELAY_MAX) * 1000))

            await page.close()
    finally:
        encerrar_chrome(chrome)
        print("Chrome encerrado.")

    elapsed = time.time() - start
    ok = con.execute(
        "SELECT COUNT(*) FROM enriquecimento_ean WHERE buscador = ? AND status = 'ok'",
        (args.rescrape_buscador,),
    ).fetchone()[0]
    print(f"\nConcluído em {elapsed/60:.1f} min. {ok}/{len(rows)} com imagem.")
    con.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true",
                        help="Abre o Chrome para login no Google e Mercado Livre")
    parser.add_argument("-n", "--limite", type=int, default=None,
                        help="Quantidade máxima de EANs a processar")
    fontes = ["google"] + [l["nome"] for l in LOJAS_FALLBACK]
    parser.add_argument("--fonte", choices=fontes, default=None, metavar="FONTE",
                        help=f"Pesquisa apenas nesta fonte: {', '.join(fontes)}")
    parser.add_argument("--reprocessar", action="store_true",
                        help="Reprocessa EANs já encontrados (status ok)")
    parser.add_argument("--rescrape-buscador", metavar="BUSCADOR",
                        help="Re-faz o scraping (sem nova busca) para EANs de um buscador específico com status != ok")
    parser.add_argument("--rebuscar-buscador", metavar="BUSCADOR",
                        help="Refaz a busca completa apenas para EANs encontrados por um buscador específico (origem=loja_direta, status=ok)")
    parser.add_argument("--rebuscar-todos", action="store_true",
                        help="Refaz a busca completa para todos os buscadores loja_direta numa única sessão do Chrome")
    args = parser.parse_args()

    if args.setup:
        await cmd_setup()
    elif args.rebuscar_todos:
        await cmd_rebuscar_todos(args)
    elif args.rebuscar_buscador:
        await cmd_rebuscar_buscador(args)
    elif args.rescrape_buscador:
        await cmd_rescrape_buscador(args)
    else:
        await cmd_extrair(args)


if __name__ == "__main__":
    asyncio.run(main())
