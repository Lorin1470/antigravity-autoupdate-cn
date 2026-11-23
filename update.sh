#!/bin/bash
# ==============================================================================
# Google Antigravity macOS 一鍵更新與漢化/儀表板腳本
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 補充 macOS 常見環境路徑 (Homebrew, nvm, fnm, volta, mise, asdf 等)
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=""
if [ -n "$REAL_USER" ] && command -v dscl >/dev/null 2>&1; then
    REAL_HOME=$(dscl . -read "/Users/$REAL_USER" NFSHomeDirectory 2>/dev/null | awk '{print $2}')
fi
if [ -z "$REAL_HOME" ] || [ ! -d "$REAL_HOME" ]; then
    REAL_HOME="$HOME"
fi

for p in "$REAL_HOME/.volta/bin" "$REAL_HOME/.asdf/shims" "$REAL_HOME/.local/share/mise/shims" "$REAL_HOME/.local/bin" "$REAL_HOME/.fnm/current/bin"; do
    [ -d "$p" ] && export PATH="$p:$PATH"
done

# 優先尋找支援 Python 3.10+ 的 Python 直譯器 (Antigrative Dashboard 需要 3.10+)
PYTHON_BIN=""
for candidate in \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10 \
    /usr/local/bin/python3 \
    python3.12 \
    python3.11 \
    python3.10 \
    python3
do
    if command -v "$candidate" >/dev/null 2>&1; then
        CAND_BIN="$(command -v "$candidate")"
        IS_GE_310=$("$CAND_BIN" -c "import sys; print(1 if sys.version_info >= (3, 10) else 0)" 2>/dev/null || echo 0)
        if [ "$IS_GE_310" = "1" ]; then
            PYTHON_BIN="$CAND_BIN"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    else
        echo "[錯誤] 系統未安裝 python3，請先安裝 Python 3！"
        exit 1
    fi
fi

# 檢查 Node.js
if ! command -v node >/dev/null 2>&1; then
    echo "[錯誤] 系統未安裝 node，漢化引擎需要 Node.js 環境！"
    echo "請至 https://nodejs.org 下載安裝 Node.js (LTS 版本)。"
    exit 1
fi

# 執行核心更新程式
exec "$PYTHON_BIN" "$SCRIPT_DIR/auto_updater.py" "$@"
