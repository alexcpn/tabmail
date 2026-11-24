#!/usr/bin/env sh
# Add tabmail to your desktop's app launcher, so it can be started by
# pressing Super (Linux) or Cmd+Space (macOS) and typing "tabmail" or "mail".
#
#   ./install-launcher.sh             install
#   ./install-launcher.sh --uninstall remove
#
# Linux: writes ~/.local/share/applications/tabmail.desktop (opens in your
#        default terminal). macOS: creates ~/Applications/tabmail.app, which
#        opens Terminal running tabmail.
set -eu

DIR=$(cd "$(dirname "$0")" && pwd)
UV=$(command -v uv || true)

case "$(uname -s)" in
Linux)
    TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/applications/tabmail.desktop"
    if [ "${1:-}" = "--uninstall" ]; then
        rm -f "$TARGET" && echo "Removed $TARGET"
        exit 0
    fi
    [ -n "$UV" ] || { echo "uv not found: install it from https://docs.astral.sh/uv/" >&2; exit 1; }
    mkdir -p "$(dirname "$TARGET")"
    # Absolute paths: launchers don't load your shell profile, so PATH may lack uv.
    cat > "$TARGET" <<EOF
[Desktop Entry]
Type=Application
Name=tabmail
GenericName=Mail
Comment=Your inbox, sorted by common sense and a small AI
Keywords=mail;email;inbox;gmail;
Exec="$UV" run "$DIR/tabmail.py"
Path=$DIR
Terminal=true
Icon=internet-mail
Categories=Network;Email;
EOF
    chmod 644 "$TARGET"
    command -v update-desktop-database >/dev/null 2>&1 \
        && update-desktop-database "$(dirname "$TARGET")" >/dev/null 2>&1 || true
    echo "Installed $TARGET"
    echo "Press Super and type 'tabmail' or 'mail'."
    ;;
Darwin)
    TARGET="$HOME/Applications/tabmail.app"
    if [ "${1:-}" = "--uninstall" ]; then
        rm -rf "$TARGET" && echo "Removed $TARGET"
        exit 0
    fi
    [ -n "$UV" ] || { echo "uv not found: install it from https://docs.astral.sh/uv/" >&2; exit 1; }
    mkdir -p "$HOME/Applications"
    rm -rf "$TARGET"
    CMD="cd '$DIR' && '$UV' run tabmail.py; exit"
    osacompile -o "$TARGET" \
        -e "tell application \"Terminal\"" \
        -e "    activate" \
        -e "    do script \"$CMD\"" \
        -e "end tell"
    echo "Installed $TARGET"
    echo "Press Cmd+Space and type 'tabmail'. (Typing just 'mail' finds Apple Mail first.)"
    ;;
*)
    echo "Unsupported system: $(uname -s)" >&2
    exit 1
    ;;
esac
