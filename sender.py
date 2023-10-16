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
import pygame
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


# 音频线程
# 非蓝牙耳机channels视情况修改
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


class Main(QMainWindow):

    def __init__(self, ui_file, default_video_dir='./temp/final_output'):
        super().__init__()

        self.setWindowTitle("digital person : sender")

        loader = QUiLoader()
        self.ui = loader.load(ui_file)
        self.setCentralWidget(self.ui)

        # 1.本地音频
        # 默认打开位置在 open_audio 内修改
        # 请将文件重命名为最新的 output_时间戳 14位.wav 便于后续使用
        self.ui.openAudio_button.clicked.connect(self.open_audio)
        self.ui.play_pause_button.clicked.connect(self.play_pause_audio)

        self.mp3_file = ""
        self.audio_playing = False

        # 3.打开摄像头录制 保存音频
        # 默认保存位置在 start_camera/stop_camera 内同时修改
        self.ui.start_button.clicked.connect(self.start_camera)
        self.ui.stop_button.clicked.connect(self.stop_camera)

        # 初始化摄像头
        self.camera = cv2.VideoCapture(0)
        self.camera.set(3, 320)  # 设置宽度
        self.camera.set(4, 240)  # 设置高度
        self.camera.set(5, 10)  # 设置帧率

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        self.is_camera_running = False
        self.video_writer = None

        # 创建音频处理线程
        self.audio_thread = AudioThread()

        # 4.音频转文本
        # 默认读取生成/本地音频位置以及生成txt文件位置在 geneTXT 内修改
        self.ui.generateTXT.clicked.connect(self.geneTXT)

        self.alert_shown = False

    def check_folder(self):
        if not self.alert_shown and self.target_file_name in os.listdir(self.monitor_folder):
            QMessageBox.information(self, 'OK', '信道编码已完成，大小为33445字节！')
            full_path = os.path.join(self.monitor_folder, self.target_file_name)
            os.remove(full_path)
            self.alert_shown = True

    def geneTXT(self):
        audio_folder = './temp/generateTXT/generateWAV/'

        # 获取音频文件夹内所有音频文件的列表
        audio_files = glob.glob(os.path.join(audio_folder, 'output_*.wav'))

        # 检查是否有音频文件
        if not audio_files:
            print("没有找到音频文件")
            return

        # 根据时间戳排序，选择最新的音频文件
        audio_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        latest_audio_file = audio_files[0]

        genetxt = run_auto_speech_recognition(latest_audio_file)
        self.ui.plainTextEdit.setPlainText(genetxt)

        # 使用当前时间戳作为后缀添加到文件名
        current_timestamp = datetime.datetime.now().strftime("_%Y%m%d%H%M%S")
        # 保存到发送端共享文件夹
        # ...
        file_path = f"./temp/generateTXT/txt/text{current_timestamp}.txt"

        with open(file_path, "w") as file:
            file.write(genetxt)

        print(f"已保存到文件 {file_path}")

        # 获取文件大小（以bit为单位）
        file_size_bytes = os.path.getsize(file_path)

        # 展示语义编码已完成 并展示大小
        dialog = QDialog()
        dialog.resize(400, 200)

        layout = QVBoxLayout()
        label = QLabel("语义编码已完成，编码后大小为{}字节".format(file_size_bytes))
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        dialog.setLayout(layout)
        dialog.exec_()

        time.sleep(10)

        # 监测信道编码
        self.monitor_folder = "\\\\192.168.137.19\\share"  # 设置要监测的文件夹路径
        # self.monitor_folder = "D:\project_test"  # 设置要监测的文件夹路径
        self.target_file_name = "信道编码.txt"  # 设置目标文件名

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_folder)
        self.timer.start(2000)  # 设置定时器

    def start_camera(self):
        empty = ''
        self.ui.plainTextEdit.setPlainText(empty)
        if not self.is_camera_running:
            self.is_camera_running = True
            self.ui.start_button.setText("Stop Camera")
            self.timer.start(1000 // 15)

            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter("./temp/generateTXT/generateAVI/output.avi", fourcc, 20.0, (640, 480))

            # 启动音频处理线程
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

            # 获取当前时间戳
            current_timestamp = datetime.datetime.now().strftime("_%Y%m%d%H%M%S")

            # 音频文件路径
            audio_file_path = f'./temp/generateTXT/generateWAV/output_{current_timestamp}.wav'

            # 检查是否已存在音频文件，如果存在则删除它
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

            # 计算初始视频大小
            video_path = './temp/generateTXT/generateAVI/output.avi'
            video_file_size_bytes = os.path.getsize(video_path)
            audio_file_size_bytes = os.path.getsize(audio_file_path)
            # video_file_size_bits = video_file_size_bytes * 8
            # audio_file_size_bits = audio_file_size_bytes * 8

            self.ui.label_3.setText("原视频大小为{}字节".format(video_file_size_bytes + audio_file_size_bytes))

    def update_frame(self):
        ret, frame = self.camera.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # 获取Label的大小
            label_width = self.ui.label_2.width()
            label_height = self.ui.label_2.height()
            # 按比例缩放视频帧以适应Label的大小
            scaled_image = convert_to_qt_format.scaled(label_width, label_height, Qt.KeepAspectRatio)
            # 设置Label的Pixmap
            self.ui.label_2.setPixmap(QPixmap.fromImage(scaled_image))

    def closeEvent(self, event):
        self.stop_camera()

    def open_audio(self):
        audio = QFileDialog().getOpenFileName(self, '选择音频文件',
                                              './temp/generateTXT/generateWAV',
                                              '*.wav')

        audio_path = audio[0]
        self.mp3_file = audio_path

        if self.mp3_file:
            pygame.mixer.init()
            pygame.mixer.music.load(self.mp3_file)

            self.ui.play_pause_button.setEnabled(True)

    def play_pause_audio(self):
        if not self.audio_playing:
            pygame.mixer.music.play()

            self.ui.play_pause_button.setText("暂停音频")
            self.audio_playing = True
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
                self.ui.play_pause_button.setText("继续播放")
            else:
                pygame.mixer.music.unpause()
                self.ui.play_pause_button.setText("暂停音频")

    def open_image(self):
        options = QFileDialog.Options()
        image_path, _ = QFileDialog.getOpenFileName(self, "选择图片文件",
                                                    "./temp/img",
                                                    "图像文件 (*.jpg *.jpeg *.png *.bmp *.gif);;所有文件 (*)",
                                                    options=options)

        if image_path:
            pixmap = QPixmap(image_path)
            self.ui.image_label.setPixmap(pixmap)
            self.ui.image_label.setScaledContents(True)
            self.ui.image_path_label.setText(f"图片路径：{image_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Main(r'D:\deeplearning\digitalperson2\UI\sender.ui')
    player.show()
    sys.exit(app.exec_())
