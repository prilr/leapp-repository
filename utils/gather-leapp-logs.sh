#!/bin/bash
# Gather ELevate/Leapp upgrade logs from a remote machine.
#
# Based on the log collection guidance in the CloudLinux ELevate documentation:
# https://cloudlinux.com/documentation/cloudlinuxos/elevate/
#
# The following items are collected (as documented):
#   - All files in /var/log/leapp
#   - /var/lib/leapp/leapp.db
#   - journalctl output
#   - /var/log/elevate-cpanel.log  (when --cpanel is passed)
#
# Usage: gather-leapp-logs.sh [OPTIONS] [user@]host
#
# Options:
#   -o, --output DIR    Local directory to save logs into
#                       (default: leapp-logs-<host>-<timestamp>)
#   -i, --identity KEY  SSH private key file
#   -p, --port PORT     SSH port (default: 22)
#   --cpanel            Also collect /var/log/elevate-cpanel.log
#   -h, --help          Show this help message and exit
#
# Examples:
#   gather-leapp-logs.sh root@192.0.2.10
#   gather-leapp-logs.sh --cpanel -i ~/.ssh/id_rsa root@192.0.2.10
#   gather-leapp-logs.sh -o /tmp/my-logs root@192.0.2.10

set -euo pipefail

usage() {
    sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
OUTPUT_DIR=""
SSH_KEY=""
SSH_PORT="22"
CPANEL=0
TARGET=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)
            OUTPUT_DIR="$2"; shift 2 ;;
        -i|--identity)
            SSH_KEY="$2"; shift 2 ;;
        -p|--port)
            SSH_PORT="$2"; shift 2 ;;
        --cpanel)
            CPANEL=1; shift ;;
        -h|--help)
            usage 0 ;;
        -*)
            echo "Unknown option: $1" >&2; usage 1 ;;
        *)
            if [[ -n "$TARGET" ]]; then
                echo "Unexpected argument: $1" >&2; usage 1
            fi
            TARGET="$1"; shift ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    echo "Error: remote host is required." >&2
    usage 1
fi

# ---------------------------------------------------------------------------
# Build SSH / SCP option strings
# ---------------------------------------------------------------------------
SSH_OPTS=(-o StrictHostKeyChecking=no -o BatchMode=yes -p "$SSH_PORT")
SCP_OPTS=(-o StrictHostKeyChecking=no -P "$SSH_PORT")
if [[ -n "$SSH_KEY" ]]; then
    SSH_OPTS+=(-i "$SSH_KEY")
    SCP_OPTS+=(-i "$SSH_KEY")
fi

# ---------------------------------------------------------------------------
# Resolve output directory
# ---------------------------------------------------------------------------
HOST="${TARGET##*@}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="leapp-logs-${HOST}-${TIMESTAMP}"
fi
OUTPUT_DIR="$(realpath -m "$OUTPUT_DIR")"

echo "==> Gathering ELevate/Leapp logs from ${TARGET} into ${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# Remote temp archive path
# ---------------------------------------------------------------------------
REMOTE_ARCHIVE="/tmp/leapp-logs-${TIMESTAMP}.tgz"

# ---------------------------------------------------------------------------
# Step 1: Pack /var/log/leapp + /var/lib/leapp/leapp.db on the remote machine
# (as documented: tar -czf leapp-logs.tgz /var/log/leapp /var/lib/leapp/leapp.db)
# ---------------------------------------------------------------------------
echo "--> Packing /var/log/leapp and /var/lib/leapp/leapp.db ..."

CPANEL_INCLUDE=""
if [[ "$CPANEL" -eq 1 ]]; then
    CPANEL_INCLUDE="/var/log/elevate-cpanel.log"
fi

# Build the remote tar command; ignore missing files so the script doesn't
# abort when e.g. leapp.db or the cPanel log don't exist yet.
ssh "${SSH_OPTS[@]}" "$TARGET" bash -s -- "$REMOTE_ARCHIVE" "$CPANEL_INCLUDE" <<'REMOTE_TAR'
REMOTE_ARCHIVE="$1"
CPANEL_INCLUDE="$2"

PATHS="/var/log/leapp /var/lib/leapp/leapp.db"
if [[ -n "$CPANEL_INCLUDE" ]]; then
    PATHS="$PATHS $CPANEL_INCLUDE"
fi

# Collect only paths that exist
EXISTING=""
for p in $PATHS; do
    if [[ -e "$p" ]]; then
        EXISTING="$EXISTING $p"
    else
        echo "  [warn] $p not found on remote, skipping"
    fi
done

if [[ -z "$EXISTING" ]]; then
    echo "  [warn] No leapp log paths found on remote machine."
    # Create an empty archive so the rest of the script can continue.
    tar -czf "$REMOTE_ARCHIVE" --files-from /dev/null
else
    # shellcheck disable=SC2086
    tar -czf "$REMOTE_ARCHIVE" $EXISTING
fi
REMOTE_TAR

# ---------------------------------------------------------------------------
# Step 2: Capture journalctl output on the remote machine
# ---------------------------------------------------------------------------
echo "--> Collecting journalctl output ..."
REMOTE_JOURNAL="/tmp/leapp-journal-${TIMESTAMP}.txt"
ssh "${SSH_OPTS[@]}" "$TARGET" \
    "journalctl --no-pager > ${REMOTE_JOURNAL} 2>/dev/null || true"

# ---------------------------------------------------------------------------
# Step 3: Download everything
# ---------------------------------------------------------------------------
mkdir -p "$OUTPUT_DIR"
echo "--> Downloading log archive ..."
scp "${SCP_OPTS[@]}" "${TARGET}:${REMOTE_ARCHIVE}" "${OUTPUT_DIR}/leapp-logs.tgz"

echo "--> Downloading journalctl output ..."
scp "${SCP_OPTS[@]}" "${TARGET}:${REMOTE_JOURNAL}" "${OUTPUT_DIR}/journalctl.txt"

# ---------------------------------------------------------------------------
# Step 4: Extract the archive locally for easy inspection
# ---------------------------------------------------------------------------
echo "--> Extracting log archive ..."
tar -xzf "${OUTPUT_DIR}/leapp-logs.tgz" -C "$OUTPUT_DIR" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Step 5: Clean up temp files on the remote machine
# ---------------------------------------------------------------------------
echo "--> Cleaning up remote temp files ..."
ssh "${SSH_OPTS[@]}" "$TARGET" "rm -f ${REMOTE_ARCHIVE} ${REMOTE_JOURNAL}" || true

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "==> Logs saved to: ${OUTPUT_DIR}"
echo ""
echo "    Key files:"
echo "      ${OUTPUT_DIR}/leapp-logs.tgz           (archive — attach to bug reports)"
echo "      ${OUTPUT_DIR}/journalctl.txt            (full journal)"
if [[ -d "${OUTPUT_DIR}/var/log/leapp" ]]; then
    echo "      ${OUTPUT_DIR}/var/log/leapp/             (leapp log directory)"
    [[ -f "${OUTPUT_DIR}/var/log/leapp/leapp-report.txt" ]] && \
        echo "      ${OUTPUT_DIR}/var/log/leapp/leapp-report.txt"
    [[ -f "${OUTPUT_DIR}/var/log/leapp/leapp-upgrade.log" ]] && \
        echo "      ${OUTPUT_DIR}/var/log/leapp/leapp-upgrade.log"
fi
if [[ "$CPANEL" -eq 1 && -f "${OUTPUT_DIR}/var/log/elevate-cpanel.log" ]]; then
    echo "      ${OUTPUT_DIR}/var/log/elevate-cpanel.log"
fi
echo ""
echo "==> When filing a bug report, attach: leapp-logs.tgz and journalctl.txt"
