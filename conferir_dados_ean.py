"""
FASE 2 — Conferência dos dados extraídos.
Executa após revisão manual da extração.

Comandos:
  listar    Exibe nome e descrição de cada EAN (scraping + Mintel)
  conferir  Confronto textual + validação de imagem via Claude Vision

Requer: ANTHROPIC_API_KEY no ambiente (apenas para o comando conferir).
"""

import argparse
import base64
import os
import sqlite3
from pathlib import Path

import anthropic

DB_PATH = "mintel.db"


# ── DB ────────────────────────────────────────────────────────────────────────

def setup_db(con: sqlite3.Connection):
    cols = {r[1] for r in con.execute("PRAGMA table_info(enriquecimento_ean)")}
    for col, tipo in [("conferencia", "TEXT"), ("conf_motivo", "TEXT")]:
        if col not in cols:
            con.execute(f"ALTER TABLE enriquecimento_ean ADD COLUMN {col} {tipo}")
    con.commit()


def buscar_mintel(ean: str, con: sqlite3.Connection) -> dict | None:
    row = con.execute(
        """SELECT produto, variante_produto, marca, descricao_produto_pt
           FROM produtos WHERE codigo_barras = ?""",
        (ean,),
    ).fetchone()
    if not row:
        return None
    return {"produto": row[0], "variante": row[1], "marca": row[2], "descricao": row[3]}


# ── Confronto textual ─────────────────────────────────────────────────────────

def confrontar_com_mintel(ean: str, nome_scraped: str | None, con: sqlite3.Connection) -> dict:
    mintel = buscar_mintel(ean, con)
    if not mintel:
        return {"ok": None, "motivo": "EAN não encontrado no Mintel"}
    if not nome_scraped:
        return {"ok": False, "motivo": "Nome scraped vazio", "mintel": mintel}

    nome_mintel = f"{mintel['marca'] or ''} {mintel['produto'] or ''}".strip()
    palavras_mintel = set(nome_mintel.lower().split())
    palavras_scraped = set(nome_scraped.lower().split())
    comuns = palavras_mintel & palavras_scraped
    score = len(comuns) / max(len(palavras_mintel), 1)

    return {
        "ok": score >= 0.3,
        "score": round(score, 2),
        "nome_mintel": nome_mintel,
        "mintel": mintel,
    }


# ── Validação de imagem ───────────────────────────────────────────────────────

def validar_imagem_claude(imagem_local: str, client: anthropic.Anthropic) -> dict:
    p = Path(imagem_local)
    if not p.exists():
        return {"ok": None, "motivo": "Arquivo não encontrado"}

    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                 ".webp": "image/webp", ".gif": "image/gif"}
    media_type = media_map.get(p.suffix.lower(), "image/jpeg")
    b64 = base64.standard_b64encode(p.read_bytes()).decode()

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=80,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": (
                    "Esta imagem mostra um produto cosmético (shampoo, creme, perfume, "
                    "maquiagem, etc.)? Responda apenas: SIM ou NÃO, seguido de uma razão "
                    "em até 10 palavras."
                )},
            ],
        }],
    )
    resposta = msg.content[0].text.strip()
    return {"ok": resposta.upper().startswith("SIM"), "resposta": resposta}


# ── Comandos ──────────────────────────────────────────────────────────────────

def cmd_listar(con: sqlite3.Connection):
    rows = con.execute("""
        SELECT e.ean, e.nome, e.descricao, e.status, e.buscador,
               p.produto, p.variante_produto, p.marca, p.descricao_produto_pt
        FROM enriquecimento_ean e
        LEFT JOIN produtos p ON p.codigo_barras = e.ean
        ORDER BY e.processado DESC
    """).fetchall()

    if not rows:
        print("Nenhum EAN processado ainda.")
        return

    for ean, nome, desc, status, buscador, produto, variante, marca, desc_pt in rows:
        print(f"\n{'─'*70}")
        print(f"EAN: {ean}  [{status}]  fonte: {buscador or '—'}")

        nome_mintel = " ".join(filter(None, [marca, produto, variante])) or None
        print(f"  Mintel  nome : {nome_mintel or '(não encontrado)'}")
        if desc_pt:
            print(f"  Mintel  desc : {desc_pt[:150]}{'...' if len(desc_pt) > 150 else ''}")

        print(f"  Scraped nome : {nome or '(vazio)'}")
        if desc:
            print(f"  Scraped desc : {desc[:150]}{'...' if len(desc) > 150 else ''}")


def cmd_conferir(con: sqlite3.Connection, client: anthropic.Anthropic):
    setup_db(con)

    rows = con.execute("""
        SELECT ean, nome, descricao, imagem_local
        FROM enriquecimento_ean
        WHERE status = 'ok'
        ORDER BY processado
    """).fetchall()

    print(f"{len(rows)} EAN(s) com status 'ok' para conferência.\n")

    for ean, nome, desc, imagem_local in rows:
        res_texto = confrontar_com_mintel(ean, nome, con)
        res_img = (
            validar_imagem_claude(imagem_local, client)
            if imagem_local
            else {"ok": None, "motivo": "sem imagem"}
        )

        flag_t = "✓" if res_texto.get("ok") else ("?" if res_texto.get("ok") is None else "✗")
        flag_i = "✓" if res_img.get("ok") else ("?" if res_img.get("ok") is None else "✗")

        score = res_texto.get("score", "")
        score_str = f"  score={score}" if score != "" else ""
        print(f"  {ean}  texto:{flag_t}{score_str}  imagem:{flag_i}  {(nome or '')[:50]}")

        motivo = "; ".join(filter(None, [
            res_texto.get("motivo", ""),
            res_img.get("resposta", "") or res_img.get("motivo", ""),
        ]))
        conferencia = (
            "ok" if (res_texto.get("ok") and res_img.get("ok"))
            else "parcial" if (res_texto.get("ok") or res_img.get("ok"))
            else "falhou"
        )
        con.execute(
            "UPDATE enriquecimento_ean SET conferencia=?, conf_motivo=? WHERE ean=?",
            (conferencia, motivo, ean),
        )

    con.commit()
    print("\nConferência concluída.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Confere dados extraídos por EAN.")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("listar", help="Exibe nome e descrição de cada EAN (scraping + Mintel)")
    sub.add_parser("conferir", help="Confronto textual + validação de imagem (requer ANTHROPIC_API_KEY)")
    args = parser.parse_args()

    con = sqlite3.connect(DB_PATH)

    if args.cmd == "conferir":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Erro: defina ANTHROPIC_API_KEY no ambiente.")
            con.close()
            return
        cmd_conferir(con, anthropic.Anthropic(api_key=api_key))
    else:
        cmd_listar(con)

    con.close()


if __name__ == "__main__":
    main()
