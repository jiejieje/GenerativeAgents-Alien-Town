#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cv2
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import timedelta
import numpy
from PIL import Image
import math
import json

PIL_AVAILABLE = True  # 假设 PIL 始终可用，在 main 函数中检查

class VideoSpriteSheetGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("视频帧提取与合成图生成器（支持批量处理）")
        
        # 让根窗口的列也能自适应
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # 初始大小设置为屏幕的百分比，而不是固定值
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        initial_width = int(screen_width * 0.6)
        initial_height = int(screen_height * 0.8)
        self.root.geometry(f"{initial_width}x{initial_height}")
        self.root.minsize(int(screen_width*0.4), int(screen_height*0.5)) # 设置最小尺寸

        self.root.resizable(True, True)

        # 新增：批量处理相关变量
        self.video_paths = []  # 存储批量选择的视频路径
        self.batch_processing = False
        self.progress_var = tk.DoubleVar(value=0)
        self.status_text = tk.StringVar(value="准备就绪")

        # 视频帧提取 变量
        self.video_path = tk.StringVar()
        self.output_dir = tk.StringVar() # 视频帧输出目录，同时作为合成图的输入目录
        self.prefix = tk.StringVar(value="frame")
        self.start_time = tk.StringVar()
        self.end_time = tk.StringVar()
        self.fps_value = tk.IntVar(value=3)  # 新增：每秒提取多少帧
        self.resize_enabled = tk.BooleanVar(value=False)
        self.width = tk.IntVar(value=0)
        self.height = tk.IntVar(value=0)
        self.quality = tk.IntVar(value=95)
        self.auto_time_enabled = tk.BooleanVar(value=True)
        self.output_format = tk.StringVar(value="jpg")
        self.is_processing_video = False # 这个标志现在只在内部逻辑中使用，主要用 is_processing
        self.is_processing_composite = False # 这个标志现在只在内部逻辑中使用，主要用 is_processing
        self.is_processing = False # 新增：统一的单个处理状态标志
        self.video_info = {}

        # 合成图生成 变量
        self.composite_output_dir = tk.StringVar() # 合成图输出目录，可以与视频帧输出目录不同
        self.output_size = tk.StringVar(value="3200")

        # 新增：配置文件路径
        self.settings_file = "video_generator_settings.json"
        
        # 创建UI
        self.create_widgets()
        
        # 加载配置
        self.load_settings()

        # 绑定事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # --- Start of scrollbar implementation ---
        container = ttk.Frame(self.root)
        container.grid(row=0, column=0, sticky="nsew") # 使用grid并填充整个窗口
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, padding="10")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 修改布局以适应grid
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # --- End of scrollbar implementation ---

        # 设置主框架的列权重，使其能够自适应宽度
        self.scrollable_frame.columnconfigure(0, weight=1)

        # 视频帧提取部分
        video_frame = ttk.Frame(self.scrollable_frame, padding="10")
        video_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.create_video_frame_widgets(video_frame)

        # 合成图生成部分
        composite_frame = ttk.LabelFrame(self.scrollable_frame, text="合成图生成", padding="10")
        composite_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        self.create_composite_widgets(composite_frame)

        # 统一的状态和进度条
        status_frame = ttk.Frame(self.scrollable_frame)
        status_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        status_frame.columnconfigure(0, weight=1)
        self.progressbar = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, length=100, mode='determinate', variable=self.progress_var)
        self.progressbar.grid(row=0, column=0, sticky="ew", pady=5)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_text)
        self.status_label.grid(row=1, column=0, sticky="ew")

        # 操作按钮 (公共部分)
        button_frame = ttk.Frame(self.scrollable_frame)
        button_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=10)

        # 为了让按钮居中且间距合理，使用一个内部frame
        center_button_frame = ttk.Frame(button_frame)
        center_button_frame.pack()

        ttk.Button(center_button_frame, text="分析视频", command=self.analyze_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_button_frame, text="提取帧并生成合成图", command=self.start_extraction).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_button_frame, text="停止提取", command=self.stop_extraction).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_button_frame, text="修复问题", command=self.fix_common_issues).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_button_frame, text="批量选择视频", command=self.batch_browse_videos).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_button_frame, text="批量处理", command=self.batch_process_videos).pack(side=tk.LEFT, padx=5)
        ttk.Button(center_button_frame, text="退出", command=self.on_close).pack(side=tk.RIGHT, padx=5)


    def create_video_frame_widgets(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1) # 让父框架的列也能扩展
        # 文件选择部分
        file_frame = ttk.Frame(parent_frame)
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(file_frame, text="视频文件:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.video_path, width=50).grid(row=0, column=1, padx=5, sticky=tk.EW)
        ttk.Button(file_frame, text="浏览...", command=self.browse_video).grid(row=0, column=2, padx=5)

        ttk.Label(file_frame, text="帧输出目录:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.output_dir, width=50).grid(row=1, column=1, padx=5, sticky=tk.EW)
        ttk.Button(file_frame, text="浏览...", command=self.browse_output_dir).grid(row=1, column=2, padx=5)

        ttk.Label(file_frame, text="文件前缀:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(file_frame, textvariable=self.prefix, width=20).grid(row=2, column=1, padx=5, sticky=tk.W)

        # 让包含输入框的列（第1列）可以随窗口拉伸
        file_frame.columnconfigure(1, weight=1)

        # 选项部分
        options_frame = ttk.Frame(parent_frame)
        options_frame.pack(fill=tk.X, pady=5)

        # 时间选择
        time_frame = ttk.Frame(options_frame)
        time_frame.pack(fill=tk.X, pady=5)
        time_frame.columnconfigure(2, weight=1) # 让提示文本列可以扩展

        ttk.Checkbutton(time_frame, text="自动设置视频时间范围", variable=self.auto_time_enabled).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))

        ttk.Label(time_frame, text="开始时间:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(time_frame, textvariable=self.start_time, width=15).grid(row=1, column=1, padx=5, sticky=tk.W)
        ttk.Label(time_frame, text="(格式: HH:MM:SS 或 MM:SS 或秒数)").grid(row=1, column=2, sticky=tk.W, padx=5)

        ttk.Label(time_frame, text="结束时间:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(time_frame, textvariable=self.end_time, width=15).grid(row=2, column=1, padx=5, sticky=tk.W)
        ttk.Label(time_frame, text="(格式同上，留空表示视频结束)").grid(row=2, column=2, sticky=tk.W, padx=5)

        # 帧提取速率
        ttk.Label(options_frame, text="每秒提取帧数:").pack(anchor=tk.W, pady=5)
        fps_frame = ttk.Frame(options_frame)
        fps_frame.pack(fill=tk.X, pady=5)
        fps_spin = ttk.Spinbox(fps_frame, from_=1, to=60, textvariable=self.fps_value, width=8, command=self.update_fps_label)
        fps_spin.pack(side=tk.LEFT, padx=5)
        self.fps_label = ttk.Label(fps_frame, text="1")
        self.fps_label.pack(side=tk.LEFT, padx=5)

        # 调整大小选项
        resize_frame = ttk.Frame(options_frame)
        resize_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(resize_frame, text="调整输出图片大小", variable=self.resize_enabled).grid(
            row=0, column=0, columnspan=4, sticky=tk.W, pady=5)

        ttk.Label(resize_frame, text="宽度:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(resize_frame, textvariable=self.width, width=8).grid(row=1, column=1, padx=5, sticky=tk.W)

        ttk.Label(resize_frame, text="高度:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(resize_frame, textvariable=self.height, width=8).grid(row=1, column=3, padx=5, sticky=tk.W)

        # 输出格式选项
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=5)

        ttk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT, padx=5)

        formats = [("JPG", "jpg"), ("PNG", "png"), ("BMP", "bmp")]
        for i, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=text, value=value,
                           variable=self.output_format).pack(side=tk.LEFT, padx=10)

        # 质量选项
        ttk.Label(options_frame, text="JPEG质量:").pack(anchor=tk.W, pady=5)
        quality_frame = ttk.Frame(options_frame)
        quality_frame.pack(fill=tk.X, pady=5)

        ttk.Scale(quality_frame, from_=1, to=100, orient=tk.HORIZONTAL,
                 variable=self.quality, command=self.update_quality_label).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.quality_label = ttk.Label(quality_frame, text="95%")
        self.quality_label.pack(side=tk.RIGHT, padx=5)


    def create_composite_widgets(self, parent_frame):
        # 容器框架，使用grid布局来更好地控制
        container = ttk.Frame(parent_frame)
        container.pack(fill=tk.X, expand=True)
        container.columnconfigure(1, weight=1) # 让第二列（输入框）扩展

        # 输入文件夹 (使用视频帧输出目录)
        ttk.Label(container, text="帧图片输入目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(container, textvariable=self.output_dir, width=50, state='readonly').grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)

        # 输出文件夹
        ttk.Label(container, text="合成图输出目录:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(container, textvariable=self.composite_output_dir, width=50).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(container, text="浏览...", command=self.browse_composite_output_dir).grid(row=1, column=2, padx=5, pady=5)

        # 输出图片尺寸设置
        size_frame = ttk.LabelFrame(parent_frame, text="合成图尺寸", padding="5")
        size_frame.pack(fill=tk.X, pady=10, padx=5)

        self.output_size = tk.StringVar(value="3200")
        ttk.Label(size_frame, text="尺寸:").grid(row=0, column=0)
        ttk.Entry(size_frame, textvariable=self.output_size, width=10).grid(row=0, column=1)
        ttk.Label(size_frame, text="x").grid(row=0, column=2)
        ttk.Entry(size_frame, textvariable=self.output_size, width=10).grid(row=0, column=3)
        ttk.Label(size_frame, text="像素").grid(row=0, column=4)


    # 视频帧提取功能函数 (大部分从原脚本 VideoToFramesGUI 复制)
    def browse_video(self):
        filename = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv"), ("所有文件", "*.*")]
        )
        if filename:
            self.video_path.set(filename)
            video_name = os.path.splitext(os.path.basename(filename))[0]
            output_dir = os.path.join(os.path.dirname(filename), video_name + "_frames")
            self.output_dir.set(output_dir)
            self.composite_output_dir.set(output_dir) # 默认合成图输出目录与帧图片输出目录相同
            self.analyze_video()

    def browse_output_dir(self):
        dirname = filedialog.askdirectory(title="选择帧输出目录")
        if dirname:
            self.output_dir.set(dirname)
            self.composite_output_dir.set(dirname) # 默认合成图输出目录与帧图片输出目录相同

    def browse_composite_output_dir(self):
        dirname = filedialog.askdirectory(title="选择合成图输出目录")
        if dirname:
            self.composite_output_dir.set(dirname)

    def update_fps_label(self):
        self.fps_label.config(text=f"{self.fps_value.get()}")

    def update_quality_label(self, value):
        self.quality_label.config(text=f"{int(float(value))}%")

    def analyze_video(self):
        video_path = self.video_path.get()
        if not video_path:
            messagebox.showerror("错误", "请先选择视频文件！")
            return

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                messagebox.showerror("错误", f"无法打开视频文件: {video_path}")
                return

            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0

            self.video_info = {
                "frame_count": frame_count,
                "fps": fps,
                "width": width,
                "height": height,
                "duration": duration
            }

            if not self.width.get() or not self.height.get():
                self.width.set(width)
                self.height.set(height)

            if self.auto_time_enabled.get():
                self.start_time.set("0")
                self.end_time.set(str(round(duration, 2)))
                status_msg = "视频分析完成，已自动设置开始/结束时间"
            else:
                status_msg = "视频分析完成"

            cap.release()
            self.status_text.set(status_msg)
        except Exception as e:
            messagebox.showerror("错误", f"分析视频时出错: {str(e)}")

    def format_time(self, seconds):
        td = timedelta(seconds=seconds)
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{int(td.microseconds/1000):03d}"

    def time_to_seconds(self, time_str):
        if not time_str:
            return None
        if time_str.isdigit():
            return float(time_str)
        parts = time_str.replace(',', '.').split(':')
        seconds = 0
        if len(parts) == 3:
            h, m, s = parts
            seconds = int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            seconds = int(m) * 60 + float(s)
        else:
            try:
                seconds = float(parts[0])
            except ValueError:
                raise ValueError(f"无法解析时间格式: {time_str}")
        return seconds

    def start_extraction(self):
        if self.is_processing or self.batch_processing:
            messagebox.showinfo("提示", "当前正在处理中，请等待完成或停止当前任务")
            return

        video_path = self.video_path.get()
        output_dir = self.output_dir.get()
        composite_output_dir = self.composite_output_dir.get() # 合成图输出目录也要检查

        if not video_path:
            messagebox.showerror("错误", "请先选择视频文件！")
            return
        if not output_dir:
            messagebox.showerror("错误", "请选择帧输出目录！")
            return
        if not composite_output_dir:
            messagebox.showerror("错误", "请选择合成图输出目录！")
            return

        # 确保分析视频信息
        if not self.video_info or self.video_info.get("path") != video_path:
             self.analyze_video()
             if not self.video_info: # 分析失败则返回
                 return

        try:
            self.is_processing = True # 设置主处理状态
            self.status_text.set("开始处理视频...")
            self.progress_var.set(0)

            # 启动合并后的处理线程
            processing_thread = threading.Thread(
                target=self._process_single_video_thread,
                args=(video_path, output_dir, composite_output_dir)
            )
            processing_thread.daemon = True
            processing_thread.start()

        except ValueError as e:
            messagebox.showerror("参数错误", str(e))
            self.is_processing = False # 出错时重置状态
        except Exception as e:
            messagebox.showerror("错误", f"启动处理时出错: {str(e)}")
            self.is_processing = False # 出错时重置状态

    # 新增：合并处理单个视频的线程函数
    def _process_single_video_thread(self, video_path, output_dir, composite_output_dir):
        try:
            self.status_text.set("正在提取帧...")
            self.progress_var.set(0)
            # 单个处理时，保存帧到磁盘 (output_dir)，不返回内存帧
            extract_success, _ = self._extract_frames_logic(video_path, output_dir, return_frames_in_memory=False)

            if not extract_success:
                 self.update_status("帧提取失败，无法继续生成合成图。", error=True)
                 return

            self.status_text.set("正在生成合成图...")
            self.progress_var.set(0)
            # 从磁盘读取帧 (output_dir 作为输入源)
            self._generate_composite_logic(output_dir, composite_output_dir, is_frames_in_memory=False)

            self.update_status("单个视频处理完成！")
        except Exception as e:
            import traceback
            error_msg = f"处理过程中出错: {str(e)}\n{traceback.format_exc()}"
            self.update_status(error_msg, error=True)
        finally:
            self.is_processing = False # 无论成功失败，最后都重置状态
            self.progress_var.set(0) # 重置进度条


    # 修改：提取核心逻辑，返回成功与否 和 帧列表（如果需要）
    def _extract_frames_logic(self, video_path, output_dir_if_saving, return_frames_in_memory=False):
        collected_frames = [] if return_frames_in_memory else None
        cap = None # Ensure cap is defined for finally block
        try:
            prefix = self.prefix.get()
            quality = self.quality.get()
            resize = None
            if self.resize_enabled.get():
                width = self.width.get()
                height = self.height.get()
                if width > 0 and height > 0:
                    resize = (width, height)

            video_fps = self.video_info.get("fps", 0)
            target_fps = self.fps_value.get()
            if video_fps <= 0 or target_fps <= 0:
                self.update_status("错误：视频帧率或目标帧率无效", error=True)
                return False, None
            interval = max(1, round(video_fps / target_fps))

            start_time_str = self.start_time.get()
            end_time_str = self.end_time.get()
            start_time = self.time_to_seconds(start_time_str) if start_time_str else 0
            end_time = self.time_to_seconds(end_time_str) if end_time_str else self.video_info.get("duration", None)

            if not return_frames_in_memory and output_dir_if_saving:
                try:
                    os.makedirs(output_dir_if_saving, exist_ok=True)
                except Exception as e:
                    self.update_status(f"帧输出目录错误: {str(e)}", error=True)
                    return False, None
            elif return_frames_in_memory and output_dir_if_saving:
                # Batch mode with this new logic shouldn't be trying to save individual frames
                # self.update_status("警告: 在内存返回模式下，不应指定帧输出目录。", error=False)
                pass # Do nothing with output_dir_if_saving if frames are returned in memory

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.update_status(f"错误：无法打开视频文件 {video_path}", error=True)
                return False, None

            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            # width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) # Not directly used here anymore
            # height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if frame_count <= 0 or fps <= 0:
                 self.update_status(f"错误：无效的视频信息 (帧数: {frame_count}, 帧率: {fps})", error=True)
                 cap.release()
                 return False, None

            start_frame = int(start_time * fps)
            end_frame = frame_count - 1
            if end_time is not None:
                end_frame = min(end_frame, int(end_time * fps))

            if start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                actual_start_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                if abs(actual_start_frame - start_frame) > fps:
                     self.update_status(f"警告：无法精确设置开始帧 {start_frame}，实际从 {actual_start_frame} 开始", error=False)

            total_frames_to_process = end_frame - start_frame + 1
            if total_frames_to_process <= 0:
                 self.update_status(f"错误：计算得到的待处理帧数为0或负数", error=True)
                 cap.release()
                 return False, None

            expected_output_frames = total_frames_to_process // interval
            # if expected_output_frames <= 0: # Allow 0 expected frames

            digits = len(str(expected_output_frames)) if expected_output_frames > 0 else 1
            current_frame_index = start_frame
            saved_or_collected_count = 0
            failed_count = 0
            frames_processed_in_loop = 0

            self.update_status(f"开始提取 {expected_output_frames} 帧...")

            while current_frame_index <= end_frame:
                ret, frame = cap.read()
                if not ret:
                    self.update_status(f"警告：在帧 {current_frame_index} 无法读取，提前结束。已处理 {saved_or_collected_count} 帧.", error=False)
                    break

                if (current_frame_index - start_frame) % interval == 0:
                    # This try-except is for individual frame processing
                    try:
                        processed_frame = frame
                        if resize:
                            # This inner try-except is for the resize operation
                            try:
                                processed_frame = cv2.resize(frame, resize, interpolation=cv2.INTER_AREA)
                            except Exception as resize_e:
                                self.update_status(f"帧 {current_frame_index} 调整大小时出错: {resize_e}", error=False)
                                # Use original frame if resize fails, processed_frame remains original frame

                        if return_frames_in_memory:
                            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                            collected_frames.append(rgb_frame) # Store as numpy array (RGB)
                            saved_or_collected_count += 1
                        elif output_dir_if_saving:
                            # Corrected f-string syntax
                            output_file_base = os.path.join(output_dir_if_saving, f"{prefix}_{saved_or_collected_count:0{digits}d}")
                            output_format_str = self.output_format.get().lower()
                            output_file = f"{output_file_base}.{output_format_str}"

                            save_success = False
                            encode_params = []
                            if output_format_str == 'jpg' or output_format_str == 'jpeg':
                                encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                            elif output_format_str == 'png':
                                png_compression = min(9, max(0, int((100 - quality) / 10)))
                                encode_params = [cv2.IMWRITE_PNG_COMPRESSION, png_compression]
                            elif output_format_str == 'webp':
                                encode_params = [cv2.IMWRITE_WEBP_QUALITY, quality]
                            try:
                                cv2.imencode(f'.{output_format_str}', processed_frame, encode_params)[1].tofile(output_file)
                                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                                    save_success = True
                            except Exception as imwrite_e:
                                 self.update_status(f"OpenCV保存帧 {saved_or_collected_count} ({output_file}) 失败: {imwrite_e}", error=False)
                            if save_success:
                                saved_or_collected_count += 1
                            else:
                                failed_count += 1
                                self.update_status(f"错误：无法保存帧 {saved_or_collected_count} 到 {output_file}", error=False)
                        else:
                            failed_count +=1
                            self.update_status("错误：提取帧逻辑目标不明确（无保存路径且不返回内存帧）", error=True)

                        if expected_output_frames > 0:
                            progress_percent = (saved_or_collected_count / expected_output_frames) * 100
                            self.update_progress(progress_percent)
                        current_progress_percent = 0
                        if expected_output_frames > 0 : 
                            current_progress_percent = (saved_or_collected_count / expected_output_frames) * 100 
                        if saved_or_collected_count % 20 == 0 and saved_or_collected_count > 0:
                            self.update_status(f"已处理: {saved_or_collected_count} 帧 ({current_progress_percent:.1f}%)")

                    except Exception as e_inner_frame_processing:
                        self.update_status(f"处理帧 {current_frame_index} 内循环时出错: {str(e_inner_frame_processing)}")
                        failed_count += 1

                current_frame_index += 1
                frames_processed_in_loop += 1
                if frames_processed_in_loop > frame_count * 1.2: # Increased tolerance slightly
                    self.update_status(f"警告：处理的帧数 ({frames_processed_in_loop}) 远超视频总帧数 ({frame_count}). 可能视频未正确结束读取。", error=False)
                    break

            cap.release()
            final_status = f"帧提取完成！共循环 {frames_processed_in_loop} 次，目标处理 {saved_or_collected_count} 帧"
            if failed_count > 0:
                final_status += f"，失败 {failed_count} 帧"
            self.update_status(final_status)
            self.update_progress(100)
            return saved_or_collected_count > 0 or (return_frames_in_memory and saved_or_collected_count == 0 and expected_output_frames == 0), collected_frames

        except Exception as e:
            import traceback
            self.update_status(f"提取帧核心逻辑出错: {str(e)}\n{traceback.format_exc()}", error=True)
            return False, None
        finally:
            if cap and cap.isOpened():
                cap.release()

    # 修改：提取核心逻辑，可以从内存中的帧或文件夹生成
    def _generate_composite_logic(self, input_source, output_folder, is_frames_in_memory=False, show_notifications=True):
        try:
            if not PIL_AVAILABLE:
                self.update_status("错误：缺少Pillow库，无法生成合成图。请安装：pip install Pillow", error=True)
                return False

            if not is_frames_in_memory and (not isinstance(input_source, str) or not os.path.isdir(input_source)):
                 self.update_status(f"错误：帧图片输入目录无效或不存在: {input_source}", error=True)
                 return False
            elif is_frames_in_memory and (not isinstance(input_source, list)):
                 self.update_status(f"错误：内存帧输入不是列表类型", error=True)
                 return False

            try:
                os.makedirs(output_folder, exist_ok=True)
            except Exception as e_mkdir:
                 self.update_status(f"错误：创建合成图输出目录失败: {output_folder} ({e_mkdir})", error=True)
                 return False

            try:
                size = int(self.output_size.get())
                if size <= 0: raise ValueError("尺寸必须大于0")
            except ValueError as e_size:
                self.update_status(f"错误：无效的合成图尺寸设置 ({e_size})", error=True)
                return False

            self.update_status("开始生成合成图...")
            self.progress_var.set(0)
            self.root.update()

            images = []
            if is_frames_in_memory:
                opencv_frames = input_source
                if not opencv_frames:
                    self.update_status("错误：内存中没有帧数据可用于生成合成图。", error=True)
                    return False
                for idx, cv_frame_rgb in enumerate(opencv_frames):
                    try:
                        pil_image = Image.fromarray(cv_frame_rgb)
                        images.append(pil_image)
                        if len(images) % 50 == 0 and len(opencv_frames) > 0:
                            self.update_progress((len(images) / len(opencv_frames)) * 10)
                    except Exception as e_conv:
                        self.update_status(f"警告：转换内存中第 {idx} 帧为图片失败: {e_conv}", error=False)
                        continue
            else: # Load from disk
                input_folder_path = input_source
                def get_number(filename):
                    import re
                    match = re.findall(r'\d+', filename)
                    return int(match[-1]) if match else float('inf')
                try:
                     all_files = os.listdir(input_folder_path)
                except Exception as e_listdir:
                     self.update_status(f"错误：无法读取输入目录 {input_folder_path}: {e_listdir}", error=True)
                     return False
                image_files_on_disk = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp'))]
                if not image_files_on_disk:
                    self.update_status(f"错误：输入目录 {input_folder_path} 中没有找到支持的图片文件！", error=True)
                    return False
                image_files_on_disk.sort(key=get_number)
                for idx, img_file in enumerate(image_files_on_disk):
                    img_path = os.path.join(input_folder_path, img_file)
                    try:
                        img = Image.open(img_path)
                        images.append(img)
                        if len(images) % 50 == 0 and len(image_files_on_disk) > 0:
                            self.update_progress((len(images) / len(image_files_on_disk)) * 10)
                    except Exception as e_load:
                        self.update_status(f"警告：无法打开图片 {img_file}，已跳过: {e_load}", error=False)
                        continue

            if not images:
                 self.update_status(f"错误：未能成功准备任何图片数据用于生成合成图。", error=True)
                 return False

            widths, heights = set(), set()
            for img in images: # Get dimensions from loaded PIL images
                widths.add(img.width)
                heights.add(img.height)

            if len(widths) > 1 or len(heights) > 1:
                 self.update_status(f"警告：帧图片尺寸不一致 (宽度: {widths}, 高度: {heights})，将使用第一张图片尺寸进行布局。", error=False)

            single_width = images[0].width
            single_height = images[0].height
            if single_width <= 0 or single_height <= 0:
                 self.update_status(f"错误：无效的图片尺寸 ({single_width}x{single_height}) 来自第一张图片。", error=True)
                 return False

            num_images = len(images)
            cols = math.ceil(math.sqrt(num_images * (single_height / single_width))) if single_width > 0 and single_height > 0 else math.ceil(math.sqrt(num_images))
            if cols == 0: cols = 1 # Avoid division by zero if num_images is 0, though caught earlier
            rows = math.ceil(num_images / cols)
            if rows == 0 and num_images > 0 : rows = 1 # ensure rows is at least 1 if there are images
            if num_images == 0: rows = 0 # If no images, rows should be 0.

            total_width = single_width * cols
            total_height = single_height * rows
            
            if num_images > 0 and (total_width == 0 or total_height == 0):
                 self.update_status(f"错误: 计算的总合成图尺寸为零 ({total_width}x{total_height})，但有 {num_images} 张图片。", error=True)
                 return False
            if num_images == 0 : # If there are no images, consider it a success with empty output
                self.update_status("没有图片可用于生成合成图，跳过生成。")
                total_width, total_height = size, size # default size for empty
                sprite_sheet_resized = Image.new('RGBA', (size, size), (0,0,0,0))
                frames_meta = {}
            else:
                self.update_status(f"开始拼接 {num_images} 张图片 ({cols}x{rows})...")
                self.update_progress(15)
                sprite_sheet = Image.new('RGBA', (total_width, total_height), (0, 0, 0, 0))
                frames_meta = {}
                scale_factor = size / total_width if total_width > 0 else 1
                final_sprite_width = size
                final_sprite_height = int(total_height * scale_factor) if total_width > 0 and total_height > 0 else size
                if final_sprite_height == 0 and num_images > 0: final_sprite_height = size # fallback for safety

                scaled_single_width = int(single_width * scale_factor)
                scaled_single_height = int(single_height * scale_factor)

                if num_images > 0 and (scaled_single_width <= 0 or scaled_single_height <= 0):
                     self.update_status(f"错误：计算得到的缩放后单帧尺寸无效 ({scaled_single_width}x{scaled_single_height})", error=True)
                     return False

                for idx, img in enumerate(images):
                    current_col = idx % cols
                    current_row = idx // cols
                    x_pos = current_col * single_width
                    y_pos = current_row * single_height
                    try:
                         current_img_to_paste = img
                         if img.width != single_width or img.height != single_height:
                              current_img_to_paste = img.resize((single_width, single_height), Image.Resampling.LANCZOS)
                         sprite_sheet.paste(current_img_to_paste, (x_pos, y_pos))
                    except Exception as paste_e:
                         self.update_status(f"警告：粘贴图片 {idx} 时出错，已跳过: {paste_e}", error=False)
                         continue
                    scaled_x = int(x_pos * scale_factor)
                    scaled_y = int(y_pos * scale_factor)
                    frame_key = str(idx + 1)
                    frames_meta[frame_key] = {
                        "frame": {"x": scaled_x, "y": scaled_y, "w": scaled_single_width, "h": scaled_single_height},
                        "rotated": False, "trimmed": False,
                        "spriteSourceSize": {"x": 0, "y": 0, "w": scaled_single_width, "h": scaled_single_height},
                        "sourceSize": {"w": scaled_single_width, "h": scaled_single_height},
                        "anchor": {"x": 0.5, "y": 0.5}
                    }
                    self.update_progress(15 + (idx / num_images * 60))
                self.update_status("正在缩放合成图...")
                self.update_progress(80)
                try:
                    resampling_method = Image.Resampling.LANCZOS
                    sprite_sheet_resized = sprite_sheet.resize((final_sprite_width, final_sprite_height), resampling_method)
                except Exception as resize_e:
                     self.update_status(f"错误：缩放合成图时出错: {resize_e}", error=True)
                     return False

            self.update_progress(90)
            output_image_path = os.path.join(output_folder, "texture.png")
            output_json_path = os.path.join(output_folder, "composite.json")
            try:
                sprite_sheet_resized.save(output_image_path, format='PNG')
                self.update_status(f"合成图已保存到: {output_image_path}")
            except Exception as save_img_e:
                self.update_status(f"错误：保存合成图图片失败: {save_img_e}", error=True)
                return False

            json_data = {
                "frames": frames_meta,
                "meta": {
                    "app": "VideoSpriteSheetGenerator", "version": "1.2",
                    "image": "texture.png", "format": "RGBA8888",
                    "size": {"w": sprite_sheet_resized.width, "h": sprite_sheet_resized.height},
                    "scale": "1"
                }
            }
            try:
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=4)
                self.update_status(f"JSON元数据已保存到: {output_json_path}")
            except Exception as save_json_e:
                 self.update_status(f"错误：保存JSON文件失败: {save_json_e}", error=True)
                 return False

            self.progress_var.set(100)
            self.update_status("合成图生成完成！")
            if show_notifications:
                if num_images > 0: # Only show success if images were processed
                    messagebox.showinfo("成功", f"合成图和JSON文件已生成！\n图片: {output_image_path}\nJSON: {output_json_path}")
                    if messagebox.askyesno("完成", "是否打开合成图输出目录？"):
                        self.open_output_dir(output_folder)
                elif is_frames_in_memory and not input_source : # specifically if called with empty list from batch mode
                    messagebox.showinfo("提示", f"没有提取到帧，空的合成图已生成。\n图片: {output_image_path}\nJSON: {output_json_path}")

            return True
        except Exception as e:
            import traceback
            self.update_status(f"生成合成图核心逻辑出错: {str(e)}\n{traceback.format_exc()}", error=True)
            return False

    def batch_browse_videos(self):
        filenames = filedialog.askopenfilenames(
            title="批量选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv"), ("所有文件", "*.*")]
        )
        if filenames:
            self.video_paths = list(filenames)
            self.status_text.set(f"已选择 {len(self.video_paths)} 个视频文件")

    def batch_process_videos(self):
        if self.is_processing or self.batch_processing: # 检查两个标志
            messagebox.showinfo("提示", "当前正在处理中，请等待完成或停止当前任务")
            return
        if not self.video_paths:
            messagebox.showerror("错误", "请先批量选择视频文件！")
            return

        self.batch_processing = True # 设置批量处理状态
        self.progress_var.set(0)
        self.status_text.set("开始批量处理...")
        threading.Thread(target=self._batch_process_thread, daemon=True).start()

    def _batch_process_thread(self):
        total = len(self.video_paths)
        success_count = 0
        failed_videos = []

        for idx, video_path in enumerate(self.video_paths):
            current_video_basename = os.path.basename(video_path)
            self.status_text.set(f"正在处理 ({idx+1}/{total}): {current_video_basename}")
            self.progress_var.set((idx / total) * 100)

            video_name = os.path.splitext(current_video_basename)[0]
            base_dir = os.path.dirname(video_path)
            
            # 将每个视频的所有输出（帧图片、合成图）都放在一个文件夹里
            output_dir = os.path.join(base_dir, f"{video_name}_output")
            
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e_mkdir:
                error_msg = f"创建输出目录失败: {e_mkdir}"
                self.update_status(error_msg, error=True)
                failed_videos.append(f"{current_video_basename}: {error_msg}")
                continue # 跳过此视频

            try:
                 self.video_path.set(video_path)
                 self.analyze_video()
                 if not self.video_info:
                     raise Exception(f"无法分析视频 {current_video_basename}")

                 self.update_status(f"提取帧到磁盘: {current_video_basename}")
                 # 批量处理时，帧提取到磁盘
                 extract_success, _ = self._extract_frames_logic(video_path, output_dir, return_frames_in_memory=False)

                 if not extract_success:
                     raise Exception(f"提取帧失败: {current_video_basename}")

                 self.update_status(f"生成合成图: {current_video_basename}")
                 # 从磁盘中的帧生成合成图，且不显示处理中弹窗
                 composite_success = self._generate_composite_logic(output_dir, output_dir, is_frames_in_memory=False, show_notifications=False)

                 if not composite_success:
                      raise Exception(f"生成合成图失败: {current_video_basename}")

                 success_count += 1
                 self.update_status(f"处理成功: {current_video_basename}")
            except Exception as e:
                 self.update_status(f"处理失败: {current_video_basename} - {str(e)}", error=True)
                 failed_videos.append(f"{current_video_basename}: {str(e)}")
            # finally 在循环外进行整体状态重置

        # 批量处理结束
        self.progress_var.set(100)
        final_batch_status = f"批量处理完成！成功 {success_count}/{total} 个视频。"
        if failed_videos:
             final_batch_status += f"\n失败列表:\n" + "\n".join(failed_videos)
             messagebox.showwarning("批量处理结果", final_batch_status)
        else:
             messagebox.showinfo("批量处理结果", final_batch_status)

        if success_count > 0 and self.video_paths:
            first_video_dir = os.path.dirname(self.video_paths[0])
            if messagebox.askyesno("打开目录", f"是否打开第一个视频所在的目录？\n{first_video_dir}"):
                self.open_output_dir(first_video_dir)

        self.status_text.set(final_batch_status)
        self.is_processing = False # 确保单个处理标志也重置
        self.batch_processing = False # 重置批量处理状态

    def update_progress(self, value):
        def update():
            self.progress_var.set(value)
        self.root.after(0, update)

    def update_status(self, message, error=False):
        def update():
            self.status_text.set(message)
            if error:
                messagebox.showerror("错误", message)
        self.root.after(0, update)

    def stop_extraction(self):
        if self.is_processing:
            self.is_processing = False
            self.status_text.set("正在停止提取帧...")

    def open_output_dir(self, path):
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                import subprocess
                subprocess.Popen(['open', path])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录: {str(e)}")

    def save_settings(self):
        settings = {
            "video_path": self.video_path.get(),
            "output_dir": self.output_dir.get(),
            "composite_output_dir": self.composite_output_dir.get(),
            "prefix": self.prefix.get(),
            "start_time": self.start_time.get(),
            "end_time": self.end_time.get(),
            "fps_value": self.fps_value.get(),
            "resize_enabled": self.resize_enabled.get(),
            "width": self.width.get(),
            "height": self.height.get(),
            "quality": self.quality.get(),
            "auto_time_enabled": self.auto_time_enabled.get(),
            "output_format": self.output_format.get(),
            "output_size": self.output_size.get(),
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"无法保存设置: {e}")

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.video_path.set(settings.get("video_path", ""))
                    self.output_dir.set(settings.get("output_dir", ""))
                    self.composite_output_dir.set(settings.get("composite_output_dir", ""))
                    self.prefix.set(settings.get("prefix", "frame"))
                    self.start_time.set(settings.get("start_time", ""))
                    self.end_time.set(settings.get("end_time", ""))
                    self.fps_value.set(settings.get("fps_value", 3))
                    self.resize_enabled.set(settings.get("resize_enabled", False))
                    self.width.set(settings.get("width", 0))
                    self.height.set(settings.get("height", 0))
                    self.quality.set(settings.get("quality", 95))
                    self.auto_time_enabled.set(settings.get("auto_time_enabled", True))
                    self.output_format.set(settings.get("output_format", "jpg"))
                    self.output_size.set(settings.get("output_size", "3200"))
        except Exception as e:
            print(f"无法加载设置: {e}")

    def on_close(self):
        self.save_settings() # 保存设置
        if self.is_processing or self.is_processing_composite:
            if messagebox.askyesno("确认", "当前正在处理中，确定要退出吗？"):
                self.is_processing = False
                self.is_processing_composite = False
                self.root.destroy()
        else:
            self.root.destroy()

    def quick_setting(self, start=None, end=None, fps=None):
        if not self.video_info:
            messagebox.showinfo("提示", "请先分析视频")
            return

        if start is not None:
            self.start_time.set(str(start))
        if end is not None:
            self.end_time.set(str(end))
        elif end is None and start is not None:
            self.end_time.set(str(round(self.video_info["duration"], 2)))
        if fps is not None and self.video_info["fps"] > 0:
            self.fps_value.set(fps)
            self.update_fps_label()
        self.status_text.set("已应用快速设置")

    def set_one_frame_per_second(self):
        if not self.video_info or self.video_info["fps"] <= 0:
            messagebox.showinfo("提示", "请先分析视频")
            return
        self.fps_value.set(1)
        self.update_fps_label()
        self.status_text.set(f"已设置为每秒提取1帧")

    def set_frames_per_second(self, target_fps):
        if not self.video_info or self.video_info["fps"] <= 0:
            messagebox.showinfo("提示", "请先分析视频")
            return
        self.fps_value.set(target_fps)
        self.update_fps_label()
        self.status_text.set(f"已设置为每秒{target_fps}帧")

    def fix_common_issues(self):
        if self.is_processing or self.is_processing_composite:
            messagebox.showinfo("提示", "当前正在处理中，请等待完成或停止当前任务")
            return

        issues_fixed = []
        try:
            cv2_version = cv2.__version__
            issues_fixed.append(f"✓ OpenCV 版本 {cv2_version} 已正确安装")
        except:
            messagebox.showerror("错误", "无法检测OpenCV版本，请确保已正确安装OpenCV")
            return

        global PIL_AVAILABLE
        if not PIL_AVAILABLE:
            try:
                import subprocess
                self.update_status("正在尝试安装PIL/Pillow库...", error=False)
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
                issues_fixed.append("✓ 成功安装PIL/Pillow库")
                from PIL import Image
                PIL_AVAILABLE = True
            except Exception as e:
                issues_fixed.append(f"✗ 无法安装PIL/Pillow库: {str(e)}")
                issues_fixed.append("请手动运行: pip install pillow")
        else:
            issues_fixed.append("✓ PIL/Pillow库已安装，可用作OpenCV的备选方案")

        output_dir = self.output_dir.get()
        if output_dir:
            try:
                cleaned_path = ''.join(c for c in output_dir if c.isalnum() or c in r"\_/.:- ")
                if cleaned_path != output_dir:
                    self.output_dir.set(cleaned_path)
                    self.composite_output_dir.set(cleaned_path) # 同时更新合成图的输入目录
                    issues_fixed.append("✓ 已清理输出路径中的非法字符")

                os.makedirs(cleaned_path, exist_ok=True)
                test_file = os.path.join(cleaned_path, "__test_write__.txt")
                with open(test_file, 'w') as f:
                    f.write("测试")
                os.remove(test_file)
                issues_fixed.append("✓ 输出目录权限检查通过")
            except Exception as e:
                issues_fixed.append(f"✗ 输出目录问题: {str(e)}")
                try:
                    import pathlib
                    home_dir = str(pathlib.Path.home() / "Documents" / "视频帧提取")
                    os.makedirs(home_dir, exist_ok=True)
                    self.output_dir.set(home_dir)
                    self.composite_output_dir.set(home_dir) # 同时更新合成图的输入目录
                    issues_fixed.append(f"✓ 已将输出目录重设为: {home_dir}")
                except:
                    issues_fixed.append("✗ 无法自动修复输出目录问题")

        video_path = self.video_path.get()
        if video_path:
            if not os.path.exists(video_path):
                issues_fixed.append(f"✗ 视频文件不存在: {video_path}")
            else:
                methods = [
                    (cv2.CAP_ANY, "自动检测"),
                    (cv2.CAP_FFMPEG, "FFMPEG"),
                    (cv2.CAP_DSHOW, "DirectShow")
                ]

                success = False
                best_method = None

                for method, name in methods:
                    try:
                        cap = cv2.VideoCapture(video_path, method)
                        if cap.isOpened():
                            ret, frame = cap.read()
                            if ret and frame is not None:
                                success = True
                                best_method = name
                                cap.release()
                                break
                        cap.release()
                    except:
                        pass

                if success:
                    issues_fixed.append(f"✓ 视频文件可以使用 {best_method} 解码器成功打开")
                else:
                    issues_fixed.append("✗ 无法成功读取视频帧，请尝试转换视频格式")
                    if messagebox.askyesno("转换格式", "是否需要了解如何转换视频格式？"):
                        conversion_msg = """
  推荐使用以下工具转换视频格式:
  1. VLC媒体播放器 - 可以转换为MP4(H.264)
  2. HandBrake - 开源视频转码软件
  3. FFmpeg - 命令行工具，最强大的转换工具

  建议转换为MP4格式，使用H.264编码，这是OpenCV最兼容的格式。
  """
                        messagebox.showinfo("视频格式转换建议", conversion_msg)

        if self.resize_enabled.get():
            if self.width.get() <= 0 or self.height.get() <= 0:
                issues_fixed.append("✗ 无效的输出图片尺寸")
                if self.video_info and "width" in self.video_info:
                    self.width.set(self.video_info["width"])
                    self.height.set(self.video_info["height"])
                    issues_fixed.append("✓ 已重置为视频原始尺寸")
                else:
                    self.resize_enabled.set(False)
                    issues_fixed.append("✓ 已禁用调整大小选项")

        try:
            test_dir = output_dir or os.path.expanduser("~")
            output_format = self.output_format.get()
            test_file = os.path.join(test_dir, f"cv2_imwrite_test.{output_format}")
            test_img = numpy.zeros((100, 100, 3), numpy.uint8)
            test_img[:] = (255, 255, 255)
            if cv2.imwrite(test_file, test_img):
                issues_fixed.append(f"✓ OpenCV图片写入测试通过 ({output_format}格式)")
                if os.path.exists(test_file):
                    os.remove(test_file)
            else:
                issues_fixed.append(f"✗ OpenCV无法写入{output_format}格式图片")
                test_formats = [f for f in ['jpg', 'png', 'bmp'] if f != output_format]
                for fmt in test_formats:
                    alt_file = os.path.join(test_dir, f"cv2_imwrite_test.{fmt}")
                    if cv2.imwrite(alt_file, test_img):
                        issues_fixed.append(f"✓ 但可以保存为{fmt}格式")
                        self.output_format.set(fmt)
                        issues_fixed.append(f"✓ 已自动切换到{fmt}格式")
                        if os.path.exists(alt_file):
                            os.remove(alt_file)
                        break
        except Exception as e:
            issues_fixed.append(f"✗ 图片写入测试失败: {str(e)}")

        result = "\n".join(issues_fixed)
        messagebox.showinfo("诊断结果", f"检查完成:\n\n{result}")


def main():
    root = tk.Tk()
    app = VideoSpriteSheetGenerator(root)

    # 检查必要的库
    try:
        import numpy
    except ImportError:
        print("错误：未安装numpy库。请运行：pip install numpy")
        messagebox.showerror("缺少依赖库", "未安装numpy库。请运行：pip install numpy")
        sys.exit(1)

    global PIL_AVAILABLE
    try:
        from PIL import Image
        PIL_AVAILABLE = True
        print("PIL库已成功导入，将用作图片保存和合成图生成")
    except ImportError:
        PIL_AVAILABLE = False
        print("警告：未安装PIL库。图片保存和合成图生成可能会失败，尝试安装PIL...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
            from PIL import Image
            PIL_AVAILABLE = True
            print("成功安装和导入PIL/Pillow库")
        except:
            print("无法自动安装PIL。如果图片保存或合成图生成失败，请手动运行: pip install pillow")


    root.mainloop()

if __name__ == "__main__":
    main()