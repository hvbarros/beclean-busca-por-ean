import sqlite3
import openpyxl
from datetime import datetime

XLSX_PATH = "mintel.xlsx"
DB_PATH = "mintel.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS produtos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_barras       TEXT,
    produto             TEXT,
    variante_produto    TEXT,
    marca               TEXT,
    marca_be_clean      TEXT,
    empresa_principal   TEXT,
    categoria           TEXT,
    sub_categoria       TEXT,
    descricao_produto   TEXT,
    posicionamento      TEXT,
    ingredientes        TEXT,
    fragrancias         TEXT,
    formatos_texturas   TEXT,
    tipo_formato        TEXT,
    data_publicacao     TEXT,
    imagem_url          TEXT,
    registar_link       TEXT,
    alergenos_avisos    TEXT
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_codigo_barras ON produtos (codigo_barras);
"""

INSERT_SQL = """
INSERT INTO produtos (
    codigo_barras, produto, variante_produto, marca, marca_be_clean,
    empresa_principal, categoria, sub_categoria, descricao_produto,
    posicionamento, ingredientes, fragrancias, formatos_texturas,
    tipo_formato, data_publicacao, imagem_url, registar_link, alergenos_avisos
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def normalize_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def load():
    print(f"Lendo {XLSX_PATH}...")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb["Base analisada"]

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(CREATE_TABLE + CREATE_INDEX)

    batch = []
    skipped = 0
    inserted = 0

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
        (
            codigo_barras, produto, variante_produto, marca, marca_be_clean,
            empresa_principal, categoria, sub_categoria, descricao_produto,
            posicionamento, ingredientes, fragrancias, formatos_texturas,
            tipo_formato, data_publicacao, imagem_url, registar_link, alergenos_avisos,
            *_extra
        ) = (*row, *([None] * 18))  # pad to at least 18 fields

        if codigo_barras is None and produto is None:
            skipped += 1
            continue

        batch.append((
            str(codigo_barras).strip() if codigo_barras is not None else None,
            produto, variante_produto, marca, marca_be_clean,
            empresa_principal, categoria, sub_categoria, descricao_produto,
            posicionamento, ingredientes, fragrancias, formatos_texturas,
            tipo_formato, normalize_date(data_publicacao),
            imagem_url, registar_link, alergenos_avisos,
        ))

        if len(batch) >= 1000:
            cur.executemany(INSERT_SQL, batch)
            inserted += len(batch)
            batch.clear()
            print(f"  {inserted} linhas inseridas...", end="\r")

    if batch:
        cur.executemany(INSERT_SQL, batch)
        inserted += len(batch)

    con.commit()
    con.close()
    print(f"\nConcluído: {inserted} linhas inseridas, {skipped} ignoradas.")
    print(f"Banco salvo em: {DB_PATH}")


if __name__ == "__main__":
    load()
