import tkinter as tk
from tkinter import messagebox
import cv2
import os
import time
from datetime import datetime
from threading import Thread
import sqlite3

class CameraGUI:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x800")
        self.root.title("摄像头管理系统")

        # 设置表头
        headers = ["编号", "设备名称", "IP地址", "时间间隔", "操作", "添加摄像头", "全部开始拍照", "全部暂停拍照"]
        for col, header in enumerate(headers):
            tk.Label(self.root, text=header).grid(row=0, column=col)

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

        # 启动后台循环线程
        self.running = True
        self.capture_thread = Thread(target=self.capture_and_upload_images)
        self.capture_thread.start()

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
        tk.Button(self.root, text="开始拍照", command=lambda c=cam_id: self.start_camera(c)).grid(row=row, column=6)
        tk.Button(self.root, text="停止拍照", command=lambda c=cam_id: self.stop_camera(c)).grid(row=row, column=7)

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

    def start_camera(self, cam_id):
        """开始从摄像头拍照"""
        self.camera_states[cam_id] = True

    def stop_camera(self, cam_id):
        """停止从摄像头拍照"""
        self.camera_states[cam_id] = False

    def start_all_cameras(self):
        """全部开始拍照"""
        for cam_id in self.camera_states:
            self.camera_states[cam_id] = True

    def stop_all_cameras(self):
        """全部停止拍照"""
        for cam_id in self.camera_states:
            self.camera_states[cam_id] = False

    def capture_and_upload_images(self):
        """后台拍照和上传线程"""
        while self.running:
            conn = sqlite3.connect("cameras.db")  # 线程内创建新的数据库连接
            cursor = conn.cursor()
            cursor.execute("SELECT id, ip, interval FROM cameras")
            cameras = cursor.fetchall()

            for cam_id, ip, interval in cameras:
                if not ip:  # 如果 IP 地址为空，跳过此摄像头
                    continue

                if self.camera_states.get(cam_id, False):  # 只有在开始拍照状态下才进行拍照
                    current_time = time.time()
                    last_capture_time = self.last_capture_times.get(cam_id, 0)

                    # 检查是否超过时间间隔
                    if current_time - last_capture_time >= interval:
                        rtsp_url = f"rtsp://{ip}/11"
                        cap = cv2.VideoCapture(rtsp_url)

                        if not cap.isOpened():
                            print(f"Error: Cannot open video stream for camera {cam_id}")
                            continue

                        success, frame = cap.read()
                        if success:
                            now = datetime.now()
                            year_folder = str(now.year)
                            month_folder = f"{now.month:02d}"
                            day_folder = f"{now.day:02d}"

                            # 创建目录
                            local_day_folder = os.path.join(year_folder, month_folder, day_folder)
                            if not os.path.exists(local_day_folder):
                                os.makedirs(local_day_folder)

                            # 保存图像
                            timestamp = now.strftime("%Y%m%d_%H%M%S")
                            filename = f"{cam_id}_{timestamp}.jpeg"
                            file_path = os.path.join(local_day_folder, filename)
                            cv2.imwrite(file_path, frame)
                            print(f"Saved image {filename} for camera {cam_id}")

                        cap.release()
                        self.last_capture_times[cam_id] = current_time  # 更新拍照时间

            conn.close()  # 关闭数据库连接
            time.sleep(1)  # 等待 1 秒后再检查

if __name__ == "__main__":
    root = tk.Tk()
    app = CameraGUI(root)
    root.mainloop()
