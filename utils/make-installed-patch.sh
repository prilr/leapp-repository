#!/bin/bash
# Produce a patch that upgrades the *installed* leapp-repository files
# (from whichever leapp-upgrade-* RPM is on the host) to the state of a
# newer git ref.
#
# The upstream Makefile has no `install` target — the RPM spec does all
# the install-time path mangling. This script mirrors that mangling so a
# plain `git diff` between two refs can be applied with `patch -p1 -d /`
# against the files dropped on disk by the RPM.
#
# Usage:
#   utils/make-installed-patch.sh [--from=<major>] <from-ref> [to-ref] [output.patch]
#
# Examples:
#   utils/make-installed-patch.sh v0.20.0-7.cloudlinux
#   utils/make-installed-patch.sh --from=el8 v0.20.0-7.cloudlinux origin/cloudlinux out.patch
#   LEAPP_FROM=9 utils/make-installed-patch.sh v1.0.0
#
# Path mapping (see packaging/leapp-repository.spec %install):
#   repos/*                -> <install_root>/*
#   commands/*             -> <sitelib>/leapp/cli/commands/*
#   etc/leapp/transaction/ -> /etc/leapp/transaction/
#
# --- Selecting the target leapp variant --------------------------------------
#
# The script needs to know which leapp-upgrade-el{X}toel{X+1} variant it
# is producing a patch for, so it can pick the right python sitelib and
# know which `system_upgrade/<tree>/` subtree the RPM ships.
#
# Resolution order, highest priority first:
#
#   1. Direct env-var override of an individual value:
#        $LEAPP_PYTHON_SITELIB, $LEAPP_KEEP_SUBTREES, $LEAPP_REPO_INSTALL_ROOT
#      Set these when a specific layout needs forcing.
#
#   2. --from=<major>  (or $LEAPP_FROM)
#      A single parameter that names the source major version of the IPU.
#      Accepted values: 7, 8, 9, 10, el7, el8, el9, el10, cl7, cl8, cl9, cl10
#      (anything ending in a digit; the digit is what matters).
#      Picks sitelib + migration subtree from the table below.
#      Use this on a dev machine that has no leapp-upgrade-* RPM
#      installed, or to cross-build a patch targeting a different host.
#
#   3. RPM autodetection from the live host:
#      - sitelib:  `rpm -qal 'leapp-upgrade-*' | grep site-packages`
#      - subtrees: `ls $install_root/system_upgrade/`
#      Used when --from is absent and the RPM is installed locally.
#
#   4. Built-in fallback (install_root only; sitelib and subtrees go
#      unset, and the script warns + drops the affected hunks).
#
# --from table:
#
#   --from    migration subtree   sitelib (distro python)
#   -----     -----------------   -----------------------
#   7         el7toel8            /usr/lib/python2.7/site-packages
#   8         el8toel9            /usr/lib/python3.6/site-packages
#   9         el9toel10           /usr/lib/python3.9/site-packages
#   10        el10toel11          /usr/lib/python3.12/site-packages
#
# `common`, `cloudlinux`, and `wp-toolkit` subtrees are added to the
# keep list automatically when they exist in the source tree.
#
# --- Fixed exclusions (always stripped regardless of variant) ----------------
#
#   - repos/**/tests/**, repos/**/Makefile, repos/common/**/test.py
#   - commands/tests/**
#   - everything outside repos/, commands/, etc/leapp/transaction/
set -euo pipefail

die() { echo "error: $*" >&2; exit 1; }
warn() { echo "warn: $*" >&2; }

# --- arg parsing -------------------------------------------------------------

FROM_VERSION="${LEAPP_FROM:-}"
POSARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --from=*) FROM_VERSION="${1#--from=}"; shift ;;
        --from)   FROM_VERSION="${2:-}"; shift 2 ;;
        -h|--help)
            sed -n '2,/^set -/p' "$0" | sed 's/^# \?//;$d'
            exit 0 ;;
        --) shift; POSARGS+=("$@"); break ;;
        *)  POSARGS+=("$1"); shift ;;
    esac
done

FROM_REF="${POSARGS[0]:-}"
TO_REF="${POSARGS[1]:-HEAD}"
OUT="${POSARGS[2]:-leapp-repository-${FROM_REF//\//_}-to-${TO_REF//\//_}.patch}"

[[ -n "$FROM_REF" ]] || die "usage: $0 [--from=<major>] <from-ref> [to-ref] [output.patch]"

cd "$(git rev-parse --show-toplevel)"

# --- resolve target layout ---------------------------------------------------

INSTALL_ROOT="${LEAPP_REPO_INSTALL_ROOT:-/usr/share/leapp-repository/repositories}"

# Defaults from --from (if given). Keyed by the distro major digit.
FROM_SITELIB=""
FROM_SUBTREE=""
if [[ -n "$FROM_VERSION" ]]; then
    # Accept 7 / el7 / cl7 / rhel7 / ... — trailing digit(s) wins.
    if [[ "$FROM_VERSION" =~ ([0-9]+)$ ]]; then
        major="${BASH_REMATCH[1]}"
    else
        die "unrecognized --from value: '$FROM_VERSION' (expected e.g. 7, el8, cl9)"
    fi
    case "$major" in
        7)  FROM_SITELIB="/usr/lib/python2.7/site-packages"
            FROM_SUBTREE="el7toel8" ;;
        8)  FROM_SITELIB="/usr/lib/python3.6/site-packages"
            FROM_SUBTREE="el8toel9" ;;
        9)  FROM_SITELIB="/usr/lib/python3.9/site-packages"
            FROM_SUBTREE="el9toel10" ;;
        10) FROM_SITELIB="/usr/lib/python3.12/site-packages"
            FROM_SUBTREE="el10toel11" ;;
        *)  die "unsupported --from major version: $major" ;;
    esac
fi

# sitelib: direct override > --from > RPM autodetect > unset.
SITELIB="${LEAPP_PYTHON_SITELIB:-$FROM_SITELIB}"
if [[ -z "$SITELIB" ]]; then
    SITELIB=$(rpm -qal 'leapp-upgrade-*' 2>/dev/null \
        | grep -oE '/usr/lib/python[^/]+/site-packages' \
        | sort -u | head -1)
fi
[[ -n "$SITELIB" ]] || warn "no python sitelib known (no --from, no leapp-upgrade-* RPM); commands/* hunks will be dropped"

# subtrees: direct override > --from > RPM autodetect > empty.
KEEP_SUBTREES="${LEAPP_KEEP_SUBTREES:-}"
if [[ -z "$KEEP_SUBTREES" && -n "$FROM_SUBTREE" ]]; then
    # Include the migration subtree plus every common/fork subtree that
    # exists in the source tree (`common`, `cloudlinux`, `wp-toolkit`).
    for t in common cloudlinux wp-toolkit "$FROM_SUBTREE"; do
        [[ -d "repos/system_upgrade/$t" ]] && KEEP_SUBTREES+="${KEEP_SUBTREES:+,}$t"
    done
fi
if [[ -z "$KEEP_SUBTREES" && -d "$INSTALL_ROOT/system_upgrade" ]]; then
    KEEP_SUBTREES=$(find "$INSTALL_ROOT/system_upgrade" -mindepth 1 -maxdepth 1 -type d \
        -printf '%f,' 2>/dev/null | sed 's/,$//')
fi
[[ -n "$KEEP_SUBTREES" ]] || warn "no system_upgrade/ subtrees known; all will be included"

# --- build excludes ----------------------------------------------------------

EXCLUDES=(
    # never shipped by the RPM
    ':(exclude,glob).github/**'
    ':(exclude,glob)ci/**'
    ':(exclude,glob)docs/**'
    ':(exclude,glob)packaging/**'
    ':(exclude,glob)utils/**'
    ':(exclude)Makefile'
    ':(exclude)conftest.py'
    ':(exclude)pytest.ini'
    ':(exclude)setup.cfg'
    ':(exclude)requirements.txt'
    ':(exclude)README.md'
    ':(exclude)CONTRIBUTING.md'
    ':(exclude)LICENSE'
    ':(exclude,glob)buildsys-pre-build*'
    # spec post-install scrubs
    ':(exclude,glob)repos/**/tests/**'
    ':(exclude,glob)repos/**/Makefile'
    ':(exclude,glob)repos/common/**/test.py'
    ':(exclude,glob)commands/tests/**'
)

# Drop commands/* entirely when sitelib is unknown.
[[ -z "$SITELIB" ]] && EXCLUDES+=( ':(exclude,glob)commands/**' )

# Drop any system_upgrade subtree not in the keep list.
if [[ -n "$KEEP_SUBTREES" && -d repos/system_upgrade ]]; then
    IFS=',' read -ra keep_arr <<< "$KEEP_SUBTREES"
    for src_sub in repos/system_upgrade/*/; do
        src_name=$(basename "$src_sub")
        keep=0
        for k in "${keep_arr[@]}"; do
            [[ "$src_name" == "$k" ]] && { keep=1; break; }
        done
        [[ "$keep" == 0 ]] && EXCLUDES+=( ":(exclude,glob)repos/system_upgrade/${src_name}/**" )
    done
fi

# --- generate & rewrite ------------------------------------------------------

# Normalize detected roots to start with a single '/' so the rewrite
# preserves the `a/`/`b/` prefix that patch -p1 expects.
INSTALL_ROOT="/${INSTALL_ROOT#/}"
[[ -n "$SITELIB" ]] && SITELIB="/${SITELIB#/}"

# sed rewrites anchored to a/ and b/ so only patch header lines are
# touched, not hunk contents.
SED_ARGS=(
    -e "s|([ab])/etc/leapp/transaction/|\1/etc/leapp/transaction/|g"
    -e "s|([ab])/repos/|\1${INSTALL_ROOT}/|g"
)
[[ -n "$SITELIB" ]] && SED_ARGS+=( -e "s|([ab])/commands/|\1${SITELIB}/leapp/cli/commands/|g" )

git diff "${FROM_REF}..${TO_REF}" -- . "${EXCLUDES[@]}" \
    | sed -E "${SED_ARGS[@]}" \
    > "$OUT"

if ! [[ -s "$OUT" ]]; then
    rm -f "$OUT"
    die "no installable changes between ${FROM_REF} and ${TO_REF}"
fi

# --- report & dry-run --------------------------------------------------------
#
# Dry-run only makes sense when the patch targets *this* host's layout.
# If we're cross-building (--from picked a variant that isn't installed
# here, or no leapp-upgrade-* RPM is installed at all), a "success"
# would just mean the diff happened not to touch any variant-specific
# paths, and a "failure" would not mean the patch is wrong. Skip it.

patch_targets_this_host() {
    [[ -d "$INSTALL_ROOT" ]] || { echo "install_root missing: $INSTALL_ROOT"; return 1; }
    [[ -z "$SITELIB" || -d "$SITELIB" ]] || { echo "sitelib missing: $SITELIB"; return 1; }
    if [[ -n "$KEEP_SUBTREES" ]]; then
        IFS=',' read -ra _keeps <<< "$KEEP_SUBTREES"
        for t in "${_keeps[@]}"; do
            [[ -d "$INSTALL_ROOT/system_upgrade/$t" ]] || {
                echo "subtree not installed here: system_upgrade/$t"; return 1; }
        done
    fi
    return 0
}

echo >&2
echo "from_version = ${FROM_VERSION:-<autodetect>}" >&2
echo "install_root = $INSTALL_ROOT" >&2
echo "sitelib      = ${SITELIB:-<unset, commands/* excluded>}" >&2
echo "subtrees     = ${KEEP_SUBTREES:-<all>}" >&2
echo >&2

if ! command -v patch >/dev/null 2>&1; then
    : # no patch binary, nothing to do
elif skip_reason=$(patch_targets_this_host); then
    echo "--- dry-run applying to / ---" >&2
    if patch --dry-run -p1 -d / < "$OUT" >&2; then
        echo "--- dry-run OK ---" >&2
    else
        echo "--- dry-run FAILED; inspect before applying ---" >&2
    fi
else
    echo "--- skipping dry-run: patch targets a layout other than this host ($skip_reason) ---" >&2
fi

echo "$OUT"

cat >&2 <<EOF

To apply:   patch -p1 -d / < $OUT
To revert:  patch -R -p1 -d / < $OUT
EOF
