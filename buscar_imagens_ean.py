"""
Busca imagens de produtos pelo EAN.
Estratégia:
  1. Bing Search → primeiro resultado não-Bing → extrai og:image da página
  2. Mercado Livre → busca direta por EAN → og:image do produto

Resultados salvos em mintel.db, tabela enriquecimento_ean.
Retomável: EANs já processados são pulados.
"""

import asyncio
import base64
import csv
import mimetypes
import random
import sqlite3
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

CSV_PATH = "falta_enriquecimento.csv"
DB_PATH = "mintel.db"
IMG_DIR = Path("imagens")
DELAY_MIN = 2.5
DELAY_MAX = 4.5


# ── DB ──────────────────────────────────────────────────────────────────────

def setup_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS enriquecimento_ean (
            ean          TEXT PRIMARY KEY,
            nome         TEXT,
            imagem_url   TEXT,
            imagem_local TEXT,
            descricao    TEXT,
            fonte_url    TEXT,
            status       TEXT,
            processado   TEXT
        )
    """)
    # Adiciona coluna se a tabela já existia sem ela
    cols = {r[1] for r in con.execute("PRAGMA table_info(enriquecimento_ean)")}
    if "imagem_local" not in cols:
        con.execute("ALTER TABLE enriquecimento_ean ADD COLUMN imagem_local TEXT")
    con.commit()


def load_pending(con: sqlite3.Connection) -> list[str]:
    done = {r[0] for r in con.execute("SELECT ean FROM enriquecimento_ean").fetchall()}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        all_eans = [row["ean"].strip() for row in csv.DictReader(f) if row["ean"].strip()]
    pending = [e for e in all_eans if e not in done]
    print(f"Total: {len(all_eans)} | Já processados: {len(done)} | Pendentes: {len(pending)}")
    return pending


def save_result(con, ean, nome, imagem_url, imagem_local, descricao, fonte_url, status):
    con.execute("""
        INSERT OR REPLACE INTO enriquecimento_ean
            (ean, nome, imagem_url, imagem_local, descricao, fonte_url, status, processado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (ean, nome, imagem_url, imagem_local, descricao, fonte_url, status, datetime.now().isoformat()))
    con.commit()


def download_image(imagem_url: str, ean: str) -> str | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
        with httpx.Client(follow_redirects=True, timeout=15) as client:
            r = client.get(imagem_url, headers=headers)
            r.raise_for_status()

        # Determina extensão pelo Content-Type ou pela URL
        ct = r.headers.get("content-type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(ct) or Path(urllib.parse.urlparse(imagem_url).path).suffix or ".jpg"
        ext = ext.replace(".jpe", ".jpg")  # normaliza .jpe → .jpg

        dest = IMG_DIR / f"{ean}{ext}"
        dest.write_bytes(r.content)
        return str(dest)
    except Exception as e:
        print(f"    ↳ falha no download: {e}")
        return None


# ── Extração ────────────────────────────────────────────────────────────────

async def extract_meta(page: Page) -> dict:
    return await page.evaluate("""() => {
        const g = (sel, attr) => {
            const el = document.querySelector(sel);
            return el ? el.getAttribute(attr) : null;
        };
        let img = g('meta[property="og:image"]', 'content');
        if (!img) {
            // Schema.org
            try {
                for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
                    const d = JSON.parse(s.textContent);
                    const obj = Array.isArray(d) ? d[0] : d;
                    if (obj && obj.image) {
                        const i = Array.isArray(obj.image) ? obj.image[0] : obj.image;
                        img = typeof i === 'string' ? i : (i && i.url) || null;
                        if (img) break;
                    }
                }
            } catch {}
        }
        return {
            nome: g('meta[property="og:title"]', 'content') || document.title || null,
            imagem: img,
            descricao: g('meta[property="og:description"]', 'content')
                    || g('meta[name="description"]', 'content')
                    || null,
        };
    }""")


# ── Bing ────────────────────────────────────────────────────────────────────

def decode_bing_url(bing_url: str) -> str | None:
    try:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(bing_url).query)
        u = params.get("u", [""])[0]
        if u.startswith("a1"):
            b64 = u[2:] + "=" * (-len(u[2:]) % 4)
            return base64.b64decode(b64).decode("utf-8", errors="ignore")
    except Exception:
        pass
    return None


async def search_bing(page: Page, ean: str) -> str | None:
    await page.goto(
        f"https://www.bing.com/search?q={ean}&setlang=pt-BR&cc=BR",
        wait_until="domcontentloaded",
        timeout=20000,
    )
    await page.wait_for_timeout(random.randint(800, 1400))

    raw_links = await page.evaluate("""() =>
        Array.from(document.querySelectorAll('#b_results h2 a'))
            .map(a => a.href)
    """)

    for raw in raw_links:
        if "bing.com" not in raw:
            return raw  # já é URL direta
        decoded = decode_bing_url(raw)
        if decoded and "bing.com" not in decoded:
            return decoded

    return None


# ── Mercado Livre ────────────────────────────────────────────────────────────

async def search_ml(page: Page, ean: str) -> str | None:
    await page.goto(
        f"https://www.mercadolivre.com.br/jm/search?as_word={ean}",
        wait_until="domcontentloaded",
        timeout=20000,
    )
    await page.wait_for_timeout(random.randint(800, 1400))

    first = await page.query_selector(".poly-card a, .ui-search-result__content a")
    if not first:
        return None
    href = await first.get_attribute("href")
    return href.split("?")[0] if href else None


# ── Processamento de um EAN ──────────────────────────────────────────────────

async def process_ean(page: Page, ean: str, con: sqlite3.Connection):
    product_url = None
    fonte = "bing"

    try:
        product_url = await search_bing(page, ean)
    except Exception as e:
        print(f"  {ean} Bing erro: {e}")

    if not product_url:
        try:
            product_url = await search_ml(page, ean)
            fonte = "mercadolivre"
        except Exception as e:
            print(f"  {ean} ML erro: {e}")

    if not product_url:
        save_result(con, ean, None, None, None, None, None, "sem_resultado")
        print(f"  {ean} → sem resultado")
        return

    try:
        await page.goto(product_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(random.randint(600, 1200))
        info = await extract_meta(page)
    except PWTimeout:
        save_result(con, ean, None, None, None, None, product_url, "timeout_produto")
        print(f"  {ean} → timeout na página do produto")
        return
    except Exception as e:
        save_result(con, ean, None, None, None, None, product_url, "erro_produto")
        print(f"  {ean} → erro na página: {e}")
        return

    imagem_local = None
    if info["imagem"]:
        imagem_local = download_image(info["imagem"], ean)

    status = "ok" if imagem_local else ("sem_imagem" if not info["imagem"] else "download_falhou")
    save_result(con, ean, info["nome"], info["imagem"], imagem_local, info["descricao"], product_url, status)

    flag = "✓" if imagem_local else "✗"
    print(f"  {ean} [{flag}] [{fonte}] {(info['nome'] or '')[:60]}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    IMG_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    setup_db(con)
    pending = load_pending(con)

    if not pending:
        print("Nenhum EAN pendente.")
        con.close()
        return

    start = time.time()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--lang=pt-BR"],
        )
        context = await browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        print(f"\nIniciando busca de {len(pending)} EANs...\n")

        for i, ean in enumerate(pending, 1):
            await process_ean(page, ean, con)
            await page.wait_for_timeout(int(random.uniform(DELAY_MIN, DELAY_MAX) * 1000))

            if i % 50 == 0:
                elapsed = time.time() - start
                rate = i / elapsed
                remaining = (len(pending) - i) / rate if rate > 0 else 0
                print(f"\n  >>> {i}/{len(pending)} | {rate:.1f}/s | ~{remaining/60:.0f} min restantes\n")

        await browser.close()

    elapsed = time.time() - start
    print(f"\nConcluído em {elapsed/60:.1f} min.")
    cur = con.cursor()
    for status, count in cur.execute("SELECT status, COUNT(*) FROM enriquecimento_ean GROUP BY status"):
        print(f"  {status}: {count}")
    con.close()


if __name__ == "__main__":
    asyncio.run(main())
