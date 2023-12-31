# -*- coding: utf-8 -*-

import os
import re
import time
import zipfile

BaseDir = os.path.dirname(os.path.abspath(__file__))


class TimeUtils(object):
    UnderLineFormatter = "%Y_%m_%d_%H_%M_%S"
    NormalFormatter = "%Y-%m-%d %H-%M-%S"
    ColonFormatter = "%Y-%m-%d %H:%M:%S"

    # 文件路径要用这个，mac有空格，很麻烦
    @staticmethod
    def getCurrentTimeUnderline():
        return time.strftime(TimeUtils.UnderLineFormatter, time.localtime(time.time()))

    @staticmethod
    def getCurrentTime():
        return time.strftime(TimeUtils.NormalFormatter, time.localtime(time.time()))

    @staticmethod
    def formatTimeStamp(timestamp):
        return time.strftime(TimeUtils.NormalFormatter, time.localtime(timestamp))

    @staticmethod
    def getTimeStamp(time_str, format):
        timeArray = time.strptime(time_str, format)
        # 转换成时间戳
        return time.mktime(timeArray)

    @staticmethod
    def is_between_times(timestamp, begin_timestamp, end_timestamp):
        if begin_timestamp < timestamp and timestamp < end_timestamp:
            return True
        else:
            return False

    @staticmethod
    def get_interval(begin_timestamp, end_timestamp):
        '''
        :param begin_timestamp:
        :param end_timestamp:
        :return:求起止时间戳之间的时间间隔 ，返回H,浮点数
        '''
        interval = end_timestamp - begin_timestamp
        return round(float(interval) / (60 * 60))


class FileUtils(object):

    @staticmethod
    def makedir(dir):
        if not os.path.exists(dir):
            os.makedirs(dir)

    @staticmethod
    def get_top_dir():
        dir = os.path.dirname(BaseDir)
        path = os.path.dirname(dir)
        print("path:%s" % path)
        return path

    @staticmethod
    def get_files(path=None, pattern=None):
        """
        :param path: 目录
        :param pattern: 正则
        :return: 递归遍历目录，返回匹配的文件路径
        """
        file_list = []
        if path is None or not os.path.exists(path):  # 没有路径返回空
            return file_list
        for oneFile in os.listdir(path):
            if os.path.isfile(os.path.join(path, oneFile)):
                match = False
                if pattern:
                    match = re.match(pattern, oneFile, flags=0)
                if match:
                    file_list.append(os.path.join(path, oneFile))  # 是文件 且匹配正则成功 则添加文件
            elif os.path.isdir(os.path.join(path, oneFile)):
                file_list.extend(FileUtils.get_files(os.path.join(path, oneFile), pattern))  # 是文件夹 遍历下一级目录下 符合正则的文件 并追加
        return file_list

    @staticmethod
    def get_FileSize(filePath):
        """
        获取文件的大小,结果保留4位小数，单位为MB
        :param filePath:
        :return:
        """
        fsize = os.path.getsize(filePath)
        fsize = fsize / float(1024 * 1024)
        return round(fsize, 4)

    @staticmethod
    def get_FileAccessTime(filePath):
        """获取文件的访问时间"""
        t = os.path.getatime(filePath)
        return t

    @staticmethod
    def get_FileCreateTime(filePath):
        """获取文件的创建时间"""
        t = os.path.getctime(filePath)
        return t

    @staticmethod
    def get_FileModifyTime(filePath):
        """获取文件的修改时间"""
        t = os.path.getmtime(filePath)
        return t


class ZipUtils(object):

    @staticmethod
    def zip_dir(dirname, zipfilename):
        """
        压缩文件
        :param dirname: 带压缩文件路径 或 文件地址
        :param zipfilename: 压缩文件名
        :return:
        """
        filelist = []
        if os.path.isfile(dirname):
            filelist.append(dirname)
        else:
            for root, dirs, files in os.walk(dirname):
                for name in files:
                    filelist.append(os.path.join(root, name))

        with zipfile.ZipFile(zipfilename, "w", zipfile.zlib.DEFLATED) as zf:
            for tar in filelist:
                arcname = tar[len(dirname):]
                zf.write(tar, arcname)

    @staticmethod
    def zip_unpack(zipfilename, dirname):
        """
        解压文件
        :param zipfilename: 压缩文件名
        :param dirname: 解压文件目录
        :return:
        """
        if not os.path.exists(dirname):
            FileUtils.makedir(dirname)

        # 解压文件到指定目录（默认当前目录）
        with zipfile.ZipFile(zipfilename) as zf:
            # 等同 ZipFile.extractall()
            for file in zf.namelist():
                zf.extract(file, dirname)
