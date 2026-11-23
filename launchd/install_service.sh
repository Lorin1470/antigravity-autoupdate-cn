#!/bin/bash
# ==============================================================================
# 安裝 macOS LaunchAgent 定時智慧更新服務 (登入自啟動 + 每 4 小時自動檢查)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_SUPPORT_DIR="$HOME/Library/Application Support/AntigravityUpdater"
PLIST_NAME="com.google.antigravity.autoupdate.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "正在同步更新程式至系統應用支援目錄以符合 macOS TCC 權限規範..."
mkdir -p "$APP_SUPPORT_DIR" "$HOME/Library/LaunchAgents"

cp -f "$BASE_DIR/auto_updater.py" "$APP_SUPPORT_DIR/"
cp -f "$BASE_DIR/update.sh" "$APP_SUPPORT_DIR/"
cp -f "$BASE_DIR/config.json" "$APP_SUPPORT_DIR/"
chmod +x "$APP_SUPPORT_DIR/update.sh" "$APP_SUPPORT_DIR/auto_updater.py"

if [ ! -d "$APP_SUPPORT_DIR/deps" ]; then
    echo "正在複製相依組件庫至系統目錄..."
    cp -R "$BASE_DIR/deps" "$APP_SUPPORT_DIR/"
fi

# 建立 Runner 腳本
cat << 'RUNNER_EOF' > "$APP_SUPPORT_DIR/runner.sh"
#!/bin/bash
DIR="$HOME/Library/Application Support/AntigravityUpdater"
cd "$DIR"
exec bash "$DIR/update.sh" --background >> /tmp/antigravity_autoupdate.log 2>&1
RUNNER_EOF
chmod +x "$APP_SUPPORT_DIR/runner.sh"

# 建立 LaunchAgent 配置檔 (登入即時檢查 + 每 4 小時檢查一次)
cat << EOF > "$TARGET_PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.google.antigravity.autoupdate</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$APP_SUPPORT_DIR/runner.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>14400</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/antigravity_autoupdate.log</string>
    <key>StandardOutPath</key>
    <string>/tmp/antigravity_autoupdate.log</string>
</dict>
</plist>
EOF

launchctl unload "$TARGET_PLIST" 2>/dev/null || true
launchctl load "$TARGET_PLIST"

echo "======================================================"
echo " [成功] 後台自啟動智慧更新服務已成功啟用！"
echo " 1. 開機/登入時將自動檢查更新 (RunAtLoad: true)"
echo " 2. 每 4 小時在後台自動檢查官方最新版本"
echo " 3. 若軟體未開啟，將無感自動下載升級並完成繁中漢化"
echo " 4. 若軟體正在使用中，將跳出 macOS 系統通知提醒"
echo " 如需停用服務，請執行: bash launchd/uninstall_service.sh"
echo "======================================================"
