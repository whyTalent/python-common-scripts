import json
import platform
import re
import shutil
import time
import typing
import zipfile
from queue import Queue
from typing import Union

import tidevice
from biplist import readPlistFromString

from mdevice.model import AppInfo, DeviceInfo
from mdevice.tools.cmdkit import CmdKit
from mdevice.tools.log import LogUtils
from mdevice.tools.timer import time_cost

logger = LogUtils.LOGGER_DEBUG

# https://gist.githubusercontent.com/adamawolf/3048717/raw/4407bc61de88444a232f1dca6bd6b8e444698f83/Apple_mobile_device_types.txt

mapping = {
    'iPhone4,1': {'model': 'iPhone 4S', 'size': '640x960'},
    'iPhone5,1': {'model': 'iPhone 5 (GSM)', 'size': '640x1136'},
    'iPhone5,2': {'model': 'iPhone 5 (GSM+CDMA)', 'size': '640x1136'},
    'iPhone5,3': {'model': 'iPhone 5C (GSM)', 'size': '640x1136'},
    'iPhone5,4': {'model': 'iPhone 5C (Global)', 'size': '640x1136'},
    'iPhone6,1': {'model': 'iPhone 5S (GSM)', 'size': '640x1136'},
    'iPhone6,2': {'model': 'iPhone 5S (Global)', 'size': '640x1136'},
    'iPhone7,1': {'model': 'iPhone 6 Plus', 'size': '1080x1920'},
    'iPhone7,2': {'model': 'iPhone 6', 'size': '750x1134'},
    'iPhone8,1': {'model': 'iPhone 6s', 'size': '750x1334'},
    'iPhone8,2': {'model': 'iPhone 6s Plus', 'size': '1080x1920'},
    'iPhone8,4': {'model': 'iPhone SE (GSM)', 'size': '640x1136'},
    'iPhone9,1': {'model': 'iPhone 7', 'size': '750x1134'},
    'iPhone9,2': {'model': 'iPhone 7 Plus', 'size': '1080x1920'},
    'iPhone9,3': {'model': 'iPhone 7', 'size': '750x1134'},
    'iPhone9,4': {'model': 'iPhone 7 Plus', 'size': '1080x1920'},
    'iPhone10,1': {'model': 'iPhone 8', 'size': '750x1334'},
    'iPhone10,2': {'model': 'iPhone 8 Plus', 'size': '1080x1920'},
    'iPhone10,3': {'model': 'iPhone X Global', 'size': '1125x2436'},
    'iPhone10,4': {'model': 'iPhone 8', 'size': '750x1334'},
    'iPhone10,5': {'model': 'iPhone 8 Plus', 'size': '1080x1920'},
    'iPhone10,6': {'model': 'iPhone X GSM', 'size': '1125x2436'},
    'iPhone11,2': {'model': 'iPhone XS', 'size': '1125x2436'},
    'iPhone11,4': {'model': 'iPhone XS Max', 'size': '1242x2688'},
    'iPhone11,6': {'model': 'iPhone XS Max Global', 'size': '1242x2688'},
    'iPhone11,8': {'model': 'iPhone XR', 'size': '828x1792'},
    'iPhone12,1': {'model': 'iPhone 11', 'size': '828x1792'},
    'iPhone12,3': {'model': 'iPhone 11 Pro', 'size': '1125x2436'},
    'iPhone12,5': {'model': 'iPhone 11 Pro Max', 'size': '1242x2688'},
    'iPhone12,8': {'model': 'iPhone SE 2nd Gen', 'size': '750x1334'},
    'iPhone13,1': {'model': 'iPhone 12 Mini', 'size': '1080x2340'},
    'iPhone13,2': {'model': 'iPhone 12', 'size': '1170x2532'},
    'iPhone13,3': {'model': 'iPhone 12 Pro', 'size': '1170x2532'},
    'iPhone13,4': {'model': 'iPhone 12 Pro Max', 'size': '1284x2778'},
    'iPhone14,2': {'model': 'iPhone 13 Pro', 'size': '1170x2532'},
    'iPhone14,3': {'model': 'iPhone 13 Pro Max', 'size': '1284x2778'},
    'iPhone14,4': {'model': 'iPhone 13 Mini', 'size': '1080x2340'},
    'iPhone14,5': {'model': 'iPhone 13', 'size': '1170x2532'},
    'iPad5,1': {'model': 'iPad mini 4 (WiFi)', 'size': '1170x2532'},
    'iPad5,2': {'model': '4th Gen iPad mini (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad5,3': {'model': 'iPad Air 2 (WiFi)', 'size': '1170x2532'},
    'iPad5,4': {'model': 'iPad Air 2 (Cellular)', 'size': '1170x2532'},
    'iPad6,3': {'model': 'iPad Pro (9.7 inch, WiFi)', 'size': '1170x2532'},
    'iPad6,4': {'model': 'iPad Pro (9.7 inch, WiFi+LTE)', 'size': '1170x2532'},
    'iPad6,7': {'model': 'iPad Pro (12.9 inch, WiFi)', 'size': '1170x2532'},
    'iPad6,8': {'model': 'iPad Pro (12.9 inch, WiFi+LTE)', 'size': '1170x2532'},
    'iPad6,11': {'model': 'iPad (2017)', 'size': '1170x2532'},
    'iPad6,12': {'model': 'iPad (2017)', 'size': '1170x2532'},
    'iPad7,1': {'model': 'iPad Pro 2nd Gen (WiFi)', 'size': '1170x2532'},
    'iPad7,2': {'model': 'iPad Pro 2nd Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad7,3': {'model': 'iPad Pro 10.5-inch 2nd Gen', 'size': '1170x2532'},
    'iPad7,4': {'model': 'iPad Pro 10.5-inch 2nd Gen', 'size': '1170x2532'},
    'iPad7,5': {'model': 'iPad 6th Gen (WiFi)', 'size': '1170x2532'},
    'iPad7,6': {'model': 'iPad 6th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad7,11': {'model': 'iPad 7th Gen 10.2-inch (WiFi)', 'size': '1170x2532'},
    'iPad7,12': {'model': 'iPad 7th Gen 10.2-inch (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad8,1': {'model': 'iPad Pro 11 inch 3rd Gen (WiFi)', 'size': '1170x2532'},
    'iPad8,2': {'model': 'iPad Pro 11 inch 3rd Gen (1TB, WiFi)', 'size': '1170x2532'},
    'iPad8,3': {'model': 'iPad Pro 11 inch 3rd Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad8,4': {'model': 'iPad Pro 11 inch 3rd Gen (1TB, WiFi+Cellular)', 'size': '1170x2532'},
    'iPad8,5': {'model': 'iPad Pro 12.9 inch 3rd Gen (WiFi)', 'size': '1170x2532'},
    'iPad8,6': {'model': 'iPad Pro 12.9 inch 3rd Gen (1TB, WiFi)', 'size': '1170x2532'},
    'iPad8,7': {'model': 'iPad Pro 12.9 inch 3rd Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad8,8': {'model': 'iPad Pro 12.9 inch 3rd Gen (1TB, WiFi+Cellular)', 'size': '1170x2532'},
    'iPad8,9': {'model': 'iPad Pro 11 inch 4th Gen (WiFi)', 'size': '1170x2532'},
    'iPad8,10': {'model': 'iPad Pro 11 inch 4th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad8,11': {'model': 'iPad Pro 12.9 inch 4th Gen (WiFi)', 'size': '1170x2532'},
    'iPad8,12': {'model': 'iPad Pro 12.9 inch 4th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad11,1': {'model': 'iPad mini 5th Gen (WiFi)', 'size': '1170x2532'},
    'iPad11,2': {'model': 'iPad mini 5th Gen', 'size': '1170x2532'},
    'iPad11,3': {'model': 'iPad Air 3rd Gen (WiFi)', 'size': '1170x2532'},
    'iPad11,4': {'model': 'iPad Air 3rd Gen', 'size': '1170x2532'},
    'iPad11,6': {'model': 'iPad 8th Gen (WiFi)', 'size': '1170x2532'},
    'iPad11,7': {'model': 'iPad 8th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad12,1': {'model': 'iPad 9th Gen (WiFi)', 'size': '1170x2532'},
    'iPad12,2': {'model': 'iPad 9th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad14,1': {'model': 'iPad mini 6th Gen (WiFi)', 'size': '1170x2532'},
    'iPad14,2': {'model': 'iPad mini 6th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad13,1': {'model': 'iPad Air 4th Gen (WiFi)', 'size': '1170x2532'},
    'iPad13,2': {'model': 'iPad Air 4th Gen (WiFi+Cellular)', 'size': '1170x2532'},
    'iPad13,4': {'model': 'iPad Pro 11 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,5': {'model': 'iPad Pro 11 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,6': {'model': 'iPad Pro 11 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,7': {'model': 'iPad Pro 11 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,8': {'model': 'iPad Pro 12.9 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,9': {'model': 'iPad Pro 12.9 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,10': {'model': 'iPad Pro 12.9 inch 5th Gen', 'size': '1170x2532'},
    'iPad13,11': {'model': 'iPad Pro 12.9 inch 5th Gen', 'size': '1170x2532'},
}


class IDBKit(object):
    _ports = Queue(100)

    def __init__(self, sn=None):
        if platform.system() != 'Darwin':
            return
        self._sn = sn
        if self._sn is None:
            devices = self.list_device()
            if len(devices) > 0:
                self._sn = devices[0]

    def _log(self, info):
        logger.info("%s: %s" % (self._sn, info))

    @property
    def sn(self):
        return self._sn

    @property
    def info(self):
        """
        设备信息
        :return:
        """
        try:
            product_type = CmdKit.run_sysCmd(
                "tidevice --udid %s info | grep ProductType | awk -F: '{print $2}'" % self._sn).strip()
            os_version = CmdKit.run_sysCmd(
                "tidevice --udid %s info | grep ProductVersion | awk -F: '{print $2}'" % self._sn).strip()
            cpu_abi = CmdKit.run_sysCmd(
                "tidevice --udid %s info | grep CPUArchitecture | awk -F: '{print $2}'" % self._sn).strip()

            if product_type.find("iPhone") != -1:
                brand = 'iPhone'
            elif product_type.find("iPad") != -1:
                brand = 'iPad'
            elif product_type.find("iPod") != -1:
                brand = 'iPod'
            else:
                brand = ''

            models = mapping.get(product_type)

        except Exception as e:
            self._log(e)
            return None

        device_info = DeviceInfo(sn=self._sn, os_type="iOS", os_version=os_version,
                                 sdk_version=os_version,
                                 brand=brand, model=models['model'], market_name=models['model'],
                                 rom_version=os_version, cpu_abi=cpu_abi, display=models['size'])
        return device_info

    @classmethod
    def set_port(cls, start=10600, end=11000, step=5):
        for port in range(start, end, step):
            cls._ports.put(port)

    @classmethod
    def get_port(cls):
        return cls._ports.get()

    @staticmethod
    def get_app_data(file_or_url: str) -> AppInfo:
        """
        获取APP信息
        :param file_or_url:
        :return:
        """
        filepath = CmdKit.download(file_or_url)
        if zipfile.is_zipfile(filepath):
            ipaobj = zipfile.ZipFile(filepath)
            info_path = IDBKit._get_ios_info_path(ipaobj)
            if info_path:
                plist_data = ipaobj.read(info_path)
                plist_root = readPlistFromString(plist_data)
                labelname = plist_root['CFBundleDisplayName']
                version = plist_root['CFBundleShortVersionString']
                bundle_id = plist_root['CFBundleIdentifier']
                bundle_version = plist_root['CFBundleVersion']

                return AppInfo(bundle_id, version, labelname, bundle_version)

    @staticmethod
    def _get_ios_info_path(ipaobj):
        """
        获取ipa包 Info.plist 文件
        :param ipaobj:
        :return:
        """
        infopath_re = re.compile(r'.*.app/Info.plist')
        for i in ipaobj.namelist():
            m = infopath_re.match(i)
            if m is not None:
                return m.group()

    @staticmethod
    def list_device():
        """
        设备列表
        :return:
        """
        if platform.system() != 'Darwin':
            return []
        _output = CmdKit.run_sysCmd('idevice_id -l')
        if "not found" not in _output:
            return [serial for serial in _output.split('\n') if serial]
        else:
            return []

    def install(self, file_or_url: Union[str, typing.IO], app_info=None, over_install=True, timeout=180) -> tuple:
        """
        ipa 包下载安装(卸载或覆盖安装)
        :param file_or_url:
        :param app_info:
        :param over_install:
        :param timeout:
        :return:
        """
        filepath = CmdKit.download(file_or_url)
        self._log(filepath)
        self._log("包下载路径：" + filepath)
        if not app_info:
            app_info = self.get_app_data(filepath)
        device_app_version = self.get_app_version(app_info.app_id)
        if device_app_version:
            self._log("已安装应用的版本号：" + device_app_version)
            self._log("待测应用的版本号：" + app_info.version)
        if not over_install:
            self._log("Installing package...")
            res = CmdKit.run_sysCmd("tidevice --udid {0} uninstall {1}".format(self._sn, app_info.app_id),
                              timeout=timeout)
            res = CmdKit.run_sysCmd("tidevice --udid {0} install {1}".format(self._sn, filepath), timeout=timeout)
            self._log("Install complete...")
        else:
            self._log("Installing package...")
            res = CmdKit.run_sysCmd("tidevice --udid {0} install {1}".format(self._sn, file_or_url), timeout=timeout)
            self._log("Install complete...")
        self._log("Clear package path...")
        shutil.rmtree(filepath, ignore_errors=True)
        data = res.split('\n')
        if "Complete" in data:
            return app_info, "success"
        else:
            return app_info, "failed"

    def uninstall(self, package_name):
        """
        APP卸载安装
        :param package_name:
        :return:
        """
        if CmdKit.run_sysCmd('tidevice --udid {0} uninstall {1}'.format(self._sn, package_name)).find(
                'Complete') >= 0:
            return True
        else:
            return False

    def get_app_version(self, package_name):
        output = CmdKit.run_sysCmd("tidevice --udid {0} applist |grep {1}".format(self._sn, package_name)).strip()
        try:
            version_name = output.split(' ')[2]
            return version_name
        except Exception as e:
            self._log(e)
            return None

    def kill_app(self, package_name):
        CmdKit.run_sysCmd("tidevice --udid {0} kill {1}".format(self._sn, package_name))

    def get_app_name(self, package_name):
        output = CmdKit.run_sysCmd("tidevice --udid {0} applist |grep {1}".format(self._sn, package_name)).strip()
        try:
            app_name = output.split(' ')[1]
            return app_name
        except Exception:
            return None

    def screencap(self, name=None):
        """
        截图放本地
        :param name:
        :return:
        """
        if name is None:
            _key = str(int(time.time() * 1000))
        else:
            _key = name
        CmdKit.run_sysCmd('tidevice --udid {0} screenshot {1}.png'.format(self._sn, _key))
        try:
            return '{0}.png'.format(_key)
        except Exception as e:
            self._log(e)
            return None

    def wda_proxy(self, port=8200, timeout=1800):
        CmdKit.run_sysCmd(
            "tidevice -u {0} xctest -B com.facebook.WebDriverAgentRunner.xctrunner -e USB_PORT:{1}".format(self._sn,
                                                                                                           port),
            timeout=timeout)

    def relay(self, port=8100, timeout=1800):
        CmdKit.run_sysCmd(
            "tidevice -u {0} relay {1} 8100".format(self._sn,
                                                    port), timeout=timeout)

    def screen_record(self, localPath=None, timeout=10):
        """
        录屏
        :param localPath:
        :param timeout:
        :return:
        """
        pass

    def reboot(self) -> None:
        """
        reboot phone
        """
        CmdKit.run_sysCmd("idevicediagnostics restart -u %s" % self._sn)

    def get_system_available_size(self):
        """
        设备剩余可用存储
        :return:
        """
        try:
            t = tidevice.Device(udid=self._sn)
            size = float(t.storage_info()['free']) / 1000000000
            self._log(t.storage_info()['free'])
            return size
        except Exception as e:
            self._log(e)
            return 100000

    def get_third_packages(self):
        """
        APP列表
        :return:
        """
        res = CmdKit.run_sysCmd("tidevice --udid " + self._sn + " applist | awk -F' ' '{print $1}'")
        result = res.replace('\r', '').splitlines()
        installed_app_list = []
        for app in result:
            installed_app_list.append(app)
        return installed_app_list

    def get_battery_level(self):
        """
        电量
        :return:
        """
        try:
            res = CmdKit.run_sysCmd(
                "tidevice --udid " + self._sn + " info --domain com.apple.mobile.battery --json")
            return json.loads(res)['BatteryCurrentCapacity']
        except Exception as e:
            self._log(e)

    @time_cost(info='清理第三方应用')
    def clear_third_packages(self):
        try:
            third_packages = self.get_third_packages()
            for p in third_packages:
                self.uninstall(p)
        except Exception as e:
            self._log(e)
