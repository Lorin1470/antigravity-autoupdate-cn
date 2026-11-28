#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Antigravity 自動更新與漢化/儀表板整合腳本 (macOS)
功能：
1. 自動檢查 Google Antigravity 官方最新版本
2. 下載官方安裝包並校驗 SHA-512 完整性
3. 自動安裝並保留安全備份
4. 自動同步最新繁體/簡體中文化補丁 (antigravity2-cn) 並套用注入
5. 自動同步最新 Antigrative Dashboard 插件並套用
6. 自動啟動支援調試端口的 Antigravity (Dashboard)
"""

import os
import sys
import platform
import json
import re
import time
import base64
import hashlib
import shutil
import tempfile
import plistlib
import subprocess
import urllib.request
import argparse
from pathlib import Path

# ANSI 顏色常量
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

def _ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log_info(msg):
    print(f"[{_ts()}] {Colors.BLUE}[資訊]{Colors.RESET} {msg}", flush=True)

def log_success(msg):
    print(f"[{_ts()}] {Colors.GREEN}[成功]{Colors.RESET} {msg}", flush=True)

def log_warning(msg):
    print(f"[{_ts()}] {Colors.YELLOW}[警告]{Colors.RESET} {msg}", flush=True)

def log_error(msg):
    print(f"[{_ts()}] {Colors.RED}[錯誤]{Colors.RESET} {msg}", flush=True)

def log_step(step_num, total_steps, title):
    print(f"\n[{_ts()}] {Colors.BOLD}{Colors.CYAN}=== 步驟 [{step_num}/{total_steps}]: {title} ==={Colors.RESET}", flush=True)

def notify_macos(title, message):
    try:
        clean_title = title.replace('"', '\\"')
        clean_message = message.replace('"', '\\"')
        subprocess.run([
            "osascript", "-e",
            f'display notification "{clean_message}" with title "{clean_title}" sound name "Glass"'
        ], capture_output=True)
    except Exception:
        pass

class AntigravityAutoUpdater:
    def __init__(self, config_path=None):
        self.script_dir = Path(__file__).resolve().parent
        self.config_path = config_path or (self.script_dir / 'config.json')
        self.config = self.load_config()
        self.arch = self.detect_arch()
        self.app_path = Path(self.config.get('app_path', '/Applications/Antigravity.app'))
        self.deps_dir = self.script_dir / 'deps'
        self.cn_repo_dir = self.deps_dir / 'antigravity2-cn'
        self.dashboard_repo_dir = self.deps_dir / 'antigrative-dashboard'
        self.manifest_base = "https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/manifest"

    def load_config(self):
        default_cfg = {
            "language": "tw",
            "brand_title": "english",
            "app_path": "/Applications/Antigravity.app",
            "enable_dashboard": True,
            "auto_launch": True,
            "git_proxy": ""
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_cfg = json.load(f)
                    default_cfg.update(user_cfg)
            except Exception as e:
                log_warning(f"讀取 config.json 失敗，使用預設配置: {e}")
        return default_cfg

    def detect_arch(self):
        machine = platform.machine().lower()
        if machine in ['arm64', 'aarch64']:
            return 'arm64'
        elif machine in ['x86_64', 'amd64']:
            return 'x64'
        else:
            log_warning(f"未知架構 {machine}，預設使用 arm64")
            return 'arm64'

    def get_local_version(self):
        info_plist = self.app_path / 'Contents' / 'Info.plist'
        if not info_plist.exists():
            return None
        try:
            with open(info_plist, 'rb') as f:
                plist = plistlib.load(f)
                return plist.get('CFBundleShortVersionString') or plist.get('CFBundleVersion')
        except Exception as e:
            log_warning(f"讀取本機 Info.plist 失敗: {e}")
            return None

    def get_remote_manifest(self, retries=3, delay=3):
        candidates = []
        arch_tag = 'arm' if self.arch == 'arm64' else 'x64'

        for attempt in range(1, retries + 1):
            candidates.clear()
            # 來源 1: 官方官網發布頁面 (最新首發版本)
            try:
                log_info(f"正在檢查官方官網發布版本 (https://antigravity.google/download)...")
                req_web = urllib.request.Request(
                    "https://antigravity.google/download",
                    headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
                )
                with urllib.request.urlopen(req_web, timeout=12) as resp:
                    html = resp.read().decode('utf-8')
                pattern = rf'https://storage\.googleapis\.com/antigravity-public/antigravity-hub/([0-9\.]+-[0-9]+)/darwin-{arch_tag}/Antigravity\.(dmg|zip)'
                m = re.search(pattern, html)
                if m:
                    build_id = m.group(1)
                    ver = build_id.split('-')[0]
                    zip_url = f'https://storage.googleapis.com/antigravity-public/antigravity-hub/{build_id}/darwin-{arch_tag}/Antigravity.zip'
                    candidates.append({
                        'version': ver,
                        'url': zip_url,
                        'sha512': None,
                        'source': '官方官網'
                    })
            except Exception as e:
                log_warning(f"檢查官方官網發布頁面失敗 (嘗試 {attempt}/{retries}): {e}")

            # 來源 2: 官方自動更新清單 (分批推播通道)
            manifest_url = f"{self.manifest_base}/latest-{self.arch}-mac.yml"
            try:
                log_info(f"正在檢查官方推送清單 ({manifest_url})...")
                req = urllib.request.Request(
                    manifest_url,
                    headers={'User-Agent': 'AntigravityAutoUpdater/1.0'}
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    content = resp.read().decode('utf-8')
                version_m = re.search(r'^version:\s*(.+)$', content, re.MULTILINE)
                url_m = re.search(r'url:\s*(https?://[^\s]+)', content)
                sha_m = re.search(r'sha512:\s*([^\s]+)', content)
                if version_m and url_m:
                    candidates.append({
                        'version': version_m.group(1).strip(),
                        'url': url_m.group(1).strip(),
                        'sha512': sha_m.group(1).strip() if sha_m else None,
                        'source': '推送通道'
                    })
            except Exception as e:
                log_warning(f"檢查官方推送清單失敗 (嘗試 {attempt}/{retries}): {e}")

            if candidates:
                break

            if attempt < retries:
                log_info(f"網路暫時不可用，正在等待 {delay} 秒後重試...")
                time.sleep(delay)

        if not candidates:
            raise RuntimeError("無法連線至任何官方更新來源，請檢查網路連線或稍後重試。")

        # 排序選取版本號最高的來源
        candidates.sort(key=lambda c: self.parse_semver(c['version']), reverse=True)
        best = candidates[0]
        log_success(f"取得最新版本: v{best['version']} (來源: {best['source']})")
        return best

    def parse_semver(self, ver_str):
        if not ver_str:
            return (0, 0, 0)
        clean = re.sub(r'^[^\d]*', '', ver_str)
        parts = []
        for x in clean.split('.'):
            num = re.sub(r'[^\d].*$', '', x)
            parts.append(int(num) if num.isdigit() else 0)
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])

    def is_app_running(self):
        try:
            exe_marker = f"{self.app_path}/Contents/MacOS/Antigravity"
            res = subprocess.run(
                ["/bin/ps", "-ww", "-axo", "command="],
                capture_output=True,
                text=True
            )
            for line in res.stdout.splitlines():
                if exe_marker in line and "Helper" not in line and "--type=" not in line:
                    return True
            return False
        except Exception:
            return False

    def quit_app(self, timeout=10):
        if not self.is_app_running():
            return True

        log_info("偵測到 Antigravity 正在執行，正在發送安全退出指令...")
        subprocess.run(
            ["osascript", "-e", 'tell application "Antigravity" to quit'],
            capture_output=True
        )

        start = time.time()
        while time.time() - start < timeout:
            if not self.is_app_running():
                log_success("Antigravity 已正常關閉。")
                return True
            time.sleep(0.5)

        log_warning("程式未在超時時間內關閉，正在強制終止以確保升級順利...")
        subprocess.run(
            ["pkill", "-9", "-f", "Antigravity.app/Contents/MacOS/Antigravity"],
            capture_output=True
        )
        time.sleep(1)
        return not self.is_app_running()

    def download_file(self, url, dest_path, expected_sha512=None):
        log_info(f"開始下載安裝包: {url}")
        curl_bin = shutil.which("curl")

        if curl_bin:
            cmd = [
                curl_bin,
                "-fL",
                "-C", "-",
                "--retry", "5",
                "--retry-delay", "3",
                "--connect-timeout", "20",
                "--speed-limit", "10240",
                "--speed-time", "30",
                "-#",
                "-o", str(dest_path),
                url
            ]
            for attempt in range(1, 4):
                res = subprocess.run(cmd)
                if res.returncode == 0:
                    break
                if res.returncode == 33 and os.path.exists(dest_path):
                    os.remove(dest_path)
                if attempt < 3:
                    log_warning(f"下載中斷 (代碼 {res.returncode})，3 秒後自動斷點續傳 (第 {attempt}/3 輪)...")
                    time.sleep(3)
                else:
                    raise RuntimeError(f"下載失敗，請檢查網路連線 (curl exit code: {res.returncode})")
        else:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                total_size = int(resp.headers.get('Content-Length', 0))
                downloaded = 0
                block_size = 65536
                start_time = time.time()

                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = resp.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = downloaded * 100 / total_size
                            elapsed = time.time() - start_time
                            speed = (downloaded / (1024 * 1024)) / (elapsed if elapsed > 0 else 1)
                            sys.stdout.write(
                                f"\r{Colors.CYAN}[下載進度]{Colors.RESET} {percent:5.1f}% "
                                f"({downloaded/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB) "
                                f"@ {speed:.1f} MB/s"
                            )
                            sys.stdout.flush()
                print()

        log_success("檔案下載完成！")

        if expected_sha512:
            log_info("正在校驗 SHA-512 完整性雜湊值...")
            hasher = hashlib.sha512()
            with open(dest_path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    hasher.update(chunk)
            actual_b64 = base64.b64encode(hasher.digest()).decode('ascii')
            if actual_b64 != expected_sha512:
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
                raise ValueError(
                    f"雜湊校驗失敗！預期: {expected_sha512}, 實際: {actual_b64}"
                )
            log_success("雜湊校驗通過 (SHA-512 符合官方簽署)！")

    def install_official_app(self, zip_path):
        temp_extract = Path(tempfile.mkdtemp(prefix="antigravity_extract_"))
        try:
            log_info("正在解壓縮官方安裝套件 (ditto)...")
            res = subprocess.run(
                ["/usr/bin/ditto", "-x", "-k", str(zip_path), str(temp_extract)],
                capture_output=True,
                text=True
            )
            if res.returncode != 0:
                raise RuntimeError(f"解壓縮失敗: {res.stderr}")

            new_app = temp_extract / "Antigravity.app"
            if not new_app.exists():
                candidates = list(temp_extract.glob("*.app"))
                if candidates:
                    new_app = candidates[0]
                else:
                    raise RuntimeError("解壓目錄中未找到 Antigravity.app！")

            backup_path = Path(f"/tmp/Antigravity_backup_{int(time.time())}.app")
            if self.app_path.exists():
                log_info(f"正在建立舊版本備份 -> {backup_path}")
                try:
                    shutil.copytree(str(self.app_path), str(backup_path), symlinks=True)
                except Exception as e:
                    log_warning(f"備份舊版本失敗 (繼續安裝): {e}")

                log_info(f"正在移除舊版本 {self.app_path}...")
                shutil.rmtree(str(self.app_path))

            log_info(f"正在部署新版本至 {self.app_path}...")
            shutil.move(str(new_app), str(self.app_path))

            log_info("正在解除 macOS Quarantine 隔離屬性...")
            subprocess.run(["xattr", "-cr", str(self.app_path)], capture_output=True)

            log_success(f"官方新版本已成功安裝至 {self.app_path}！")

        finally:
            if temp_extract.exists():
                shutil.rmtree(str(temp_extract), ignore_errors=True)

    def sync_git_repo(self, repo_dir, repo_url):
        env = os.environ.copy()
        proxy = self.config.get('git_proxy')
        if proxy:
            env['https_proxy'] = proxy
            env['http_proxy'] = proxy

        if not repo_dir.exists():
            log_info(f"正在克隆倉庫 {repo_url}...")
            res = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
                capture_output=True,
                text=True,
                env=env
            )
            if res.returncode != 0:
                raise RuntimeError(f"git clone 失敗: {res.stderr}")
            subprocess.run(["git", "-C", str(repo_dir), "config", "core.autocrlf", "false"], capture_output=True, env=env)
        else:
            log_info(f"正在同步更新倉庫 {repo_dir.name}...")
            subprocess.run(["git", "-C", str(repo_dir), "config", "core.autocrlf", "false"], capture_output=True, env=env)
            subprocess.run(["git", "-C", str(repo_dir), "checkout", "-f"], capture_output=True, env=env)
            subprocess.run(["git", "-C", str(repo_dir), "fetch", "--depth", "1", "origin", "main"], capture_output=True, env=env)
            res = subprocess.run(
                ["git", "-C", str(repo_dir), "reset", "--hard", "origin/main"],
                capture_output=True,
                text=True,
                env=env
            )
            if res.returncode != 0:
                log_warning(f"git reset 失敗: {res.stderr}")

    def apply_localization(self, lang="tw", brand_title="english"):
        log_info(f"正在準備套用漢化 (語言: {lang.upper()}, 品牌樣式: {brand_title})...")
        self.sync_git_repo(self.cn_repo_dir, "https://github.com/qqxpee/antigravity2-cn.git")

        engine_script = self.cn_repo_dir / "localization_engine.js"
        if not engine_script.exists():
            raise RuntimeError(f"未找到 localization_engine.js: {engine_script}")

        cmd = [
            "node",
            str(engine_script),
            f"--{lang}",
            "--brand-title", brand_title,
            "--install-dir", str(self.app_path),
            "--no-kill"
        ]

        log_info(f"執行中文化注入引擎: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=str(self.cn_repo_dir), text=True)
        if res.returncode != 0:
            raise RuntimeError(f"漢化引擎執行失敗 (Exit Code: {res.returncode})")

        log_success("Antigravity 中文化注入與 Ad-hoc 簽名完成！")

    def apply_dashboard(self):
        log_info("正在準備同步 Antigrative Dashboard 插件...")
        self.sync_git_repo(self.dashboard_repo_dir, "https://github.com/ATtacK030130/antigrative-dashboard.git")

        manage_script = self.dashboard_repo_dir / "manage.py"
        if not manage_script.exists():
            raise RuntimeError(f"未找到 manage.py: {manage_script}")

        log_info("正在執行 dashboard 插件安裝與啟動包設定...")
        res = subprocess.run([sys.executable, str(manage_script), "install"], cwd=str(self.dashboard_repo_dir), text=True)
        if res.returncode != 0:
            log_warning("Dashboard install 退出碼非 0，請檢查日誌。")
        else:
            log_success("Dashboard 插件已成功安裝至用戶外掛目錄，啟動包配置完成！")

        # 檢查 status
        try:
            status_res = subprocess.run(
                [sys.executable, str(manage_script), "status"],
                cwd=str(self.dashboard_repo_dir),
                capture_output=True,
                text=True
            )
            if status_res.returncode == 0:
                status_json = json.loads(status_res.stdout)
                log_info(f"Dashboard 狀態: 整合模式={status_json.get('integrationMode')}, 啟用={status_json.get('enabled')}")
        except Exception:
            pass

    def launch_app(self):
        dashboard_app = Path(os.path.expanduser("~/Applications/Antigravity (Dashboard).app"))
        if self.config.get('enable_dashboard', True) and dashboard_app.exists():
            log_info(f"正在啟動 {dashboard_app} (支援模型欄儀表板即時串流)...")
            subprocess.run(["open", "-a", str(dashboard_app)])
        elif self.app_path.exists():
            log_info(f"正在啟動 {self.app_path}...")
            subprocess.run(["open", "-a", str(self.app_path)])
        else:
            log_warning("未找到可啟動的 Antigravity 應用程式。")

    def run(self, check_only=False, force=False, patch_only=False, lang=None, brand_title=None, no_launch=False, background=False):
        if not background:
            print(f"{Colors.BOLD}{Colors.HEADER}===================================================={Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.HEADER}   Google Antigravity macOS 自動更新與漢化整合工具   {Colors.RESET}")
            print(f"{Colors.BOLD}{Colors.HEADER}===================================================={Colors.RESET}")

        target_lang = lang or self.config.get('language', 'tw')
        target_brand = brand_title or self.config.get('brand_title', 'english')

        local_ver = self.get_local_version()
        if not background:
            log_info(f"本機架構: {self.arch} | 目前安裝版本: {local_ver or '未安裝'}")

        # 1. 檢查更新
        if not background:
            log_step(1, 4 if patch_only else 6, "檢查官方最新版本")
        try:
            manifest = self.get_remote_manifest()
        except Exception as e:
            if background:
                log_warning(f"後台檢查網路不可用，略過本次排程: {e}")
                return 0
            raise
        remote_ver = manifest['version']
        if not background:
            log_info(f"官方最新版本: {remote_ver} (來自 {manifest.get('source', '官方管道')})")

        has_update = False
        if not local_ver:
            has_update = True
            if not background:
                log_info("本機尚未安裝 Antigravity，將進行全新安裝。")
        else:
            local_tuple = self.parse_semver(local_ver)
            remote_tuple = self.parse_semver(remote_ver)
            if remote_tuple > local_tuple:
                has_update = True
                if not background:
                    log_info(f"發現新版本！本地: v{local_ver} -> 官方最新: v{remote_ver}")
            elif remote_tuple == local_tuple:
                if not background:
                    log_info(f"目前已是官方最新版本 (v{local_ver})。")
            else:
                if not background:
                    log_info(f"本地版本 (v{local_ver}) 高於或等於官方伺服器最新發布版本。")

        if check_only:
            if has_update:
                print(f"\n{Colors.GREEN}[結果] 存在可用更新: v{remote_ver}！{Colors.RESET}")
                return 10
            else:
                print(f"\n{Colors.CYAN}[結果] 目前已是最新版，無須更新。{Colors.RESET}")
                return 0

        # 後台自啟動模式處理
        if background:
            if not has_update:
                return 0

            temp_zip = Path(tempfile.gettempdir()) / f"Antigravity-{remote_ver}-{self.arch}.zip"
            log_info(f"後台偵測到新版本 v{remote_ver}，正在背景預先下載安裝檔...")
            self.download_file(manifest['url'], temp_zip, manifest.get('sha512'))

            if self.is_app_running():
                prompt_state_file = Path(tempfile.gettempdir()) / "antigravity_prompt_state.json"
                should_prompt = True
                try:
                    if prompt_state_file.exists():
                        st = json.loads(prompt_state_file.read_text(encoding='utf-8'))
                        if st.get('version') == remote_ver and (time.time() - st.get('timestamp', 0)) < 14400:
                            should_prompt = False
                except Exception:
                    pass

                if not should_prompt:
                    log_info(f"新版本 v{remote_ver} 已在背景就緒，4 小時內已提示過使用者，等待軟體關閉後自動套用。")
                    return 0

                try:
                    prompt_state_file.write_text(json.dumps({
                        'version': remote_ver,
                        'timestamp': time.time()
                    }), encoding='utf-8')
                except Exception:
                    pass

                log_info(f"新版本 v{remote_ver} 已預先下載完畢，彈出視窗詢問使用者是否立即重啟更新...")
                dlg_script = (
                    f'button returned of (display dialog '
                    f'"Google Antigravity 已在背景為您下載好最新版本 v{remote_ver}！\\n\\n'
                    f'是否立即重啟以套用官方更新與繁體中文化？（約需 5 秒）" '
                    f'buttons {{"稍後再說", "立即重啟更新"}} '
                    f'default button "立即重啟更新" '
                    f'with title "Antigravity 自動更新就緒")'
                )
                res = subprocess.run(["osascript", "-e", dlg_script], capture_output=True, text=True)
                if res.returncode == 0 and "立即重啟更新" in res.stdout:
                    log_info("使用者選擇立即重啟更新，開始安全關閉並套用安裝...")
                    self.quit_app()
                    try:
                        self.install_official_app(temp_zip)
                    finally:
                        if temp_zip.exists():
                            try: temp_zip.unlink()
                            except Exception: pass
                    self.apply_localization(lang=target_lang, brand_title=target_brand)
                    if self.config.get('enable_dashboard', True):
                        self.apply_dashboard()
                    if self.config.get('auto_launch', True):
                        self.launch_app()
                    notify_macos(
                        "Antigravity 自動更新成功",
                        f"已升級至 v{remote_ver} 並完成繁中漢化與儀表板配置！"
                    )
                else:
                    log_info("使用者選擇稍後更新，安裝檔已暫存就緒。")
                return 0
            else:
                log_info(f"後台偵測到新版本 v{remote_ver} 且應用未運行，開始執行無感自動更新...")
                try:
                    self.install_official_app(temp_zip)
                finally:
                    if temp_zip.exists():
                        try: temp_zip.unlink()
                        except Exception: pass

                self.apply_localization(lang=target_lang, brand_title=target_brand)
                if self.config.get('enable_dashboard', True):
                    self.apply_dashboard()

                notify_macos(
                    "Antigravity 自動更新成功",
                    f"軟體已在後台自動完成 v{remote_ver} 更新，並已套用繁中中文化與儀表板！"
                )
                return 0

        if not patch_only and not has_update and not force:
            print(f"\n{Colors.YELLOW}提示: 目前軟體已是最新版。若需要重新套用漢化或儀表板，請加 --force 或 --patch-only 參數。{Colors.RESET}")
            return 0

        # 2. 下載官方最新安裝包 (在關閉應用前下載，支援斷點續傳)
        if not patch_only:
            log_step(2, 6, "下載官方最新安裝包")
            temp_zip = Path(tempfile.gettempdir()) / f"Antigravity-{remote_ver}-{self.arch}.zip"
            self.download_file(manifest['url'], temp_zip, manifest.get('sha512'))

            # 3. 安全關閉目前運行的 App
            log_step(3, 6, "安全關閉 Antigravity 避免檔案鎖定")
            self.quit_app()

            # 4. 替換與部署全新官方版本
            log_step(4, 6, "替換與部署全新官方版本")
            try:
                self.install_official_app(temp_zip)
            finally:
                if temp_zip.exists():
                    try:
                        temp_zip.unlink()
                    except Exception:
                        pass
        else:
            log_step(2, 4, "安全關閉 Antigravity 避免檔案鎖定")
            self.quit_app()

        # 5. 套用漢化
        log_step(5 if not patch_only else 3, 4 if patch_only else 6, "同步並注入中文漢化套件")
        self.apply_localization(lang=target_lang, brand_title=target_brand)

        # 6. 套用儀表板
        if self.config.get('enable_dashboard', True):
            log_step(5 if not patch_only else 3, 4 if patch_only else 6, "同步並配置 Antigrative Dashboard 插件")
            self.apply_dashboard()

        # 6. 重新啟動
        final_step = 4 if patch_only else 6
        if not no_launch and self.config.get('auto_launch', True):
            log_step(final_step, final_step, "重新啟動 Antigravity")
            self.launch_app()
        else:
            log_info("已設定不自動啟動應用程式。")

        print(f"\n{Colors.BOLD}{Colors.GREEN}===================================================={Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}   🎉 更新與漢化設定全部完成！享受流暢的中文開發體驗！   {Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN}===================================================={Colors.RESET}\n")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Google Antigravity 自動更新與漢化/儀表板整合工具")
    parser.add_argument("--check", action="store_true", help="僅檢查是否有官方更新")
    parser.add_argument("--force", action="store_true", help="強制重新下載官方安裝包並重新套用漢化")
    parser.add_argument("--patch-only", action="store_true", help="不重新下載官方安裝檔，僅重新同步並套用漢化與儀表板")
    parser.add_argument("--lang", choices=["tw", "sc"], help="指定語言: tw (繁體中文) 或 sc (簡體中文)")
    parser.add_argument("--brand-title", choices=["english", "hidden", "translated"], help="左上角品牌文字樣式")
    parser.add_argument("--no-launch", action="store_true", help="完成後不自動啟動 Antigravity")
    parser.add_argument("--background", action="store_true", help="以背景守護模式執行（靜默檢查，非使用中時自動更新，使用中時彈出通知）")

    args = parser.parse_args()

    updater = AntigravityAutoUpdater()
    try:
        code = updater.run(
            check_only=args.check,
            force=args.force,
            patch_only=args.patch_only,
            lang=args.lang,
            brand_title=args.brand_title,
            no_launch=args.no_launch,
            background=args.background
        )
        sys.exit(code)
    except KeyboardInterrupt:
        print("\n使用者中斷操作。")
        sys.exit(130)
    except Exception as e:
        log_error(f"執行過程中發生異常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
