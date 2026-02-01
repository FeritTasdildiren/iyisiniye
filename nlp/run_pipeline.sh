#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# iyisiniye NLP Batch Pipeline - Shell Runner
# ──────────────────────────────────────────────────────────────
# Kullanim:
#   ./run_pipeline.sh              # Normal calistirma
#   ./run_pipeline.sh --dry-run    # Test modu (DB'ye yazmaz)
#   ./run_pipeline.sh --batch-size 200 --verbose
# ──────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
LOCK_FILE="${SCRIPT_DIR}/.pipeline.lock"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/runner_$(date +%Y%m%d_%H%M%S).log"

# Log dizini
mkdir -p "${LOG_DIR}"

# ── Yardimci fonksiyonlar ────────────────────────────────────

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "${msg}" | tee -a "${LOG_FILE}"
}

error() {
    log "HATA: $1"
    exit 1
}

# ── Lock kontrolu ────────────────────────────────────────────

if [ -f "${LOCK_FILE}" ]; then
    LOCK_PID=$(head -1 "${LOCK_FILE}" 2>/dev/null | grep -oP '\d+' || echo "")
    if [ -n "${LOCK_PID}" ] && kill -0 "${LOCK_PID}" 2>/dev/null; then
        error "Baska bir pipeline zaten calisiyor (PID: ${LOCK_PID}). Cikiliyor."
    else
        log "Eski lock dosyasi bulundu ama process calismiyior. Temizleniyor."
        rm -f "${LOCK_FILE}"
    fi
fi

# ── Scraper kontrolu (PM2) ──────────────────────────────────

if command -v pm2 &>/dev/null; then
    SCRAPER_RUNNING=$(pm2 jlist 2>/dev/null | python3 -c "
import sys, json
try:
    procs = json.load(sys.stdin)
    for p in procs:
        name = p.get('name', '')
        status = p.get('pm2_env', {}).get('status', '')
        if 'scraper' in name.lower() and status == 'online':
            print('yes')
            sys.exit(0)
    print('no')
except:
    print('no')
" 2>/dev/null || echo "no")

    if [ "${SCRAPER_RUNNING}" = "yes" ]; then
        log "UYARI: Scraper sureci calisiyor. Pipeline yine de baslatilacak (incremental mod)."
        log "  Not: Pipeline sadece processed=false olan kayitlari isler, scraper ile cakisma riski dusuk."
    fi
else
    log "PM2 bulunamadi, scraper kontrolu atlanıyor."
fi

# ── Virtual environment ──────────────────────────────────────

if [ ! -d "${VENV_DIR}" ]; then
    error "Python venv bulunamadi: ${VENV_DIR}. Lutfen once venv olusturun."
fi

log "Virtual environment aktiflesitiriliyor: ${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

# Python kontrolu
PYTHON_VERSION=$(python3 --version 2>&1)
log "Python: ${PYTHON_VERSION}"

# ── Pipeline calistir ────────────────────────────────────────

log "NLP Batch Pipeline baslatiliyor..."
log "Argumanlar: $*"
log "Log dosyasi: ${LOG_FILE}"

# Pipeline'i calistir, tum argumanlari ilet
python3 "${SCRIPT_DIR}/src/nlp_batch_pipeline.py" "$@" 2>&1 | tee -a "${LOG_FILE}"
PIPELINE_EXIT=${PIPESTATUS[0]}

# ── Sonuc ────────────────────────────────────────────────────

if [ ${PIPELINE_EXIT} -eq 0 ]; then
    log "Pipeline basariyla tamamlandi."
elif [ ${PIPELINE_EXIT} -eq 2 ]; then
    log "UYARI: Pipeline tamamlandi, ancak bazi yorumlar basarisiz oldu."
else
    log "HATA: Pipeline basarisiz oldu (exit code: ${PIPELINE_EXIT})"
fi

# ── Eski loglari temizle (30 günden eski) ────────────────────

find "${LOG_DIR}" -name "*.log" -mtime +30 -delete 2>/dev/null || true

deactivate 2>/dev/null || true

exit ${PIPELINE_EXIT}
