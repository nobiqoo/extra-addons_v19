#!/usr/bin/env bash
# Sincroniza (espejo) el contenido de odone_v19 en este directorio.
# Lo que se cree/modifique/borre en el origen se replica aquí.
#
# Uso:
#   ./sync.sh            sincroniza una vez
#   ./sync.sh --dry-run  muestra lo que haría sin cambiar nada
#   ./sync.sh --watch    sincroniza y queda vigilando cambios (Ctrl+C para salir)
set -euo pipefail

SRC="/home/miguel/Documentos/Miguel/odone/Proyectos/odone_v19/"
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"
INTERVAL="${SYNC_INTERVAL:-5}"   # segundos entre sincronizaciones en modo --watch sin inotify

# Elementos excluidos: no se copian desde el origen y no se borran en el destino.
EXCLUDES=(
  --exclude='/.git/'
  --exclude='/.github/'
  --exclude='/sync.sh'
)

if [[ ! -d "$SRC" ]]; then
  echo "Error: no existe el origen $SRC" >&2
  exit 1
fi

sync_once() {
  rsync -a --delete "${EXCLUDES[@]}" "$@" "$SRC" "$DEST"
}

case "${1:-}" in
  --dry-run|-n)
    sync_once --dry-run --itemize-changes
    ;;
  --watch|-w)
    sync_once
    echo "[$(date '+%F %T')] Sincronizado. Vigilando cambios en $SRC ..."
    if command -v inotifywait >/dev/null 2>&1; then
      while inotifywait -qq -r -e modify,create,delete,move,attrib --exclude '/\.git(hub)?/' "$SRC"; do
        sleep 1   # agrupa ráfagas de cambios
        sync_once
        echo "[$(date '+%F %T')] Sincronizado."
      done
    else
      echo "(inotifywait no instalado; usando sondeo cada ${INTERVAL}s. Instalar: sudo apt install inotify-tools)"
      while sleep "$INTERVAL"; do
        changes="$(sync_once --itemize-changes)"
        [[ -n "$changes" ]] && echo "[$(date '+%F %T')] Sincronizado:" && echo "$changes"
      done
    fi
    ;;
  ""|--once)
    sync_once
    echo "Sincronización completa: $SRC -> $DEST"
    ;;
  *)
    sed -n '2,9p' "$0"
    exit 1
    ;;
esac
