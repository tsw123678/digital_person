# -*- coding = utf-8 -*-
# @Date: 2023/9/25
# @Time: 21:51
# @Author:tsw
# @File：receiver.py
# @Software: PyCharm
# -*- coding: utf-8 -*-
# @Date: 2023/9/20
# @Time: 10:09
# @Author: tsw
# @File: main_show.py
# @Software: PyCharm
import glob
import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
from PySide2.QtGui import QPixmap, QImage, QDesktopServices
from PySide2.QtMultimedia import QMediaContent, QMediaPlayer
from PySide2.QtWidgets import QApplication, QMainWindow, QPushButton, QFileDialog, QLabel, QProgressBar, QVBoxLayout, \
    QWidget, QMessageBox, QHBoxLayout, QSizePolicy, QDialog
from PySide2.QtCore import QTimer, Qt, QObject, QThread, Signal, QUrl, Slot
from PySide2.QtUiTools import QUiLoader
from VALL.make_Audio_class import generate_and_save_audio
import time
from OpenGL.GLUT import *
from PySide2.QtMultimediaWidgets import QVideoWidget
from utils.toAVI import convert_mp4_to_avi


def getpath():
    source_dir = './temp/final_output'
    target_dir = './temp/final_output'
    convert_mp4_to_avi(source_dir, target_dir, delete_original=True)

    # 目标目录路径
    global latest_file_path
    directory_path = './temp/final_output'
    # 获取目录中所有文件
    files = os.listdir(directory_path)
    # 过滤出时间戳文件
    timestamped_files = [file for file in files if '_' in file and '.' in file]
    # 如果没有符合条件的文件，这里处理异常情况
    if not timestamped_files:
        print("没有找到符合条件的文件")
    else:
        # 根据文件名中的时间戳来排序文件
        sorted_files = sorted(timestamped_files, key=lambda x: os.path.getmtime(os.path.join(directory_path, x)),
                              reverse=True)
        # 获取最新的文件名
        latest_file_name = sorted_files[0]
        # 获取最新文件的完整相对路径
        latest_file_path = os.path.join(directory_path, latest_file_name)
        latest_file_path = latest_file_path.replace("\\", "/")
        # print("最新的文件是:", latest_file_name)
        print("最新文件的完整相对路径是:", latest_file_path)

    return latest_file_path


# 主窗口
class Main(QMainWindow):

    def __init__(self, ui_file, default_video_dir='./temp/final_output'):
        super().__init__()

        self.setWindowTitle("digital person : receiver")

        loader = QUiLoader()
        self.ui = loader.load(ui_file)
        self.setCentralWidget(self.ui)

        # 2.选择图片
        # 默认打开位置在 open_image 内修改
        #self.ui.select_image_button.clicked.connect(self.open_image)

        # 5.文本转音频
        # 默认保存位置在 geneAudio/playAudio 内修改
        self.ui.generateAudio.clicked.connect(self.geneAudio)

        # 播放音频
        self.media_player = QMediaPlayer()
        self.ui.play_pause_button_2.clicked.connect(self.playAudio)

        # 6.合成视频
        # 默认播放地址在 make_final_video 内修改
        self.ui.makevideo.clicked.connect(self.make_final_video)

        # 7.播放
        self.ui.play_video.clicked.connect(self.playVideo)
        self.openGLWidget = self.ui.openGLWidget

        layout = QVBoxLayout()
        self.vw = QVideoWidget()
        layout.addWidget(self.vw)
        self.openGLWidget.setLayout(layout)

        layout.addWidget(self.vw, 1)  # 添加伸展因子
        self.vw.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.player = None

    def playVideo(self):
        try:
            self.player = QMediaPlayer()
            self.player.setVideoOutput(self.vw)  # 视频部件
            video_file_path = getpath()
            # video_file_path='./temp/test/test.avi'
            media_content = QMediaContent(QUrl.fromLocalFile(video_file_path))
            self.player.setMedia(media_content)

            self.player.play()  # 播放视频
            self.vw.show()
        except Exception as e:
            print("发生错误：", str(e))

    def make_final_video(self):
        # 指定音频文件所在的目录
        audio_directory = './temp/generateAudio'
        pattern = os.path.join(audio_directory, 'regeneAudio_*.wav')
        audio_files = glob.glob(pattern)
        audio_files.sort(key=os.path.getmtime, reverse=True)

        # 检查是否有找到音频文件
        if audio_files:
            # 获取最新的音频文件路径（相对路径）
            latest_audio_relative_path = audio_files[0]

            # 打印最新文件的相对路径
            print("最新音频文件的相对路径:", latest_audio_relative_path)
        else:
            print("未找到音频文件")

        # 图片路径
        image = './temp/img/person.png'
        # 保存路径
        dir = './temp/final_output'

        os.system(
            "python ./SadTalker/inference.py --driven_audio %s --source_image %s --enhancer gfpgan --result_dir %s --size 256 --preprocess crop" % (
                latest_audio_relative_path, image, dir))
        #self.ui.video_tip.setText("已成功合成 点击按钮查看")

        # 展示语义解码已完成
        dialog = QDialog()
        dialog.resize(400, 200)

        layout = QVBoxLayout()
        label = QLabel("语义解码已完成，点击按钮可查看视频")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        dialog.setLayout(layout)
        dialog.exec_()

    def playAudio(self):
        audio_directory = './temp/generateAudio'

        # 获取目录中的所有音频文件
        audio_files = [file for file in os.listdir(audio_directory) if file.startswith('regeneAudio_')]

        if not audio_files:
            print("No audio files found.")
            return

        # 从文件名中提取时间戳并排序文件列表
        audio_files.sort(key=lambda x: os.path.getmtime(os.path.join(audio_directory, x)), reverse=True)

        # 选择最新的音频文件进行播放
        latest_audio_file = audio_files[0]
        latest_audio_path = os.path.join(audio_directory, latest_audio_file)

        media_content = QMediaContent(QUrl.fromLocalFile(latest_audio_path))
        self.media_player.setMedia(media_content)
        self.media_player.play()

    def geneAudio(self):
        # directory_path = "\\\\192.168.137.19\\share\\rec"
        # txt_files = os.listdir(directory_path)
        #
        # # 从文件名中提取时间戳并找到最新的txt文件
        # latest_txt_file = None
        # latest_timestamp = 0
        #
        # txt_files = [f for f in os.listdir(directory_path) if f.endswith('_output.txt')]
        # txt_files.sort(key=lambda x: os.path.getmtime(os.path.join(directory_path, x)), reverse=True)
        # newest_txt_file = txt_files[0]
        #
        # latest_txt_file=os.path.join(directory_path, newest_txt_file)


        # test
        latest_txt_file='./temp/generateTXT/txt/text_20231013120736.txt'

        if latest_txt_file:
            with open(latest_txt_file, "r", encoding="gbk") as file:
                content = file.read()

            # 生成时间戳
            timestamp = time.strftime("%Y%m%d%H%M%S")

            # 生成音频文件名，添加时间戳
            audio_filename = f'./temp/generateAudio/regeneAudio_{timestamp}.wav'

            generate_and_save_audio(content, audio_filename)
            self.ui.label_3.setText("已成功生成，请点击播放")
        else:
            self.ui.label_3.setText("没有找到符合格式的txt文件")

    # def open_image(self):
    #     options = QFileDialog.Options()
    #     image_path, _ = QFileDialog.getOpenFileName(self, "选择图片文件",
    #                                                 "./temp/img",
    #                                                 "图像文件 (*.jpg *.jpeg *.png *.bmp *.gif);;所有文件 (*)",
    #                                                 options=options)
    #
    #     if image_path:
    #         pixmap = QPixmap(image_path)
    #         self.ui.image_label.setPixmap(pixmap)
    #         self.ui.image_label.setScaledContents(True)
    #         self.ui.image_path_label.setText(f"图片路径：{image_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = Main("./UI/receiver.ui")
    player.show()
    sys.exit(app.exec_())
