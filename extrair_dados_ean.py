"""
FASE 1 — Extração de dados por EAN.
Fontes: Bing Search → loja → scraping | Mercado Livre fallback
Salva em mintel.db, tabela enriquecimento_ean.
Retomável: EANs já processados são pulados.
"""

import argparse
import asyncio
import csv
import difflib
import mimetypes
import random
import re
import sqlite3
import subprocess
import time
import unicodedata
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
LIMIAR_SIMILARIDADE = 0.20
MAX_LINKS_GOOGLE = 10


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
        ("motivo_suspeito", "TEXT"),
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

    ok_set = {r[0] for r in con.execute(
        "SELECT ean FROM enriquecimento_ean WHERE status IN ('ok', 'suspeito')"
    ).fetchall()}

    # Data da última tentativa por EAN (para os não-ok e não-suspeito)
    ultima = {r[0]: r[1] for r in con.execute(
        "SELECT ean, processado FROM enriquecimento_ean WHERE status NOT IN ('ok', 'suspeito')"
    ).fetchall()}

    pendentes = [e for e in all_eans if e not in ok_set]
    # Nunca tentados (sem data) primeiro; depois os mais antigos
    pendentes.sort(key=lambda e: ultima.get(e) or "")
    return pendentes


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
            print(f"        imagem placeholder ignorada")
            return PLACEHOLDER
        ct = r.headers.get("content-type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(ct) or Path(urllib.parse.urlparse(url).path).suffix or ".jpg"
        ext = ext.replace(".jpe", ".jpg")
        dest = IMG_DIR / f"{ean}{ext}"
        dest.write_bytes(r.content)
        return str(dest)
    except Exception as e:
        print(f"        download falhou: {e}")
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

async def search_google(page: Page, query: str) -> list[str]:
    await page.goto(
        f"https://www.google.com.br/search?q={urllib.parse.quote_plus(query)}&hl=pt-BR",
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
    links = [l for l in links if not any(ig in l for ig in BLACKLIST)]
    return links[:MAX_LINKS_GOOGLE]


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
    "dentalspeed.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "shopee.com",
    # catálogos e documentos — nunca são páginas de produto
    "scribd.com",
    "issuu.com",
    "fliphtml5.com",
    # registros regulatórios e legislação
    "inmetro.gov.br",
    "legislacao.fazenda.sp.gov.br",
    # sites de EAN sem produto real
    "ean13brasil.net",
    "hal.science",
    # marketplaces estrangeiros / bloqueados
    "fruugo.",
    "ubuy.",
}


# ── Lojas de farmácia e cosméticos ────────────────────────────────────────────

LOJAS_FALLBACK_ATIVO = True

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
        "nome":           "ultrafarma",
        "url":            "https://www.ultrafarma.com.br/busca?q={nome}",
        "seletor":        "a.product-item-link, .product-name a, .product-card a",
        "busca_por_nome": True,   # não aceita EAN; busca pelo nome do produto
        "verificar_ean":  True,   # entra em cada resultado e confirma o EAN no texto
        "max_candidatos": 5,
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


def _dominios_lojas() -> list[str]:
    """Domínios das lojas diretas para filtro site: no Google (exclui blacklistadas)."""
    dominios = []
    for loja in LOJAS_FALLBACK:
        if any(b in loja["url"] for b in BLACKLIST):
            continue
        host = urllib.parse.urlparse(loja["url"]).netloc.lower()
        host = re.sub(r'^www\d*\.', '', host)
        if host and host not in dominios:
            dominios.append(host)
    return dominios


async def _search_por_nome(page: Page, loja: dict, ean: str, con: sqlite3.Connection | None) -> str | None:
    """
    Busca um produto por nome (para lojas que não aceitam EAN).
    Navega até cada resultado e verifica se o EAN aparece no texto da página.
    Retorna a URL do primeiro resultado onde o EAN é confirmado, ou None.
    """
    if not con:
        return None

    row = con.execute(
        "SELECT nome_produto_pt, marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    if not row:
        return None
    nome_pt, marca, produto = row
    nome_busca = _limpar_nome(nome_pt or f"{marca} {produto}").strip()
    if not nome_busca:
        return None

    url_busca = loja["url"].format(nome=urllib.parse.quote_plus(nome_busca))
    await page.goto(url_busca, wait_until=loja.get("wait_until", "domcontentloaded"), timeout=20000)
    await page.wait_for_timeout(loja.get("extra_wait", random.randint(800, 1200)))

    seletor_timeout = loja.get("seletor_timeout", 5000)
    try:
        await page.wait_for_selector(loja["seletor"], timeout=seletor_timeout, state="attached")
    except PWTimeout:
        return None

    els = await page.query_selector_all(loja["seletor"])
    max_cand = loja.get("max_candidatos", 5)

    candidatos: list[str] = []
    for el in els[:max_cand * 2]:  # pega mais elementos para ter margem após deduplicação
        href = await el.get_attribute("href")
        if href:
            if not href.startswith("http"):
                href = urllib.parse.urljoin(page.url, href)
            href = href.split("?")[0]
            if href not in candidatos:
                candidatos.append(href)
        if len(candidatos) >= max_cand:
            break

    for href in candidatos:
        await page.goto(href, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1000)
        ean_presente = await page.evaluate(f"() => document.body.innerText.includes('{ean}')")
        if ean_presente:
            return href

    await safe_goto_blank(page)
    return None


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
            print(f"      {nome_loja}: pulado (timeout nesta execução)")
            continue
        if con and not reprocessar and ja_tentou(con, ean, nome_loja):
            print(f"      {nome_loja}: pulado (já tentado)")
            continue
        print(f"      {nome_loja}:", end=" ", flush=True)
        try:
            # Lojas que não aceitam EAN: busca pelo nome do produto
            if loja.get("busca_por_nome"):
                resultado = await _search_por_nome(page, loja, ean, con)
                if resultado:
                    print("link encontrado")
                    return resultado, nome_loja
                print("EAN não encontrado em nenhum candidato")
                if con:
                    marcar_tentativa(con, ean, nome_loja)
                continue

            await page.goto(loja["url"].format(ean=ean), wait_until=loja.get("wait_until", "domcontentloaded"), timeout=20000)
            extra_wait = loja.get("extra_wait", random.randint(800, 1200))
            await page.wait_for_timeout(extra_wait)
            seletor_timeout = loja.get("seletor_timeout", 5000)
            try:
                el = await page.wait_for_selector(loja["seletor"], timeout=seletor_timeout, state="attached")
            except PWTimeout:
                el = None
            if el and loja.get("sem_resultado_js"):
                js = loja["sem_resultado_js"].format(ean=ean)
                sem_resultado = await page.evaluate(js)
                if sem_resultado:
                    print("sem resultado (verificação JS)")
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
                    print(f"não achou  (título: {titulo})")
                    for lk in links:
                        print(f"        a.{lk['cls'][:30]} | {lk['texto']} | {lk['href'][:80]}")
                else:
                    print("não achou")
                if con:
                    marcar_tentativa(con, ean, nome_loja)
                continue

            if loja.get("clicar"):
                texto = (await el.inner_text()).strip()[:60]
                href_dbg = await el.get_attribute("href") or "(sem href)"
                print(f"elemento: '{texto}' | href: {href_dbg}")
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
                    print(f"        → {url_depois}")
                    return url_depois, loja["nome"]
                print("não navegou")

            href = await el.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = urllib.parse.urljoin(page.url, href)
                print("link encontrado")
                return href.split("?")[0], loja["nome"]
            print("não achou")
            if con:
                marcar_tentativa(con, ean, nome_loja)
        except PWTimeout:
            print(f"timeout")
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
    "verifique para continuar",   # captcha da Shopee
)


async def extract_product_amazon(page: Page) -> dict:
    return await page.evaluate("""() => {
        // Nome: #productTitle → span#productTitle → h1 → og:title (sem prefixo Amazon)
        let nome = null, nome_fonte = null;
        const tituloEl = document.querySelector('#productTitle, span#productTitle');
        if (tituloEl?.innerText?.trim()) {
            nome = tituloEl.innerText.trim();
            nome_fonte = 'amazon:#productTitle';
        }
        if (!nome) {
            const h1 = document.querySelector('h1')?.innerText?.trim();
            if (h1) { nome = h1; nome_fonte = 'h1'; }
        }
        if (!nome) {
            const og = document.querySelector('meta[property="og:title"]')?.getAttribute('content');
            if (og) {
                nome = og.replace(/^Amazon\\.com\\.br\\s*[:\\-]\\s*/i, '')
                         .replace(/\\s*[:\\-]\\s*Amazon\\.com\\.br$/i, '').trim();
                nome_fonte = 'og:title';
            }
        }

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
            nome_fonte,
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


async def _dispensar_modal_idioma_shopee(page: Page):
    """Fecha o modal de seleção de idioma da Shopee escolhendo Português."""
    try:
        btn = page.locator("text=Português").first
        await btn.wait_for(state="visible", timeout=4000)
        await btn.click()
        await page.wait_for_timeout(1000)
    except PWTimeout:
        pass


async def _simular_mouse_shopee(page: Page):
    """
    Move o mouse de forma orgânica pela página para contornar detecção de bot da Shopee.
    Faz 4-6 movimentos suaves para posições aleatórias + um scroll leve.
    """
    try:
        vp = page.viewport_size or {"width": 1280, "height": 720}
        w, h = vp["width"], vp["height"]
        # Começa próximo ao centro para parecer natural
        x, y = w // 2 + random.randint(-100, 100), h // 2 + random.randint(-80, 80)
        await page.mouse.move(x, y, steps=random.randint(8, 15))
        for _ in range(random.randint(3, 5)):
            await page.wait_for_timeout(random.randint(180, 420))
            x += random.randint(-200, 200)
            y += random.randint(-150, 150)
            x = max(50, min(x, w - 50))
            y = max(50, min(y, h - 50))
            await page.mouse.move(x, y, steps=random.randint(6, 14))
        # Scroll suave para simular leitura
        await page.wait_for_timeout(random.randint(300, 600))
        await page.mouse.wheel(0, random.randint(120, 350))
        await page.wait_for_timeout(random.randint(400, 800))
    except Exception:
        pass


async def extract_product_ultrafarma(page: Page) -> dict:
    return await page.evaluate("""() => {
        const g = (sel, attr) => document.querySelector(sel)?.getAttribute(attr) ?? null;

        // og:title tem o nome real; h1 costuma ser o logo do site ("Ultrafarma")
        let nome = null, nome_fonte = null;
        const og_title = g('meta[property="og:title"]', 'content');
        if (og_title) {
            nome = og_title.replace(/\\s*[\\-|–]\\s*Ultrafarma.*$/i, '').trim();
            nome_fonte = 'og:title';
        }
        if (!nome || /^ultrafarma$/i.test(nome)) {
            const h1 = document.querySelector('h1')?.innerText?.trim() ?? null;
            if (h1 && !/^ultrafarma$/i.test(h1)) {
                nome = h1;
                nome_fonte = 'h1';
            }
        }

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

        let descricao = null, desc_fonte = null;
        const meta = g('meta[name="description"]', 'content');
        if (meta) { descricao = meta; desc_fonte = 'meta:description'; }

        return { nome, nome_fonte, imagem, descricao, desc_fonte };
    }""")


async def extract_product_martinsatacado(page: Page) -> dict:
    return await page.evaluate("""() => {
        const g = (sel, attr) => document.querySelector(sel)?.getAttribute(attr) ?? null;

        // Nome: h1 preferido; og:title com sufixo "| Martins Atacado" removido como fallback
        const h1 = document.querySelector('h1')?.innerText?.trim() ?? null;
        let nome = h1, nome_fonte = h1 ? 'h1' : null;
        if (!nome) {
            const og = g('meta[property="og:title"]', 'content');
            if (og) {
                nome = og.replace(/\\s*\\|\\s*Martins Atacado\\s*$/i, '').trim();
                nome_fonte = 'og:title';
            }
        }

        // Imagem: img[src*='catalogoimg'] é a imagem do produto no CDN do Martins
        const imgEl = document.querySelector("img[src*='catalogoimg'][alt]");
        const imagem = imgEl?.getAttribute('src') ?? null;

        const meta = g('meta[name="description"]', 'content');
        const descricao = meta ?? g('meta[property="og:description"]', 'content');
        const desc_fonte = meta ? 'meta:description' : (descricao ? 'og:description' : null);

        return { nome, nome_fonte, imagem, descricao, desc_fonte };
    }""")


async def navigate_and_extract(page: Page, url: str) -> dict | None:
    is_martins = "martinsatacado.com.br" in url
    wait_until = "networkidle" if is_martins else "domcontentloaded"
    await page.goto(url, wait_until=wait_until, timeout=25000)
    await page.wait_for_timeout(random.randint(700, 1300))
    if "shopee.com" in url:
        await _simular_mouse_shopee(page)
        await _dispensar_modal_idioma_shopee(page)
    if "amazon.com" in url:
        parsed = urllib.parse.urlparse(url)
        if parsed.path.rstrip("/") in ("/s", "") or "search-alias" in url:
            return None
        info = await extract_product_amazon(page)
    elif "farmaciasapp.com.br" in url:
        info = await extract_product_farmaciasapp(page)
    elif "salvadosvirtual.com.br" in url:
        info = await extract_product_salvadosvirtual(page)
    elif "ultrafarma.com.br" in url:
        info = await extract_product_ultrafarma(page)
    elif is_martins:
        info = await extract_product_martinsatacado(page)
    else:
        info = await extract_product(page)
    if info["nome"]:
        nome_lower = info["nome"].strip().lower()
        if any(g in nome_lower for g in NOMES_GENERICOS):
            return None
    return info


def mintel_info(ean: str, con: sqlite3.Connection) -> str:
    row = con.execute(
        "SELECT marca, produto, nome_produto_pt FROM produtos WHERE codigo_barras = ?",
        (ean,),
    ).fetchone()
    if not row:
        return "(não encontrado no Mintel)"
    marca, produto, nome_pt = row
    nome_en = " ".join(filter(None, [marca, produto]))
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


_RUIDO_MARCA = re.compile(
    r'\b('
    # natureza / ambiente
    r'flores\s+e\s+aromas|flores|aromas|natureza|naturais|naturals|natural'
    r'|verde|eco|terra|campo|jardim|garden|ervas|erva|planta|plantas|agua|aguas'
    # público-alvo
    r'|baby|bebe|kids|men|man|women|woman|masculino|feminino|infantil|unissex'
    # categoria de produto
    r'|hair|skin|skincare|body|face|makeup|cabelos|capilar|pele|higiene|banho'
    # sufixos corporativos / descritores de setor
    r'|cosmeticos|cosmetics|perfumaria|beleza|beauty'
    # qualidade / canal
    r'|professional|profissional|professionnel|salon|spa|expert|expertise'
    r'|premium|ultra|super|plus|max|pro'
    # atributos de produto
    r'|care|collection|colecao|linha|serie|series|line|edition|limited'
    r'|intense|fresh|soft|clean|vegan|sensitive|clinical|derma|dermo'
    # funções capilares / cosméticas
    r'|hidratacao|nutricao|nutri|antiqueda|reconstrucao|forca|reparacao|repair'
    r'|brilho|protect|glow|control|liso|lisa'
    # adjetivos genéricos
    r'|puro|pura|puros|puras|belo|bela|bom|boa|real|royal|gold|golden'
    # geográficos / outros
    r'|brasil|brasileira|brasileiro|vida|viva|vivaz|soul|love'
    r')\b',
    re.IGNORECASE,
)


# Marcas cujo nome é inteiramente composto de termos genéricos mas são marcas reais conhecidas.
# Quando a limpeza resultaria em string vazia, retorna o nome protegido em vez de vazio.
_MARCAS_PROTEGIDAS = [
    "Baby Care",
    "Baby Clean",
    "Bela Kids",
    "Beleza Brasileira",
    "Beleza Natural",
    "Brasil Care",
    "Care Natural Beauty",
    "Care",
    "Clean Baby",
    "Max Gold",
    "Natural",
    "Protect Baby",
    "Protect Hair",
    "Real Love",
    "Salon Line",
    "Soft Clean Beauty",
    "Soft Clean",
    "Vivaz Cosmetics",
    "Vivaz",
]


def _limpar_marca(marca: str) -> str:
    """Remove termos genéricos do nome da marca, mantendo apenas o identificador distintivo."""
    limpo = _RUIDO_MARCA.sub(' ', marca)
    limpo = re.sub(r'\s{2,}', ' ', limpo).strip()
    if not limpo:
        marca_lower = marca.lower()
        for protegida in _MARCAS_PROTEGIDAS:
            if marca_lower.startswith(protegida.lower()):
                return protegida
    return limpo


_NOME_DOCUMENTO = re.compile(
    r'\b(tabela|cat[aá]logo|cat[aá]log|relat[oó]rio|lista\s+de|planilha'
    r'|price\s+list|pricelist|listagem|portf[oó]lio)\b',
    re.IGNORECASE,
)


_RUIDO_ECOMMERCE = re.compile(
    r'('
    # frases de logística/disponibilidade
    r'\benvio\s+imediato\b|\bpronta\s+entrega\b|\benvio\s+r[aá]pido\b|\bfrete\s+gr[aá]tis\b'
    r'|\bproduto\s+no\s+brasil\b|\bno\s+brasil\b|\blacrado\b'
    r'|\blan[cç]amento\b|\brelan[cç]amento\b'
    r'|\b100%\s+original\b|\bproduto\s+original\b|\boriginal\s+importado\b|\bimportado\b'
    r'|\bembalagem\s+original\b|\bembalagem\s+fechada\b'
    r'|\bgarantia\s+\w+|\bcom\s+garantia\b'
    r'|\bnacional\b|\bnota\s+fiscal\b'
    r'|\s*-\s*[Aa]tacado\b.*'                  # "- Atacado Vila Nova - ..."
    # quantidade/preço de atacado
    r'|\bx\s+\d+\b'                            # "x 1", "x 12"
    r'|\bLeve\s+\d+\w*,\s*Pague\s+\d+\w*'     # "Leve 300ml, Pague 250ml"
    r'|\bEmbalagem\s+\d+[Xx]\d+.*'             # "Embalagem 6X100 GR - Preço Unitário..."
    r'|\bPreço\s+Unitário\s+R\$[\d,.]+\b'
    r'|\s*-\s*\d+\s+[Uu]nd\.?\s*$'            # "- 24 Und" no final
    # conversões de unidade
    r'|\(\d+[\.,]\d+\s*FlOz\)'                 # "(10.14FlOz)"
    r'|\(\d+[\.,]\d+\s*oz\)'                   # "(3.38oz)"
    # separadores de descrição
    r'|\s*\|.*$'                               # "| Controla Volume e Reduz Frizz"
    r'|\bApp\s+[A-Z]\w+'                       # "App Pharma"
    r')',
    re.IGNORECASE,
)


def _limpar_nome(texto: str) -> str:
    """Remove fragmentos de marketing de vendedor do nome do produto."""
    limpo = _RUIDO_ECOMMERCE.sub(' ', texto)
    limpo = re.sub(r'\s{2,}', ' ', limpo)
    limpo = re.sub(r'[\s\-]+$', '', limpo)  # traço/espaço solto no final
    return limpo.strip()


# Palavras genéricas de categoria de produto — sozinhas não identificam um produto específico
_TOKENS_GENERICOS = {
    'shampoo', 'xampu', 'condicionador', 'sabonete', 'soap', 'creme', 'cream',
    'gel', 'loção', 'locao', 'lotion', 'serum', 'mascara', 'spray', 'oleo',
    'oil', 'balm', 'gloss', 'batom', 'esmalte', 'base', 'powder', 'po',
    'hidratante', 'moisturizer', 'protetor', 'desodorante', 'perfume', 'cologne',
    'colonia', 'toalha', 'lenco', 'toalhete', 'talco', 'escova', 'brush',
    'maquiagem', 'makeup', 'beauty', 'beleza', 'skin', 'hair', 'body',
}


def _tokens(texto: str) -> set[str]:
    """Normaliza texto e retorna conjunto de tokens relevantes."""
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


def _marca_no_dominio(marca: str | None, url: str | None) -> bool:
    """Retorna True se o domínio da URL parece ser o site oficial da marca."""
    if not marca or not url:
        return False
    domain = urllib.parse.urlparse(url).netloc.lower()
    nfkd = unicodedata.normalize("NFKD", marca)
    normalizado = nfkd.encode("ASCII", "ignore").decode().lower()
    normalizado = re.sub(r"[^a-z0-9\s]", "", normalizado)
    palavras = [w for w in normalizado.split() if len(w) > 3]
    return any(w in domain for w in palavras)


def _expandir_compostos(t_a: set, t_b: set) -> set:
    """Para palavras compostas sem espaço (ex: 'dutycolor'), encontra tokens de t_b
    que sejam substring de algum token de t_a (e vice-versa), com mín. 4 chars."""
    extra: set = set()
    for a in t_a:
        for b in t_b:
            if len(a) >= 4 and len(b) >= 4 and a != b:
                if b in a:
                    extra.add(b)
                elif a in b:
                    extra.add(a)
    return extra


def _sim_par(t_encontrado: set, nome_ref: str) -> float:
    """Similaridade entre um conjunto de tokens e um nome de referência."""
    t_ref = _tokens(nome_ref)
    if not t_ref:
        return 0.0
    intersec = t_encontrado & t_ref
    # Fallback: tokens compostos como "dutycolor" vs "duty"+"color"
    if not intersec:
        intersec = _expandir_compostos(t_encontrado, t_ref)
    sim = len(intersec) / min(len(t_encontrado), len(t_ref))
    if len(intersec) == 1 and intersec <= _TOKENS_GENERICOS:
        return 0.0
    return sim


def _slug_url(url: str) -> str | None:
    """Retorna o segmento mais descritivo do path da URL (hífens → espaços).
    Ignora segmentos puramente numéricos ou muito curtos."""
    if not url:
        return None
    path = urllib.parse.urlparse(url).path.rstrip("/")
    segments = [s for s in path.split("/") if s and not re.fullmatch(r'\d+', s) and len(s) > 3]
    slug = segments[-1] if segments else ""
    return slug.replace("-", " ") or None


def _nome_e_dominio(nome: str, url: str | None) -> bool:
    """Retorna True se o nome extraído é apenas o nome do site (scraping inválido)."""
    if not url:
        return False
    host = urllib.parse.urlparse(url).hostname or ""
    # "www.ultrafarma.com.br" → "ultrafarma"
    host = re.sub(r"^www\d*\.", "", host.lower())
    stem = host.split(".")[0]
    return bool(stem) and _tokens(nome) == {stem}


def similaridade_nome(nome_encontrado: str | None, ean: str, con: sqlite3.Connection,
                      produto_url: str | None = None) -> float:
    """
    Calcula similaridade entre o nome encontrado e o nome Mintel.
    Testa contra PT e EN; aprova se qualquer uma passar.
    Se a URL for do site oficial da marca, aprova diretamente.
    Se o nome extraído é apenas o nome do site (scraping falho), usa slug da URL.
    Retorna 1.0 se não há dados Mintel (sem base para rejeitar).
    """
    if not nome_encontrado:
        return 0.0
    if _NOME_DOCUMENTO.search(nome_encontrado):
        return 0.0
    row = con.execute(
        "SELECT nome_produto_pt, marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    if not row:
        return 1.0
    nome_pt, marca, produto = row
    if _marca_no_dominio(marca, produto_url):
        return 1.0

    # Se o scraper capturou só o nome do site, tenta o slug da URL
    nome_ref = nome_encontrado
    if _nome_e_dominio(nome_encontrado, produto_url):
        slug = _slug_url(produto_url)
        if slug:
            print(f"        slug: nome '{nome_encontrado}' parece ser o site, usando URL")
            nome_ref = slug

    t_encontrado = _tokens(_limpar_nome(nome_ref))
    if not t_encontrado:
        return 1.0
    # Exige que todos os tokens da marca limpa estejam presentes no nome encontrado
    if marca:
        t_marca = _tokens(_limpar_marca(marca))
        if t_marca:
            for tok in t_marca:
                if tok in t_encontrado:
                    continue
                # aceita typos leves (ex: "naturallis" ↔ "naturaliss")
                if any(
                    difflib.SequenceMatcher(None, tok, t).ratio() >= 0.85
                    for t in t_encontrado
                    if abs(len(t) - len(tok)) <= 2
                ):
                    continue
                return 0.0
    nome_en = " ".join(filter(None, [marca, produto]))
    sims = [_sim_par(t_encontrado, ref) for ref in [nome_pt, nome_en] if ref]
    return max(sims) if sims else 1.0


def _tentar_download(info: dict, ean: str, fonte: str, con: sqlite3.Connection) -> tuple:
    """Tenta baixar a imagem. Retorna (imagem_local, placeholder_detectado)."""
    if not info.get("imagem"):
        return None, False
    resultado = download_image(info["imagem"], ean)
    if resultado is PLACEHOLDER:
        print(f"        placeholder em {fonte}")
        marcar_tentativa(con, ean, fonte)
        return None, True
    return resultado, False


def _salvar_suspeito_se_necessario(
    con: sqlite3.Connection, ean: str, info: dict,
    img: str | None, produto_url: str, buscador: str, origem: str, sim: float = 0.0,
    motivo: str = "",
):
    """Salva como suspeito somente se a similaridade for maior que a do suspeito já registrado."""
    if not info.get("nome"):
        return
    if sim == 0.0:
        return
    existente = con.execute(
        "SELECT status, nome, produto_url FROM enriquecimento_ean WHERE ean = ?", (ean,)
    ).fetchone()
    if existente is not None and existente[0] == "ok":
        return
    if existente is not None and existente[0] == "suspeito":
        sim_existente = similaridade_nome(existente[1], ean, con, produto_url=existente[2])
        if sim <= sim_existente:
            return
    ref_row = con.execute(
        "SELECT nome_produto_pt, marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    if ref_row:
        nome_pt_r, marca_r, prod_r = ref_row
        ref_str = nome_pt_r or f"{marca_r} {prod_r}".strip()
    else:
        ref_str = ""
    marca_str = ref_row[1] if ref_row else ""
    marca_limpa = _limpar_marca(marca_str) if marca_str else ""
    motivo_exib = f": {motivo}" if motivo else ""
    print(f"        → suspeito{motivo_exib}")
    print(f"          referência: {ref_str[:75]}")
    if marca_str:
        exibir = f"{marca_limpa}" + (f"  (de: {marca_str})" if marca_limpa != marca_str else "")
        print(f"          marca:      {exibir[:90]}")
    save_result(con, ean,
        nome=info["nome"], nome_fonte=info["nome_fonte"],
        imagem_url=info["imagem"], imagem_local=img,
        descricao=info["descricao"], desc_fonte=info["desc_fonte"],
        produto_url=produto_url, buscador=buscador,
        origem=origem, status="suspeito", motivo_suspeito=motivo)


def _imprimir_resumo_ean(ean: str, con: sqlite3.Connection):
    """Imprime resumo do resultado final de um EAN e uma linha em branco de separação."""
    row = con.execute(
        "SELECT nome, produto_url, buscador, status FROM enriquecimento_ean WHERE ean = ?", (ean,)
    ).fetchone()
    ref_row = con.execute(
        "SELECT nome_produto_pt, marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    ref_nome = ""
    ref_marca = ""
    if ref_row:
        nome_pt_r, marca_r, prod_r = ref_row
        ref_nome = nome_pt_r or f"{marca_r} {prod_r}".strip()
        ref_marca = marca_r or ""
    if row:
        nome_enc, url, buscador, status = row
        sim = similaridade_nome(nome_enc, ean, con, produto_url=url) if nome_enc else 0.0
        print(f"  ── resultado ──────────────────────────────────────")
        print(f"     status:     {status}  ({sim:.0%})")
        print(f"     link:       {(url or '')[:120]}")
        print(f"     nome:       {(nome_enc or '')[:75]}")
        print(f"     ref. marca: {ref_marca[:55]}")
        print(f"     ref. nome:  {ref_nome[:75]}")
    else:
        print(f"  ── resultado ──────────────────────────────────────")
        print(f"     status:     sem_resultado")
        print(f"     ref. marca: {ref_marca[:55]}")
        print(f"     ref. nome:  {ref_nome[:75]}")
    print()


async def _tentar_links_google(
    page: Page, links: list[str], ean: str, con: sqlite3.Connection,
    label: str, verificar_ean: bool = False,
) -> tuple | None:
    """
    Itera links do Google, extrai dados e salva o primeiro resultado válido como suspeito.
    verificar_ean=True (busca por nome): confirma se o EAN aparece no texto da página.
    verificar_ean=False (busca por EAN): confirma pelo limiar de similaridade de nome.
    Retorna (produto_url, buscador, info, origem, imagem_local) no primeiro aceite, ou None.
    """
    for url in links:
        dom = dominio(url)
        printed_dom = False
        try:
            result = await navigate_and_extract(page, url)
            if result is None:
                print(f"      {dom}: sem dados úteis")
                printed_dom = True
                continue
            print(f"      {dom}")
            printed_dom = True
            img, placeholder = _tentar_download(result, ean, dom, con)
            if placeholder:
                continue
            sim = similaridade_nome(result["nome"], ean, con, produto_url=url)
            nome_log = _limpar_nome(result["nome"] or "")
            print(f"        Nome encontrado: {nome_log[:60]} (similaridade {sim:.0%})")
            if sim == 0.0:
                continue
            motivos = []
            if verificar_ean:
                ean_presente = await page.evaluate(f"() => document.body.innerText.includes('{ean}')")
                if not ean_presente:
                    motivos.append("EAN ausente")
            if sim < LIMIAR_SIMILARIDADE:
                motivos.append("similaridade baixa")
            if motivos:
                _salvar_suspeito_se_necessario(con, ean, result, img, url, dom, "google", sim, motivo=", ".join(motivos))
                continue
            if verificar_ean:
                print(f"        EAN confirmado ✓")
            else:
                print(f"        achou ✓")
            return url, dom, result, "google", img
        except PWTimeout:
            if not printed_dom:
                print(f"      {dom}")
            print(f"        timeout")
            await safe_goto_blank(page)
        except Exception as e:
            if not printed_dom:
                print(f"      {dom}")
            print(f"        erro: {e}")
            await safe_goto_blank(page)
    return None


async def _executar_lojas(
    page: Page, ean: str, lojas: list, con: sqlite3.Connection,
    reprocessar: bool, sites_pausados: set | None, label: str = "Lojas diretas",
) -> tuple | None:
    """Itera lojas diretas. Retorna (url, loja, result, 'loja_direta', img) no primeiro aceite, ou None."""
    print(f"    {label}")
    try:
        while True:
            url, loja = await search_lojas(page, ean, lojas, con=con, reprocessar=reprocessar, sites_pausados=sites_pausados)
            if not url:
                return None
            try:
                result = await navigate_and_extract(page, url)
                if result is None:
                    print(f"        nome genérico")
                    marcar_tentativa(con, ean, loja)
                    continue
                img, placeholder = _tentar_download(result, ean, loja, con)
                if placeholder:
                    continue
                sim = similaridade_nome(result["nome"], ean, con, produto_url=url)
                nome_log = _limpar_nome(result["nome"] or "")
                print(f"        Nome encontrado: {nome_log[:60]} (similaridade {sim:.0%})")
                if sim == 0.0:
                    marcar_tentativa(con, ean, loja)
                    continue
                if sim < LIMIAR_SIMILARIDADE:
                    _salvar_suspeito_se_necessario(con, ean, result, img, url, loja, "loja_direta", sim, motivo="similaridade baixa")
                    marcar_tentativa(con, ean, loja)
                    continue
                print(f"        achou ✓")
                return url, loja, result, "loja_direta", img
            except PWTimeout:
                print(f"        timeout, próxima loja")
                marcar_tentativa(con, ean, loja)
                if sites_pausados is not None:
                    sites_pausados.add(loja)
                await safe_goto_blank(page)
            except Exception as e:
                print(f"        erro: {e}, próxima loja")
                marcar_tentativa(con, ean, loja)
                await safe_goto_blank(page)
    except Exception as e:
        print(f"        erro geral: {e}")
        await safe_goto_blank(page)
    return None


async def process_ean(page: Page, ean: str, con: sqlite3.Connection, fonte: str | None = None, reprocessar: bool = False, sites_pausados: set | None = None):
    row_h = con.execute(
        "SELECT nome_produto_pt, marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    print(f"  {ean}")
    if row_h:
        nome_pt_h, marca_h, produto_h = row_h
        nome_en_h = f"{marca_h} {produto_h}".strip()
        if marca_h:   print(f"    marca:    {marca_h}")
        if nome_pt_h: print(f"    nome PT:  {nome_pt_h[:85]}")
        if nome_en_h and nome_en_h != nome_pt_h:
                      print(f"    nome EN:  {nome_en_h[:85]}")
    print()

    produto_url, buscador, info, origem, imagem_local = None, None, None, None, None

    if not fonte or fonte == "google":
        site_filter = " OR ".join(f"site:{d}" for d in _dominios_lojas())

        row = con.execute(
            "SELECT nome_produto_pt, marca, produto FROM produtos WHERE codigo_barras = ?", (ean,)
        ).fetchone()
        candidatos_nome: list[tuple[str, str]] = []
        if row:
            nome_pt, marca, produto_col = row
            nome_en = f"{marca} {produto_col}".strip()
            if nome_pt:
                candidatos_nome.append(("nome PT", _limpar_nome(nome_pt).strip()))
            if nome_en and nome_en != nome_pt:
                candidatos_nome.append(("nome EN", _limpar_nome(nome_en).strip()))

        async def _tentar_google(query: str, label: str, verificar_ean: bool) -> bool:
            nonlocal produto_url, buscador, info, origem, imagem_local
            print(f"    Google — {label}")
            try:
                links = await search_google(page, query)
                if not links:
                    print(f"      sem resultados")
                    return False
                hit = await _tentar_links_google(page, links, ean, con, label, verificar_ean=verificar_ean)
                if hit:
                    produto_url, buscador, info, origem, imagem_local = hit
                    return True
            except Exception as e:
                print(f"      erro: {e}")
                await safe_goto_blank(page)
            return False

        # 1. EAN restrito a lojas diretas
        if not produto_url:
            await _tentar_google(f"{ean} ({site_filter})", "EAN restrito", verificar_ean=True)

        # 2. EAN livre
        if not produto_url:
            await _tentar_google(ean, "EAN livre", verificar_ean=True)

        # 3. Nome restrito a lojas diretas
        if not produto_url:
            for label_nome, nome_busca in candidatos_nome:
                if nome_busca and await _tentar_google(
                    f"{nome_busca} ({site_filter})", f"{label_nome} restrito", verificar_ean=True
                ):
                    break

        # 4. Lojas diretas
        if LOJAS_FALLBACK_ATIVO and not produto_url:
            hit = await _executar_lojas(page, ean, lojas_ordenadas(ean, con), con, reprocessar, sites_pausados)
            if hit:
                produto_url, buscador, info, origem, imagem_local = hit

        # 5. Nome livre
        if not produto_url:
            for label_nome, nome_busca in candidatos_nome:
                if nome_busca and await _tentar_google(nome_busca, f"{label_nome} livre", verificar_ean=True):
                    break

    # Loja específica por --fonte loja_name (sem busca Google)
    if LOJAS_FALLBACK_ATIVO and not produto_url and fonte and fonte != "google":
        lojas = [l for l in LOJAS_FALLBACK if l["nome"] == fonte]
        hit = await _executar_lojas(page, ean, lojas, con, reprocessar, sites_pausados)
        if hit:
            produto_url, buscador, info, origem, imagem_local = hit

    if not produto_url:
        existente = con.execute(
            "SELECT status FROM enriquecimento_ean WHERE ean = ?", (ean,)
        ).fetchone()
        if existente and existente[0] == "suspeito":
            print(f"    → sem resultado confirmado, mantido como suspeito para revisão")
        else:
            save_result(con, ean, status="sem_resultado")
            print(f"    → sem resultado")
        _imprimir_resumo_ean(ean, con)
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

    _imprimir_resumo_ean(ean, con)


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


def _is_crash(exc: Exception) -> bool:
    return "crashed" in str(exc).lower() or "target closed" in str(exc).lower()


async def _reconectar_chrome(pw, chrome_proc: subprocess.Popen):
    """Encerra o Chrome crashado, inicia um novo e retorna (proc, page)."""
    print("\n  ⚠ Chrome crashou — reiniciando...")
    encerrar_chrome(chrome_proc)
    await asyncio.sleep(3)
    novo_proc = iniciar_chrome()
    await asyncio.sleep(3)
    browser = await pw.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = await context.new_page()
    print("  Chrome reiniciado.\n")
    return novo_proc, page


async def cmd_setup():
    """Abre o Chrome real para login e aguarda confirmação do usuário."""
    PROFILE_DIR.mkdir(exist_ok=True)
    print("Abrindo Chrome para configuração de sessão...\n")
    proc = iniciar_chrome()

    try:
        print("[ 1/3 ] Google")
        print("        Faça login na sua conta Google no Chrome que abriu.")
        input("        Quando terminar, pressione ENTER aqui... ")

        print("\n[ 2/3 ] Mercado Livre")
        print("        Acesse mercadolivre.com.br e faça login.")
        input("        Quando terminar, pressione ENTER aqui... ")

        print("\n[ 3/3 ] Shopee")
        print("        Acesse shopee.com.br e faça login.")
        print("        Selecione o idioma Português se solicitado.")
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
                try:
                    await process_ean(page, ean, con, fonte=args.fonte, reprocessar=args.reprocessar, sites_pausados=sites_pausados)
                except Exception as e:
                    if _is_crash(e):
                        chrome, page = await _reconectar_chrome(pw, chrome)
                        await process_ean(page, ean, con, fonte=args.fonte, reprocessar=args.reprocessar, sites_pausados=sites_pausados)
                    else:
                        raise
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
        "suspeito":        "? Resultado encontrado, aguardando confirmação",
        "sem_resultado":   "✗ EAN não encontrado",
        "sem_imagem":      "✗ Página encontrada, mas sem imagem",
        "download_falhou": "✗ Imagem encontrada, mas falhou ao baixar",
        "timeout":         "✗ Página demorou demais para carregar",
        "erro_pagina":     "✗ Erro ao acessar a página do produto",
        "fora_do_escopo":  "— Fora do escopo do CSV",
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
    processado = con.execute(
        "SELECT COUNT(*) FROM enriquecimento_ean WHERE status != 'fora_do_escopo'"
    ).fetchone()[0]
    ok = con.execute("SELECT COUNT(*) FROM enriquecimento_ean WHERE status='ok'").fetchone()[0]
    print(f"  {'Total processado':<18} {'':<45} {processado:>6}")
    print(f"  {'Taxa de sucesso':<18} {'':<45} {ok/processado*100:>5.1f}%")
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


async def _rebuscar_lista(page, con: sqlite3.Connection, eans: list[str], buscador: str, sites_pausados: set, start: float, total: int, offset: int, pw=None, chrome_ref: list | None = None):
    """Processa uma lista de EANs num buscador específico usando a página já aberta."""
    for i, ean in enumerate(eans, 1):
        try:
            await process_ean(page, ean, con, fonte=buscador, sites_pausados=sites_pausados)
        except Exception as e:
            if _is_crash(e) and pw is not None and chrome_ref is not None:
                chrome_ref[0], page = await _reconectar_chrome(pw, chrome_ref[0])
                await process_ean(page, ean, con, fonte=buscador, sites_pausados=sites_pausados)
            else:
                raise
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
            chrome_ref = [chrome]
            await _rebuscar_lista(page, con, eans, args.rebuscar_buscador, sites_pausados, start, len(eans), 0, pw=pw, chrome_ref=chrome_ref)
            chrome = chrome_ref[0]
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

            chrome_ref = [chrome]
            for buscador, eans in agenda:
                print(f"\n{'='*60}")
                print(f"  {buscador} — {len(eans)} EANs")
                print(f"{'='*60}\n")
                await _rebuscar_lista(page, con, eans, buscador, sites_pausados, start, total, offset, pw=pw, chrome_ref=chrome_ref)
                offset += len(eans)
            chrome = chrome_ref[0]

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

            chrome_ref = [chrome]
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
                    if _is_crash(e):
                        print("✗ crash — reiniciando Chrome")
                        chrome_ref[0], page = await _reconectar_chrome(pw, chrome_ref[0])
                    else:
                        print(f"✗ erro: {e}")
                        await safe_goto_blank(page)

                await page.wait_for_timeout(int(random.uniform(DELAY_MIN, DELAY_MAX) * 1000))

            chrome = chrome_ref[0]
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


def cmd_limpar_suspeitos():
    """Remove todos os registros com status='suspeito' do banco e suas imagens locais."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT ean, imagem_local FROM enriquecimento_ean WHERE status = 'suspeito'"
    ).fetchall()

    if not rows:
        print("Nenhum suspeito encontrado.")
        con.close()
        return

    print(f"{len(rows)} suspeitos encontrados. Removendo...")
    eans = [r[0] for r in rows]
    ph = ",".join("?" * len(eans))
    con.execute(f"DELETE FROM enriquecimento_ean WHERE ean IN ({ph})", eans)
    con.execute(f"DELETE FROM busca_tentativa WHERE ean IN ({ph})", eans)
    con.commit()

    removidas = 0
    for _, imagem_local in rows:
        if imagem_local:
            p = Path(imagem_local)
            if p.exists():
                p.unlink()
                removidas += 1

    print(f"  {len(eans)} registros removidos do banco.")
    if removidas:
        print(f"  {removidas} imagens locais apagadas.")
    print("EANs liberados para nova busca na próxima execução.")
    con.close()


def cmd_marcar_fora_escopo():
    """Marca com status='fora_do_escopo' os EANs da tabela produtos que não estão no CSV."""
    con = sqlite3.connect(DB_PATH)
    setup_db(con)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        eans_csv = {row["ean"].strip() for row in csv.DictReader(f) if row["ean"].strip()}

    todos = {r[0] for r in con.execute(
        "SELECT codigo_barras FROM produtos WHERE codigo_barras IS NOT NULL AND codigo_barras != ''"
    ).fetchall()}

    fora = todos - eans_csv
    if not fora:
        print("Nenhum EAN fora do escopo encontrado.")
        con.close()
        return

    agora = datetime.now().isoformat()
    con.executemany(
        "INSERT OR IGNORE INTO enriquecimento_ean (ean, status, processado) VALUES (?, 'fora_do_escopo', ?)",
        [(ean, agora) for ean in fora],
    )
    con.commit()
    marcados = con.execute(
        "SELECT COUNT(*) FROM enriquecimento_ean WHERE status = 'fora_do_escopo'"
    ).fetchone()[0]
    print(f"{marcados} EANs marcados como 'fora_do_escopo' (de {len(fora)} fora do CSV).")
    con.close()


def cmd_limpar_falsos_positivos():
    """Remove do banco registros existentes com similaridade abaixo do limiar."""
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT e.ean, e.nome, e.imagem_local, e.produto_url
        FROM enriquecimento_ean e
        WHERE e.status IN ('ok', 'sem_imagem') AND e.nome IS NOT NULL
    """).fetchall()

    para_remover = []
    for ean, nome_encontrado, imagem_local, produto_url in rows:
        sim = similaridade_nome(nome_encontrado, ean, con, produto_url=produto_url)
        if sim < LIMIAR_SIMILARIDADE:
            nome_mintel = con.execute(
                "SELECT COALESCE(nome_produto_pt, marca || ' ' || produto) FROM produtos WHERE codigo_barras = ?",
                (ean,)
            ).fetchone()
            para_remover.append((ean, sim, nome_encontrado, nome_mintel[0] if nome_mintel else "", imagem_local))

    if not para_remover:
        print("Nenhum falso positivo encontrado.")
        con.close()
        return

    print(f"Falsos positivos encontrados: {len(para_remover)}\n")
    for ean, sim, nome_enc, nome_min, _ in sorted(para_remover, key=lambda x: x[1]):
        print(f"  {sim:.2f}  {ean}")
        print(f"       encontrado: {nome_enc[:75]}")
        print(f"       mintel:     {nome_min[:75]}")

    print(f"\nRemovendo {len(para_remover)} registros do banco...")
    eans = [r[0] for r in para_remover]
    ph = ",".join("?" * len(eans))
    con.execute(f"DELETE FROM enriquecimento_ean WHERE ean IN ({ph})", eans)
    con.commit()

    removidas = 0
    for _, _, _, _, imagem_local in para_remover:
        if imagem_local:
            p = Path(imagem_local)
            if p.exists():
                p.unlink()
                removidas += 1

    print(f"  {len(eans)} registros removidos do banco.")
    print(f"  {removidas} imagens locais apagadas.")
    print("\nEANs liberados para nova busca na próxima execução.")
    con.close()


async def cmd_reprocessar_ean(args):
    """Apaga registro e histórico de um EAN e reprocessa do zero."""
    ean = args.ean.strip()
    con = sqlite3.connect(DB_PATH)
    setup_db(con)

    existe = con.execute(
        "SELECT 1 FROM produtos WHERE codigo_barras = ?", (ean,)
    ).fetchone()
    if not existe:
        print(f"EAN {ean} não encontrado na tabela produtos.")
        con.close()
        return

    print(f"EAN: {ean}  {mintel_info(ean, con)}")

    # Remove registro anterior e imagem
    row = con.execute(
        "SELECT imagem_local FROM enriquecimento_ean WHERE ean = ?", (ean,)
    ).fetchone()
    if row:
        if row[0]:
            p = Path(row[0])
            if p.exists():
                p.unlink()
                print(f"  Imagem anterior removida: {row[0]}")
        con.execute("DELETE FROM enriquecimento_ean WHERE ean = ?", (ean,))
        print("  Registro anterior removido.")

    # Limpa histórico de tentativas por loja
    tentativas = con.execute(
        "SELECT COUNT(*) FROM busca_tentativa WHERE ean = ?", (ean,)
    ).fetchone()[0]
    if tentativas:
        con.execute("DELETE FROM busca_tentativa WHERE ean = ?", (ean,))
        print(f"  {tentativas} tentativa(s) anteriores apagadas.")

    con.commit()

    IMG_DIR.mkdir(exist_ok=True)
    print(f"\nIniciando Chrome... (log em {CHROME_LOG})")
    chrome = iniciar_chrome()
    await asyncio.sleep(2)

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            print("Conectado.\n")
            await process_ean(page, ean, con, reprocessar=True, sites_pausados=set())
            await page.close()
    finally:
        encerrar_chrome(chrome)
        print("Chrome encerrado.")

    resultado = con.execute(
        "SELECT status, buscador, produto_url FROM enriquecimento_ean WHERE ean = ?", (ean,)
    ).fetchone()
    if resultado:
        print(f"\nResultado: status={resultado[0]} | buscador={resultado[1]} | url={resultado[2]}")
    else:
        print("\nNenhum resultado encontrado.")
    con.close()


async def main():
    fontes = ["google"] + [l["nome"] for l in LOJAS_FALLBACK]
    parser = argparse.ArgumentParser(
        description=(
            "Busca imagens e dados de produtos por EAN em lojas brasileiras.\n"
            "Por padrão (sem flags) processa todos os EANs pendentes:\n"
            "  1. Tenta todos os links válidos da 1ª página do Google.\n"
            "  2. Se não encontrar, testa cada loja diretamente (fallback).\n"
            "  Resultados são salvos em mintel.db (tabela enriquecimento_ean)\n"
            "  e imagens em imagens/<EAN>.{jpg,png}."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  # Primeira configuração (login Google / Mercado Livre):\n"
            "  python extrair_dados_ean.py --setup\n"
            "\n"
            "  # Processar até 100 EANs pendentes:\n"
            "  python extrair_dados_ean.py -n 100\n"
            "\n"
            "  # Forçar busca apenas pelo Google (sem fallback para lojas):\n"
            "  python extrair_dados_ean.py --fonte google\n"
            "\n"
            "  # Repetir scraping de página para EANs da Ultrafarma sem imagem:\n"
            "  python extrair_dados_ean.py --rescrape-buscador ultrafarma\n"
            "\n"
            "  # Rebuscar (busca completa do zero) EANs antes encontrados via Panvel:\n"
            "  python extrair_dados_ean.py --rebuscar-buscador panvel\n"
            "\n"
            "  # Rebuscar todos os buscadores loja_direta numa única sessão:\n"
            "  python extrair_dados_ean.py --rebuscar-todos\n"
            "\n"
            "  # Remover falsos positivos do banco (similaridade < limiar):\n"
            "  python extrair_dados_ean.py --limpar-falsos-positivos\n"
            "\n"
            f"Fontes disponíveis: {', '.join(fontes)}"
        ),
    )
    parser.add_argument("--setup", action="store_true",
                        help="Abre o Chrome para login no Google e Mercado Livre (necessário na primeira execução)")
    parser.add_argument("-n", "--limite", type=int, default=None, metavar="N",
                        help="Limita a N EANs nesta execução (útil para testes)")
    parser.add_argument("--fonte", choices=fontes, default=None, metavar="FONTE",
                        help="Restringe a busca a uma única fonte; sem esta flag usa Google + fallback para todas as lojas")
    parser.add_argument("--reprocessar", action="store_true",
                        help="Inclui EANs com status 'ok' na fila (re-extrai mesmo os já encontrados)")
    parser.add_argument("--rescrape-buscador", metavar="BUSCADOR",
                        help=(
                            "Re-faz apenas o scraping da página para EANs de BUSCADOR com status != ok. "
                            "Não realiza nova busca — usa a URL já salva no banco. "
                            "Útil quando o seletor ou a extração de nome/imagem foi corrigida."
                        ))
    parser.add_argument("--rebuscar-buscador", metavar="BUSCADOR",
                        help=(
                            "Refaz a busca completa (Google + lojas) para EANs que foram encontrados "
                            "por BUSCADOR via loja_direta com status=ok. "
                            "Remove os registros atuais e reprocessa do zero."
                        ))
    parser.add_argument("--rebuscar-todos", action="store_true",
                        help="Versão de --rebuscar-buscador para todos os buscadores loja_direta numa única sessão do Chrome")
    parser.add_argument("--marcar-fora-escopo", action="store_true",
                        help=(
                            f"Marca com status='fora_do_escopo' todos os EANs da tabela produtos "
                            f"que não constam em {CSV_PATH}. Executar uma vez para limpar o banco."
                        ))
    parser.add_argument("--limpar-suspeitos", action="store_true",
                        help="Remove todos os registros suspeitos do banco e libera os EANs para nova busca.")
    parser.add_argument("--limpar-falsos-positivos", action="store_true",
                        help=(
                            "Varre enriquecimento_ean e remove registros ok/sem_imagem cuja similaridade "
                            f"de nome está abaixo do limiar ({int(LIMIAR_SIMILARIDADE * 100)}%%). "
                            "Apaga também a imagem local correspondente."
                        ))
    parser.add_argument("--ean", metavar="EAN",
                        help=(
                            "Reprocessa um EAN específico do zero: apaga registro anterior e histórico "
                            "de tentativas, depois tenta todas as fontes (Google EAN, Google nome PT/EN, "
                            "todas as lojas) independentemente do que foi tentado antes."
                        ))
    args = parser.parse_args()

    if args.setup:
        await cmd_setup()
    elif args.marcar_fora_escopo:
        cmd_marcar_fora_escopo()
    elif args.limpar_suspeitos:
        cmd_limpar_suspeitos()
    elif args.limpar_falsos_positivos:
        cmd_limpar_falsos_positivos()
    elif args.ean:
        await cmd_reprocessar_ean(args)
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
