# -*- coding = utf-8 -*-
# @Date: 2023/9/25
# @Time: 20:04
# @Author:tsw
# @File：sender.py
# @Software: PyCharm
import sys
import wave
import cv2
import pyaudio
from PySide2.QtGui import QPixmap, QImage
from PySide2.QtWidgets import QApplication, QMainWindow, QVBoxLayout
from PySide2.QtCore import QTimer, Qt, QThread, QCoreApplication
from PySide2.QtUiTools import QUiLoader
from pydub import AudioSegment
from FunASR.ASR_class import run_auto_speech_recognition
import datetime
import time
import glob
import os

os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'


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

    def __init__(self, ui_file):
        super().__init__()

        self.setWindowTitle("Digital Person : Sender")

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

        self.ui.text.setWordWrap(True)

    def geneTXT(self):
        self.ui.label_process.setText("Semantic extraction is in progress!")
        QCoreApplication.processEvents()

        audio_folder = './temp/generateTXT/generateWAV/'
        audio_files = glob.glob(os.path.join(audio_folder, 'output_*.wav'))

        if not audio_files:
            print("没有找到音频文件")
            return

        audio_files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        latest_audio_file = audio_files[0]

        # 语义提取时长
        start_time = time.time()
        genetxt = run_auto_speech_recognition(latest_audio_file)
        end_time = time.time()
        self.sc_extraction_time = "{:.2f}".format(end_time - start_time)

        self.ui.text.setText(genetxt)

        current_timestamp = datetime.datetime.now().strftime("_%Y%m%d%H%M%S")
        # 保存文本到发送端共享文件夹
        # file_path = f"./temp/generateTXT/txt/text{current_timestamp}.txt"
        file_path = f"./temp/generateTXT/txt/text{current_timestamp}.txt"

        with open(file_path, "w") as file:
            file.write(genetxt)

        print(f"已保存到文件 {file_path}")

        file_size_bytes = os.path.getsize(file_path)
        self.txt_size = file_size_bytes
        self.ui.label_process.setText("Semantic extraction is completed.")

        time.sleep(2)

        # 监测语义编码、信道编码
        # 设置要监测的文件夹路径
        # self.monitor_folder = "\\\\192.168.137.19\\share"
        self.monitor_folder = "D:\project_test"
        self.target_files = {"语义编码.txt": self.handle_semantic, "信道编码.txt": self.handle_channel}
        self.detected_files = set()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_folder)
        self.timer.start(2000)

    def load_img(self):
        image_path = './temp/img/tsw.png'
        pixmap = QPixmap(image_path)

        label_width = self.ui.img.width()
        label_height = self.ui.img.height()

        pixmap = pixmap.scaledToWidth(label_width)
        pixmap = pixmap.scaledToHeight(label_height)

        self.ui.img.setPixmap(pixmap)

    def load_img_voice(self):
        image_path = './temp/img/voice.png'
        pixmap = QPixmap(image_path)

        label_width = self.ui.voice.width()
        label_height = self.ui.voice.height()

        pixmap = pixmap.scaledToWidth(label_width)
        pixmap = pixmap.scaledToHeight(label_height)

        self.ui.voice.setPixmap(pixmap)

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
        self.ui.text.setText(empty)
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

        # 人脸图片
        self.load_img()
        QCoreApplication.processEvents()

        # 音色图片
        self.load_img_voice()
        QCoreApplication.processEvents()

        # 计算初始音频大小 字节
        audio_file_size_bytes = os.path.getsize(audio_file_path)
        self.audio_size = int(audio_file_size_bytes)
        self.geneTXT()
        QCoreApplication.processEvents()

        # 显示information
        # 视频时长
        audio = AudioSegment.from_file(audio_file_path)
        audio_time = len(audio) / 1000  # 将毫秒转换为秒
        self.audio_time = "{:.2f}".format(audio_time)
        # 语义提取：self.sc_extraction_time
        # 音频大小：self.audio_size
        # 文本大小：self.txt_size
        # 编码后大小：32

    def handle_semantic(self):
        print("语义编码已完成，大小为aaa字节")
        self.ui.label_process.setText("Semantic encode is completed.")
        full_path = os.path.join(self.monitor_folder, "语义编码.txt")
        os.remove(full_path)

    def handle_channel(self):
        print("信道编码已完成，大小为bbb字节")
        self.ui.label_process.setText("Channel encode is completed.")
        full_path = os.path.join(self.monitor_folder, "信道编码.txt")
        os.remove(full_path)

        text = f"Duration\n\nCapture Video:{self.audio_time}s\n\nSemantic Extraction:{self.sc_extraction_time}s\n\nEncoding:3.26s"
        self.ui.content.setText(text)
        text2 = f"Data Size\n\nAudio:{self.audio_size}bytes\n\nContent:{self.txt_size}bytes\n\nChannel Encoding:32bytes"
        self.ui.content_2.setText(text2)

    def update_frame(self):
        ret, frame = self.camera.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            convert_to_qt_format = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)

            label_width = self.ui.record_video.width()
            label_height = self.ui.record_video.height()

            scaled_image = convert_to_qt_format.scaled(label_width, label_height, Qt.IgnoreAspectRatio)
            self.ui.record_video.setPixmap(QPixmap.fromImage(scaled_image))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Main(r'D:\deeplearning\digitalperson2\UI\sender.ui')
    player.resize(1178, 803)
    player.show()
    sys.exit(app.exec_())
