#!/bin/sh
# Check prerequisites before asking Things for its version and list count.
set -eu

connect=yes
case "${1-}" in
    --no-connect) connect=no ;;
    --help|-h)
        printf '%s\n' 'Usage: sh check_setup.sh [--no-connect]' \
            'Requires macOS and Python 3.10+. Default: verify the Things connection.' \
            'Use --no-connect to check prerequisites without contacting Things.' \
            'Set THINGS_PYTHON to use a specific Python executable.'
        exit 0 ;;
    '') ;;
    *) printf '%s\n' 'Unknown option. Use --help.' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    printf '%s\n' 'Pass at most one option. Use --help.' >&2
    exit 2
fi

if [ "$(uname -s)" != Darwin ]; then
    printf '%s\n' 'Things requires execution on a Mac with Things 3 installed.' \
        'Open a local chat on that Mac or select a connected Mac host.' >&2
    exit 1
fi

check_python() {
    [ -n "$1" ] && [ -x "$1" ] || return 1
    # Avoid triggering the developer-tools installer through the macOS stub.
    if [ "$1" = /usr/bin/python3 ] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
        return 1
    fi
    "$1" -c 'import sys; print(".".join(map(str, sys.version_info[:3]))); sys.exit(sys.version_info < (3, 10))' 2>/dev/null
}

things_python=''
things_python_version=''
if [ -n "${THINGS_PYTHON-}" ]; then
    things_python=$THINGS_PYTHON
    if ! things_python_version=$(check_python "$things_python"); then
        printf '%s\n' 'THINGS_PYTHON must point to an executable Python 3.10 or later.' >&2
        exit 1
    fi
else
    things_path_python=$(command -v python3 || true)
    for candidate in "$things_path_python" /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
        if things_python_version=$(check_python "$candidate"); then
            things_python=$candidate
            break
        fi
    done
fi

if [ -z "$things_python" ]; then
    printf '%s\n' 'Python 3.10 or later was not found.' \
        'Use a bundled Python runtime supplied by your agent, or install Python from https://www.python.org/downloads/macos/.' \
        'To select an existing runtime, set THINGS_PYTHON to its absolute executable path.' >&2
    exit 1
fi

printf 'macOS: supported\nPython: %s (%s)\n' "$things_python" "$things_python_version"
if [ "$connect" = no ]; then
    printf '%s\n' 'Prerequisites found. Things connection has not been checked.'
    exit 0
fi

things_script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
printf '%s\n' 'Checking the Things connection. macOS may ask for Automation permission.'
exec "$things_python" "$things_script_dir/things.py" status
