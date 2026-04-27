#!/bin/bash
# Gather ELevate/Leapp upgrade logs from a customer machine via sshbox using ssa.
#
# Uses the sshbox gateway host and the `ssa` tool to reach customer servers.
# Remote commands are base64-encoded locally and decoded+executed on the
# customer machine, to avoid shell quoting issues across two hops.
# Binary file contents are streamed through stdout via base64 encoding.
#
# Based on the log collection guidance in the CloudLinux ELevate documentation:
# https://cloudlinux.com/documentation/cloudlinuxos/elevate/
#
# Usage: gather-leapp-logs-sshbox.sh [OPTIONS]
#
# Required:
#   -t, --ticket ID         Ticket ID (passed to ssa for audit purposes)
#   -a, --address HOST      Customer server hostname or IP address
#
# Options:
#   -T, --type TYPE         ssa credentials type: ssh, control_panel, custom, direct
#                           (default: ssh)
#   -u, --user USER         SSH username (only for --type direct)
#   -p, --port PORT         SSH port (only for --type direct, default: 22)
#   --cpanel                Also collect /var/log/elevate-cpanel.log
#   --sshbox HOST           sshbox host alias or address (default: sshbox)
#   -o, --output DIR        Local directory to save logs into
#                           (default: leapp-logs-<address>-<timestamp>)
#   -h, --help              Show this help message and exit
#
# Examples:
#   gather-leapp-logs-sshbox.sh -t 12345 -a customer.example.com
#   gather-leapp-logs-sshbox.sh -t 12345 -a 192.0.2.10 -T direct -u root --cpanel
#   gather-leapp-logs-sshbox.sh -t 12345 -a host.example.com --sshbox mysshbox -o /tmp/logs

set -euo pipefail

usage() {
    sed -n '/^# Usage:/,/^[^#]/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
TICKET=""
ADDRESS=""
CREDS_TYPE="ssh"
SSA_USER=""
SSA_PORT=""
CPANEL=0
SSHBOX="sshbox"
OUTPUT_DIR=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--ticket)   TICKET="$2";     shift 2 ;;
        -a|--address)  ADDRESS="$2";    shift 2 ;;
        -T|--type)     CREDS_TYPE="$2"; shift 2 ;;
        -u|--user)     SSA_USER="$2";   shift 2 ;;
        -p|--port)     SSA_PORT="$2";   shift 2 ;;
        --cpanel)      CPANEL=1;        shift   ;;
        --sshbox)      SSHBOX="$2";     shift 2 ;;
        -o|--output)   OUTPUT_DIR="$2"; shift 2 ;;
        -h|--help)     usage 0 ;;
        *)  echo "Unknown option: $1" >&2; usage 1 ;;
    esac
done

[[ -z "$TICKET"  ]] && { echo "Error: --ticket is required." >&2; usage 1; }
[[ -z "$ADDRESS" ]] && { echo "Error: --address is required." >&2; usage 1; }

# ---------------------------------------------------------------------------
# Build the ssa options string
# ---------------------------------------------------------------------------
SSA_OPTS="-t ${TICKET} -a ${ADDRESS} -T ${CREDS_TYPE}"
[[ -n "$SSA_USER" ]] && SSA_OPTS="${SSA_OPTS} -u ${SSA_USER}"
[[ -n "$SSA_PORT" ]] && SSA_OPTS="${SSA_OPTS} -p ${SSA_PORT}"

# ---------------------------------------------------------------------------
# Resolve output directory (without creating it yet)
# ---------------------------------------------------------------------------
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="leapp-logs-${ADDRESS}-${TIMESTAMP}"
fi
OUTPUT_DIR="$(realpath -m "$OUTPUT_DIR")"

echo "==> Gathering ELevate/Leapp logs from ${ADDRESS} via ${SSHBOX} into ${OUTPUT_DIR}"

# ---------------------------------------------------------------------------
# Helpers
#
# Remote commands are base64-encoded locally and piped through:
#   ssh sshbox "ssa ... -c 'echo BASE64 | base64 -d | bash'"
# This sidesteps all quoting issues across the two-hop connection.
#
# ssa_exec CMD      -- run CMD on the customer machine; stdout goes to caller
# ssa_download CMD DEST -- same, but CMD must emit base64-encoded binary;
#                          its output is decoded and written to DEST
# ---------------------------------------------------------------------------
ssa_exec() {
    local encoded
    encoded=$(printf '%s' "$1" | base64 -w0)
    ssh "$SSHBOX" "ssa ${SSA_OPTS} -c 'echo ${encoded} | base64 -d | bash'"
}

ssa_download() {
    local encoded
    encoded=$(printf '%s' "$1" | base64 -w0)
    ssh "$SSHBOX" "ssa ${SSA_OPTS} -c 'echo ${encoded} | base64 -d | bash'" | base64 -d > "$2"
}

# ---------------------------------------------------------------------------
# Step 1: Verify connectivity to sshbox and customer machine before touching
# the local filesystem — output directory is only created after this succeeds.
# ---------------------------------------------------------------------------
echo "--> Verifying connectivity to ${ADDRESS} via ${SSHBOX} ..."
ssa_exec "true"

# ---------------------------------------------------------------------------
# Step 2: Pack /var/log/leapp + /var/lib/leapp/leapp.db on the customer machine.
# Mirrors the documented command:
#   tar -czf leapp-logs.tgz /var/log/leapp /var/lib/leapp/leapp.db
# The archive is base64-encoded for safe streaming through the two-hop pipe.
# ---------------------------------------------------------------------------
echo "--> Packing /var/log/leapp and /var/lib/leapp/leapp.db ..."

# EXTRA_PATHS is expanded locally into the script before encoding.
EXTRA_PATHS=""
[[ "$CPANEL" -eq 1 ]] && EXTRA_PATHS="/var/log/elevate-cpanel.log"

# Variables intended for the remote shell are escaped (\$) so the local shell
# passes them through literally; ${EXTRA_PATHS} is intentionally unescaped for
# local expansion.
REMOTE_PACK=$(cat <<SCRIPT
PATHS=""
for p in /var/log/leapp /var/lib/leapp/leapp.db ${EXTRA_PATHS}; do
    if [ -e "\$p" ]; then
        PATHS="\$PATHS \$p"
    else
        echo "[warn] \$p not found on remote, skipping" >&2
    fi
done
if [ -z "\$PATHS" ]; then
    echo "[warn] No leapp paths found on remote." >&2
    tar -czf - --files-from /dev/null | base64
else
    tar -czf - \$PATHS | base64
fi
SCRIPT
)

mkdir -p "$OUTPUT_DIR"
ssa_download "$REMOTE_PACK" "${OUTPUT_DIR}/leapp-logs.tgz"

# ---------------------------------------------------------------------------
# Step 3: Capture journalctl output
# ---------------------------------------------------------------------------
echo "--> Collecting journalctl output ..."
ssa_exec "journalctl --no-pager" > "${OUTPUT_DIR}/journalctl.txt"

# ---------------------------------------------------------------------------
# Step 4: Extract archive locally for easy inspection
# ---------------------------------------------------------------------------
echo "--> Extracting log archive ..."
tar -xzf "${OUTPUT_DIR}/leapp-logs.tgz" -C "$OUTPUT_DIR" 2>/dev/null || true

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
