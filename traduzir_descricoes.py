"""
Traduz a coluna descricao_produto (EN) para PT-BR e salva em descricao_produto_pt.
- Aproveita cache: só traduz descrições únicas ainda não traduzidas.
- Usa threads para paralelismo (default: 5).
- Retomável: pode ser interrompido e reiniciado sem perder progresso.
"""

import sqlite3
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator

DB_PATH = "mintel.db"
THREADS = 5
DELAY_BETWEEN_REQUESTS = 0.3  # segundos por thread


def ensure_column(con):
    cur = con.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(produtos)").fetchall()]
    if "descricao_produto_pt" not in cols:
        cur.execute("ALTER TABLE produtos ADD COLUMN descricao_produto_pt TEXT")
        con.commit()
        print("Coluna descricao_produto_pt criada.")
    else:
        print("Coluna descricao_produto_pt já existe.")


def build_translation_cache(con):
    cur = con.cursor()
    cur.execute("""
        SELECT DISTINCT descricao_produto, descricao_produto_pt
        FROM produtos
        WHERE descricao_produto IS NOT NULL AND descricao_produto != ''
    """)
    cache = {}
    for en, pt in cur.fetchall():
        if pt is not None:
            cache[en] = pt
    return cache


def fetch_pending(con, cache):
    cur = con.cursor()
    cur.execute("""
        SELECT DISTINCT descricao_produto
        FROM produtos
        WHERE descricao_produto IS NOT NULL AND descricao_produto != ''
    """)
    all_texts = [r[0] for r in cur.fetchall()]
    return [t for t in all_texts if t not in cache]


def translate_one(text: str) -> tuple[str, str | None]:
    for attempt in range(4):
        try:
            result = GoogleTranslator(source="en", target="pt").translate(text)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return text, result
        except Exception as e:
            wait = 2 ** attempt
            print(f"\n  [retry {attempt+1}] erro: {e!r} — aguardando {wait}s")
            time.sleep(wait)
    return text, None


def flush_cache(con, cache_snapshot: dict):
    cur = con.cursor()
    cur.executemany(
        "UPDATE produtos SET descricao_produto_pt = ? WHERE descricao_produto = ? AND descricao_produto_pt IS NULL",
        [(pt, en) for en, pt in cache_snapshot.items() if pt is not None],
    )
    con.commit()


def main():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    ensure_column(con)

    print("Carregando cache de traduções existentes...")
    cache = build_translation_cache(con)
    print(f"  Já traduzidas: {len(cache)}")

    pending = fetch_pending(con, cache)
    print(f"  Pendentes: {len(pending)}")

    if not pending:
        print("Nada a fazer — todas as descrições já estão traduzidas.")
        con.close()
        return

    lock = threading.Lock()
    done = 0
    failed = 0
    batch_cache: dict[str, str] = {}
    FLUSH_EVERY = 100

    print(f"\nIniciando tradução com {THREADS} threads...\n")
    start = time.time()

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(translate_one, t): t for t in pending}

        for future in as_completed(futures):
            en, pt = future.result()
            with lock:
                if pt is not None:
                    batch_cache[en] = pt
                    done += 1
                else:
                    failed += 1

                total_done = done + failed
                if total_done % FLUSH_EVERY == 0:
                    flush_cache(con, dict(batch_cache))
                    batch_cache.clear()
                    elapsed = time.time() - start
                    rate = total_done / elapsed if elapsed > 0 else 0
                    remaining = (len(pending) - total_done) / rate if rate > 0 else 0
                    print(
                        f"  {total_done}/{len(pending)} | "
                        f"{rate:.1f} trad/s | "
                        f"restam ~{remaining/60:.1f} min | "
                        f"falhas: {failed}",
                        flush=True,
                    )

    if batch_cache:
        flush_cache(con, batch_cache)

    elapsed = time.time() - start
    print(f"\nConcluído em {elapsed/60:.1f} min.")
    print(f"  Traduzidas com sucesso: {done}")
    print(f"  Falhas: {failed}")

    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM produtos WHERE descricao_produto_pt IS NOT NULL")
    print(f"  Total com tradução no banco: {cur.fetchone()[0]}")
    con.close()


if __name__ == "__main__":
    main()
