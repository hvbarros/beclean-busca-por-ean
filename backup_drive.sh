#!/usr/bin/env bash
# Faz backup de mintel.db, mintel.xlsx, falta_enriquecimento.csv e imagens/
# para uma subpasta timestampada no Google Drive.
#
# Dependência: gws (Google Workspace CLI)
# Pasta destino: baselabs-projetos/ativos/beclean/busca-por-ean/<YYYY-MM-DD-HH-MM>

set -euo pipefail

DRIVE_PARENT="1h0oqsW2AgqIjF1t5YAv9ShCWD5wiD2cb"
TS=$(date +%Y-%m-%d-%H-%M)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ZIP="$SCRIPT_DIR/imagens_backup.zip"

echo "=== Backup BeClean → Google Drive ==="
echo "Destino: busca-por-ean/$TS"
echo

# Cria subpasta com timestamp
echo "Criando subpasta $TS..."
SUBFOLDER_ID=$(gws drive files create \
    --json "{\"name\": \"$TS\", \"mimeType\": \"application/vnd.google-apps.folder\", \"parents\": [\"$DRIVE_PARENT\"]}" \
    --params '{"supportsAllDrives": true}' 2>&1 \
  | grep -v keyring \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

if [ -z "$SUBFOLDER_ID" ]; then
    echo "Erro: não foi possível criar a subpasta." >&2
    exit 1
fi
echo "  ID: $SUBFOLDER_ID"
echo

# Compacta imagens
echo "Compactando imagens/..."
zip -q "$ZIP" "$SCRIPT_DIR"/imagens/*.jpg
echo "  $(du -sh "$ZIP" | cut -f1) → imagens_backup.zip"
echo

# Upload de cada arquivo
upload() {
    local FILE="$1"
    local NAME
    NAME=$(basename "$FILE")
    echo -n "  Enviando $NAME... "
    gws drive files create \
        --json "{\"name\": \"$NAME\", \"parents\": [\"$SUBFOLDER_ID\"]}" \
        --upload "$FILE" \
        --params '{"supportsAllDrives": true}' 2>&1 \
      | grep -v keyring \
      | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'OK ({d[\"id\"]})')"
}

upload "$SCRIPT_DIR/falta_enriquecimento.csv"
upload "$SCRIPT_DIR/mintel.xlsx"
upload "$SCRIPT_DIR/mintel.db"
upload "$ZIP"

# Remove zip temporário
rm -f "$ZIP"

echo
echo "Backup concluído: busca-por-ean/$TS"
