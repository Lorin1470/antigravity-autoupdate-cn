#!/bin/bash
# ==============================================================================
# 卸載 macOS LaunchAgent 定時檢查服務
# ==============================================================================
PLIST_NAME="com.google.antigravity.autoupdate.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"
APP_SUPPORT_DIR="$HOME/Library/Application Support/AntigravityUpdater"

if [ -f "$TARGET_PLIST" ]; then
    launchctl unload "$TARGET_PLIST" 2>/dev/null || true
    rm -f "$TARGET_PLIST"
    echo "======================================================"
    echo " [成功] 後台自啟動智慧更新服務已成功卸載並停用！"
    echo "======================================================"
else
    echo "[資訊] 未找到已安裝的服務。"
fi
