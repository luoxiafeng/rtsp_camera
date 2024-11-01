import cv2
import time
import os
from datetime import datetime
from ftplib import FTP

def capture_and_upload(video_url, interval=10, ftp_ip='43.136.93.100', ftp_user='test', ftp_pass='LiZdxBNTpajPFp6d'):
    # 初始化视频捕获
    cap = cv2.VideoCapture(video_url)
    
    if not cap.isOpened():
        print("Error: Cannot open video stream")
        return

    while True:
        success, frame = cap.read()
        if not success:
            print("Error: Failed to capture frame")
            break
        
        # 获取当前时间作为文件名（精确到秒）
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + '.jpeg'
        
        # 保存图像为JPEG格式
        cv2.imwrite(filename, frame)
        
        # 上传图像到FTP服务器
        upload_to_ftp(filename, ftp_ip, ftp_user, ftp_pass)
        
        # 删除本地保存的图片文件
        #os.remove(filename)

        # 等待指定的时间间隔
        time.sleep(interval)
    
    cap.release()

def upload_to_ftp(filename, ftp_ip, ftp_user, ftp_pass):
    try:
        # 连接到FTP服务器
        with FTP(ftp_ip) as ftp:
            ftp.login(user=ftp_user, passwd=ftp_pass)
            with open(filename, 'rb') as file:
                # 上传文件到FTP服务器
                ftp.storbinary(f'STOR {filename}', file)
        print(f"Uploaded {filename} to FTP server")
    except Exception as e:
        print(f"Failed to upload {filename} to FTP: {e}")

if __name__ == "__main__":
    # 设置RTSP地址和间隔时间（秒）
    rtsp_url = "rtsp://192.168.1.69/11"  # 替换为实际的RTSP地址
    capture_interval = 10  # 自定义间隔时间，单位为秒
    
    # 调用捕获和上传函数
    capture_and_upload(rtsp_url, interval=capture_interval)