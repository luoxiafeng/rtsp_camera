import tkinter as tk
from tkinter import messagebox, Menu
import cv2
import os
import time
from datetime import datetime
from threading import Thread
import json
import sqlite3
from ftplib import FTP

class CameraGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x800")
        self.root.title("摄像头管理系统")

        # 菜单栏设置
        menu_bar = Menu(self.root)
        settings_menu = Menu(menu_bar, tearoff=0)
        settings_menu.add_command(label="设置FTP", command=self.open_ftp_settings)
        menu_bar.add_cascade(label="设置", menu=settings_menu)
        self.root.config(menu=menu_bar)

        # 设置表头
        headers = ["编号", "设备名称", "IP地址", "时间间隔", "操作", "添加摄像头", "全部开始拍照", "全部暂停拍照"]
        for col, header in enumerate(headers):
            tk.Label(self.root, text=header).grid(row=0, column=col)

        # 加载FTP配置信息
        self.load_ftp_settings()

        # 数据库连接
        self.conn = sqlite3.connect("cameras.db")
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS cameras 
                               (id INTEGER PRIMARY KEY, name TEXT, ip TEXT, interval INTEGER)''')
        self.camera_states = {}  # 保存每个摄像头的状态
        self.last_capture_times = {}  # 保存每个摄像头上次拍照的时间戳

        # 加载摄像头数据
        self.load_cameras()

        # 添加摄像头按钮
        tk.Button(self.root, text="添加摄像头", command=self.add_camera).grid(row=1, column=5)

        # 全部开始拍照、全部暂停拍照按钮
        tk.Button(self.root, text="全部开始拍照", command=self.start_all_cameras).grid(row=1, column=6)
        tk.Button(self.root, text="全部暂停拍照", command=self.stop_all_cameras).grid(row=1, column=7)

        # 初始化线程状态
        self.running = False
        self.capture_thread = None
        self.ftp_connection = None  # 全局FTP连接

    def load_cameras(self):
        """从数据库加载摄像头数据"""
        self.cursor.execute("SELECT id, name, ip, interval FROM cameras")
        cameras = self.cursor.fetchall()
        for cam_id, name, ip, interval in cameras:
            self.add_camera_row(cam_id, name or "", ip or "", interval or 10)
            self.last_capture_times[cam_id] = 0  # 初始化上次拍照时间

    def add_camera_row(self, cam_id, name="", ip="", interval=10):
        """添加一行摄像头信息"""
        row = cam_id + 1
        self.camera_states[cam_id] = False  # 初始化为未拍照状态

        # 编号
        tk.Label(self.root, text=str(cam_id)).grid(row=row, column=0)

        # 设备名称
        name_entry = tk.Entry(self.root)
        name_entry.insert(0, name)
        name_entry.grid(row=row, column=1)

        # IP地址
        ip_entry = tk.Entry(self.root)
        ip_entry.insert(0, ip)
        ip_entry.grid(row=row, column=2)

        # 时间间隔
        interval_entry = tk.Entry(self.root)
        interval_entry.insert(0, str(interval))
        interval_entry.grid(row=row, column=3)

        # 操作按钮
        tk.Button(self.root, text="删除", command=lambda c=cam_id, r=row, n=name_entry, i=ip_entry, inter=interval_entry: self.delete_camera(c, n, i, inter)).grid(row=row, column=4)
        tk.Button(self.root, text="保存", command=lambda c=cam_id, n=name_entry, i=ip_entry, inter=interval_entry: 
                  self.save_camera(c, n.get(), i.get(), inter.get())).grid(row=row, column=5)

        # 开始和停止拍照按钮，互斥选择
        start_button = tk.Button(self.root, text="开始拍照", command=lambda c=cam_id: self.toggle_camera_state(c, start_button, stop_button))
        stop_button = tk.Button(self.root, text="停止拍照", command=lambda c=cam_id: self.toggle_camera_state(c, stop_button, start_button))
        start_button.grid(row=row, column=6)
        stop_button.grid(row=row, column=7)
        
        # 设置默认选中“停止拍照”按钮
        self.set_button_selected(stop_button, start_button)

    def add_camera(self):
        """添加新的摄像头行"""
        self.cursor.execute("INSERT INTO cameras (name, ip, interval) VALUES ('', '', 10)")
        self.conn.commit()
        cam_id = self.cursor.lastrowid
        self.add_camera_row(cam_id)
        self.last_capture_times[cam_id] = 0  # 初始化新的摄像头的上次拍照时间

    def delete_camera(self, cam_id, name_entry, ip_entry, interval_entry):
        """删除摄像头数据（编号保留，清空其他内容）"""
        # 清空数据库中该摄像头的数据
        self.cursor.execute("UPDATE cameras SET name='', ip='', interval=10 WHERE id=?", (cam_id,))
        self.conn.commit()

        # 清空 GUI 界面上的名称、IP 和时间间隔
        name_entry.delete(0, tk.END)
        ip_entry.delete(0, tk.END)
        interval_entry.delete(0, tk.END)
        interval_entry.insert(0, "10")  # 设置默认值为10

        messagebox.showinfo("删除成功", f"摄像头 {cam_id} 数据已清空，但保留编号")

    def save_camera(self, cam_id, name, ip, interval):
        """保存摄像头数据到数据库"""
        self.cursor.execute("UPDATE cameras SET name=?, ip=?, interval=? WHERE id=?", (name, ip, int(interval), cam_id))
        self.conn.commit()
        messagebox.showinfo("保存成功", f"摄像头 {cam_id} 数据已更新")

    def toggle_camera_state(self, cam_id, selected_button, other_button):
        """根据用户操作切换摄像头状态，互斥选择按钮"""
        if selected_button["text"] == "开始拍照":
            self.camera_states[cam_id] = True
        else:
            self.camera_states[cam_id] = False
        self.set_button_selected(selected_button, other_button)

    def set_button_selected(self, selected_button, other_button):
        """设置按钮的选中和非选中状态"""
        selected_button.config(bg="green", fg="white", relief=tk.SUNKEN)
        other_button.config(bg="SystemButtonFace", fg="black", relief=tk.RAISED)

    def start_all_cameras(self):
        """全部开始拍照"""
        for cam_id in self.camera_states:
            self.camera_states[cam_id] = True

        # 设置所有开始拍照按钮为选中状态
        for row in range(1, len(self.camera_states) + 2):  # 调整循环范围，确保处理所有按钮
            start_button = self.root.grid_slaves(row=row, column=6)
            stop_button = self.root.grid_slaves(row=row, column=7)
            if start_button and stop_button:
                self.set_button_selected(start_button[0], stop_button[0])

        # 如果线程未运行，启动新线程
        if not self.running:
            self.running = True
            self.capture_thread = Thread(target=self.capture_and_upload_images)
            self.capture_thread.start()

    def stop_all_cameras(self):
        """全部停止拍照"""
        for cam_id in self.camera_states:
            self.camera_states[cam_id] = False

        # 设置所有停止拍照按钮为选中状态
        for row in range(1, len(self.camera_states) + 2):  # 调整循环范围，确保处理所有按钮
            start_button = self.root.grid_slaves(row=row, column=6)
            stop_button = self.root.grid_slaves(row=row, column=7)
            if start_button and stop_button:
                self.set_button_selected(stop_button[0], start_button[0])

        # 停止后台拍照线程
        self.running = False

    def open_ftp_settings(self):
        """打开FTP设置窗口"""
        self.ftp_window = tk.Toplevel(self.root)
        self.ftp_window.title("FTP设置")
        self.ftp_window.geometry("300x200")

        tk.Label(self.ftp_window, text="FTP IP地址").pack()
        self.ftp_ip_entry = tk.Entry(self.ftp_window)
        self.ftp_ip_entry.insert(0, self.ftp_settings.get("ip", ""))
        self.ftp_ip_entry.pack()

        tk.Label(self.ftp_window, text="FTP 用户名").pack()
        self.ftp_user_entry = tk.Entry(self.ftp_window)
        self.ftp_user_entry.insert(0, self.ftp_settings.get("user", ""))
        self.ftp_user_entry.pack()

        tk.Label(self.ftp_window, text="FTP 密码").pack()
        self.ftp_pass_entry = tk.Entry(self.ftp_window, show="*")
        self.ftp_pass_entry.insert(0, self.ftp_settings.get("pass", ""))
        self.ftp_pass_entry.pack()

        tk.Button(self.ftp_window, text="保存", command=self.save_ftp_settings).pack()

    def save_ftp_settings(self):
        """保存FTP设置到文件"""
        self.ftp_settings = {
            "ip": self.ftp_ip_entry.get(),
            "user": self.ftp_user_entry.get(),
            "pass": self.ftp_pass_entry.get(),
        }
        with open("ftp.json", "w") as f:
            json.dump(self.ftp_settings, f)
        self.ftp_window.destroy()
        messagebox.showinfo("保存成功", "FTP配置信息已保存")

    def load_ftp_settings(self):
        """加载FTP设置"""
        try:
            with open("ftp.json", "r") as f:
                self.ftp_settings = json.load(f)
        except FileNotFoundError:
            self.ftp_settings = {}

    def capture_and_upload_images(self):
        """后台线程轮询各摄像头并拍照上传"""
        conn = sqlite3.connect("cameras.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, ip, interval FROM cameras")
        cameras = cursor.fetchall()
        conn.close()
        while self.running:
            for cam_id, ip, interval in cameras:
                if not ip or not self.camera_states.get(cam_id):
                    continue

                last_capture_time = self.last_capture_times.get(cam_id, 0)
                current_time = time.time()
                if current_time - last_capture_time >= interval:
                    cap = cv2.VideoCapture(f"rtsp://{ip}/11")
                    success, frame = cap.read()
                    if success:
                        now = datetime.now()
                        year, month, day = str(now.year), f"{now.month:02d}", f"{now.day:02d}"
                        local_folder = os.path.join(year, month, day)
                        if not os.path.exists(local_folder):
                            os.makedirs(local_folder)
                        filename = f"{cam_id}_{now.strftime('%H%M%S')}.jpeg"
                        file_path = os.path.join(local_folder, filename)
                        cv2.imwrite(file_path, frame)
                        self.upload_to_ftp(file_path, year, month, day, filename)
                        self.last_capture_times[cam_id] = current_time
                    cap.release()
            time.sleep(0.01)

    def upload_to_ftp(self, file_path, year, month, day, filename):
        """上传图片到FTP服务器，按日期创建文件夹"""
        try:
            ftp = FTP(self.ftp_settings["ip"])
            ftp.login(user=self.ftp_settings["user"], passwd=self.ftp_settings["pass"])

            # 创建年、月、日目录
            for folder in [year, month, day]:
                if folder not in ftp.nlst():
                    ftp.mkd(folder)
                ftp.cwd(folder)

            with open(file_path, "rb") as file:
                ftp.storbinary(f'STOR {filename}', file)

            ftp.quit()
            print(f"图片 {filename} 已上传至FTP服务器")
        except Exception as e:
            print(f"上传图片到FTP失败: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CameraGUI(root)
    root.mainloop()
