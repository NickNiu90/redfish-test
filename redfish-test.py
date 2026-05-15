import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import threading
from urllib.parse import urlparse, urljoin
import configparser
import os
from datetime import datetime
import sys
import locale  # 用于检测系统语言
import time

VERSION="v1.1.0"

# 禁用 SSL 证书警告（测试环境使用）
requests.packages.urllib3.disable_warnings()

# 配置文件路径
CONFIG_FILE = "redfish_tool_config.ini"
# 日志文件路径
LOG_FILE = "redfish_tool_debug.log"
# 最大历史记录数
MAX_HISTORY = 10
# 日志文件最大大小（MB），超过则自动分割
MAX_LOG_SIZE = 5  # 5MB

# ========== 界面适配常量（防止变形的核心） ==========
MIN_WINDOW_WIDTH = 800   # 窗口最小宽度
MIN_WINDOW_HEIGHT = 600  # 窗口最小高度
MIN_COMBO_WIDTH = 20     # 下拉框最小宽度
MIN_BUTTON_WIDTH = 10     # 按钮最小宽度

BASE_PATH = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.abspath('.')

# ========== 多语言配置 ==========
LANG_CONFIG = {
    "zh": {
        "title": "Redfish 测试工具{}",
        "connect_config": "连接配置",
        "redfish_url": "Redfish URL:",
        "delete_selected_url": "删除选中",
        "username": "用户名:",
        "password": "密码:",
        "auth_type": "认证方式:",
        "connect": "连接",
        "disconnect": "断开",
        "refresh": "刷新资源",
        "resource_list": "资源列表",
        "redfish_resource": "Redfish 资源",
        "json_data": "JSON 数据{}",
        "debug_log": "调试日志",
        "clear_log": "清空日志",
        "confirm": "确认",
        "prompt": "提示",
        "success": "成功",
        "error": "错误",
        "no_url_selected": "请先选中要删除的URL！",
        "delete_url_confirm": "是否删除URL：{}？",
        "url_not_in_history": "选中的URL不在历史记录中！",
        "url_deleted": "URL {} 已彻底删除！",
        "clear_log_confirm": "是否清空所有日志（包括日志文件）？",
        "log_cleared": "日志已清空！",
        "connection_success": "连接并加载资源完成！",
        "connection_failed": "连接失败：{}",
        "disconnect_success": "已断开 Redfish 连接！",
        "disconnect_failed": "断开连接异常：{}",
        "refresh_success": "资源列表已刷新",
        "refresh_failed": "刷新失败：{}",
        "load_tree_failed": "加载资源树失败：{}",
        "no_resource_selected": "未选择资源节点，跳过加载",
        "load_resource_failed": "加载资源失败：{}",
        "invalid_url": "无效的Redfish URL格式！示例：https://192.168.1.100/redfish/v1 或 http://192.168.1.100:80/redfish/v1",
        "auth_failed": "{}认证失败！请检查URL、账号密码或认证方式，响应状态码：{}",
        "refresh_10s": "自动刷新 10/s",
        "refresh_10s_content": "（自动刷新 10/s）",
    },
    "en": {
        "title": "Redfish Test Tool{}",
        "connect_config": "Connection Configuration",
        "redfish_url": "Redfish URL:",
        "delete_selected_url": "Delete",
        "username": "Username:",
        "password": "Password:",
        "auth_type": "Auth Type:",
        "connect": "Connect",
        "disconnect": "Disconnect",
        "refresh": "Refresh",
        "resource_list": "Resource List",
        "redfish_resource": "Redfish Resources",
        "json_data": "JSON Data{}",
        "debug_log": "Debug Log",
        "clear_log": "Clear Log",
        "confirm": "Confirm",
        "prompt": "Prompt",
        "success": "Success",
        "error": "Error",
        "no_url_selected": "Please select a URL to delete first!",
        "delete_url_confirm": "Are you sure to delete URL: {}?",
        "url_not_in_history": "The selected URL is not in history!",
        "url_deleted": "URL {} has been deleted completely!",
        "clear_log_confirm": "Are you sure to clear all logs (including log file)?",
        "log_cleared": "Logs cleared successfully!",
        "connection_success": "Connected and loaded resources successfully!",
        "connection_failed": "Connection failed: {}",
        "disconnect_success": "Disconnected from Redfish service!",
        "disconnect_failed": "Disconnection exception: {}",
        "refresh_success": "Resource list refreshed successfully",
        "refresh_failed": "Refresh failed: {}",
        "load_tree_failed": "Failed to load resource tree: {}",
        "no_resource_selected": "No resource node selected, skipping loading",
        "load_resource_failed": "Failed to load resource: {}",
        "invalid_url": "Invalid Redfish URL format! Example: https://192.168.1.100/redfish/v1 or http://192.168.1.100:80/redfish/v1",
        "auth_failed": "{} authentication failed! Please check URL, account password or authentication method, response status code: {}",
        "refresh_10s": "refresh 10/s",
        "refresh_10s_content": " (refresh 10/s)"
    }
}

class RedfishGUIApp:
    def __init__(self, root):
        self.root = root
        
        # ========== 多语言初始化 ==========
        # 自动检测系统语言
        
        # self.current_lang = self._detect_system_language()
        self.current_lang = "en"
        # 关键修复1：lang_var 存储显示名称（中文/English），而非代码
        self.lang_var = tk.StringVar(value=self._get_lang_display_name(self.current_lang))

        
        # 设置初始窗口标题
        self.root.title(LANG_CONFIG[self.current_lang]["title"].format(VERSION))
        
        # 1. 启动最大化 + 限制最小窗口尺寸（防止缩放过小导致变形）
        try:
            self.root.iconbitmap(os.path.join(BASE_PATH, 'assets/images/icon.ico')) 
        except:
            self._log("Icon file not found, using default icon", skip_ui=True)
        self.root.state('zoomed')
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        
        # 2. 根窗口权重配置（基础缩放）
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # 初始化配置解析器
        self.config = configparser.ConfigParser()
        self.url_history = []  # 存储URL历史列表
        self.auto_refresh_var = tk.BooleanVar()
        self._load_config()  # 加载本地配置

        # 配置项
        self.redfish_url_var = tk.StringVar(value=self.url_history[0] if self.url_history else "https://192.168.1.100/redfish/v1")
        self.username = tk.StringVar(value="admin")
        self.password = tk.StringVar(value="password")
        self.auth_type = tk.StringVar(value="Basic")  # JSON / Basic

        self.session = None
        self.base_url = ""
        self.full_base_url = ""

        # 初始化日志文件（检查大小，避免过大）
        self._check_log_size()

        self._setup_ui()
        # 语言变更回调（修改为处理显示名称）
        self.lang_var.trace('w', self._on_language_change)
        
    def _detect_system_language(self):
        """自动检测系统语言，返回zh或en"""
        try:
            # 获取系统默认语言
            system_lang, _ = locale.getlocale()
            self._log(f"Detected system language: {system_lang}", skip_ui=True)
            # 中文系统返回zh，其他返回en
            if system_lang and (system_lang.startswith('zh') or 'CN' in system_lang):
                return "zh"
            else:
                return "en"
        except:
            # 检测失败默认使用英文
            self._log("Failed to detect system language, default to English", skip_ui=True)
            return "en"
    
    def _get_lang_code(self, display_name):
        """根据显示名称获取语言代码"""
        lang_mapping = {"中文": "zh", "English": "en"}
        return lang_mapping.get(display_name, "en")
    
    def _get_lang_display_name(self, lang_code):
        """根据语言代码获取显示名称"""
        reverse_mapping = {"zh": "中文", "en": "English"}
        return reverse_mapping.get(lang_code, "English")

    def _on_language_change(self, *args):
        """语言变更时更新界面文本（修复：处理显示名称）"""
        # 关键修复2：从显示名称转换为语言代码
        display_name = self.lang_var.get()
        self.current_lang = self._get_lang_code(display_name)
        self._log(f"Language changed to: {self.current_lang} (display name: {display_name})", skip_ui=True)
        # 更新窗口标题
        self.root.title(LANG_CONFIG[self.current_lang]["title"].format(VERSION))
        # 重新初始化UI文本
        self._update_ui_text()

    def _update_ui_text(self):
        """更新所有界面元素的文本"""
        lang = self.current_lang
        # 更新连接配置框架标题
        self.connect_frame["text"] = LANG_CONFIG[lang]["connect_config"]
        # 更新标签文本
        self.url_label["text"] = LANG_CONFIG[lang]["redfish_url"]
        self.delete_btn["text"] = LANG_CONFIG[lang]["delete_selected_url"]
        self.user_label["text"] = LANG_CONFIG[lang]["username"]
        self.pwd_label["text"] = LANG_CONFIG[lang]["password"]
        self.auth_label["text"] = LANG_CONFIG[lang]["auth_type"]
        # 更新按钮文本
        self.connect_btn["text"] = LANG_CONFIG[lang]["connect"]
        self.disconnect_btn["text"] = LANG_CONFIG[lang]["disconnect"]
        self.refresh_btn["text"] = LANG_CONFIG[lang]["refresh"]
        # 更新资源列表框架标题
        self.left_frame["text"] = LANG_CONFIG[lang]["resource_list"]
        # 更新资源树列标题
        self.tree.heading("#0", text=LANG_CONFIG[lang]["redfish_resource"])
        # 更新JSON数据框架标题
        self.json_frame["text"] = LANG_CONFIG[lang]["json_data"].format(LANG_CONFIG[self.current_lang]["refresh_10s_content"] if self.auto_refresh_var.get() else "")
        # 更新调试日志框架标题
        self.log_frame["text"] = LANG_CONFIG[lang]["debug_log"]
        # 更新清空日志按钮文本
        self.clear_log_btn["text"] = LANG_CONFIG[lang]["clear_log"]
        # 新增：更新自动刷新复选框文本
        if hasattr(self, 'refresh_checkbox'):
            self.refresh_checkbox["text"] = LANG_CONFIG[lang]["refresh_10s"]

    def _check_log_size(self):
        """检查日志文件大小，超过阈值则重命名备份"""
        try:
            if os.path.exists(LOG_FILE):
                file_size = os.path.getsize(LOG_FILE) / (1024 * 1024)  # 转换为MB
                if file_size > MAX_LOG_SIZE:
                    # 重命名备份（加时间戳）
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_log = f"{LOG_FILE}.bak.{timestamp}"
                    os.rename(LOG_FILE, backup_log)
                    self._log(f"Log file exceeds {MAX_LOG_SIZE}MB, backed up to: {backup_log}", skip_ui=True)
        except Exception as e:
            # 避免日志检查失败影响主程序
            self._log(f"Failed to check log file size: {str(e)}", skip_ui=True)

    def _get_timestamp(self):
        """获取格式化时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _log(self, msg, skip_ui=False):
        """
        统一日志处理：同步写入界面和文件（完整日志格式）
        :param msg: 日志内容
        :param skip_ui: 是否跳过界面显示（仅文件日志）
        """
        # 1. 写入日志文件（核心：所有日志都走这里）
        try:
            timestamp = self._get_timestamp()
            thread_name = threading.current_thread().name
            log_line = f"[{timestamp}] [{thread_name}] {msg}\n"
            
            # 追加写入文件
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            # 日志写入失败不影响主程序运行
            print(f"Failed to write to log file: {str(e)}")

        # 2. 显示到界面日志面板（除非跳过）
        if not skip_ui and hasattr(self, 'log_text'):
            try:
                # 界面日志保留完整时间戳
                full_ts = self._get_timestamp()
                ui_log_line = f"[{full_ts}] [{thread_name}] {msg}\n"
                
                # 临时解除只读（修复原代码遗漏的state配置）
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, ui_log_line)
                self.log_text.config(state=tk.DISABLED)
                self.log_text.see(tk.END)  # 自动滚动到最后
                self.root.update_idletasks()
            except Exception as e:
                print(f"Failed to update UI log: {str(e)}")

    def _load_config(self):
        """加载本地配置文件，获取URL历史记录"""
        # 默认值
        default_url = "https://192.168.1.100/redfish/v1"
        default_auto_refresh = False  # 默认关闭自动刷新
        
        # 清空现有历史（避免重复加载）
        self.url_history.clear()
        
        # 检查配置文件是否存在
        if os.path.exists(CONFIG_FILE):
            try:
                self.config.read(CONFIG_FILE, encoding="utf-8")
                # 读取URL历史（以逗号分隔）
                if "URL_HISTORY" in self.config and "history_list" in self.config["URL_HISTORY"]:
                    history_str = self.config["URL_HISTORY"]["history_list"]
                    # 去重+过滤空值+验证URL格式
                    temp_history = [
                        url.strip() for url in history_str.split(",") 
                        if url.strip() and self._is_valid_url(url.strip())
                    ]
                    # 去重（保留顺序）
                    seen = set()
                    self.url_history = [x for x in temp_history if not (x in seen or seen.add(x))]
                    
                # 新增：读取自动刷新状态
                if "SETTINGS" in self.config and "auto_refresh_10s" in self.config["SETTINGS"]:
                    self.auto_refresh_var.set(self.config["SETTINGS"]["auto_refresh_10s"].lower() == "true")
                else:
                    self.auto_refresh_var.set(default_auto_refresh)
                    
                self._log(f"Successfully loaded URL history: {self.url_history}")
                self._log(f"Successfully loaded auto refresh status: {self.auto_refresh_var.get()}")
            except Exception as e:
                self._log(f"Failed to load config file: {str(e)}, using default URL")
                self.url_history = [default_url]
                self.auto_refresh_var.set(default_auto_refresh)
        else:
            self._log("Config file does not exist, initializing default URL")
            self.url_history = [default_url]
            self.auto_refresh_var.set(default_auto_refresh)

    def _save_config(self, skip_add=False):
        """
        保存URL历史到配置文件
        :param skip_add: 是否跳过将当前URL加入历史（删除操作时用）
        """
        try:
            # 仅在非删除操作时，将当前URL加入历史
            if not skip_add:
                current_url = self.redfish_url_var.get().strip()
                if current_url and self._is_valid_url(current_url):
                    # 移除已存在的相同URL（避免重复）
                    if current_url in self.url_history:
                        self.url_history.remove(current_url)
                        self._log(f"Removed duplicate URL: {current_url}")
                    # 插入到列表头部（最新的在最前面）
                    self.url_history.insert(0, current_url)
                    self._log(f"Added URL to history: {current_url}")
            
            # 限制最大记录数
            if len(self.url_history) > MAX_HISTORY:
                removed_urls = self.url_history[MAX_HISTORY:]
                self.url_history = self.url_history[:MAX_HISTORY]
                self._log(f"Exceeded maximum history records, removed URLs: {removed_urls}")
            
            # 写入配置文件（关键：覆盖式写入）
            self.config["URL_HISTORY"] = {"history_list": ",".join(self.url_history)}
            # 新增：保存自动刷新状态
            self.config["SETTINGS"] = {"auto_refresh_10s": str(self.auto_refresh_var.get())}
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                self.config.write(f)
            # json_frame
            if self.auto_refresh_var.get():
                self.json_frame.config(text=LANG_CONFIG[self.current_lang]["json_data"].format(LANG_CONFIG[self.current_lang]["refresh_10s_content"]))
            else:
                self.json_frame.config(text=LANG_CONFIG[self.current_lang]["json_data"].format(""))
            self._log(f"Saved URL history to config file: {self.url_history}")
            self._log(f"Saved auto refresh status to config file: {self.auto_refresh_var.get()}")
            
            # 强制更新下拉列表
            self.url_combobox['values'] = []  # 先清空
            self.url_combobox['values'] = self.url_history  # 重新设置
            # 刷新下拉列表显示
            self.url_combobox.update()
        except Exception as e:
            self._log(f"Failed to save config file: {str(e)}")

    def _is_valid_url(self, url):
        """验证URL格式是否合法"""
        try:
            parsed = urlparse(url)
            # 必须包含协议（http/https）和主机名
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False

    def _delete_selected_url(self):
        """删除选中的URL历史记录"""
        lang = self.current_lang
        selected_url = self.redfish_url_var.get().strip()
        if not selected_url:
            self._log("Failed to delete URL: No URL selected")
            messagebox.showwarning(LANG_CONFIG[lang]["prompt"], LANG_CONFIG[lang]["no_url_selected"])
            return
        
        if selected_url in self.url_history:
            # 确认删除
            if messagebox.askyesno(LANG_CONFIG[lang]["confirm"], LANG_CONFIG[lang]["delete_url_confirm"].format(selected_url)):
                # 1. 从内存列表中删除（核心）
                self.url_history.remove(selected_url)
                self._log(f"Deleted URL from memory: {selected_url}")
                
                # 2. 保存配置（跳过添加当前URL，避免删了又加回来）
                self._save_config(skip_add=True)
                
                # 3. 更新输入框显示
                if self.url_history:
                    self.redfish_url_var.set(self.url_history[0])  # 设置为第一个历史记录
                    self._log(f"Updated input box to first historical URL: {self.url_history[0]}")
                else:
                    self.redfish_url_var.set("")  # 无历史则清空
                    self._log("URL history is empty, cleared input box")
                
                # 4. 强制刷新下拉列表
                self.url_combobox['values'] = self.url_history
                self.url_combobox.update()
                self._log(f"Refreshed dropdown list, current history: {self.url_history}")
                
                self._log(f"URL {selected_url} has been completely deleted!")
                messagebox.showinfo(LANG_CONFIG[lang]["success"], LANG_CONFIG[lang]["url_deleted"].format(selected_url))
        else:
            self._log(f"Deletion failed: Selected URL {selected_url} is not in history")
            messagebox.showwarning(LANG_CONFIG[lang]["prompt"], LANG_CONFIG[lang]["url_not_in_history"])

    def _setup_ui(self):
        # ========== 核心优化：解决缩放变形的布局配置 ==========
        # 主容器（承载所有组件）
        main_container = ttk.Frame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=5)
        # 配置主容器权重：第1行（主内容区）占满剩余空间，第2行固定高度放清空日志按钮
        main_container.rowconfigure(1, weight=1)
        main_container.columnconfigure(0, weight=1)

        # 1. 顶部连接配置栏（防变形核心：固定最小尺寸+统一对齐）
        self.connect_frame = ttk.LabelFrame(main_container, text=LANG_CONFIG[self.current_lang]["connect_config"])
        self.connect_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        # 配置列权重（差异化分配，避免按钮被过度拉伸）
        connect_col_weights = [0, 3, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0]  # 增加一列放语言选择
        for idx, weight in enumerate(connect_col_weights):
            self.connect_frame.columnconfigure(idx, weight=weight, minsize=60)  # 列最小宽度60

        # Redfish URL：标签 + 下拉框（固定最小宽度，防止缩放过窄）
        self.url_label = ttk.Label(self.connect_frame, text=LANG_CONFIG[self.current_lang]["redfish_url"])
        self.url_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.url_combobox = ttk.Combobox(
            self.connect_frame, 
            textvariable=self.redfish_url_var, 
            values=self.url_history,
            state="normal",
            width=MIN_COMBO_WIDTH  # 最小宽度，可拉伸
        )
        self.url_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        # 下拉框宽度自适应（保留原有逻辑）
        self.url_combobox.configure(postcommand=lambda: self.url_combobox.configure(
            width=max(MIN_COMBO_WIDTH, len(max(self.url_history, key=len)) if self.url_history else MIN_COMBO_WIDTH)
        ))

        # 删除URL按钮（固定最小宽度，防止变形）
        self.delete_btn = ttk.Button(self.connect_frame, text=LANG_CONFIG[self.current_lang]["delete_selected_url"], 
                                    command=self._delete_selected_url, width=MIN_BUTTON_WIDTH)
        self.delete_btn.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # 用户名（标签+输入框）
        self.user_label = ttk.Label(self.connect_frame, text=LANG_CONFIG[self.current_lang]["username"])
        self.user_label.grid(row=0, column=3, padx=5, pady=5, sticky="e")
        user_entry = ttk.Entry(self.connect_frame, textvariable=self.username)
        user_entry.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
        user_entry.configure(width=15)  # 固定合理宽度，不随窗口过度拉伸

        # 密码（标签+输入框）
        self.pwd_label = ttk.Label(self.connect_frame, text=LANG_CONFIG[self.current_lang]["password"])
        self.pwd_label.grid(row=0, column=5, padx=5, pady=5, sticky="e")
        pwd_entry = ttk.Entry(self.connect_frame, textvariable=self.password, show="*")
        pwd_entry.grid(row=0, column=6, padx=5, pady=5, sticky="ew")
        pwd_entry.configure(width=15)  # 固定合理宽度

        # 认证方式（标签+下拉框）
        self.auth_label = ttk.Label(self.connect_frame, text=LANG_CONFIG[self.current_lang]["auth_type"])
        self.auth_label.grid(row=0, column=7, padx=5, pady=5, sticky="e")
        auth_combo = ttk.Combobox(self.connect_frame, textvariable=self.auth_type, values=["JSON", "Basic"], width=MIN_BUTTON_WIDTH)
        auth_combo.grid(row=0, column=8, padx=5, pady=5, sticky="ew")

        # 功能按钮（固定最小宽度，统一对齐）
        self.connect_btn = ttk.Button(self.connect_frame, text=LANG_CONFIG[self.current_lang]["connect"], 
                                     command=self._connect, width=MIN_BUTTON_WIDTH)
        self.connect_btn.grid(row=0, column=9, padx=10, pady=5, sticky="ew")
        self.disconnect_btn = ttk.Button(self.connect_frame, text=LANG_CONFIG[self.current_lang]["disconnect"], 
                                        command=self._disconnect, state=tk.DISABLED, width=MIN_BUTTON_WIDTH)
        self.disconnect_btn.grid(row=0, column=10, padx=5, pady=5, sticky="ew")
        self.refresh_btn = ttk.Button(self.connect_frame, text=LANG_CONFIG[self.current_lang]["refresh"], 
                                     command=self._refresh_tree, state=tk.DISABLED, width=MIN_BUTTON_WIDTH)
        self.refresh_btn.grid(row=0, column=11, padx=5, pady=5, sticky="ew")

        # # 语言选择下拉框
        # lang_label = ttk.Label(self.connect_frame, text="Language/语言:")
        # lang_label.grid(row=0, column=12, padx=5, pady=5, sticky="e")
        # # 关键修复3：下拉框直接绑定显示名称，不需要额外的映射变量
        # lang_combo = ttk.Combobox(self.connect_frame, textvariable=self.lang_var, 
        #                          values=["中文", "English"], width=8, state="readonly")
        # lang_combo.grid(row=0, column=13, padx=5, pady=5, sticky="ew")
        # # 设置初始值
        # lang_combo.set(self._get_lang_display_name(self.current_lang))
        # # 绑定语言选择事件（简化：直接用lang_var的trace即可，无需额外绑定）
        # lang_combo.bind("<<ComboboxSelected>>", lambda e: None)  # 空绑定，避免重复触发

        # 2. 主区域：资源树 + JSON + 调试日志（兼容修复：移除PanedWindow的minsize参数）
        main_pane = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        main_pane.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # 左侧资源树（权重1，通过Frame嵌套实现最小尺寸限制）
        left_container = ttk.Frame(main_pane)  # 嵌套Frame实现最小尺寸
        left_container.pack_propagate(False)    # 禁止Frame随子组件收缩
        left_container.configure(width=200)     # 最小宽度200
        self.left_frame = ttk.LabelFrame(left_container, text=LANG_CONFIG[self.current_lang]["resource_list"])
        self.left_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        main_pane.add(left_container, weight=1)
        
        self.tree = ttk.Treeview(self.left_frame)
        self.tree.heading("#0", text=LANG_CONFIG[self.current_lang]["redfish_resource"])
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # 右侧上下分栏：JSON + 调试日志（权重2，嵌套Frame实现最小尺寸）
        right_container = ttk.Frame(main_pane)
        right_container.pack_propagate(False)
        right_container.configure(width=400)    # 最小宽度400
        right_pane = ttk.PanedWindow(right_container, orient=tk.VERTICAL)
        right_pane.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        main_pane.add(right_container, weight=2)

        # JSON 区域（权重3，嵌套Frame实现最小高度）
        json_container = ttk.Frame(right_pane)
        json_container.pack_propagate(False)
        json_container.configure(height=300)    # 最小高度300
        self.json_frame = ttk.LabelFrame(json_container, text=LANG_CONFIG[self.current_lang]["json_data"].format(LANG_CONFIG[self.current_lang]["refresh_10s_content"] if self.auto_refresh_var.get() else ""))
        self.json_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        right_pane.add(json_container, weight=3)
        
        self.json_text = scrolledtext.ScrolledText(self.json_frame, font=("Consolas", 10))
        self.json_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 调试日志区域（权重1，仅保留日志文本框，按钮移到外层）
        log_container = ttk.Frame(right_pane)
        log_container.pack_propagate(False)
        log_container.configure(height=150)     # 最小高度150
        self.log_frame = ttk.LabelFrame(log_container, text=LANG_CONFIG[self.current_lang]["debug_log"])
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # 仅保留日志文本框，按钮移到主容器底部
        self.log_text = scrolledtext.ScrolledText(self.log_frame, font=("Consolas", 9), fg="gray", state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        right_pane.add(log_container, weight=1)

        # ========== 核心修复：清空日志按钮移到主容器底部，永久可见 ==========
        # 按钮容器（固定在主容器右下角，不受日志面板影响）
        btn_container = ttk.Frame(main_container)
        btn_container.grid(row=2, column=0, sticky="e", padx=10, pady=5)
        
        # 新增：refresh 10/s 复选框
        self.refresh_checkbox = ttk.Checkbutton(
            btn_container,
            text=LANG_CONFIG[self.current_lang]["refresh_10s"],
            variable=self.auto_refresh_var,
            command=lambda: self._save_config(skip_add=True)  # 状态变化时保存配置
        )
        self.refresh_checkbox.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 清空日志按钮（固定尺寸，永久显示）
        self.clear_log_btn = ttk.Button(btn_container, text=LANG_CONFIG[self.current_lang]["clear_log"], 
                                       command=self._clear_all_log, width=MIN_BUTTON_WIDTH)
        self.clear_log_btn.pack(side=tk.RIGHT)

        # 程序关闭时自动保存配置
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 初始化日志
        self._log("Program started, initialization completed, config file path: {}, log file path: {}".format(CONFIG_FILE, LOG_FILE))

    def _clear_all_log(self):
        """清空界面日志和文件日志"""
        lang = self.current_lang
        # 确认清空
        if messagebox.askyesno(LANG_CONFIG[lang]["confirm"], LANG_CONFIG[lang]["clear_log_confirm"]):
            # 清空界面日志
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)
            # 清空文件日志
            try:
                with open(LOG_FILE, "w", encoding="utf-8") as f:
                    clear_msg = f"[{self._get_timestamp()}] Logs cleared manually\n"
                    f.write(clear_msg)
                self._log("Cleared all logs (UI + file)", skip_ui=True)
                self._log("Logs cleared")
            except Exception as e:
                self._log(f"Failed to clear log file: {str(e)}")
            messagebox.showinfo(LANG_CONFIG[lang]["success"], LANG_CONFIG[lang]["log_cleared"])

    def _on_close(self):
        """窗口关闭时保存配置"""
        self._log("Program starting shutdown process...")
        self._log("Saving URL history config...")
        self._save_config()
        self._log("Config saved successfully, program exiting normally")
        self.root.destroy()

    def _connect(self):
        def task():
            lang = self.current_lang
            try:
                self._set_buttons(False)
                self._log("Starting to connect to Redfish service...")
                
                # 1. 保存当前URL到历史记录
                self._save_config()
                
                # 2. 解析并验证 URL
                input_url = self.redfish_url_var.get().strip()
                self._log(f"URL to connect: {input_url}")
                if not self._is_valid_url(input_url):
                    raise Exception(LANG_CONFIG[lang]["invalid_url"])
                
                parsed_base = urlparse(input_url)
                self._log(f"Parsed URL: scheme={parsed_base.scheme}, netloc={parsed_base.netloc}, path={parsed_base.path}")
                
                self.base_url = input_url
                self.full_base_url = f"{parsed_base.scheme}://{parsed_base.netloc}"
                self._log(f"Full base URL: {self.full_base_url}")

                # check if BOSSssss
                resp = requests.get("{}/boss/probe/PVProStatus.jsp".format(self.full_base_url), verify=False, timeout=10)
                #self._log(f"BOSS probe PStatus: {resp.status_code}")                
                if resp.status_code in (200, 2000):
                    pass
                else:
                    raise Exception("Loading...")
                
                
                # 3. 构建登录请求（适配不同厂商路径）
                login_paths = [
                    "/SessionService/Sessions",  # 标准路径
                    "/redfish/v1/SessionService/Sessions",  # 完整路径
                    "/SessionService/CreateSession"  # 部分厂商（如华为）
                ]
                
                login_success = False
                current_auth_type = self.auth_type.get().strip()
                self._log(f"Currently selected authentication type: {current_auth_type}")
                resp = None

                # ====================== Basic 认证逻辑 ======================
                if current_auth_type == "Basic":
                    self._log("Using Basic authentication mode (access root URL with Auth directly)")
                    # Basic 认证不需要POST登录，直接GET带Auth访问Redfish根路径
                    test_url = self.base_url
                    self._log(f"Basic auth request URL: {test_url}")
                    auth = (self.username.get(), self.password.get())
                    self._log(f"Basic auth username: {self.username.get()}, password: {'*' * len(self.password.get())}")
                    
                    # 发送Basic认证请求
                    resp = requests.get(test_url, auth=auth, verify=False, timeout=10)
                    self._log(f"Basic auth response status code: {resp.status_code}")
                    self._log(f"Basic auth response headers: {dict(resp.headers)}")
                    self._log(f"Basic auth response content (first 500 chars): {resp.text[:500]}")

                    if resp.status_code in (200, 201, 202):
                        # Basic认证成功
                        login_success = True
                        self._log("Basic authentication succeeded!")
                        # 初始化会话并绑定Basic认证
                        self.session = requests.Session()
                        self.session.verify = False
                        self.session.auth = auth  # 关键：绑定Basic认证到会话
                        self._log("Basic auth session initialized, subsequent requests will carry auth info automatically")

                # ====================== JSON 认证逻辑（修复核心） ======================
                elif current_auth_type == "JSON":
                    self._log("Using JSON form authentication mode")
                    # 先初始化会话（修复：JSON认证也需要先创建session）
                    self.session = requests.Session()
                    self.session.verify = False
                    
                    for login_path in login_paths:
                        login_url = self._get_absolute_url(login_path)
                        self._log(f"Trying login path: {login_url}")
                        
                        try:
                            payload = {"UserName": self.username.get(), "Password": self.password.get()}
                            self._log(f"Sending JSON auth data: {payload}")
                            headers = {"Content-Type": "application/json"}
                            # 使用session发送POST请求（修复：之前用了全局requests，不是session）
                            resp = self.session.post(login_url, json=payload, headers=headers, timeout=10)
                            
                            self._log(f"Login response status code: {resp.status_code}")
                            self._log(f"Login response headers: {dict(resp.headers)}")
                            self._log(f"Login response content (first 500 chars): {resp.text[:500]}")

                            if resp.status_code in (200, 201):
                                # 登录成功
                                login_success = True
                                self._log(f"JSON authentication succeeded! Using path: {login_path}")
                                
                                # 提取认证 Token/Cookie（修复：绑定到session）
                                if "X-Auth-Token" in resp.headers:
                                    self.session.headers["X-Auth-Token"] = resp.headers["X-Auth-Token"]
                                    self._log(f"Set X-Auth-Token to Session: {resp.headers['X-Auth-Token'][:20]}...")
                                if "Set-Cookie" in resp.headers:
                                    self.session.headers["Cookie"] = resp.headers["Set-Cookie"]
                                    self._log(f"Set Cookie to Session: {resp.headers['Set-Cookie'][:50]}...")
                                break
                            else:
                                self._log(f"Login failed for path {login_path}, status code: {resp.status_code}")
                        except Exception as e:
                            self._log(f"Request exception for path {login_path}: {str(e)}")
                            continue
                
                # 认证失败处理
                if not login_success:
                    # 清空无效的session
                    self.session = None
                    raise Exception(LANG_CONFIG[lang]["auth_failed"].format(current_auth_type, resp.status_code if resp else 'None'))

                # 5. 加载资源树
                self._log("Starting to load Redfish resource tree...")
                self._load_full_tree()
                self._log("Connection and resource loading completed!")
                messagebox.showinfo(LANG_CONFIG[lang]["success"], LANG_CONFIG[lang]["connection_success"])
                self._set_buttons(True)

            except Exception as e:
                error_msg = LANG_CONFIG[lang]["connection_failed"].format(str(e))
                self._log(error_msg)
                if str(e).startswith("Loading"):
                    pass
                else:
                    messagebox.showerror(LANG_CONFIG[lang]["error"], error_msg)
                # 清空无效session
                self.session = None
                self._set_buttons(False, connect_enable=True)

        threading.Thread(target=task, name="ConnectThread", daemon=True).start()

    def _disconnect(self):
        lang = self.current_lang
        try:
            self._log("Starting to disconnect from Redfish service...")
            if self.session:
                # 尝试登出
                logout_paths = ["/SessionService/Sessions", "/redfish/v1/SessionService/Sessions"]
                for logout_path in logout_paths:
                    try:
                        logout_url = self._get_absolute_url(logout_path)
                        self._log(f"Trying logout path: {logout_url}")
                        resp = self.session.delete(logout_url, timeout=3)
                        self._log(f"Logout response status code: {resp.status_code}")
                        self._log(f"Logout succeeded, path: {logout_path}")
                        break
                    except Exception as e:
                        self._log(f"Logout failed for path {logout_path}: {str(e)}")
                self.session = None
                self._log("Session cleared")

            # 清空界面
            self._log("Starting to clear resource tree and JSON panel...")
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.json_text.delete(1.0, tk.END)
            self._log("Cleared resource tree and JSON panel")
            
            self._set_buttons(False, connect_enable=True)
            self._log("Disconnected from Redfish service")
            messagebox.showinfo(LANG_CONFIG[lang]["success"], LANG_CONFIG[lang]["disconnect_success"])
        except Exception as e:
            error_msg = LANG_CONFIG[lang]["disconnect_failed"].format(str(e))
            self._log(error_msg)
            messagebox.showerror(LANG_CONFIG[lang]["error"], error_msg)

    def _refresh_tree(self):
        def refresh_task():
            lang = self.current_lang
            try:
                self.refresh_btn.config(state=tk.DISABLED)
                self._log("Starting to refresh resource tree...")
                self._load_full_tree()
                self._log("Resource tree refresh completed!")
                messagebox.showinfo(LANG_CONFIG[lang]["success"], LANG_CONFIG[lang]["refresh_success"])
                self.refresh_btn.config(state=tk.NORMAL)
            except Exception as e:
                error_msg = LANG_CONFIG[lang]["refresh_failed"].format(str(e))
                self._log(error_msg)
                messagebox.showerror(LANG_CONFIG[lang]["error"], error_msg)
                self.refresh_btn.config(state=tk.NORMAL)
        
        threading.Thread(target=refresh_task, name="RefreshThread", daemon=True).start()

    def _set_buttons(self, connected, connect_enable=None):
        enable = tk.NORMAL if connected else tk.DISABLED
        if connect_enable is None:
            connect_enable = not connected
        self.connect_btn.config(state=tk.NORMAL if connect_enable else tk.DISABLED)
        self.disconnect_btn.config(state=enable)
        self.refresh_btn.config(state=enable)
        self._log(f"Updated button states: Connect button={tk.NORMAL if connect_enable else tk.DISABLED}, Disconnect/Refresh buttons={enable}")

    def _get_absolute_url(self, resource_path):
        """将相对路径转换为完整的绝对URL"""
        if resource_path.startswith(("http://", "https://")):
            return resource_path
        elif resource_path.startswith("/"):
            return urljoin(self.full_base_url, resource_path)
        else:
            return urljoin(self.base_url, resource_path)

    def _load_full_tree(self):
        lang = self.current_lang
        # 清空现有树
        self._log("Clearing existing resource tree...")
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.session:
            self._log("Session is empty, skipping resource tree loading")
            return
        
        try:
            self._log(f"Starting to load resource tree, base URL: {self.base_url}")
            root_node = self.tree.insert("", tk.END, text="Root", values=[self.base_url])
            self._load_children(self.base_url, root_node)
            self._log("Resource tree loading completed!")
        except Exception as e:
            error_msg = LANG_CONFIG[lang]["load_tree_failed"].format(str(e))
            self._log(error_msg)
            messagebox.showerror(LANG_CONFIG[lang]["error"], error_msg)

    def _load_children(self, url, parent_node):
        try:
            absolute_url = self._get_absolute_url(url)
            self._log(f"Loading child resources: {absolute_url}")
            
            r = self.session.get(absolute_url, timeout=5)
            self._log(f"Response status code for {absolute_url}: {r.status_code}")
            if r.status_code != 200:
                self._log(f"Failed to get {absolute_url}, status code: {r.status_code}")
                return
            
            data = r.json()
            
            self._log(f"Successfully retrieved {absolute_url}, data length: {len(str(data))}, duration: {r.elapsed.total_seconds()}")

            # 处理 Members 集合
            if "Members" in data and isinstance(data["Members"], list):
                self._log(f"{absolute_url} contains {len(data['Members'])} Members child resources")
                for m in data["Members"]:
                    member_path = m.get("@odata.id")
                    if not member_path:
                        self._log(f"Members item has no @odata.id, skipping")
                        continue
                    member_url = self._get_absolute_url(member_path)
                    name = member_path.split("/")[-1]
                    if not self._exists(parent_node, name, member_url):
                        node = self.tree.insert(parent_node, tk.END, text=name, values=[member_url])
                        self._load_children(member_path, node)

            # 处理单个子资源
            sub_resource_count = 0
            for k, v in data.items():
                if k.startswith("@") or k in ["Members", "Members@odata.count", "Links", "Actions"]:
                    continue
                if isinstance(v, dict) and "@odata.id" in v:
                    sub_resource_count += 1
                    sub_path = v["@odata.id"]
                    sub_url = self._get_absolute_url(sub_path)
                    name = k
                    if not self._exists(parent_node, name, sub_url):
                        node = self.tree.insert(parent_node, tk.END, text=name, values=[sub_url])
                        self._load_children(sub_path, node)
            self._log(f"Loading completed for {absolute_url}, processed {sub_resource_count} child resources")

        except Exception as e:
            self._log(f"Exception loading child resources {url}: {str(e)}")

    def _exists(self, parent, text, url):
        """检查节点是否已存在"""
        for c in self.tree.get_children(parent):
            if self.tree.item(c, "text") == text and self.tree.item(c, "values")[0] == url:
                return True
        return False

    def _on_select(self, event):
        def task():
            lang = self.current_lang
            try:
                while True:
                    sel = self.tree.selection()
                    if not sel:
                        self._log(LANG_CONFIG[lang]["no_resource_selected"])
                        return
                    url = self.tree.item(sel[0], "values")[0]
                    self._log(f"Selected resource: {url}")
                    
                    self.json_text.config(state=tk.NORMAL)
                    self.json_text.delete(1.0, tk.END)
                    self.json_text.insert(tk.END, "Loading..." if self.current_lang == "en" else "加载中...")
                    self.json_text.config(state=tk.DISABLED)
                    self.root.update_idletasks()

                    r = self.session.get(url, timeout=10)
                    self._log(f"Request status code for {url}: {r.status_code}")
                    
                    if r.status_code == 200:
                        pretty_json = json.dumps(r.json(), indent=2, ensure_ascii=False)
                        self.json_text.config(state=tk.NORMAL)
                        self.json_text.delete(1.0, tk.END)
                        self.json_text.insert(tk.END, pretty_json)
                        self.json_text.config(state=tk.DISABLED)
                        self._log(f"Successfully loaded JSON data for {url}, length: {len(pretty_json)}, duration: {r.elapsed.total_seconds()}")
                    else:
                        error_text = f"Request failed {r.status_code}\n{r.text[:500]}"
                        self.json_text.config(state=tk.NORMAL)
                        self.json_text.delete(1.0, tk.END)
                        self.json_text.insert(tk.END, error_text)
                        self.json_text.config(state=tk.DISABLED)
                        self._log(f"Request failed for {url}: {error_text}")
                    if self.auto_refresh_var.get():
                        time.sleep(10)
                    else:
                        break
            except Exception as e:
                error_msg = LANG_CONFIG[lang]["load_resource_failed"].format(str(e))
                self.json_text.config(state=tk.NORMAL)
                self.json_text.delete(1.0, tk.END)
                self.json_text.insert(tk.END, error_msg)
                self.json_text.config(state=tk.DISABLED)
                self._log(error_msg)

        threading.Thread(target=task, name="SelectThread", daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = RedfishGUIApp(root)
    root.mainloop()
