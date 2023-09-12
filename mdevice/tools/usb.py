import fcntl
import logging
import os
import re
import time

# # Equivalent of the _IO('U', 20) constant in the linux kernel.
_USB_RESET = ord('U') << 8 | 20


class USBHelper:

    def __init__(self, sn: str, logger=None):
        self.sn = sn
        self.logger = logger if logger else self._get_logger()

    def _get_logger(self):
        logger = logging.getLogger('[USB:%s]' % self.sn)
        if not logger.handlers:
            formatter = logging.Formatter(
                '%(asctime)s-%(filename)s- %(levelname)s\t #%(name)s:%(message)s')
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
            logger.setLevel(logging.INFO)
        return logger

    def _get_usb_address(self):
        """
        获取指定设备的USB总线bus地址
        eg: Bus 001 Device 002: ID 12d1:107e Huawei Technologies Co., Ltd. ANE-AL00  Serial: 8GP7N18609012954

        :return:
        """
        txt = os.popen(f'lsusb -v| grep {self.sn} -B 15|grep Bus').read()
        bus = re.compile(r'^Bus (\d{3}) Device (\d{3}):')
        m = bus.match(txt)
        if m:
            devices = {'bus': m.group(1), 'address': m.group(2)}
            self.logger.debug(devices)
            return devices['bus'], devices['address']
        else:
            self.logger.error('not found devices')
            return None, None

    def reset_usb(self):
        """
        USB重置
        https://gist.github.com/PaulFurtado/fce98aef890469f34d51

        :return:
        """
        try:
            bus, address = self._get_usb_address()
            if bus and address:
                # /dev/bus/usb/<busnum>/<devnum>
                usb_file_path = '/dev/bus/usb/{0}/{1}'.format(bus, address)
                with open(usb_file_path, 'w') as usb_file:
                    self.logger.debug(usb_file_path)
                    # 向设备发送控制命令
                    fcntl.ioctl(usb_file, _USB_RESET, 0)
                time.sleep(5)
        except Exception as e:
            self.logger.error(e)
