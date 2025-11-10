# -*- coding:utf-8 -*-
"""
FC2资源收集器 - GUI版本
基于tkinter的现代化图形界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import os
import sys
from configparser import RawConfigParser
from datetime import datetime

# 添加当前目录到Python路径（源码运行时有用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 兼容 PyInstaller 单文件环境下的导入（fc2_core）
try:
    from fc2_core import FC2GatherCore
except ModuleNotFoundError:
    # 当模块未找到时，尝试从打包资源复制到临时路径并动态加载
    import importlib.util
    import shutil
    tmp_dir = os.path.join(os.getcwd(), "_runtime")
    os.makedirs(tmp_dir, exist_ok=True)
    candidate_paths = []
    # 可能的来源：当前目录、_MEIPASS、复制到当前目录的fc2_core.py
    candidate_paths.append(os.path.join(os.getcwd(), "fc2_core.py"))
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate_paths.append(os.path.join(base, "fc2_core.py"))
    src = next((p for p in candidate_paths if os.path.exists(p)), None)
    if src:
        dst = os.path.join(tmp_dir, "fc2_core.py")
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
        spec = importlib.util.spec_from_file_location("fc2_core", dst)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        FC2GatherCore = mod.FC2GatherCore
    else:
        raise

class FC2GatherGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FC2资源收集器 v0.1")
        self.root.geometry("900x700")
        
        # 设置窗口图标
        try:
            if os.path.exists('ico.ico'):
                self.root.iconbitmap('ico.ico')
        except:
            pass
            
        # 配置
        self.config = RawConfigParser()
        self.load_config()
        
        # 核心功能
        self.core = FC2GatherCore(self.config, self.log)
        self.download_thread = None
        self.is_downloading = False
        
        # 创建界面
        self.create_menu()
        self.create_notebook()
        self.create_status_bar()
        
    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists('config.ini'):
                self.config.read('config.ini', encoding='utf-8')
            else:
                # 创建默认配置
                self.config.add_section('下载设置')
                # 默认启用手动代理并赋默认地址（用户可在设置中修改）
                self.config.set('下载设置', 'Proxy', '127.0.0.1:7897')
                self.config.set('下载设置', 'AutoProxy', '是')
                self.config.set('下载设置', 'Download_path', './Downloads/')
                self.config.set('下载设置', 'Max_dl', '3')
                self.config.set('下载设置', 'Max_retry', '3')
                self.config.set('下载设置', 'VerifySSL', '否')
                with open('config.ini', 'w', encoding='utf-8') as f:
                    self.config.write(f)
        except Exception as e:
            messagebox.showerror("配置错误", f"加载配置文件失败: {str(e)}")
    
    def save_config(self):
        """保存配置"""
        try:
            with open('config.ini', 'w', encoding='utf-8') as f:
                self.config.write(f)
            self.log("配置已保存")
        except Exception as e:
            messagebox.showerror("配置错误", f"保存配置文件失败: {str(e)}")
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="导入番号文件", command=self.import_id_file)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="下载设置", command=self.open_settings)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用帮助", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def create_notebook(self):
        """创建选项卡界面"""
        # 创建Notebook（选项卡控件）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 第一个选项卡：获取番号
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="📋 获取番号")
        self.create_tab1_content()
        
        # 第二个选项卡：抓取磁链
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="🧲 抓取磁链")
        self.create_tab2_content()
        
        # 日志区域（共享）
        self.create_log_area()
    
    def create_tab1_content(self):
        """创建第一个选项卡内容：获取番号"""
        # URL输入区域
        url_frame = ttk.LabelFrame(self.tab1, text="FC2页面URL", padding=10)
        url_frame.pack(fill='x', padx=10, pady=10)
        
        # URL输入框
        self.url_entry = ttk.Entry(url_frame, width=60)
        self.url_entry.pack(fill='x', side='left', expand=True, padx=(0, 10))
        # 默认地址为官网主页
        self.url_entry.insert(0, "https://adult.contents.fc2.com/")
        
        # 获取按钮
        self.get_ids_btn = ttk.Button(url_frame, text="🎯 获取番号", command=self.get_ids_from_url)
        self.get_ids_btn.pack(side='right')
        
        # 示例标签
        example_label = ttk.Label(self.tab1, text="示例：https://adult.contents.fc2.com/", 
                                 foreground='gray', font=('Arial', 9))
        example_label.pack(padx=10, pady=(0, 10))
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(self.tab1, text="获取结果", padding=10)
        result_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 番号列表显示
        self.ids_text = scrolledtext.ScrolledText(result_frame, height=15, width=80)
        self.ids_text.pack(fill='both', expand=True)
        
        # 按钮区域
        btn_frame = ttk.Frame(self.tab1)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        self.copy_ids_btn = ttk.Button(btn_frame, text="📋 复制番号", command=self.copy_ids)
        self.copy_ids_btn.pack(side='left', padx=(0, 10))
        
        self.save_ids_btn = ttk.Button(btn_frame, text="💾 保存到文件", command=self.save_ids_to_file)
        self.save_ids_btn.pack(side='left', padx=(0, 10))
        
        self.clear_ids_btn = ttk.Button(btn_frame, text="🗑️ 清空", command=self.clear_ids)
        self.clear_ids_btn.pack(side='left', padx=(0, 10))

        # 新增：打开下载目录按钮（获取番号选项卡）
        self.open_folder_btn_tab1 = ttk.Button(btn_frame, text="📂 打开下载目录", command=self.open_download_folder)
        self.open_folder_btn_tab1.pack(side='left')
    
    def create_tab2_content(self):
        """创建第二个选项卡内容：抓取磁链"""
        # 输入区域
        input_frame = ttk.LabelFrame(self.tab2, text="番号输入", padding=10)
        input_frame.pack(fill='x', padx=10, pady=10)
        
        # 输入方式选择
        self.input_method = tk.StringVar(value="text")
        
        method_frame = ttk.Frame(input_frame)
        method_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Radiobutton(method_frame, text="直接输入", variable=self.input_method, 
                       value="text", command=self.toggle_input_method).pack(side='left', padx=(0, 20))
        ttk.Radiobutton(method_frame, text="从文件导入", variable=self.input_method, 
                       value="file", command=self.toggle_input_method).pack(side='left')
        
        # 文本输入区域
        self.text_frame = ttk.Frame(input_frame)
        self.text_frame.pack(fill='both', expand=True)
        
        self.id_input = scrolledtext.ScrolledText(self.text_frame, height=8, width=80)
        self.id_input.pack(fill='both', expand=True)
        self.id_input.insert('1.0', "请输入FC2番号，每行一个\n例如：\nFC2-PPV-1234567\nFC2-PPV-7654321")
        
        # 文件输入区域（初始隐藏）
        self.file_frame = ttk.Frame(input_frame)
        
        self.file_path = tk.StringVar()
        self.file_entry = ttk.Entry(self.file_frame, textvariable=self.file_path, width=50, state='readonly')
        self.file_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.browse_btn = ttk.Button(self.file_frame, text="📁 浏览...", command=self.browse_file)
        self.browse_btn.pack(side='right')
        
        # 控制按钮
        control_frame = ttk.Frame(self.tab2)
        control_frame.pack(fill='x', padx=10, pady=10)
        
        self.start_btn = ttk.Button(control_frame, text="🚀 开始获取", command=self.start_download)
        self.start_btn.pack(side='left', padx=(0, 10))
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ 停止", command=self.stop_download, state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 10))
        
        self.open_folder_btn = ttk.Button(control_frame, text="📂 打开下载目录", command=self.open_download_folder)
        self.open_folder_btn.pack(side='left')
    
    def create_log_area(self):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(self.root, text="输出日志", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80)
        self.log_text.pack(fill='both', expand=True)
        
        # 进度条
        self.progress_frame = ttk.Frame(self.root)
        self.progress_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, mode='determinate')
        self.progress_bar.pack(fill='x', side='left', expand=True, padx=(0, 10))
        
        self.status_label = ttk.Label(self.progress_frame, text="就绪", width=15)
        self.status_label.pack(side='right')
    
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = ttk.Label(self.root, text="就绪", relief='sunken', anchor='w')
        self.status_bar.pack(side='bottom', fill='x')
    
    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')
        self.status_bar.config(text=message)
        self.root.update_idletasks()
    
    def toggle_input_method(self):
        """切换输入方式"""
        if self.input_method.get() == "text":
            self.file_frame.pack_forget()
            self.text_frame.pack(fill='both', expand=True)
        else:
            self.text_frame.pack_forget()
            self.file_frame.pack(fill='x')
    
    def get_ids_from_url(self):
        """从URL获取番号"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("输入错误", "请输入FC2页面URL")
            return
            
        # 禁用按钮
        self.get_ids_btn.config(state='disabled')
        self.status_label.config(text="正在获取番号...")
        
        # 清空之前的结果
        self.ids_text.delete('1.0', 'end')
        
        def run_get_ids():
            try:
                ids = self.core.get_fc2_ids_from_url(url, self.update_ids_progress)
                
                # 显示结果
                self.root.after(0, self.show_ids_result, ids)
                
            except Exception as e:
                self.root.after(0, lambda: self.log(f"获取番号失败: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.get_ids_btn.config(state='normal'))
                self.root.after(0, lambda: self.status_label.config(text="获取完成"))
        
        # 启动线程
        thread = threading.Thread(target=run_get_ids)
        thread.daemon = True
        thread.start()
    
    def update_ids_progress(self, current_page, total_pages, total_ids):
        """更新获取番号的进度"""
        progress = (current_page / max(total_pages, 1)) * 100
        self.root.after(0, lambda: self.progress_var.set(progress))
        self.root.after(0, lambda: self.status_label.config(text=f"第{current_page}/{total_pages}页，已获取{total_ids}个番号"))
    
    def show_ids_result(self, ids):
        """显示获取到的番号"""
        if ids:
            for fc2_id in ids:
                self.ids_text.insert('end', f"FC2-PPV-{fc2_id}\n")
            self.log(f"成功获取 {len(ids)} 个番号")
        else:
            self.ids_text.insert('end', "未获取到任何番号\n")
            self.log("未获取到任何番号")
    
    def copy_ids(self):
        """复制番号到剪贴板"""
        content = self.ids_text.get('1.0', 'end-1c')
        if content.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("成功", "番号已复制到剪贴板")
        else:
            messagebox.showwarning("提示", "没有可复制的番号")
    
    def save_ids_to_file(self):
        """保存番号到文件"""
        content = self.ids_text.get('1.0', 'end-1c')
        if not content.strip():
            messagebox.showwarning("提示", "没有可保存的番号")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", f"番号已保存到:\n{file_path}")
                self.log(f"番号已保存到: {file_path}")
            except Exception as e:
                messagebox.showerror("保存失败", f"保存文件失败: {str(e)}")
    
    def clear_ids(self):
        """清空番号显示"""
        self.ids_text.delete('1.0', 'end')
        self.log("已清空番号列表")
    
    def browse_file(self):
        """浏览文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path.set(file_path)
            self.log(f"已选择文件: {file_path}")
    
    def start_download(self):
        """开始获取磁力链接"""
        if self.is_downloading:
            return
            
        # 获取输入数据
        if self.input_method.get() == "text":
            input_data = self.id_input.get('1.0', 'end-1c').strip()
            if not input_data or input_data == "请输入FC2番号，每行一个\n例如：\nFC2-PPV-1234567\nFC2-PPV-7654321":
                messagebox.showwarning("输入错误", "请输入番号")
                return
        else:
            file_path = self.file_path.get()
            if not file_path:
                messagebox.showwarning("文件错误", "请选择番号文件")
                return
            input_data = file_path
        
        # 禁用按钮
        self.is_downloading = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.progress_var.set(0)
        self.status_label.config(text="准备开始...")
        
        def run_download():
            try:
                # 重新加载配置
                self.core.config = self.config
                
                results = self.core.process_fc2_list(input_data, self.update_progress)
                
                # 完成处理
                self.root.after(0, self.download_complete, results)
                
            except Exception as e:
                self.root.after(0, lambda: self.log(f"处理失败: {str(e)}"))
                self.root.after(0, self.download_complete, [])
        
        # 启动下载线程
        self.download_thread = threading.Thread(target=run_download)
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def update_progress(self, value):
        """更新进度"""
        self.progress_var.set(value)
        self.status_label.config(text=f"进度: {int(value)}%")
        self.root.update_idletasks()
    
    def stop_download(self):
        """停止下载"""
        if self.is_downloading:
            self.core.stop()
            self.is_downloading = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.status_label.config(text="已停止")
            self.log("已停止处理")
    
    def download_complete(self, results):
        """下载完成"""
        self.is_downloading = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.progress_var.set(100)
        
        if results:
            self.status_label.config(text=f"完成！共处理 {len(results)} 个番号")
            messagebox.showinfo("完成", f"处理完成！\n共处理 {len(results)} 个番号\n结果已保存到下载目录")
        else:
            self.status_label.config(text="处理完成，但未获取到结果")
    
    def import_id_file(self):
        """导入番号文件"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            # 切换到第二个选项卡
            self.notebook.select(self.tab2)
            # 设置为文件模式
            self.input_method.set("file")
            self.toggle_input_method()
            # 设置文件路径
            self.file_path.set(file_path)
            self.log(f"已导入番号文件: {file_path}")
    
    def open_download_folder(self):
        """打开下载目录"""
        download_path = self.core.read_config_value('下载设置', 'Download_path', './Downloads/')
        try:
            # 清理与归一化路径，转为绝对路径
            path = (download_path or './Downloads/').strip().strip('"').strip("'")
            path = os.path.expanduser(os.path.expandvars(path))
            if not os.path.isabs(path):
                path = os.path.abspath(path)
            path = os.path.normpath(path)

            # 自动创建并打开
            os.makedirs(path, exist_ok=True)
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开下载目录: {str(e)}\n当前路径: {download_path}")
    
    def open_settings(self):
        """打开设置窗口"""
        SettingsWindow(self.root, self.config, self.save_and_reload_config)
    
    def save_and_reload_config(self):
        """保存并重新加载配置"""
        self.save_config()
        self.load_config()
        self.core.config = self.config
    
    def show_help(self):
        """显示帮助"""
        HelpWindow(self.root)
    
    def show_about(self):
        """显示关于"""
        AboutWindow(self.root)

class SettingsWindow:
    def __init__(self, parent, config, callback):
        self.parent = parent
        self.config = config
        self.callback = callback
        
        self.window = tk.Toplevel(parent)
        self.window.title("下载设置")
        # 增大设置窗口尺寸，确保按钮区域可见
        self.window.geometry("720x540")
        try:
            # 设置最小尺寸防止内容被裁剪
            self.window.minsize(680, 520)
        except Exception:
            pass
        self.window.transient(parent)
        self.window.grab_set()
        
        # 居中显示
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - self.window.winfo_width()) // 2
        y = (self.window.winfo_screenheight() - self.window.winfo_height()) // 2
        self.window.geometry(f"+{x}+{y}")
        
        self.create_widgets()
        self.load_settings()
    
    def create_widgets(self):
        """创建设置控件"""
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # 代理设置
        proxy_frame = ttk.LabelFrame(main_frame, text="代理设置", padding=10)
        proxy_frame.pack(fill='x', pady=(0, 15))

        # 启用手动代理（是/否单选）
        ttk.Label(proxy_frame, text="启用手动代理:").grid(row=0, column=0, sticky='w', pady=5)
        self.manual_proxy_var = tk.StringVar(value='是')
        ttk.Radiobutton(proxy_frame, text="是", variable=self.manual_proxy_var, value='是', command=self.toggle_manual_proxy).grid(row=0, column=1, sticky='w')
        ttk.Radiobutton(proxy_frame, text="否", variable=self.manual_proxy_var, value='否', command=self.toggle_manual_proxy).grid(row=0, column=2, sticky='w')

        # 代理地址输入（在选择“是”时启用）
        ttk.Label(proxy_frame, text="代理地址:").grid(row=1, column=0, sticky='w', pady=5)
        self.proxy_entry = ttk.Entry(proxy_frame, width=40)
        self.proxy_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky='w')
        
        self.auto_proxy_var = tk.BooleanVar()
        ttk.Checkbutton(proxy_frame, text="自动检测系统代理", variable=self.auto_proxy_var).grid(row=2, column=0, columnspan=3, sticky='w', pady=5)
        
        self.verify_ssl_var = tk.BooleanVar()
        ttk.Checkbutton(proxy_frame, text="验证SSL证书", variable=self.verify_ssl_var).grid(row=3, column=0, columnspan=3, sticky='w', pady=5)
        
        # 下载设置
        download_frame = ttk.LabelFrame(main_frame, text="下载设置", padding=10)
        download_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(download_frame, text="下载路径:").grid(row=0, column=0, sticky='w', pady=5)
        self.download_path_entry = ttk.Entry(download_frame, width=40)
        self.download_path_entry.grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(download_frame, text="浏览...", command=self.browse_download_path).grid(row=0, column=2, pady=5)
        
        ttk.Label(download_frame, text="下载线程数:").grid(row=1, column=0, sticky='w', pady=5)
        self.max_dl_entry = ttk.Entry(download_frame, width=10)
        self.max_dl_entry.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        
        ttk.Label(download_frame, text="失败重试次数:").grid(row=2, column=0, sticky='w', pady=5)
        self.max_retry_entry = ttk.Entry(download_frame, width=10)
        self.max_retry_entry.grid(row=2, column=1, sticky='w', padx=10, pady=5)
        
        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x', pady=(20, 0))
        
        ttk.Button(btn_frame, text="确定", command=self.save_settings).pack(side='right', padx=(10, 0))
        ttk.Button(btn_frame, text="取消", command=self.window.destroy).pack(side='right')
    
    def load_settings(self):
        """加载设置"""
        try:
            proxy_val = self.config.get('下载设置', 'Proxy', fallback='否')
            if proxy_val and proxy_val.strip() != '否':
                self.manual_proxy_var.set('是')
                self.proxy_entry.insert(0, proxy_val)
            else:
                self.manual_proxy_var.set('否')
                self.proxy_entry.insert(0, '')
            # 根据当前选择更新输入框状态
            self.toggle_manual_proxy()
            self.auto_proxy_var.set(self.config.get('下载设置', 'AutoProxy', fallback='是') == '是')
            self.verify_ssl_var.set(self.config.get('下载设置', 'VerifySSL', fallback='否') == '是')
            self.download_path_entry.insert(0, self.config.get('下载设置', 'Download_path', fallback='./Downloads/'))
            self.max_dl_entry.insert(0, self.config.get('下载设置', 'Max_dl', fallback='3'))
            self.max_retry_entry.insert(0, self.config.get('下载设置', 'Max_retry', fallback='3'))
        except:
            pass
    
    def browse_download_path(self):
        """浏览下载路径"""
        path = filedialog.askdirectory()
        if path:
            self.download_path_entry.delete(0, 'end')
            self.download_path_entry.insert(0, path)
    
    def save_settings(self):
        """保存设置"""
        try:
            if not self.config.has_section('下载设置'):
                self.config.add_section('下载设置')
            
            # 将单选选择转换为配置值
            if self.manual_proxy_var.get() == '是':
                proxy_addr = self.proxy_entry.get().strip()
                if not proxy_addr:
                    messagebox.showerror("错误", "启用手动代理时必须填写代理地址，例如 http://127.0.0.1:7897 或 socks5://127.0.0.1:7897")
                    return
                self.config.set('下载设置', 'Proxy', proxy_addr)
            else:
                self.config.set('下载设置', 'Proxy', '否')
            self.config.set('下载设置', 'AutoProxy', '是' if self.auto_proxy_var.get() else '否')
            self.config.set('下载设置', 'VerifySSL', '是' if self.verify_ssl_var.get() else '否')
            self.config.set('下载设置', 'Download_path', self.download_path_entry.get())
            self.config.set('下载设置', 'Max_dl', self.max_dl_entry.get())
            self.config.set('下载设置', 'Max_retry', self.max_retry_entry.get())
            
            self.callback()
            self.window.destroy()
            messagebox.showinfo("成功", "设置已保存并生效")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存设置失败: {str(e)}")

    def toggle_manual_proxy(self):
        """根据是否启用手动代理启用/禁用地址输入"""
        enabled = (self.manual_proxy_var.get() == '是')
        state = 'normal' if enabled else 'disabled'
        try:
            self.proxy_entry.config(state=state)
        except:
            pass

class HelpWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("使用帮助")
        self.window.geometry("700x600")
        self.window.transient(parent)
        
        # 居中显示
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - self.window.winfo_width()) // 2
        y = (self.window.winfo_screenheight() - self.window.winfo_height()) // 2
        self.window.geometry(f"+{x}+{y}")
        
        self.create_widgets()
    
    def create_widgets(self):
        """创建帮助控件"""
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="FC2资源收集器 - 使用帮助", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # 创建滚动文本框
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.help_text = tk.Text(text_frame, wrap='word', yscrollcommand=scrollbar.set,
                                font=('Arial', 10), padx=10, pady=10)
        self.help_text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=self.help_text.yview)
        
        # 插入帮助内容
        help_content = """# FC2资源收集器使用帮助

## 功能概述
本工具提供两个主要功能：
1. **获取番号** - 从FC2用户页面抓取所有作品番号
2. **抓取磁链** - 根据番号列表搜索对应的磁力链接

## 第一步：获取番号

### 使用方法
1. 切换到"获取番号"选项卡
2. 输入FC2用户页面URL
3. 点击"获取番号"按钮
4. 等待抓取完成

### 支持的URL格式
- 用户作品列表页：https://adult.contents.fc2.com/users/用户名/articles?sort=date&order=desc
- 用户主页：https://adult.contents.fc2.com/users/用户名/
  （程序会自动转换为用户作品列表页）

### 功能特点
- 自动翻页抓取所有作品
- 显示每页抓取到的番号数量
- 支持复制和保存结果
- 自动保存到标准list.txt文件

## 第二步：抓取磁链

### 使用方法
1. 切换到"抓取磁链"选项卡
2. 选择输入方式：直接输入或从文件导入
3. 输入或导入番号列表
4. 点击"开始获取"按钮
5. 等待处理完成

### 番号格式支持
- 标准格式：FC2-PPV-1234567
- 简写格式：1234567
- 每行一个番号

### 结果输出
程序会在下载目录中生成两个文件：
- magnet_YYYYMMDD_HHMMSS.txt - 磁力链接列表
- details_YYYYMMDD_HHMMSS.txt - 详细信息（包含标题、URL等）

## 设置说明

### 代理设置
- **手动代理**：支持HTTP和SOCKS5代理
  - HTTP格式：http://ip:端口
  - SOCKS5格式：socks5://ip:端口
- **自动代理**：自动检测系统代理设置
- **SSL验证**：根据网络环境选择是否验证SSL证书

### 下载设置
- **下载路径**：设置资源保存的文件夹路径
- **下载线程数**：同时处理的线程数量（建议2-4）
- **失败重试次数**：网络异常时的重试次数

## 故障排除

### 网络连接问题
1. 检查代理设置是否正确
2. 尝试关闭SSL证书验证
3. 减少线程数和重试次数
4. 检查网络连接状态

### 番号解析失败
1. 确保番号格式正确
2. 检查输入文本是否有特殊字符
3. 验证番号是否有效

### 磁力链接获取失败
1. 某些番号可能没有对应的磁力链接
2. 网络环境可能影响搜索结果
3. 尝试更换代理或使用直连模式

## 注意事项
- 请合理设置线程数，避免给服务器造成过大负担
- 建议在非网络高峰期使用，以获得更好的成功率
- 获取到的磁力链接可用于下载工具进行下载
- 请遵守相关法律法规，合理使用本工具

## 版本信息
**当前版本**：v0.1

## 技术支持
如有问题，请查看日志信息或联系开发者。
"""
        
        self.help_text.insert('1.0', help_content)
        self.help_text.config(state='disabled')  # 设置为只读
        
        # 关闭按钮
        ttk.Button(main_frame, text="关闭", command=self.window.destroy).pack(pady=(20, 0))

class AboutWindow:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("关于")
        self.window.geometry("400x300")
        self.window.transient(parent)
        self.window.resizable(False, False)
        
        # 居中显示
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - self.window.winfo_width()) // 2
        y = (self.window.winfo_screenheight() - self.window.winfo_height()) // 2
        self.window.geometry(f"+{x}+{y}")
        
        self.create_widgets()
    
    def create_widgets(self):
        """创建关于控件"""
        main_frame = ttk.Frame(self.window, padding=30)
        main_frame.pack(fill='both', expand=True)
        
        # 图标（如果有的话）
        try:
            if os.path.exists('ico.ico'):
                icon = tk.PhotoImage(file='ico.ico')
                icon_label = ttk.Label(main_frame, image=icon)
                icon_label.image = icon  # 保持引用
                icon_label.pack(pady=(0, 20))
        except:
            pass
        
        # 标题
        title_label = ttk.Label(main_frame, text="FC2资源收集器", 
                               font=('Arial', 18, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # 版本
        version_label = ttk.Label(main_frame, text="版本: v0.1", 
                                 font=('Arial', 12))
        version_label.pack(pady=(0, 20))
        
        # 描述
        desc_text = tk.Text(main_frame, wrap='word', height=6, width=40,
                           font=('Arial', 10), padx=10, pady=10)
        desc_text.pack(fill='both', expand=True)
        
        description = """
FC2资源收集器是一个现代化的资源获取工具，
提供友好的图形界面，支持批量获取FC2影片的磁力链接信息。

主要功能：
• 从FC2用户页面批量抓取番号
• 根据番号列表搜索磁力链接
• 支持代理设置和SSL验证
• 实时显示进度和日志
• 结果自动保存到文件

本工具仅供学习交流使用，请合理使用。
"""
        
        desc_text.insert('1.0', description)
        desc_text.config(state='disabled')
        
        # 关闭按钮
        ttk.Button(main_frame, text="确定", command=self.window.destroy).pack(pady=(20, 0))

def main():
    """主函数"""
    root = tk.Tk()
    app = FC2GatherGUI(root)
    
    # 启动时显示欢迎信息
    app.log("FC2资源收集器 v0.1 启动成功！")
    app.log("请按照步骤使用：1.获取番号 → 2.抓取磁链")
    
    root.mainloop()

if __name__ == "__main__":
    main()