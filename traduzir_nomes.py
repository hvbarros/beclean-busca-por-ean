"""
Popula a coluna nome_produto_pt com o nome do produto em português.

Estratégia:
  1. Se descricao_produto_pt contém "já está disponível" e o trecho antes
     tem até MAX_NOME_CHARS caracteres → usa esse trecho (sem custo de API).
  2. Caso contrário → traduz `marca + " " + produto` via Google Translate.

Retomável: só processa produtos que ainda não têm nome_produto_pt.
"""

import re
import sqlite3
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from deep_translator import GoogleTranslator

DB_PATH = "mintel.db"
THREADS = 5
DELAY = 0.3
MAX_NOME_CHARS = 80
FLUSH_EVERY = 100


def ensure_column(con):
    cols = [r[1] for r in con.execute("PRAGMA table_info(produtos)").fetchall()]
    if "nome_produto_pt" not in cols:
        con.execute("ALTER TABLE produtos ADD COLUMN nome_produto_pt TEXT")
        con.commit()
        print("Coluna nome_produto_pt criada.")
    else:
        print("Coluna nome_produto_pt já existe.")


def _extrair_de_descricao(desc_pt: str | None) -> str | None:
    if not desc_pt:
        return None
    m = re.search(r"^(.{1,%d}?)\s+já está disponível" % MAX_NOME_CHARS, desc_pt)
    return m.group(1).strip() if m else None


def fetch_pending(con) -> list[tuple[int, str, str, str | None]]:
    """Retorna (id, marca, produto, desc_pt) dos que ainda não têm nome_produto_pt."""
    return con.execute("""
        SELECT id, marca, produto, descricao_produto_pt
        FROM produtos
        WHERE nome_produto_pt IS NULL
    """).fetchall()


def translate_one(text: str) -> str | None:
    for attempt in range(4):
        try:
            result = GoogleTranslator(source="en", target="pt").translate(text)
            time.sleep(DELAY)
            return result
        except Exception as e:
            wait = 2 ** attempt
            print(f"\n  [retry {attempt+1}] erro: {e!r} — aguardando {wait}s")
            time.sleep(wait)
    return None


def flush(con, updates: list[tuple[str, int]]):
    con.executemany("UPDATE produtos SET nome_produto_pt = ? WHERE id = ?", updates)
    con.commit()


def main():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    ensure_column(con)

    pending = fetch_pending(con)
    print(f"Produtos sem nome_produto_pt: {len(pending)}")

    if not pending:
        print("Nada a fazer.")
        con.close()
        return

    # Separa os que podem ser resolvidos sem API
    diretos: list[tuple[int, str]] = []
    para_traduzir: list[tuple[int, str]] = []

    for pid, marca, produto, desc_pt in pending:
        nome = _extrair_de_descricao(desc_pt)
        if nome:
            diretos.append((nome, pid))
        else:
            para_traduzir.append((pid, f"{marca} {produto}"))

    print(f"  Extraídos de descricao_produto_pt: {len(diretos)}")
    print(f"  A traduzir via Google Translate:   {len(para_traduzir)}")

    # Salva os diretos imediatamente
    if diretos:
        flush(con, diretos)
        print(f"  {len(diretos)} nomes salvos sem API.")

    if not para_traduzir:
        print("Concluído — nenhuma tradução necessária.")
        con.close()
        return

    # Tradução paralela
    lock = threading.Lock()
    done = 0
    failed = 0
    batch: list[tuple[str, int]] = []
    start = time.time()

    print(f"\nTraduzindo {len(para_traduzir)} nomes com {THREADS} threads...\n")

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(translate_one, texto): pid for pid, texto in para_traduzir}

        for future in as_completed(futures):
            pid = futures[future]
            pt = future.result()
            with lock:
                if pt is not None:
                    batch.append((pt, pid))
                    done += 1
                else:
                    failed += 1

                total = done + failed
                if total % FLUSH_EVERY == 0:
                    flush(con, list(batch))
                    batch.clear()
                    elapsed = time.time() - start
                    rate = total / elapsed if elapsed > 0 else 0
                    restam = (len(para_traduzir) - total) / rate if rate > 0 else 0
                    print(
                        f"  {total}/{len(para_traduzir)} | "
                        f"{rate:.1f}/s | "
                        f"~{restam/60:.1f} min restantes | "
                        f"falhas: {failed}",
                        flush=True,
                    )

    if batch:
        flush(con, batch)

    elapsed = time.time() - start
    print(f"\nConcluído em {elapsed/60:.1f} min.")
    print(f"  Traduzidos: {done} | Falhas: {failed}")

    total_com_nome = con.execute(
        "SELECT COUNT(*) FROM produtos WHERE nome_produto_pt IS NOT NULL"
    ).fetchone()[0]
    print(f"  Total com nome_produto_pt no banco: {total_com_nome}/24061")
    con.close()


if __name__ == "__main__":
    main()
