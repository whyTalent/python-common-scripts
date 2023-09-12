import os
import platform
import re
import signal
import subprocess

import requests

from mdevice import app_path
from mdevice.tools.log import LogUtils

logger = LogUtils.LOGGER_DEBUG


class CmdKit:

    @staticmethod
    def run_sysCmd(cmd, timeout=60):
        """
        执行命令cmd，返回命令输出的内容
        注：subprocess 模块的 Popen 调用外部程序，如果 stdout 或 stderr 参数是 pipe，
        并且程序输出超过操作系统的 pipe size时，如果使用 Popen.wait() 方式等待程序结束获取返回值，
        会导致死锁，程序卡在 wait() 调用上，因此使用 Popen.communicate() 来等待外部程序执行结束

        :param cmd: 执行的命令
        :param timeout: 最长等待时间，单位：秒
        :return:
        """
        p = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True, close_fds=True,
                             start_new_session=True)
        encoding_format = 'utf-8'
        if platform.system() == "Windows":
            encoding_format = 'gbk'
        try:
            (msg, errs) = p.communicate(timeout=timeout)
            ret_code = p.poll()
            if ret_code:
                msg = "[Error]Called Error ： " + str(msg.decode(encoding_format)) + "命令为：" + cmd
                logger.debug(msg)
            else:
                msg = str(msg.decode(encoding_format))
        except subprocess.TimeoutExpired:
            # 注意：不能只使用p.kill和p.terminate，无法杀干净所有的子进程，需要使用os.killpg
            p.kill()
            p.terminate()
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except Exception as e:
                logger.debug(e)
            # 注意：如果开启下面这两行的话，会等到执行完成才报超时错误，但是可以输出执行结果
            # (outs, errs) = p.communicate()
            # print(outs.decode('utf-8'))
            msg = "[ERROR]Timeout Error : Command '" + cmd + "' timed out after " + str(timeout) + " seconds"
            logger.debug(msg)
        except Exception as e:
            msg = "[ERROR]Unknown Error : " + str(e) + "命令为：" + cmd
            logger.debug(msg)
        return msg

    @staticmethod
    def run_sys_cmd_async(cmd):
        subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True, close_fds=True,
                         start_new_session=True)

    @staticmethod
    def download(file_or_url):
        """
        根据提供的url链接下载资源

        :param file_or_url: 资源文件链接
        :return:
        """
        for _ in range(3):
            try:
                is_url = bool(re.match(r"^https?://", file_or_url))
                if is_url:
                    url = file_or_url
                    filepath = os.path.join(app_path(), url.split("/")[-1])
                    LogUtils.LOGGER_DEBUG.debug("Download to tmp path: {0}".format(filepath))
                    with requests.get(url, stream=True) as r:
                        r.raise_for_status()
                        with open(filepath, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=1024 * 32):
                                f.write(chunk)
                elif os.path.isfile(file_or_url):
                    filepath = file_or_url
                else:
                    raise RuntimeError(
                        "Local path {} not exist".format(file_or_url))
                return filepath
            except Exception as e:
                logger.debug("DownloadError")
                logger.debug(e)


