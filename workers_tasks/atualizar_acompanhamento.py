#!/usr/bin/env python3
"""
Atualiza o acompanhamento de workers BeClean.

Equivalente ao skill /gerar-acompanhamento-workers — faz tudo via API:
  1. Descobre workers dinamicamente no Drive (pasta beclean_workers)
  2. Lê planilhas de controle de cada worker
  3. Atualiza planilha consolidada ean_aprovados
  4. Verifica evidências no Drive
  5. Gera build/resultados/index.html
  6. Publica via Wrangler R2
  7. Exibe resumo

Uso:
    python3 atualizar_acompanhamento.py [--skip-evidencias] [--skip-publish]

Dependências externas:
    gws   (google-workspace-scripts CLI, autenticado)
    wrangler  (Cloudflare CLI, autenticado)
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

DRIVE_ESPELHO = Path("/Users/hbarros/Library/CloudStorage/GoogleDrive-hbarros@baselabs.com.br/Drives compartilhados/baselabs-projetos/ativos/beclean_workers")

# ── Constantes ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent

EAN_APROVADOS_SHEET_ID = "1bNrzG38HFx9pBLTkDVUgviw1dJjpHhY62muml0RYbGA"
R2_OBJECT_KEY = "propostas/beclean/instrucoes_workers/resultados/index.html"
PUBLISH_URL = "https://propostas.baselabs.com.br/beclean/instrucoes_workers/resultados/"

TEMPLATE_EAN = "7891100000000"  # linha de exemplo do template (Natura)
RESULTADOS_VALIDOS = {"Aprovado", "Aprovado em lote", "Enviado para revisão", "Já estava revisado"}

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}


# ── Helpers de CLI ────────────────────────────────────────────────────────────

def gws(subcommand: str, params: dict | None = None, json_body: dict | None = None) -> dict:
    """Chama `gws <subcommand> [--params ...] [--json ...]` e retorna o JSON parseado."""
    cmd = ["gws"] + subcommand.split()
    if params:
        cmd += ["--params", json.dumps(params, ensure_ascii=False)]
    if json_body:
        cmd += ["--json", json.dumps(json_body, ensure_ascii=False)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gws falhou: {result.stderr.strip()}\nComando: {' '.join(cmd)}")
    text = result.stdout.strip()
    if not text:
        return {}
    return json.loads(text)


def humanize_worker(folder_name: str) -> str:
    """'paula_machado_alves__2026-05' → 'Paula Machado Alves'"""
    base = folder_name.split("__")[0]
    return " ".join(p.capitalize() for p in base.split("_"))


def data_hoje_ptbr() -> str:
    from datetime import datetime
    agora = datetime.now()
    return f"{agora.day} de {MESES_PT[agora.month]} de {agora.year} às {agora.hour:02d}:{agora.minute:02d}"


def data_hoje_ddmmaaaa() -> str:
    d = date.today()
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


# ── Passo 1 — descobrir workers ───────────────────────────────────────────────

def descobrir_workers() -> list[dict]:
    """Retorna lista de dicts com chaves: nome, folder_id"""
    print("→ Buscando pasta beclean_workers…")
    res = gws("drive files list", params={
        "q": 'name = "beclean_workers" and mimeType = "application/vnd.google-apps.folder"',
        "fields": "files(id,name)",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
    })
    files = res.get("files", [])
    if not files:
        raise RuntimeError("Pasta beclean_workers não encontrada no Drive.")
    root_id = files[0]["id"]

    print("→ Listando subpastas de workers…")
    res = gws("drive files list", params={
        "q": f'"{root_id}" in parents and mimeType = "application/vnd.google-apps.folder"',
        "fields": "files(id,name)",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
        "pageSize": 100,
    })
    workers = []
    for f in res.get("files", []):
        if f["name"] == "_TEMPLATE" or f["name"].startswith("DESATIVADO"):
            continue
        workers.append({
            "nome": humanize_worker(f["name"]),
            "folder_id": f["id"],
            "folder_name": f["name"],
        })
    print(f"   {len(workers)} workers encontrados.")
    return workers


# ── Passo 2 — ler planilhas ───────────────────────────────────────────────────

def encontrar_planilha(worker: dict) -> tuple[str | None, str | None]:
    """Retorna (spreadsheetId, createdTime ISO) da planilha de controle do worker."""
    res = gws("drive files list", params={
        "q": f'"{worker["folder_id"]}" in parents',
        "fields": "files(id,name,mimeType,createdTime)",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
    })
    for f in res.get("files", []):
        if f["mimeType"] == "application/vnd.google-apps.spreadsheet":
            return f["id"], f.get("createdTime")
    return None, None


def ler_planilha(sheet_id: str) -> list[list[str]]:
    """Lê A1:J300 da planilha e retorna lista de linhas."""
    res = gws("sheets spreadsheets values get", params={
        "spreadsheetId": sheet_id,
        "range": "A1:J5000",
    })
    return res.get("values", [])


def _ean_suspeito(ean: str) -> str | None:
    """Retorna descrição do problema se o EAN parecer inválido, None se OK."""
    digitos = re.sub(r"\D", "", ean)
    if len(digitos) < 8:
        return f"apenas {len(digitos)} dígito(s)"
    if len(digitos) not in (8, 12, 13, 14):
        return f"{len(digitos)} dígitos (esperado 8, 12, 13 ou 14)"
    # placeholder óbvio: todos zeros, todos iguais, ou sequência 123...
    if len(set(digitos)) == 1:
        return "todos os dígitos iguais (possível placeholder)"
    if digitos in ("12345678", "1234567890123", "123456789012"):
        return "sequência numérica óbvia (possível placeholder)"
    return None


def parse_planilha(rows: list[list[str]], worker_nome: str) -> dict:
    """
    Extrai métricas e lista de EANs aprovados da planilha.

    A planilha pode ter dois layouts:
      Layout padrão: Data | Tarefa | Marca | Produto | EAN | Resultado | ...
      Layout Paula:  Data | Tarefa | Marca | Produto | EAN | Resultado | Motivo | HorInicio | HorFim | Tempo...
    Em ambos, EAN está em col[4] e Resultado em col[5].
    """
    total = aprovados = revisao = ja_revisado = invalido = sem_resultado = 0
    marcas_set = set()
    eans_aprovados = []       # lista de (ean, marca, produto, resultado)
    eans_revisao = []         # lista de (ean, marca, produto)
    eans_ja_revisado = []     # lista de (ean, marca, produto)
    eans_sem_resultado = []   # lista de (ean, marca, produto)
    eans_invalidos = []       # lista de (ean, marca, produto, resultado_digitado)
    eans_suspeitos = []       # lista de (ean, marca, produto, motivo)

    for row in rows:
        if len(row) < 5:
            continue
        ean = row[4].strip() if len(row) > 4 else ""
        if not ean or ean == TEMPLATE_EAN:
            continue
        # Normaliza zeros à esquerda em EANs puramente numéricos
        # (ex: "0309970175115" → "309970175115")
        if re.fullmatch(r"\d+", ean):
            ean = ean.lstrip("0") or ean
        # ignora linhas onde col[0] é cabeçalho
        if row[0].strip().lower() in ("data", "#"):
            continue

        total += 1
        marca = row[2].strip() if len(row) > 2 else ""
        produto = row[3].strip() if len(row) > 3 else ""
        resultado = row[5].strip() if len(row) > 5 else ""

        if marca and marca not in ("Natura",):
            marcas_set.add(marca)

        # Valida formato do EAN — só marca como suspeito se ainda sem resultado
        motivo_suspeito = _ean_suspeito(ean)
        resultado_temp = row[5].strip() if len(row) > 5 else ""
        tem_resultado = resultado_temp in ("Aprovado", "Aprovado em lote", "Enviado para revisão", "Já estava revisado", "Match Down")
        if motivo_suspeito and not tem_resultado:
            eans_suspeitos.append((ean, marca, produto, motivo_suspeito))

        if resultado in ("Aprovado", "Aprovado em lote"):
            aprovados += 1
            eans_aprovados.append((ean, marca, produto, resultado))
        elif resultado == "Enviado para revisão":
            revisao += 1
            eans_revisao.append((ean, marca, produto))
        elif resultado == "Já estava revisado":
            ja_revisado += 1
            eans_ja_revisado.append((ean, marca, produto))
        elif resultado:
            invalido += 1
            eans_invalidos.append((ean, marca, produto, resultado))
        else:
            sem_resultado += 1
            eans_sem_resultado.append((ean, marca, produto))

    # Status da planilha
    if total == 0:
        status_planilha = "ruim"
    elif invalido > 0 or sem_resultado > 0 or eans_suspeitos:
        status_planilha = "alerta"
    else:
        status_planilha = "ok"

    marcas_sorted = sorted(marcas_set, key=lambda m: m.lower())

    return {
        "total": total,
        "aprovados": aprovados,
        "revisao": revisao,
        "ja_revisado": ja_revisado,
        "invalido": invalido,
        "sem_resultado": sem_resultado,
        "marcas": marcas_sorted,
        "status_planilha": status_planilha,
        "eans_aprovados": eans_aprovados,
        "eans_revisao": eans_revisao,
        "eans_ja_revisado": eans_ja_revisado,
        "eans_sem_resultado": eans_sem_resultado,
        "eans_invalidos": eans_invalidos,
        "eans_suspeitos": eans_suspeitos,
    }


def dias_corridos(created_time_iso: str | None) -> float | None:
    """Retorna dias corridos (com fração de hora) desde a criação da planilha até agora."""
    if not created_time_iso:
        return None
    from datetime import datetime, timezone
    criado = datetime.fromisoformat(created_time_iso.replace("Z", "+00:00"))
    agora = datetime.now(timezone.utc)
    delta = (agora - criado).total_seconds() / 86400
    return max(round(delta, 2), 0.01)


def coletar_dados_planilhas(workers: list[dict]) -> None:
    """Lê todas as planilhas e popula worker['dados'] em cada item."""
    print("→ Lendo planilhas de controle…")
    for i, w in enumerate(workers, 1):
        print(f"   [{i}/{len(workers)}] {w['nome']}…", flush=True)
        sheet_id, created_time = encontrar_planilha(w)
        if not sheet_id:
            print(f"   ⚠  {w['nome']}: planilha não encontrada")
            w["sheet_id"] = None
            w["dados"] = {
                "total": 0, "aprovados": 0, "revisao": 0,
                "ja_revisado": 0, "invalido": 0, "sem_resultado": 0,
                "marcas": [], "status_planilha": "ruim",
                "eans_aprovados": [], "eans_sem_resultado": [], "eans_invalidos": [],
                "eans_suspeitos": [],
                "dias_corridos": None, "vazao": None,
            }
            continue
        w["sheet_id"] = sheet_id
        rows = ler_planilha(sheet_id)
        w["dados"] = parse_planilha(rows, w["nome"])
        d = w["dados"]
        dias = dias_corridos(created_time)
        d["dias_corridos"] = dias
        d["vazao"] = round(d["total"] / dias, 1) if dias and d["total"] > 0 else None
        print(f"   ✓  {w['nome']}: {d['total']} produtos, "
              f"{d['aprovados']} aprov, {d['revisao']} rev, "
              f"{d['sem_resultado']} sem resultado, "
              f"vazão {d['vazao']} prod/dia ({dias}d)")


# ── Passo 3 — atualizar ean_aprovados ────────────────────────────────────────

def atualizar_ean_aprovados(workers: list[dict]) -> int:
    """Reescreve a planilha ean_aprovados com todos os EANs aprovados. Retorna total."""
    print("→ Atualizando planilha ean_aprovados…")

    todas_linhas: list[tuple] = []
    for w in workers:
        for ean, marca, produto, resultado in w["dados"]["eans_aprovados"]:
            todas_linhas.append((ean, marca, produto, resultado, w["nome"]))

    todas_linhas.sort(key=lambda x: (x[4], x[0]))

    data_hoje = data_hoje_ddmmaaaa()
    header = ["EAN", "Marca", "Produto", "Resultado", "Worker", "Data"]
    todas_rows = [header] + [list(r) + [data_hoje] for r in todas_linhas]
    total = len(todas_linhas)

    # Limpa o intervalo atual antes de gravar (evita sobras de execuções anteriores)
    ultimo_row = max(total + 1, 2)
    gws("sheets spreadsheets values clear",
        params={
            "spreadsheetId": EAN_APROVADOS_SHEET_ID,
            "range": f"A1:F{ultimo_row + 50}",
        },
        json_body={},
    )

    # Grava em lotes de 100 linhas para evitar payload excessivo no CLI
    LOTE = 100
    n_lotes = (len(todas_rows) + LOTE - 1) // LOTE
    for i in range(0, len(todas_rows), LOTE):
        lote = todas_rows[i:i + LOTE]
        row_inicio = i + 1  # A1 = row 1
        lote_num = i // LOTE + 1
        print(f"   … gravando lote {lote_num}/{n_lotes} (linhas {row_inicio}–{row_inicio + len(lote) - 1})")
        gws("sheets spreadsheets values update",
            params={
                "spreadsheetId": EAN_APROVADOS_SHEET_ID,
                "range": f"A{row_inicio}",
                "valueInputOption": "RAW",
            },
            json_body={"values": lote},
        )

    print(f"   ✓  {total} EANs gravados em ean_aprovados.")
    return total


# ── Passo 4 — verificar evidências (via espelho local do Drive) ───────────────

def checar_evidencias_worker(worker: dict) -> dict:
    """
    Verifica estrutura evidencias/ > [Marca]/ > [EAN]/ > screenshots/
    usando o espelho local do Google Drive em DRIVE_ESPELHO.
    """
    dados = worker["dados"]
    nome = worker["nome"]

    try:
        return _checar_evidencias_worker_impl(worker)
    except TimeoutError as e:
        path = str(e).split("'")[-2] if "'" in str(e) else str(e)
        print(f"      ⚠  timeout ao acessar Drive — pasta ainda sincronizando: {path}")
        return {
            "com_evidencia": 0,
            "status_evidencias": "alerta",
            "notas": ["Timeout ao acessar Drive — pasta ainda sincronizando"],
            "eans_sem_screenshots": [], "eans_sem_pasta": [],
        }


def _checar_evidencias_worker_impl(worker: dict) -> dict:
    dados = worker["dados"]
    nome = worker["nome"]

    if dados["total"] == 0:
        print(f"      sem produtos — pulando")
        return {"com_evidencia": 0, "status_evidencias": "ruim", "notas": [],
                "eans_sem_screenshots": [], "eans_sem_pasta": []}

    pasta_worker = DRIVE_ESPELHO / worker["folder_name"]
    pasta_ev = pasta_worker / "evidencias"

    if not pasta_ev.is_dir():
        print(f"      ⚠  pasta evidencias/ não encontrada")
        return {
            "com_evidencia": 0,
            "status_evidencias": "ruim",
            "notas": ["Pasta <code>evidencias</code> não encontrada"],
            "eans_sem_screenshots": [], "eans_sem_pasta": [],
        }

    marcas = sorted(p for p in pasta_ev.iterdir() if p.is_dir())
    print(f"      {len(marcas)} marca(s): {', '.join(m.name for m in marcas)}")

    # Corrige nomes de subpastas de screenshots escritos de forma errada
    def _parece_screenshots(nome: str) -> bool:
        """True se o nome é parecido com 'screenshots' (distância de edição <= 3)."""
        a, b = nome.lower(), "screenshots"
        if abs(len(a) - len(b)) > 3:
            return False
        # Levenshtein iterativo
        prev = list(range(len(b) + 1))
        for ch in a:
            curr = [prev[0] + 1]
            for j, bch in enumerate(b):
                curr.append(min(prev[j] + (0 if ch == bch else 1), curr[-1] + 1, prev[j + 1] + 1))
            prev = curr
        return prev[-1] <= 3

    # Corrige pastas de EAN com prefixo "EAN " (ex: "EAN 7891234567890" → "7891234567890")
    prefixos_corrigidos = 0
    for pasta_marca in marcas:
        for pasta_ean in list(pasta_marca.iterdir()):
            if not pasta_ean.is_dir(): continue
            novo_nome = re.sub(r'^EAN\s+', '', pasta_ean.name, flags=re.I).strip()
            if novo_nome != pasta_ean.name:
                destino = pasta_ean.parent / novo_nome
                pasta_ean.rename(destino)
                print(f"         ✏  '{pasta_ean.name}' → '{novo_nome}'")
                prefixos_corrigidos += 1
    if prefixos_corrigidos:
        print(f"      ✏  {prefixos_corrigidos} pasta(s) de EAN com prefixo corrigida(s)")
        # Recarrega marcas após renomeações
        marcas = sorted(p for p in pasta_ev.iterdir() if p.is_dir())

    renomeadas = 0
    for pasta_marca in marcas:
        for pasta_ean in (p for p in pasta_marca.iterdir() if p.is_dir()):
            for sub in list(pasta_ean.iterdir()):
                if sub.is_dir() and sub.name != 'screenshots' and _parece_screenshots(sub.name):
                    tmp = sub.parent / '__tmp_ss'
                    sub.rename(tmp)
                    tmp.rename(sub.parent / 'screenshots')
                    print(f"         ✏  {pasta_ean.name}: '{sub.name}' → 'screenshots'")
                    renomeadas += 1
    if renomeadas:
        print(f"      ✏  {renomeadas} pasta(s) de screenshots corrigida(s)")

    # Move imagens soltas na pasta do EAN para screenshots/
    EXTS_IMAGEM = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".heic"}
    movidas = 0
    for pasta_marca in marcas:
        for pasta_ean in (p for p in pasta_marca.iterdir() if p.is_dir()):
            imagens_soltas = [
                f for f in pasta_ean.iterdir()
                if f.is_file() and f.suffix.lower() in EXTS_IMAGEM
            ]
            if imagens_soltas:
                pasta_ss = pasta_ean / "screenshots"
                pasta_ss.mkdir(exist_ok=True)
                for img in imagens_soltas:
                    img.rename(pasta_ss / img.name)
                    movidas += 1
                print(f"         ✏  {pasta_ean.name}: {len(imagens_soltas)} imagem(ns) movida(s) → screenshots/")
    if movidas:
        print(f"      ✏  {movidas} imagem(ns) solta(s) movida(s) para screenshots/")

    com_evidencia = 0
    sem_screenshots: list[tuple[str, str, str]] = []  # (marca, ean, motivo)

    def _validar_ordem_screenshots(arquivos: list) -> str | None:
        """
        Retorna None se os screenshots estão ordenáveis, ou uma string descrevendo o problema.
        Critérios (qualquer um que passe = OK):
          1. Todos os nomes começam com dígitos ou data (ordenação por nome garantida)
          2. Todos os mtimes são distintos (ordenação por data de modificação possível)
          3. Todos têm nomes descritivos (>= 4 letras não-numéricas no stem = intencionais)
        Com um único arquivo não há ordem a verificar → sempre OK.
        """
        if len(arquivos) <= 1:
            return None
        stems = [f.stem for f in arquivos]
        # Critério 1: nome começa com dígito ou data (AAAA-MM-DD)
        if all(re.match(r"^\d", s) for s in stems):
            return None
        # Critério 2: mtimes todos distintos
        mtimes = [f.stat().st_mtime for f in arquivos]
        if len(set(mtimes)) == len(mtimes):
            return None
        # Critério 3: nomes descritivos (stem tem >= 4 letras)
        if all(len(re.sub(r"[^a-zA-ZÀ-ú]", "", s)) >= 4 for s in stems):
            return None
        return "screenshots sem ordem verificável (nomes não numerados, mtimes iguais e nomes sem descrição)"

    for pasta_marca in marcas:
        eans = sorted(p for p in pasta_marca.iterdir() if p.is_dir())
        ok_marca = 0
        nome_marca = pasta_marca.name
        print(f"      📁 {nome_marca} ({len(eans)} EANs)")

        for pasta_ean in eans:
            nome_ean = pasta_ean.name
            pasta_ss = next(
                (p for p in pasta_ean.iterdir()
                 if p.is_dir() and re.search(r"screenshot", p.name, re.I)),
                None,
            )
            if pasta_ss:
                arquivos = [f for f in pasta_ss.iterdir() if f.is_file()]
                if arquivos:
                    prob_ordem = _validar_ordem_screenshots(arquivos)
                    com_evidencia += 1
                    ok_marca += 1
                    if prob_ordem:
                        sem_screenshots.append((nome_marca, nome_ean, prob_ordem))
                        print(f"         ⚠  {nome_ean} ({len(arquivos)} arquivo(s)) — {prob_ordem}")
                    else:
                        print(f"         ✓  {nome_ean} ({len(arquivos)} arquivo(s))")
                else:
                    sem_screenshots.append((nome_marca, nome_ean, "screenshots/ vazia"))
                    print(f"         ⚠  {nome_ean} — screenshots/ vazia")
            else:
                arquivos = [f for f in pasta_ean.iterdir() if f.is_file()]
                videos = [f for f in arquivos if f.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"}]
                if videos:
                    com_evidencia += 1
                    ok_marca += 1
                    print(f"         ✓  {nome_ean} (vídeo: {videos[0].name})")
                else:
                    sem_screenshots.append((nome_marca, nome_ean, "sem evidência"))
                    if arquivos:
                        print(f"         ⚠  {nome_ean} — sem screenshots e sem vídeo ({len(arquivos)} arquivo(s) ignorado(s))")
                    else:
                        print(f"         ⚠  {nome_ean} — sem evidência")

    # Cruzamento: EANs com resultado na planilha sem pasta correspondente no Drive
    # Só considera EANs que já foram trabalhados (têm resultado) — sem_resultado ainda não foram processados
    # Normaliza nomes de pastas removendo zeros à esquerda para comparação
    # (worker pode salvar como "0309970175115" mas planilha tem "309970175115")
    eans_drive_raw = {p.name for m in marcas for p in m.iterdir() if p.is_dir()}
    eans_drive = {e.lstrip("0") or e: e for e in eans_drive_raw}  # norm → original
    # "Já estava revisado" não exige evidência — produto não foi conferido do zero
    eans_com_resultado = (
        worker["dados"].get("eans_aprovados", [])
        + [(e, m, p, "") for e, m, p in worker["dados"].get("eans_revisao", [])]
        + worker["dados"].get("eans_invalidos", [])
        + [(e, m, p, "") for e, m, p, _ in worker["dados"].get("eans_suspeitos", [])]
    )
    eans_planilha_uniq = {t[0]: t for t in eans_com_resultado}
    eans_sem_pasta = [
        (ean, t[1], t[2])
        for ean, t in eans_planilha_uniq.items()
        if ean.lstrip("0") not in eans_drive
    ]
    if eans_sem_pasta:
        print(f"      ⚠  {len(eans_sem_pasta)} EAN(s) na planilha sem pasta no Drive:")
        for ean, marca, produto in eans_sem_pasta:
            print(f"         ✗  {ean} — {marca} — {produto}")

    notas = []
    if sem_screenshots:
        n = len(sem_screenshots)
        notas.append(f"{n} EAN{'s' if n > 1 else ''} sem evidência confirmada")

    total = dados["total"]
    pct = round(com_evidencia / total * 100) if total else 0
    if pct == 100:
        status = "ok"
    elif pct >= 50:
        status = "alerta"
    else:
        status = "ruim"

    return {
        "com_evidencia": com_evidencia,
        "status_evidencias": status,
        "notas": notas,
        "eans_sem_screenshots": sem_screenshots,
        "eans_sem_pasta": eans_sem_pasta,
    }


def verificar_evidencias(workers: list[dict]) -> None:
    print("→ Verificando evidências (espelho local)…")
    for i, w in enumerate(workers, 1):
        total = w["dados"]["total"]
        print(f"   [{i}/{len(workers)}] {w['nome']} ({total} produtos)")
        ev = checar_evidencias_worker(w)
        w["dados"].update(ev)
        pct = round(ev["com_evidencia"] / total * 100) if total else 0
        print(f"      → {ev['com_evidencia']}/{total} ({pct}%) — {ev['status_evidencias']}")


def evidencias_estimadas(worker: dict) -> None:
    """Fallback: preenche evidências com valores neutros quando --skip-evidencias."""
    d = worker["dados"]
    d.setdefault("com_evidencia", 0)
    d.setdefault("status_evidencias", "alerta")
    d.setdefault("notas", ["Verificação de evidências não executada nesta rodada"])


# ── Passo 5 — gerar HTML ──────────────────────────────────────────────────────

def computar_avaliacao(w: dict) -> str:
    d = w["dados"]
    nome = w["nome"]
    if d["total"] == 0:
        return "Sem produtos registrados ainda"
    partes = [f"{d['total']} produtos"]
    if d["sem_resultado"] > 0:
        partes.append(f"⚠ {d['sem_resultado']} sem resultado")
    if d["aprovados"] > 0:
        pct_aprov = round(d["aprovados"] / d["total"] * 100)
        partes.append(f"{d['aprovados']} aprovados ({pct_aprov}%)")
    if d["sem_resultado"] == 0 and d["invalido"] == 0:
        partes.append("resultado 100% preenchido")
    return ", ".join(partes)


def montar_workers_list(workers: list[dict]) -> list[dict]:
    """Converte a lista de workers (com dados) para o formato esperado pelo HTML."""
    # Ordenar: total decrescente; empate = alfabético por nome
    ativos = [w for w in workers if w["dados"]["total"] > 0]
    inativos = [w for w in workers if w["dados"]["total"] == 0]
    ativos.sort(key=lambda w: (-w["dados"]["total"], w["nome"]))
    inativos.sort(key=lambda w: w["nome"])

    result = []
    rank = 1
    for w in ativos:
        d = w["dados"]
        marcas_str = ", ".join(d["marcas"]) if d["marcas"] else "—"
        result.append({
            "rank": rank,
            "nome": w["nome"],
            "marcas": marcas_str,
            "planilha": d["status_planilha"],
            "evidencias": d.get("status_evidencias", "alerta"),
            "avaliacao": computar_avaliacao(w),
            "total": d["total"],
            "aprovados": d["aprovados"],
            "revisao": d["revisao"],
            "ja_revisado": d.get("ja_revisado", 0),
            "invalido": d["invalido"],
            "sem_resultado": d["sem_resultado"],
            "com_evidencia": d.get("com_evidencia", 0),
            "dias_corridos": d.get("dias_corridos"),
            "vazao": d.get("vazao"),
            "notas": d.get("notas", []),
            "eans_sem_resultado": d.get("eans_sem_resultado", []),
            "eans_invalidos": d.get("eans_invalidos", []),
            "eans_sem_screenshots": d.get("eans_sem_screenshots", []),
            "eans_sem_pasta": d.get("eans_sem_pasta", []),
            "eans_suspeitos": d.get("eans_suspeitos", []),
        })
        rank += 1

    rank_inativos = rank
    for w in inativos:
        result.append({
            "rank": rank_inativos,
            "nome": w["nome"],
            "marcas": "—",
            "planilha": "ruim",
            "evidencias": "ruim",
            "avaliacao": "Sem produtos registrados ainda",
            "total": 0, "aprovados": 0, "revisao": 0,
            "ja_revisado": 0, "invalido": 0, "sem_resultado": 0, "com_evidencia": 0,
            "dias_corridos": None, "vazao": None,
            "notas": [],
            "eans_sem_resultado": [], "eans_invalidos": [], "eans_sem_screenshots": [],
            "eans_sem_pasta": [], "eans_suspeitos": [],
        })

    return result


# ── HTML idêntico ao build_resultados.py ─────────────────────────────────────

STATUS_CSS = {"ok": "badge-ok", "alerta": "badge-alerta", "ruim": "badge-ruim"}
STATUS_LABEL = {"ok": "ok", "alerta": "atenção", "ruim": "pendente"}


def badge(status: str) -> str:
    css = STATUS_CSS.get(status, "")
    label = STATUS_LABEL.get(status, status)
    return f'<span class="badge {css}">{label}</span>'


def erros_html(w: dict) -> str:
    """Soma de todos os problemas de evidência e preenchimento."""
    n = (
        len(w.get("eans_sem_resultado", []))
        + len(w.get("eans_invalidos", []))
        + len(w.get("eans_sem_screenshots", []))
        + len(w.get("eans_sem_pasta", []))
        + len(w.get("eans_suspeitos", []))
    )
    if n == 0:
        return '<span class="val-nd">—</span>'
    return f'<span class="val-ruim erros-badge">{n}</span>'


def evidencias_prop_html(w: dict) -> str:
    """Proporção encontradas/esperadas com badge de cor."""
    esperado = w["total"]
    encontrado = w.get("com_evidencia", 0)
    if esperado == 0:
        return '<span class="val-nd">—</span>'
    if encontrado > esperado:
        # mais evidências que produtos é também um problema
        css = "val-alerta"
    elif encontrado == esperado:
        css = "val-ok"
    elif encontrado / esperado >= 0.5:
        css = "val-alerta"
    else:
        css = "val-ruim"
    return f'<span class="{css}">{encontrado}/{esperado}</span>'


def vazao_html(w: dict) -> str:
    v = w.get("vazao")
    d = w.get("dias_corridos")
    if v is None:
        return '<span class="val-nd">—</span>'
    title = f"{round(d, 1)} dias corridos" if d else ""
    return f'<span class="col-vazao-val" title="{title}">{v}</span>'


def val_html(n: int | str, *, ruim_se_zero=False, nd_se_zero=False) -> str:
    if nd_se_zero and n == 0:
        return '<span class="val-nd">—</span>'
    if ruim_se_zero and n == 0:
        return f'<span class="val-ruim">{n}</span>'
    return str(n)


NCOLS = 10


def _agrupar_por_marca_html(itens_por_marca: dict[str, list[str]]) -> str:
    """Renderiza grupos de EANs organizados por marca."""
    partes = []
    for marca in sorted(itens_por_marca):
        eans_html = "".join(itens_por_marca[marca])
        partes.append(
            f'<div class="prob-grupo">'
            f'<span class="prob-grupo-marca">{marca}</span>'
            f'<ul class="prob-list">{eans_html}</ul>'
            f'</div>'
        )
    return "".join(partes)


def _detalhes_html(w: dict) -> str:
    """Gera o bloco <details> colapsável com marcas e EANs com problema."""
    secoes = []

    # Marcas
    if w["marcas"] and w["marcas"] != "—":
        secoes.append(
            f'<div class="det-secao">'
            f'<span class="det-label">marcas</span>'
            f'<span class="det-marcas">{w["marcas"]}</span>'
            f'</div>'
        )

    # EANs sem resultado — agrupados por marca
    sem_res = w.get("eans_sem_resultado", [])
    if sem_res:
        grupos: dict[str, list[str]] = {}
        for ean, marca, produto in sem_res:
            grupos.setdefault(marca, []).append(
                f'<li><code>{ean}</code>'
                f'<span class="prob-produto">{produto}</span></li>'
            )
        secoes.append(
            f'<div class="det-secao">'
            f'<span class="det-label prob-label-ruim">sem resultado ({len(sem_res)})</span>'
            f'{_agrupar_por_marca_html(grupos)}</div>'
        )

    # EANs com resultado inválido — agrupados por marca
    invalidos = w.get("eans_invalidos", [])
    if invalidos:
        grupos = {}
        for ean, marca, produto, resultado in invalidos:
            grupos.setdefault(marca, []).append(
                f'<li><code>{ean}</code>'
                f'<span class="prob-produto">{produto}</span>'
                f'<span class="prob-valor">→ "{resultado}"</span></li>'
            )
        secoes.append(
            f'<div class="det-secao">'
            f'<span class="det-label prob-label-ruim">resultado inválido ({len(invalidos)})</span>'
            f'{_agrupar_por_marca_html(grupos)}</div>'
        )

    # EANs sem screenshots ou com problema de ordem — agrupados por marca
    sem_ss = w.get("eans_sem_screenshots", [])
    if sem_ss:
        grupos = {}
        for marca, ean, motivo in sem_ss:
            grupos.setdefault(marca, []).append(
                f'<li><code>{ean}</code>'
                f'<span class="prob-valor">{motivo}</span></li>'
            )
        secoes.append(
            f'<div class="det-secao">'
            f'<span class="det-label prob-label-alerta">evidência com problema ({len(sem_ss)})</span>'
            f'{_agrupar_por_marca_html(grupos)}</div>'
        )

    # EANs na planilha sem pasta no Drive — agrupados por marca
    sem_pasta = w.get("eans_sem_pasta", [])
    if sem_pasta:
        grupos = {}
        for ean, marca, produto in sem_pasta:
            grupos.setdefault(marca, []).append(
                f'<li><code>{ean}</code>'
                f'<span class="prob-produto">{produto}</span></li>'
            )
        secoes.append(
            f'<div class="det-secao">'
            f'<span class="det-label prob-label-alerta">na planilha sem pasta no Drive ({len(sem_pasta)})</span>'
            f'{_agrupar_por_marca_html(grupos)}</div>'
        )

    # EANs com formato suspeito — agrupados por marca
    suspeitos = w.get("eans_suspeitos", [])
    if suspeitos:
        grupos = {}
        for ean, marca, produto, motivo in suspeitos:
            grupos.setdefault(marca, []).append(
                f'<li><code>{ean}</code>'
                f'<span class="prob-produto">{produto}</span>'
                f'<span class="prob-valor">→ {motivo}</span></li>'
            )
        secoes.append(
            f'<div class="det-secao">'
            f'<span class="det-label prob-label-ruim">EAN suspeito ({len(suspeitos)})</span>'
            f'{_agrupar_por_marca_html(grupos)}</div>'
        )

    if not secoes:
        return ""

    n_problemas = len(sem_res) + len(invalidos) + len(sem_ss) + len(sem_pasta) + len(suspeitos)
    summary_label = f"detalhes · {n_problemas} problema{'s' if n_problemas != 1 else ''}" if n_problemas else "detalhes"

    return (
        f'<details class="row-details">'
        f'<summary class="det-summary">{summary_label}</summary>'
        f'<div class="det-body">{"".join(secoes)}</div>'
        f'</details>'
    )


def tabela_rows_html(workers_list: list[dict], totais: dict) -> str:
    rows = ""
    for w in workers_list:
        detalhes = _detalhes_html(w)
        rows += f"""
  <tr>
    <td class="col-rank">#{w["rank"]}</td>
    <td class="col-nome"><strong>{w["nome"]}</strong></td>
    <td class="col-erros">{erros_html(w)}</td>
    <td class="col-num">{val_html(w["total"], ruim_se_zero=True)}</td>
    <td class="col-num">{val_html(w["aprovados"], nd_se_zero=True)}</td>
    <td class="col-num">{val_html(w["revisao"], nd_se_zero=True)}{' <sup class="badge-invalido" title="+ resultado inválido">+inv</sup>' if w.get("invalido") else ""}</td>
    <td class="col-num">{val_html(w.get("ja_revisado", 0), nd_se_zero=True)}</td>
    <td class="col-num">{val_html(w["sem_resultado"], ruim_se_zero=True, nd_se_zero=False) if w["sem_resultado"] > 0 else val_html(0, nd_se_zero=True)}</td>
    <td class="col-vazao">{vazao_html(w)}</td>
    <td class="col-ev">{evidencias_prop_html(w)}</td>
  </tr>"""

        if detalhes:
            rows += f"""
  <tr class="row-details-wrap">
    <td></td>
    <td colspan="{NCOLS - 1}">{detalhes}</td>
  </tr>"""

    tot_ev = totais.get("com_evidencia", 0)
    tot_total = totais["total"]
    ev_css = "val-ok" if tot_ev == tot_total and tot_total > 0 else ("val-alerta" if tot_total and tot_ev / tot_total >= 0.5 else "val-ruim")
    rows += f"""
  <tr class="row-total">
    <td class="col-rank"></td>
    <td class="col-nome"><strong>Total</strong></td>
    <td class="col-erros">—</td>
    <td class="col-num"><strong>{tot_total}</strong></td>
    <td class="col-num"><strong>{totais["aprovados"]}</strong></td>
    <td class="col-num"><strong>{totais["revisao"]}</strong></td>
    <td class="col-num"><strong>{totais.get("ja_revisado", 0)}</strong></td>
    <td class="col-num"><strong>{totais["sem_resultado"]}</strong></td>
    <td class="col-vazao">—</td>
    <td class="col-ev"><span class="{ev_css}"><strong>{tot_ev}/{tot_total}</strong></span></td>
  </tr>"""
    return rows


CSS = """
:root {
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
}
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: var(--mono);
  font-size: 15px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.shell-wide { width: min(1200px, 100% - 48px); margin-inline: auto; }
.site-header {
  position: sticky; top: 0; z-index: 80;
  background: rgba(255,255,255,0.92);
  backdrop-filter: saturate(140%) blur(8px);
  -webkit-backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid var(--line-soft);
}
.site-header .row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; height: 64px;
}
.site-header img { height: 28px; width: auto; }
.site-header .crumbs { font-size: 12px; color: var(--fg-3); letter-spacing: 0.04em; }
.site-header .crumbs a { color: var(--fg-2); text-decoration: none; }
.site-header .crumbs a:hover { color: var(--brand); }
.cover {
  padding: clamp(48px, 8vw, 80px) 0 clamp(28px, 5vw, 48px);
  border-bottom: 1px solid var(--line-soft);
  background: var(--bg-1);
}
.eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--fg-3); letter-spacing: 0.04em;
  text-transform: lowercase; margin-bottom: 20px;
}
.eyebrow .bar { width: 24px; height: 2px; background: var(--brand); display: inline-block; }
.cover h1 {
  font-family: var(--mono);
  font-size: clamp(28px, 4.5vw, 52px);
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.03em;
  margin: 0 0 20px;
  color: var(--fg);
}
.cover h1 em { font-style: italic; font-weight: 400; color: var(--brand); }
.cover .meta {
  margin-top: 28px;
  display: flex; gap: 32px; flex-wrap: wrap;
  font-size: 13px;
}
.cover .meta .k { color: var(--fg-3); letter-spacing: 0.04em; }
.cover .meta .v { color: var(--fg); margin-top: 4px; }
.content { padding: clamp(40px, 6vw, 72px) 0 clamp(56px, 8vw, 100px); }
.section-title {
  font-size: clamp(18px, 2.2vw, 24px);
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 24px;
  color: var(--fg);
  display: flex; align-items: center; gap: 10px;
}
.section-title::before { content: "//"; color: var(--brand); font-weight: 400; }
.section-desc { font-size: 14px; color: var(--fg-3); margin: -16px 0 24px; }
.report-wrap { overflow-x: auto; margin-bottom: 56px; }
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  border-radius: var(--r-3);
  overflow: hidden;
  border: 1px solid var(--line-soft);
  table-layout: auto;
}
.report-table thead th {
  text-align: left;
  padding: 10px 10px;
  background: var(--fg);
  color: var(--bg-1);
  font-size: 10.5px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-weight: 600;
  border-right: 1px solid rgba(255,255,255,0.08);
  white-space: normal;
  line-height: 1.35;
  vertical-align: bottom;
}
.report-table thead th:last-child { border-right: 0; }
.report-table tbody tr { transition: background 0.1s; }
.report-table tbody tr:nth-child(odd) { background: var(--bg-1); }
.report-table tbody tr:nth-child(even) { background: var(--bg-2); }
.report-table tbody tr:hover { background: #dde1ea; }
.report-table td {
  padding: 10px 10px;
  vertical-align: top;
  border-bottom: 1px solid var(--line-soft);
  border-right: 1px solid var(--line-soft);
  line-height: 1.4;
}
.report-table td:last-child { border-right: 0; }
.report-table tbody tr:last-child td { border-bottom: 0; }
.col-rank { text-align: center; color: var(--fg-3); font-size: 12px; }
.col-nome strong { display: block; color: var(--fg); font-weight: 600; }
.col-erros { text-align: center; }
.erros-badge { font-weight: 700; }
.col-num { text-align: center; color: var(--fg); }
.col-vazao { text-align: center; }
.col-vazao-val { font-weight: 600; color: var(--brand); cursor: help; }
.col-ev { text-align: center; font-weight: 600; }
.row-total td {
  background: var(--bg-2) !important;
  border-top: 2px solid var(--line);
  color: var(--fg);
}
sup.badge-invalido {
  font-size: 10px; font-weight: 600;
  background: var(--ruim-bg); color: var(--ruim);
  padding: 1px 5px; border-radius: 999px;
  vertical-align: middle; margin-left: 4px;
  letter-spacing: 0.02em; cursor: help;
}
.report-table tr:has(+ .row-details-wrap) td { border-bottom: none; }
.row-details-wrap td {
  padding: 0 10px 0 10px;
  border-top: none;
  background: inherit;
  white-space: normal;
}
.row-details {
  border-bottom: 1px solid var(--line-soft);
  padding-bottom: 12px;
}
.det-summary {
  font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
  text-transform: lowercase; color: var(--fg-3);
  cursor: pointer; padding: 10px 0 0;
  list-style: none; display: flex; align-items: center; gap: 6px;
  user-select: none;
}
.det-summary::-webkit-details-marker { display: none; }
.det-summary::before {
  content: "▶"; font-size: 9px; color: var(--brand);
  transition: transform 0.15s;
}
details[open] .det-summary::before { transform: rotate(90deg); }
.det-summary:hover { color: var(--fg-2); }
.det-body {
  padding: 10px 0 0;
  display: flex; flex-wrap: wrap; gap: 16px 32px;
}
.det-secao { flex: 1 1 260px; }
.det-label {
  display: inline-block; font-size: 10px; font-weight: 700;
  letter-spacing: 0.06em; text-transform: uppercase;
  color: var(--fg-3); margin-bottom: 6px;
}
.det-marcas { font-size: 11px; color: var(--fg-3); display: block; line-height: 1.6; }
.prob-label-ruim  { color: var(--ruim) !important; }
.prob-label-alerta { color: var(--alerta) !important; }
.badge {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 600;
  letter-spacing: 0.04em; text-transform: lowercase;
}
.badge-ok     { background: var(--ok-bg);     color: var(--ok); }
.badge-alerta { background: var(--alerta-bg); color: var(--alerta); }
.badge-ruim   { background: var(--ruim-bg);   color: var(--ruim); }
.val-ok    { color: var(--ok);    font-weight: 600; }
.val-alerta{ color: var(--alerta);font-weight: 600; }
.val-ruim  { color: var(--ruim);  font-weight: 600; }
.val-nd    { color: var(--fg-3); }
.criterio-box {
  background: var(--bg-1); border: 1px solid var(--line-soft);
  border-left: 3px solid var(--brand);
  border-radius: 0 var(--r-3) var(--r-3) 0;
  padding: 16px 20px; font-size: 13.5px;
  color: var(--fg-2); margin-top: 32px;
}
.criterio-sub { margin: 14px 0 4px; font-weight: 600; color: var(--fg); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
.criterio-box ol { margin: 4px 0 0 20px; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.criterio-box ol li { color: var(--fg-2); }
.criterio-box code {
  font-family: var(--mono); background: var(--bg-2);
  border: 1px solid var(--line-soft); border-radius: 3px;
  padding: 0 4px; font-size: 12px; color: var(--fg);
}
.prob-list {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: 4px;
}
.prob-list li {
  font-size: 12px; color: var(--fg-2);
  display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px;
}
.prob-list code {
  font-family: var(--mono); background: var(--bg-2);
  border: 1px solid var(--line-soft); border-radius: 3px;
  padding: 0 4px; font-size: 11px; color: var(--fg); flex-shrink: 0;
}
.prob-grupo { margin-top: 6px; }
.prob-grupo-marca { display: block; font-size: 11px; font-weight: 600; color: var(--fg-2); margin-bottom: 3px; letter-spacing: 0.02em; }
.prob-produto { color: var(--fg-2); font-size: 11px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prob-valor { color: var(--ruim); font-size: 11px; font-style: italic; }
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


def gerar_html(workers_list: list[dict], totais: dict, data_ref: str) -> str:
    n_ativos = sum(1 for w in workers_list if w["total"] > 0)
    cob_pct = round(totais["com_evidencia"] / totais["total"] * 100) if totais["total"] else 0
    rows = tabela_rows_html(workers_list, totais)
    return f"""<!DOCTYPE html>
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
      <div><div class="k">referência</div><div class="v">{data_ref}</div></div>
      <div><div class="k">tarefa</div><div class="v">Validação de Scraping (Pré-Aprovados)</div></div>
      <div><div class="k">workers ativos</div><div class="v">{n_ativos}</div></div>
      <div><div class="k">produtos validados</div><div class="v">{totais["total"]}</div></div>
      <div><div class="k">cobertura de evidências</div><div class="v">{cob_pct}%</div></div>
    </div>
  </div>
</section>

<main class="content">
  <div class="shell-wide">

    <h2 class="section-title">Tabela de resultados</h2>
    <p class="section-desc">Ordenado por número de produtos validados.</p>

    <div class="report-wrap">
      <table class="report-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Worker</th>
            <th title="Total de problemas: EANs sem resultado, resultado inválido, sem evidência, sem pasta no Drive, EAN suspeito">Erros</th>
            <th title="Produtos registrados na planilha">Vali&shy;dados</th>
            <th title="Resultado = Aprovado">Apro&shy;vados</th>
            <th title="Resultado = Enviado para revisão">Para revi&shy;são</th>
            <th title="Resultado = Já estava revisado">Já revi&shy;sado</th>
            <th title="Resultado em branco na planilha">Sem resul&shy;tado</th>
            <th title="Produtos validados por dia corrido desde a criação da planilha">Vazão<br>(prod/dia)</th>
            <th title="Pastas de EAN com evidência confirmada / total de EANs na planilha">Evidências<br>(enc/esp)</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>

    <div class="criterio-box">
      <strong>Critérios de validação</strong>
      <p class="criterio-sub">Planilha</p>
      <ol>
        <li>Resultado preenchido para cada produto (<code>Aprovado</code>, <code>Aprovado em lote</code>, <code>Enviado para revisão</code> ou <code>Já estava revisado</code>)</li>
        <li>Resultado dentro das opções válidas — qualquer outro valor é considerado inválido</li>
        <li>EAN com formato correto: 8, 12, 13 ou 14 dígitos numéricos, sem sequências óbvias de placeholder</li>
      </ol>
      <p class="criterio-sub">Evidências no Drive</p>
      <ol>
        <li>Pasta de EAN dentro da pasta da marca correspondente em <code>evidencias/</code></li>
        <li>EANs com resultado na planilha devem ter pasta no Drive</li>
        <li>Subpasta <code>screenshots</code> dentro da pasta do EAN — <strong>ou</strong> arquivo de vídeo (<code>[EAN].mp4</code>) direto na pasta do EAN</li>
        <li>Ao menos 1 arquivo de evidência dentro de <code>screenshots</code></li>
        <li>Screenshots ordenáveis: nomes começando com dígito, mtimes distintos entre si, ou nomes descritivos (≥ 4 letras)</li>
      </ol>
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


def buildar(workers_list: list[dict], totais: dict, data_ref: str) -> Path:
    print("→ Gerando HTML…")
    out_dir = ROOT / "build" / "resultados"
    out_dir.mkdir(parents=True, exist_ok=True)
    html = gerar_html(workers_list, totais, data_ref)
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"   ✓  build/resultados/index.html ({out.stat().st_size:,} bytes)")
    return out


# ── Passo 6 — publicar ────────────────────────────────────────────────────────

def publicar(html_path: Path) -> None:
    print("→ Publicando no R2…")
    result = subprocess.run(
        [
            "wrangler", "r2", "object", "put", R2_OBJECT_KEY,
            "--file", str(html_path),
            "--content-type", "text/html; charset=utf-8",
            "--remote",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"wrangler falhou:\n{result.stderr.strip()}")
    print(f"   ✓  Publicado.")

    # Validar HTTP 200
    import urllib.request
    try:
        with urllib.request.urlopen(PUBLISH_URL, timeout=10) as resp:
            status = resp.status
    except Exception as e:
        print(f"   ⚠  Não foi possível validar a URL: {e}")
        return
    if status == 200:
        print(f"   ✓  {PUBLISH_URL} → HTTP {status}")
    else:
        print(f"   ⚠  {PUBLISH_URL} → HTTP {status} (esperado 200)")


# ── Passo 7 — resumo ──────────────────────────────────────────────────────────

def exibir_resumo(workers: list[dict], workers_list: list[dict],
                  totais: dict, data_ref: str, n_eans_aprovados: int) -> None:
    n_total = len(workers)
    n_ativos = sum(1 for w in workers if w["dados"]["total"] > 0)
    n_inativos = n_total - n_ativos
    cob_pct = round(totais["com_evidencia"] / totais["total"] * 100) if totais["total"] else 0

    print()
    print("=" * 60)
    print("Acompanhamento atualizado.")
    print()
    print(f"  URL:    {PUBLISH_URL}")
    print(f"  Data:   {data_ref}")
    print(f"  Workers: {n_total} total "
          f"({n_ativos} com produtos, {n_inativos} novos)")
    print(f"  Produtos validados: {totais['total']}")
    print(f"  Aprovados: {totais['aprovados']}")
    print(f"  Cobertura de evidências: {cob_pct}%")
    print(f"  Planilha ean_aprovados: {n_eans_aprovados} EANs registrados")

    # Alertas críticos
    criticos = [
        w for w in workers_list
        if w["total"] > 0 and w["sem_resultado"] > 0
    ]
    sem_evidencia = [
        w for w in workers_list
        if w["total"] > 0 and w.get("evidencias") == "ruim"
    ]
    if criticos or sem_evidencia:
        print()
        print("  ⚠  AÇÃO IMEDIATA:")
        for w in criticos:
            print(f"     {w['nome']}: {w['sem_resultado']} produto(s) sem resultado na planilha")
        for w in sem_evidencia:
            print(f"     {w['nome']}: cobertura de evidências insuficiente")
    print("=" * 60)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-evidencias", action="store_true",
                        help="Pula verificação de evidências no Drive (mais rápido)")
    parser.add_argument("--skip-publish", action="store_true",
                        help="Pula publicação no R2 (apenas gera o HTML localmente)")
    args = parser.parse_args()

    data_ref = data_hoje_ptbr()
    print(f"\n── Acompanhamento Workers BeClean · {data_ref} ──\n")

    # Passos 1 e 2
    workers = descobrir_workers()
    coletar_dados_planilhas(workers)

    # Passo 3
    n_eans = atualizar_ean_aprovados(workers)

    # Passo 4
    if args.skip_evidencias:
        print("→ Verificação de evidências ignorada (--skip-evidencias).")
        for w in workers:
            evidencias_estimadas(w)
    else:
        verificar_evidencias(workers)

    # Passo 5
    workers_list = montar_workers_list(workers)
    totais = {
        "total":         sum(w["total"] for w in workers_list),
        "aprovados":     sum(w["aprovados"] for w in workers_list),
        "revisao":       sum(w["revisao"] for w in workers_list),
        "ja_revisado":   sum(w.get("ja_revisado", 0) for w in workers_list),
        "sem_resultado": sum(w["sem_resultado"] for w in workers_list),
        "com_evidencia": sum(w["com_evidencia"] for w in workers_list),
    }
    print("→ Gerando HTML…", flush=True)
    html_path = buildar(workers_list, totais, data_ref)

    # Também atualiza build_resultados.py com os dados frescos
    print("→ Atualizando build_resultados.py…", flush=True)
    _atualizar_build_resultados(workers_list, data_ref)

    # Passo 6
    if args.skip_publish:
        print("→ Publicação ignorada (--skip-publish).")
    else:
        publicar(html_path)

    # Passo 7
    exibir_resumo(workers, workers_list, totais, data_ref, n_eans)


def _atualizar_build_resultados(workers_list: list[dict], data_ref: str) -> None:
    """Reescreve a lista WORKERS e DATA_REFERENCIA em build_resultados.py."""
    path = ROOT / "build_resultados.py"
    if not path.exists():
        return

    def fmt_worker(w: dict) -> str:
        notas_repr = repr(w["notas"])
        marcas = w["marcas"]
        return f"""    {{
        "rank":          {w["rank"]},
        "nome":          {w["nome"]!r},
        "marcas":        {marcas!r},
        "planilha":      {w["planilha"]!r},
        "evidencias":    {w["evidencias"]!r},
        "avaliacao":     {w["avaliacao"]!r},
        "total":         {w["total"]},
        "aprovados":     {w["aprovados"]},
        "revisao":       {w["revisao"]},
        "ja_revisado":   {w.get("ja_revisado", 0)},
        "invalido":      {w["invalido"]},
        "sem_resultado": {w["sem_resultado"]},
        "com_evidencia": {w["com_evidencia"]},
        "notas": {notas_repr},
    }}"""

    workers_block = "WORKERS = [\n" + ",\n".join(fmt_worker(w) for w in workers_list) + "\n]\n"

    src = path.read_text(encoding="utf-8")

    # Substituir DATA_REFERENCIA
    src = re.sub(
        r'DATA_REFERENCIA\s*=\s*"[^"]*"',
        f'DATA_REFERENCIA = "{data_ref}"',
        src,
    )

    # Substituir bloco WORKERS
    src = re.sub(
        r"WORKERS\s*=\s*\[.*?\n\]\n",
        workers_block + "\n",
        src,
        flags=re.DOTALL,
    )

    path.write_text(src, encoding="utf-8")
    print("   ✓  build_resultados.py atualizado.")


if __name__ == "__main__":
    main()
