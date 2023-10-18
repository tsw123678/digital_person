# -*- coding = utf-8 -*-
# @Date: 2023/9/25
# @Time: 20:04
# @Author:tsw
# @File：sender.py
# @Software: PyCharm
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
import sys
import wave
import cv2
import pyaudio
import numpy as np
from PySide2.QtGui import QPixmap, QImage, QDesktopServices
from PySide2.QtWidgets import QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QProgressBar, QVBoxLayout, \
    QWidget, QMessageBox, QDialog
from PySide2.QtCore import QTimer, Qt, QObject, QThread, Signal, QUrl
from PySide2.QtUiTools import QUiLoader
from FunASR.ASR_class import run_auto_speech_recognition
import datetime
import time
import glob


# QImage转为NumPy数组
def qimage_to_ndarray(qimage):
    width, height = qimage.width(), qimage.height()
    buffer = qimage.bits()
    buffer.setsize(height * width * 4)
    arr = np.frombuffer(buffer, np.uint8).reshape((height, width, 4))
    return arr


# 音频线程 非蓝牙耳机channels视情况修改
class AudioThread(QThread):
    def __init__(self, parent=None):
        super(AudioThread, self).__init__(parent)
        self.audio_frames = []

    def run(self):
        self.audio_recording = pyaudio.PyAudio()
        self.audio_stream = self.audio_recording.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            frames_per_buffer=512
        )
        while True:
            if self.isInterruptionRequested():
                self.audio_stream.stop_stream()
                self.audio_stream.close()
                self.audio_recording.terminate()
                break
            audio_data = self.audio_stream.read(512)
            self.audio_frames.append(audio_data)


# 主窗口
class Main(QMainWindow):

    def __init__(self, ui_file, default_video_dir='./temp/final_output'):
        super().__init__()

        self.setWindowTitle("digital person : sender")

        loader = QUiLoader()
        self.ui = loader.load(ui_file)
        self.setCentralWidget(self.ui)

        # 3.打开摄像头录制 保存音频
        # 默认保存位置在 start_camera/stop_camera 内同时修改
        self.ui.start_button.clicked.connect(self.start_camera)
        self.ui.stop_button.clicked.connect(self.stop_camera)

        self.camera = cv2.VideoCapture(0)
        self.camera.set(3, 320)
        self.camera.set(4, 240)
        self.camera.set(5, 10)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        self.is_camera_running = False
        self.video_writer = None

        self.audio_thread = AudioThread()
        self.alert_shown = False

    def geneTXT(self):
        audio_folder = './temp/generateTXT/generateWAV/'

        audio_files = glob.glob(os.path.join(audio_folder, 'output_*.wav'))

        if not audio_files:
            print("没有找到音频文件")
            return

        audio_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        latest_audio_file = audio_files[0]

        genetxt = run_auto_speech_recognition(latest_audio_file)
        self.ui.plainTextEdit.setPlainText(genetxt)

        current_timestamp = datetime.datetime.now().strftime("_%Y%m%d%H%M%S")
        # 保存文本到发送端共享文件夹
        # file_path = f"./temp/generateTXT/txt/text{current_timestamp}.txt"
        file_path = f"./temp/generateTXT/txt/text{current_timestamp}.txt"

        with open(file_path, "w") as file:
            file.write(genetxt)

        print(f"已保存到文件 {file_path}")

        # 展示txt大小
        file_size_bytes = os.path.getsize(file_path)
        self.txt_size = file_size_bytes
        # 提示信息已发送
        self.ui.label_process.setText("语义提取已完成，大小为{}字节".format(file_size_bytes))

        time.sleep(5)

        # 监测语义编码、信道编码
        # 设置要监测的文件夹路径
        # self.monitor_folder = "\\\\192.168.137.19\\share"
        self.monitor_folder = "D:\project_test"
        self.target_files = {"语义编码.txt": self.handle_semantic, "信道编码.txt": self.handle_channel}
        self.detected_files = set()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_folder)
        self.timer.start(2000)

    def check_folder(self):
        for target_file, handler in self.target_files.items():
            if target_file in os.listdir(self.monitor_folder) and target_file not in self.detected_files:
                handler()
                self.detected_files.add(target_file)
                if len(self.detected_files) == len(self.target_files):
                    self.timer.stop()
                else:
                    self.detected_files.clear()

    def start_camera(self):
        empty = ''
        self.ui.plainTextEdit.setPlainText(empty)
        if not self.is_camera_running:
            self.is_camera_running = True
            self.ui.start_button.setText("Stop Camera")
            self.timer.start(1000 // 15)

            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter("./temp/generateTXT/generateAVI/output.avi", fourcc, 20.0, (640, 480))

            self.audio_thread.start()

        else:
            self.stop_camera()

    def stop_camera(self):
        if self.is_camera_running:
            self.is_camera_running = False
            self.ui.start_button.setText("Start Camera")
            self.timer.stop()

            self.video_writer.release()
            self.video_writer = None

            self.audio_thread.requestInterruption()
            self.audio_thread.wait()

            current_timestamp = datetime.datetime.now().strftime("_%Y%m%d%H%M%S")

            # 音频文件路径
            audio_file_path = f'./temp/generateTXT/generateWAV/output_{current_timestamp}.wav'

            if os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                except PermissionError:
                    print("文件被另一个程序占用，无法删除")

            time.sleep(1)
            with wave.open(audio_file_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b''.join(self.audio_thread.audio_frames))
                print("音频保存成功")

            # 计算初始视频大小 字节
            audio_file_size_bytes = os.path.getsize(audio_file_path)
            self.audio_size = int(audio_file_size_bytes)
            self.ui.video_size.setText("原音频大小为{}字节".format(audio_file_size_bytes))

            self.geneTXT()

    def handle_semantic(self):
        print("语义编码已完成，大小为aaa字节")
        self.ui.label_process.setText("语义编码已完成")
        full_path = os.path.join(self.monitor_folder, "语义编码.txt")
        os.remove(full_path)

    def handle_channel(self):
        print("信道编码已完成，大小为bbb字节")
        self.ui.label_process.setText("信道编码已完成，压缩率为{:.2f}%".format(100 * (32 / self.txt_size)))
        full_path = os.path.join(self.monitor_folder, "信道编码.txt")
        os.remove(full_path)

    def update_frame(self):
        ret, frame = self.camera.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

            label_width = self.ui.record_video.width()
            label_height = self.ui.record_video.height()
            scaled_image = convert_to_qt_format.scaled(label_width, label_height, Qt.KeepAspectRatio)
            self.ui.record_video.setPixmap(QPixmap.fromImage(scaled_image))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Main(r'D:\deeplearning\digitalperson2\UI\sender.ui')
    player.show()
    sys.exit(app.exec_())
