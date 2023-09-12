import socket

from mdevice.tools.log import LogUtils

logger = LogUtils.LOGGER_DEBUG


class HostToolKit:
    @staticmethod
    def ip():
        """
        查询本机ip地址
        :return:
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            _ip = s.getsockname()[0]
        except Exception as e:
            logger.debug(e)
            _ip = '0.0.0.0'
        finally:
            s.close()
        return _ip

    @staticmethod
    def name():
        """
        获取本机计算机名称
        :return:
        """
        name = socket.gethostname()
        if "local" in name:
            return name.split(".")[0]
        else:
            return name
