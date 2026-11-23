# Google Antigravity macOS 自動更新與漢化/儀表板整合工具

專為安裝了 **繁體/簡體中文漢化包**（[antigravity2-cn](https://github.com/qqxpee/antigravity2-cn)）與 **Antigrative Dashboard 監控儀表板**（[antigrative-dashboard](https://github.com/ATtacK030130/antigrative-dashboard)）的 macOS 用戶打造的自動化更新解決方案。

---

## 💡 為什麼需要這個工具？

1. **官方更新失效的原因**：  
   Antigravity 是基於 Electron 架構的軟體。中文化會修改核心 `app.asar` 資源檔案，使得 macOS 系統與 Electron 的應用程式數位簽名失效。官方內建的自動更新機制（`Squirrel.Mac` / `electron-updater`）在下載或套用更新包時，因簽名校驗不符而失敗或被阻擋。
2. **手動更新的痛點**：  
   每次有新版推出時，您必須手動到官網下載大體積安裝檔、替換應用程式，但更新後漢化與儀表板插件會直接遺失，又得重新手動執行各項腳本與注入。
3. **本工具的自動化成果**：  
   透過本工具，您只需**點擊一次**，即可在數秒內自動完成：
   - 🔍 **自動檢測官方最新版本**（直接對接 Google 官方更新清單）
   - 📥 **下載最新版官方安裝套件**並校驗 SHA-512 安全雜湊值
   - 📦 **安全備份舊版並全新部署** `/Applications/Antigravity.app`
   - 🌐 **自動同步最新中文漢化倉庫**（[qqxpee/antigravity2-cn](https://github.com/qqxpee/antigravity2-cn)）並執行注入與 macOS 本機 Ad-hoc 重新簽名
   - 📊 **自動同步最新儀表板**（[ATtacK030130/antigrative-dashboard](https://github.com/ATtacK030130/antigrative-dashboard)）並設定支援遠端調試端口的啟動包
   - 🚀 **自動以正確參數啟動 Antigravity**，享受最新功能與繁中介面！

---

## 🚀 快速使用方法

### 方法一：Finder 雙擊執行（最推薦 🖱️）
在 Finder 中打開此專案資料夾，**直接雙擊 `一鍵更新並漢化.command`** 即可！  
終端機視窗會自動開啟，顯示色彩進度條與執行步驟，完成後自動提示關閉。

---

### 方法二：終端機命令列（適合工程師 💻）

```bash
# 進入專案目錄
cd "/Users/kuanggou/Documents/code/google 反重力自動更新"

# 執行自動更新流程（若有新版本會自動下載、安裝、漢化並重啟）
./update.sh
```

#### 常用命令列參數：

| 參數 | 說明 | 範例 |
| :--- | :--- | :--- |
| `--check` | **僅檢查更新**：只對比本地版本與官方最新版本，不執行任何改動 | `./update.sh --check` |
| `--force` | **強制更新**：即使本地已是最新版本，依然強制重新下載、覆蓋安裝並漢化 | `./update.sh --force` |
| `--patch-only` | **僅修復/重新注入**：不重新下載官方安裝包，僅重新同步並套用漢化與儀表板 | `./update.sh --patch-only` |
| `--lang [tw\|sc]` | **指定語言**：`tw` 為繁體中文（預設），`sc` 為簡體中文 | `./update.sh --lang sc` |
| `--brand-title [style]` | **品牌文字樣式**：`english`（預設）、`hidden`（隱藏）、`translated`（中文） | `./update.sh --brand-title english` |
| `--no-launch` | 完成所有更新後**不自動啟動**應用程式 | `./update.sh --no-launch` |

---

## ⚙️ 個性化配置 (`config.json`)

您可以在目錄下的 `config.json` 中自訂預設行為，免去每次輸入參數：

```json
{
  "language": "tw",                  // 語言選擇: "tw" (繁體中文) 或 "sc" (簡體中文)
  "brand_title": "english",          // 左上角標題: "english" (推薦) / "hidden" / "translated"
  "app_path": "/Applications/Antigravity.app", // 軟體安裝路徑
  "enable_dashboard": true,          // 是否同步並啟用 Antigrative Dashboard
  "auto_launch": true,               // 完成後是否自動啟動軟體
  "git_proxy": ""                    // Git 網路代理 (若 GitHub 連線緩慢可填入如 "http://127.0.0.1:7890")
}
```

---

## 🔔 選用：開啟 macOS 後台定時更新通知

若您希望當 Google 官方發布新版本時，macOS 系統能主動彈出通知提醒您更新，可開啟內建的 LaunchAgent 服務：

```bash
# 安裝並啟用後台檢查（每 6 小時靜默檢查一次，發現新版彈出通知）
bash launchd/install_service.sh

# 如需停用/卸載後台通知服務：
bash launchd/uninstall_service.sh
```

---

## 📂 專案檔案結構

- **`一鍵更新並漢化.command`**：macOS Finder 一鍵雙擊入口腳本
- **`update.sh`**：Shell 入口封裝腳本（自動尋找相容的 Python 3.10+ 與 Node.js 環境）
- **`auto_updater.py`**：核心更新引擎（零第三方 pip 依賴，原生解析 manifest、多線程下載進度、SHA-512 校驗）
- **`config.json`**：個人偏好設定檔
- **`deps/`**：相依組件倉庫
  - `deps/antigravity2-cn/`：[qqxpee/antigravity2-cn](https://github.com/qqxpee/antigravity2-cn) 官方漢化庫（自動保持最新）
  - `deps/antigrative-dashboard/`：[ATtacK030130/antigrative-dashboard](https://github.com/ATtacK030130/antigrative-dashboard) 儀表板庫（自動保持最新）
- **`launchd/`**：macOS 系統後台定時檢查與通知服務

---

## 🛡️ 安全性與復原保證

1. **官方直連下載**：安裝套件直接從 Google 官方 Cloud Storage (`storage.googleapis.com`) 下載，絕無第三方篡改風險。
2. **雜湊校驗**：每次下載後均自動與 Google 官方 `latest-mac.yml` 的 SHA-512 雜湊比對。
3. **自動舊版備份**：覆蓋安裝前，程式會自動將現有版本暫存備份至 `/tmp/Antigravity_backup_<timestamp>.app`。
4. **原生簽名相容**：漢化套件注入完畢後，會自動調用 macOS `codesign` 進行本機 ad-hoc 簽名，並清除快取，防止系統報錯「應用程式已損毀」。
