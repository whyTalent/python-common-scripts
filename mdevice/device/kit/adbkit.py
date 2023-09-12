import imghdr
import logging
import os
import platform
import re
import shutil
import time
import xml.etree.cElementTree as ET
from typing import Tuple

from adbutils import AdbClient
from retry import retry

from mdevice import app_path
from mdevice.model import AppInfo, DeviceInfo
from mdevice.perf.android_cpu import PckCpuinfo
from mdevice.perf.android_mem import MemInfoPackage
from mdevice.tools.utils import TimeUtils, FileUtils
from mdevice.tools.cmdkit import CmdKit
from mdevice.tools.apkparse import parse_apk
from mdevice.tools.host import HostToolKit
from mdevice.tools.log import LogUtils
from mdevice.tools.request import RequestUtils
from mdevice.tools.timer import time_cost
from mdevice.tools.usb import USBHelper

logger = LogUtils.LOGGER_DEBUG
MNC_HOME = '/data/local/tmp/minicap'
MNC_SO_HOME = '/data/local/tmp/minicap.so'


class ADBKit(object):
    os_name = None
    adb_path = None

    def __init__(self, sn: str = None, device_proxy_ip: str = None, logger: logging.Logger = None, mnc=True,
                 monkey=False):
        """
        初始化
        :param sn: 设备序列号
        :param device_proxy_ip: 设备代理IP
        :param logger: log打印handler
        :param mnc:
        :param monkey: 是否触发monkey任务
        """
        self.host = HostToolKit() # 本机IP
        self.device_proxy_ip = device_proxy_ip
        self._adb_path = ADBKit.get_adb_path()  # ADBKit.exe程序的绝对路径
        self._sn = sn
        if self._sn is None:
            devices = self.list_device()
            if len(devices) > 0:
                self._sn = devices[0]
        self._os_name = None
        self.pattern = re.compile(r"\d+")
        self._properties = {}
        self.logger = logger if logger else LogUtils.LOGGER_DEBUG
        if mnc:
            MNCInstaller(self)
        if monkey:
            FastBotInstaller(self)

    def _log(self, info):
        self.logger.info("%s: %s" % (self._sn, info))

    @property
    def prop(self) -> "Property":
        return Property(self)

    @property
    def sn(self):
        return self._sn

    @staticmethod
    def get_adb_path():
        """返回adb.exe的绝对路径。优先使用指定的adb，若环境变量未指定，则返回当前脚本tools目录下的adb

        :return: 返回adb.exe的绝对路径
        :rtype: str
        """
        if ADBKit.adb_path:
            return ADBKit.adb_path
        ADBKit.adb_path = os.environ.get('ADB_PATH')
        if ADBKit.adb_path is not None and ADBKit.adb_path.endswith('adb'):
            return ADBKit.adb_path
        # 判断系统默认adb是否可用，如果系统有配，默认优先用系统的，避免5037端口冲突
        result = CmdKit.run_sysCmd('adb devices')
        if not isinstance(result, str):
            result = str(result, 'utf-8')
        # 说明自带adb  windows上返回结果不是这样 另外有可能第一次执行，adb会不正常
        if result and "command not found" not in result:
            ADBKit.adb_path = "adb"
            return ADBKit.adb_path
        static_path = app_path() + '/device/static/adb'
        ADBKit.os_name = platform.system()
        if ADBKit.os_name == "Windows":
            ADBKit.adb_path = os.path.join(static_path, "windows", "adb.exe")
        elif ADBKit.os_name == "Darwin":
            ADBKit.adb_path = os.path.join(static_path, "mac", "adb")
        else:
            ADBKit.adb_path = os.path.join(static_path, "linux", "adb")
        return ADBKit.adb_path

    @staticmethod
    def get_os_name():
        if ADBKit.os_name:
            return ADBKit.os_name
        ADBKit.os_name = platform.system()
        return ADBKit.os_name

    @time_cost(info='检查设备是否连接上')
    def is_connected(self):
        """检查设备是否连接上
        """
        if self._sn in self.list_device():
            return True
        else:
            return False

    def list_device(self):
        """获取设备列表

        :return: 返回设备列表
        :rtype: list
        """
        result = self.run_adb_cmd('devices')
        if not isinstance(result, str):
            result = result.decode('utf-8')
        result = result.replace('\r', '').splitlines()
        device_list = []
        for device in result[1:]:
            if len(device) <= 1 or '\t' not in device:
                continue
            if device.split('\t')[1] == 'device':
                # 只获取连接正常的
                device_list.append(device.split('\t')[0])
        return device_list

    @property
    def info(self):
        try:
            device_info = DeviceInfo(sn=self._sn, os_type="Android", os_version=self.get_android_version(),
                                     sdk_version=self.get_sdk_version(),
                                     brand=self.get_product_brand(), model=self.get_product_model(),
                                     rom_version=self.get_product_rom(), cpu_abi=self.get_cpu_abi(),
                                     cpu_hardware=self.get_cpu_hardware(), display=self.get_wm_size())
            return device_info
        except Exception as e:
            self._log(e)

    @staticmethod
    def recover():
        if ADBKit.check_adb_normal():
            return
        else:
            ADBKit.kill_server()
            ADBKit.start_server()

    @staticmethod
    def check_adb_normal():
        """
        验证adb是否正常运行
        :return:
        """
        result = CmdKit.run_sysCmd('adb devices')
        if not result:
            logger.debug("devices list maybe is empty")
            return True
        else:
            if "daemon not running." in result:
                logger.warning("daemon not running.")
                return False
            elif "adb server didn't ACK" in result:
                logger.warning("error: adb server didn't ACK,kill occupy 5037 port process")
                return False
            else:
                return True

    @staticmethod
    def kill_server():
        os.system("adb kill-server")

    @staticmethod
    def start_server():
        os.system("adb start-server")

    def _run_cmd_once(self, cmd, *argv, **kwds):
        """执行一次adb命令：cmd

        :param str cmd: 命令字符串
        :param list argv: 可变参数
        :param dict kwds: 可选关键字参数 (超时/异步)
        :return: 执行adb命令的子进程或执行的结果
        :rtype: Popen or str
        """
        if self._sn:
            if self.device_proxy_ip:
                cmdlet = [self._adb_path, '-H', self.device_proxy_ip, '-P 5037', '-s', self._sn, cmd]
            else:
                cmdlet = [self._adb_path, '-s', self._sn, cmd]
        else:
            if self.device_proxy_ip:
                cmdlet = [self._adb_path, '-H', self.device_proxy_ip, '-P 5037', cmd]
            else:
                cmdlet = [self._adb_path, cmd]
        for i in range(len(argv)):
            arg = argv[i]
            if not isinstance(argv[i], str):
                arg = arg.decode('utf8')
            cmdlet.append(arg)
        cmd = " ".join(cmdlet)
        timeout = 60
        if "timeout" in kwds:
            timeout = kwds['timeout']
        out = CmdKit.run_sysCmd(cmd, timeout=timeout)
        return out

    def run_adb_cmd(self, cmd, *argv, **kwds):
        """尝试执行adb命令

        :param str cmd: 命令字符串
        :param list argv: 可变参数
        :param dict kwds: 可选关键字参数 (超时/异步)
        :return: 执行adb命令的子进程或执行的结果
        :rtype: Popen or str
        """
        retry_count = 3  # 默认最多重试3次
        if "retry_count" in kwds:
            retry_count = kwds['retry_count']
        while retry_count > 0:
            ret = self._run_cmd_once(cmd, *argv, **kwds)
            if ret is not None:
                return ret
            retry_count = retry_count - 1

    def run_shell_cmd(self, cmd, **kwds):
        """执行 adb shell 命令
        """
        ret = self.run_adb_cmd('shell', '%s' % cmd, **kwds)
        # 当 adb 命令传入 sync=False时，ret是Poen对象
        if ret is None:
            self._log(u'adb cmd failed:%s ' % cmd)
        return ret

    def bugreport(self, save_path: str):
        """adb bugreport ~/Downloads/bugreport.zip
        """
        result = self.run_adb_cmd('bugreport', save_path, timeout=180)
        return result

    def push_file(self, src_path: str, dst_path: str):
        """拷贝文件到手机中

        :param str src_path: 原文件路径
        :param str dst_path: 拷贝到的文件路径
        :return: 执行adb push命令的子进程或执行的结果
        :rtype: Popen or str
        """
        if " " in src_path:
            src_path = '"' + src_path + '"'
        for _ in range(3):
            result = self.run_adb_cmd('push', src_path, dst_path, timeout=5 * 60)
            if result.find('No such file or directory') >= 0:
                self._log('file:%s not exist' % src_path)
            else:
                return result

    def pull_file(self, src_path: str, dst_path: str):
        """从手机中拉取文件
        """
        result = self.run_adb_cmd('pull', src_path, dst_path, timeout=180)
        if result and 'failed to copy' in result:
            self._log("failed to pull file:" + src_path)
        return result

    def screenshot(self, filename: str = None, display: str = None, oss: bool = False):
        if filename is None:
            filename = str(int(time.time() * 1000)) + '.png'
        elif 'png' not in filename:
            filename = filename + '.png'
        img = self.minicap(filename=filename, display=display, oss=oss)
        if not img:
            return self.screencap(filename=filename, oss=oss)
        else:
            return img

    @time_cost(info='minicap截图')
    def minicap(self, filename: str = None, display: str = None, oss: bool = False):
        try:
            for i in range(3):
                self._log("开始尝试第{0}次minicap截图".format(i))
                if display and display != '暂无' and display != '':
                    width, height = display.replace('\n', '').replace('\r', '').split(' ')[-1].split('x')
                    screen = (width, height)
                else:
                    screen = self.get_size()

                screen_size = '{}x{}@{}x{}/0'.format(screen[0], screen[1], screen[0], screen[1])
                self.run_shell_cmd(
                    'LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/minicap -s -P {0} > {1}'.format(screen_size,
                                                                                                     filename))
                self._log('screen shot saved in {}'.format(filename))
                if os.path.exists(filename) and os.path.getsize(filename) > 0 and imghdr.what(file=filename):
                    return filename
            return None
        except Exception as e:
            self._log(e)
            return None

    @time_cost(info='原生截图')
    def screencap(self, filename: str = None, optimization: bool = True, oss: bool = False):
        try:
            for i in range(3):
                self._log("开始尝试第{0}次原生截图".format(i))
                if optimization:
                    self.run_adb_cmd('exec-out screencap -p > {0}'.format(filename))
                else:
                    self.run_shell_cmd('screencap -p /sdcard/{0}'.format(filename))
                    self.run_adb_cmd('pull /sdcard/{0} .'.format(filename))
                self._log(filename)
                if os.path.exists(filename) and os.path.getsize(filename) > 0 and imghdr.what(file=filename):
                    return filename
            self.reboot()
            return None
        except Exception as e:
            self._log(e)
            self.reboot()
            return None

    def delete_file(self, file_path: str):
        """删除手机上文件
        """
        self.run_shell_cmd('rm %s' % file_path)

    def delete_folder(self, folder_path: str):
        """删除手机上的目录
        """
        self.run_shell_cmd('rm -R %s' % folder_path)

    def is_exist(self, path: str):
        """
        判断文件或文件夹是否存在
        :param path:
        :return:
        """
        result = self.run_shell_cmd('ls -l %s' % path)
        if not result:
            return False
        result = result.replace('\r\r\n', '\n')
        if 'No such file or directory' in result:
            return False
        return True

    def mkdir(self, folder_path: str):
        """
        在设备上创建目录
        :param folder_path:
        :return:
        """
        self.run_shell_cmd('mkdir %s' % folder_path)

    def get_current_activity(self):
        """获取当前activity名
        """
        if int(self.get_sdk_version()) < 26:  # android8.0以下优先选择dumpsys activity top获取当前的activity
            current_activity = self._get_top_activity_with_activity_top()
            if current_activity:
                return current_activity
            current_activity = self._get_top_activity_with_usagestats()
            if current_activity:
                return current_activity
            return None
        else:  # android 8.0以上优先根据dumsys usagestats来获取当前的activity
            current_activity = self._get_top_activity_with_usagestats()
            if current_activity:
                return current_activity
            current_activity = self._get_top_activity_with_activity_top()
            if current_activity:
                return current_activity

    def _get_top_activity_with_activity_top(self):
        """通过dumpsys activity top 获取当前activity名
        """
        ret = self.run_shell_cmd("dumpsys activity top")
        if not ret:
            return None
        lines = ret.split("\n")
        top_activity = ""
        for line in lines:
            if "ACTIVITY" in line:
                line = line.strip()
                self._log("dumpsys activity top info line :" + line)
                activity_info = line.split()[1]
                if "." in line:
                    top_activity = activity_info.replace("/", "")
                else:
                    top_activity = activity_info.split("/")[1]
                self._log("dump activity top activity:" + top_activity)
                return top_activity
        return top_activity

    def _get_top_activity_with_usagestats(self):
        """通过dumpsys usagestats获取当前activity名
        """
        top_activity = ""
        ret = self.run_shell_cmd("dumpsys usagestats")
        if not ret:
            return None
        last_activity_line = ""
        lines = ret.split("\n")
        for line in lines:
            if "MOVE_TO_FOREGROUND" in line:
                last_activity_line = line.strip()
        self._log("dumpsys usagestats MOVE_TO_FOREGROUND lastline :" + last_activity_line)
        if len(last_activity_line.split("class=")) > 1:
            top_activity = last_activity_line.split("class=")[1]
            if " " in top_activity:
                top_activity = top_activity.split()[0]
        self._log("dumpsys usagestats top activity:" + top_activity)
        return top_activity

    def get_pid_from_pck(self, package_name: str):
        """
        从ps信息中通过匹配包名，获取进程pid号，对于双开应用统计值会返回两个不同的pid后面再优化
        :param package_name: 应用包名
        :return: 该进程的pid
        """
        # 跟 get_process_pids 有点区别 这个返回主进程名的pid
        pckinfo_list = self.get_pckinfo_from_ps(package_name)
        if pckinfo_list:
            return pckinfo_list[0]["pid"]

    def get_pckinfo_from_ps(self, package_name: str):
        """
            从ps中获取应用的信息:pid,uid,packagename
            :param package_name: 目标包名
            :return: 返回目标包名的列表信息
            """
        ps_list = self.list_process()
        pck_list = []
        for item in ps_list:
            if item["proc_name"] == package_name:
                pck_list.append(item)
        return pck_list

    def clear_data(self, package_name):
        """清除指定包的 用户数据
        """
        return self.run_shell_cmd("pm clear %s" % package_name)

    def stop_package(self, packagename):
        """杀死指定包的进程
        """
        return self.run_shell_cmd("am force-stop %s" % packagename, timeout=10)

    def input(self, string):
        self.run_shell_cmd("input keyevent KEYCODE_MOVE_END")
        self.run_shell_cmd("input keyevent --longpress $(printf 'KEYCODE_DEL %.0s' {1..250})")
        return self.run_shell_cmd("input text %s" % string)

    @time_cost(info='ping')
    def ping(self, address, count):
        res = self.run_shell_cmd("ping -c %d %s" % (count, address))
        if 'unknown host' in res:
            return False
        else:
            return True

    def get_android_version(self):
        """获取系统版本，如：4.1.2
        """
        return self.prop.get("ro.build.version.release").strip()

    def get_sdk_version(self):
        """获取SDK版本，如：16
        """
        try:
            res = self.prop.get('ro.build.version.sdk').strip()
            if 'Error' in res or res == '':
                return 25
            else:
                return res
        except Exception as e:
            self._log(e)

    def get_product_brand(self):
        """获取手机品牌  如：Mi Samsung OnePlus
        """
        return self.prop.get('ro.product.brand').strip()

    def get_product_model(self):
        """获取手机型号  如：A0001 M2S
        """
        return self.prop.get('ro.product.model').strip()

    def get_product_rom(self):
        """
        获取设备ROM名，如：MHA-AL00C00B213
        """
        return self.prop.get("ro.build.display.id").strip()

    def get_screen_size(self):
        """获取屏幕大小  如：5.5 可能获取不到
        """
        return self.prop.get('ro.product.screensize').strip()

    def get_wm_size(self):
        """获取屏幕分辨率  如：Physical size:1080*1920
        """
        try:
            self.run_shell_cmd("wm size reset")
            res = self.run_shell_cmd("wm size | awk 'NR==1' | awk -F': ' '{print $2}'").strip()
            if 'x' in res:
                return res
            else:
                return "暂无"
        except Exception as e:
            self._log(e)
            return "暂无"

    def get_cpu_abi(self):
        """
        获取设备CPU架构，如：arm64-v8a,armeabi-v7a,armeabi
        """
        if int(self.get_sdk_version()) >= 21:
            return self.prop.get("ro.product.cpu.abilist").strip()
        else:
            return self.prop.get("ro.product.cpu.abi").strip()

    def get_cpu_hardware(self):
        """
        获取设备CPU Hardware，如：Hisilicon Kirin990
        """

        try:
            return self.prop.get("ro.hardware").strip()
        except Exception as e:
            self._log(e)
            return ""

    def get_size(self):
        """ get screen size, return value looks like (1080, 1920) """
        result_str = self.get_wm_size()
        width, height = result_str.replace('\n', '').replace('\r', '').split(' ')[-1].split('x')
        return width, height

    def get_process_pids(self, process_name):
        """查找包含指定进程名的进程PID
        """
        pids = []
        process_list = self.list_process()
        for process in process_list:
            if process['proc_name'] == process_name:
                pids.append(process['pid'])
        return pids

    def is_process_running(self, process_name):
        """判断进程是否存活
        """
        process_list = self.list_process()
        for process in process_list:
            if process['proc_name'] == process_name:
                return True
        return False

    def is_app_installed(self, package):
        """
        判断app是否安装
        """
        if package in self.list_installed_app():
            return True
        else:
            return False

    def list_installed_app(self):
        """
        获取已安装app列表
        :return: 返回app列表
        :rtype: list
        """
        result = self.run_shell_cmd('pm list packages -3')
        result = result.replace('\r', '').splitlines()
        installed_app_list = []
        for app in result:
            if 'package' not in app:
                continue
            if app.split(':')[0] == 'package':
                # 只获取连接正常的
                installed_app_list.append(app.split(':')[1])
        return installed_app_list

    def list_process(self):
        """获取进程列表
        """
        # <= 7.0 用ps, >=8.0 用ps -A android8.0 api level 26
        if int(self.get_sdk_version()) < 26:
            result = self.run_shell_cmd('ps')  # 不能使用grep
        else:
            result = self.run_shell_cmd('ps -A')  # 不能使用grep
        result = result.replace('\r', '')
        lines = result.split('\n')
        busybox = False
        if lines[0].startswith('PID'):
            busybox = True

        result_list = []
        for i in range(1, len(lines)):
            items = lines[i].split()
            if not busybox:
                if len(items) < 9:
                    err_msg = "ps命令返回格式错误：\n%s" % lines[i]
                    if len(items) == 8:
                        result_list.append({'uid': items[0], 'pid': int(items[1]), 'ppid': int(items[2]),
                                            'proc_name': items[7], 'status': items[-2]})
                    else:
                        logger.error(err_msg)
                else:
                    result_list.append({'uid': items[0], 'pid': int(items[1]), 'ppid': int(items[2]),
                                        'proc_name': items[8], 'status': items[-2]})
            else:
                idx = 4
                cmd = items[idx]
                if len(cmd) == 1:
                    # 有时候发现此处会有“N”
                    idx += 1
                    cmd = items[idx]
                idx += 1
                if cmd[0] == '{' and cmd[-1] == '}':
                    cmd = items[idx]
                ppid = 0
                if items[1].isdigit():
                    ppid = int(items[1])  # 有些版本中没有ppid
                result_list.append({'pid': int(items[0]), 'uid': items[1], 'ppid': ppid,
                                    'proc_name': cmd, 'status': items[-2]})
        return result_list

    def kill_process(self, process_name):
        """杀死包含指定进程
        """
        pids = self.get_process_pids(process_name)
        if pids:
            self.run_shell_cmd('kill ' + ' '.join([str(pid) for pid in pids]))
        return len(pids)

    def forward(self, port1, port2, port_type='tcp'):
        """端口转发
        :param port1: PC上的TCP端口
        :type port1:  int
        :param port2: 手机上的端口或LocalSocket地址
        :type port2:  int或String
        :param port_type:  手机上的端口类型
        :type port_type:   String，LocalSocket地址使用“localabstract”
        """
        ret = self.run_adb_cmd('forward', 'tcp:%d' % port1, '%s:%s' % (port_type, port2))
        if ret is None:
            return False
        return True

    def reboot(self, boot_type=None):
        """重启手机
        boot_type: "bootloader", "recovery", or "None".
        """
        if boot_type:
            self.run_adb_cmd('reboot ' + boot_type)
        else:
            self.run_adb_cmd('reboot')

    def _install_apk(self, apk_path: str, over_install: bool = True, downgrade: bool = False):
        if not self.is_connected():
            return "设备离线"
        timeout = 5 * 60
        cmdline = 'install %s %s %s' % ('-r -t' if over_install else '-t', "-d" if downgrade else "", apk_path)
        ret = ''
        for _ in range(1):
            try:
                ret = self.run_adb_cmd(cmdline, retry_count=1, timeout=timeout)
                self._log("安装结果：" + ret)
                if 'INSTALL_FAILED_ALREADY_EXISTS' in ret:
                    ret = 'Success'
                    break

                if 'INSTALL_CANCELED_BY_USER' in ret or 'INSTALL_FAILED_CANCELLED_BY_USER' in ret \
                        or 'INSTALL_PARSE_FAILED_NOT_APK' in ret:
                    ret = self.run_adb_cmd("install-multiple -r {0}".format(apk_path),
                                           timeout=timeout)  # 使用静默安装，可以在努比亚上不弹出确认对话框
                    self._log("安装结果：" + ret)
                    if 'INSTALL_FAILED_ALREADY_EXISTS' in ret or 'Success' in ret:
                        ret = 'Success'
                        break

                if 'INSTALL_FAILED_NO_MATCHING_ABIS' in ret or 'INSTALL_FAILED_OLDER_SDK' in ret:
                    break
            except Exception as e:
                self._log(e)
        return ret

    @time_cost(info='安装应用')
    def install_apk(self, file_or_url: str, app_info: AppInfo = None, over_install: bool = True,
                    downgrade: bool = False) -> \
            Tuple[
                AppInfo, str]:
        """安装应用
            apk_path 安装包路径
            over_install:是否覆盖暗账
            downgrade:是否允许降版本安装
        """
        # adb install 安装错误常见列表
        errors = {'INSTALL_FAILED_ALREADY_EXISTS': '程序已经存在',
                  'INSTALL_DEVICES_NOT_FOUND': '找不到设备',
                  'INSTALL_FAILED_DEVICE_OFFLINE': '设备离线',
                  'INSTALL_FAILED_INVALID_APK': '无效的APK',
                  'INSTALL_FAILED_INVALID_URI': '无效的APK文件名,确保APK文件名里无中文',
                  'INSTALL_FAILED_INSUFFICIENT_STORAGE': '没有足够的存储空间',
                  'INSTALL_FAILED_DUPLICATE_PACKAGE': '已存在同名程序',
                  'INSTALL_FAILED_NO_SHARED_USER': '请求的共享用户不存在',
                  'INSTALL_FAILED_UPDATE_INCOMPATIBLE': '以前安装过同名应用，但卸载时数据没有移除；或者已安装该应用，但签名不一致',
                  'INSTALL_FAILED_SHARED_USER_INCOMPATIBLE': '请求的共享用户存在但签名不一致',
                  'INSTALL_FAILED_MISSING_SHARED_LIBRARY': '安装包使用了设备上不可用的共享库',
                  'INSTALL_FAILED_REPLACE_COULDNT_DELETE': '替换时无法删除',
                  'INSTALL_FAILED_DEXOPT': 'dex优化验证失败或空间不足',
                  'INSTALL_FAILED_DEVICE_NOSPACE': '手机存储空间不足导致apk拷贝失败',
                  'INSTALL_FAILED_DEVICE_COPY_FAILED': '文件拷贝失败',
                  'INSTALL_FAILED_OLDER_SDK': '设备系统版本低于应用要求',
                  'INSTALL_FAILED_CONFLICTING_PROVIDER': '设备里已经存在与应用里同名的 content provider',
                  'INSTALL_FAILED_NEWER_SDK': '设备系统版本高于应用要求',
                  'INSTALL_FAILED_TEST_ONLY': '应用是 test-only 的，但安装时没有指定 -t 参数',
                  'INSTALL_FAILED_CPU_ABI_INCOMPATIBLE': '包含不兼容设备 CPU 应用程序二进制接口的 native code',
                  'INSTALL_FAILED_MISSING_FEATURE': '应用使用了设备不可用的功能',
                  'INSTALL_FAILED_CONTAINER_ERROR': 'SD卡访问失败，或应用签名与 ROM 签名一致，被当作内置应用',
                  'INSTALL_FAILED_INVALID_INSTALL_LOCATION': '不能安装到指定位置，或应用签名与 ROM 签名一致，被当作内置应用',
                  'INSTALL_FAILED_MEDIA_UNAVAILABLE': '安装位置不可用',
                  'INSTALL_FAILED_VERIFICATION_TIMEOUT': '验证安装包超时',
                  'INSTALL_PARSE_FAILED_NO_CERTIFICATES': '安装包没有签名',
                  'INSTALL_FAILED_ACWF_INCOMPATIBLE': '应用程序与设备不兼容',
                  'INSTALL_FAILED_DUPLICATE_PERMISSION': '应用尝试定义一个已经存在的权限名称',
                  'INSTALL_PARSE_FAILED_MANIFEST_EMPTY': '在 manifest 文件里找不到找可操作标签（instrumentation 或 application）',
                  'INSTALL_PARSE_FAILED_MANIFEST_MALFORMED': '解析 manifest 文件时遇到结构性错误',
                  'INSTALL_PARSE_FAILED_BAD_SHARED_USER_ID': 'manifest 文件里指定了无效的共享用户 ID',
                  'INSTALL_PARSE_FAILED_BAD_PACKAGE_NAME': 'manifest 文件里没有或者使用了无效的包名',
                  'INSTALL_PARSE_FAILED_CERTIFICATE_ENCODING': '解析 APK 文件时遇到 CertificateEncodingException',
                  'INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION': '解析器遇到异常',
                  'INSTALL_FAILED_PACKAGE_CHANGED': '应用与调用程序期望的不一致',
                  'INSTALL_FAILED_PERMISSION_MODEL_DOWNGRADE': '已安装 target SDK 支持运行时权限的同名应用，要安装的版本不支持运行时权限',
                  'INSTALL_FAILED_INTERNAL_ERROR': '系统问题导致安装失败',
                  'INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES': '已安装该应用，且签名与 APK 文件不一致 >> 先卸载原来的再安装',
                  'INSTALL_FAILED_INVALID_ZIP_FILE': '非法的zip文件 >> 先卸载原来的再安装',
                  'INSTALL_CANCELED_BY_USER': '需要用户确认才可进行安装',
                  'INSTALL_FAILED_VERIFICATION_FAILURE': '验证安装包失败 >> 尝试重启手机',
                  'INSTALL_FAILED_UID_CHANGED': '以前安装过该应用，与本次分配的 UID 不一致,/data/data目录下存在文件夹没有删除',
                  'INSTALL_FAILED_NO_MATCHING_ABIS': '应用包含设备的应用程序二进制接口不支持的 native code',
                  'INSTALL_PARSE_FAILED_NOT_APK': '非APK文件',
                  'INSTALL_FAILED_VERSION_DOWNGRADE': '已经安装了该应用更高版本',
                  'INSTALL_FAILED_USER_RESTRICTED': '用户被限制安装应用,需要关闭MIUI优化或者关闭权限监控',
                  'INSTALL_PARSE_FAILED_BAD_MANIFEST': '无法解析的 AndroidManifest.xml 文件',
                  '-99': '需要输入安装密码',
                  '-200': '需要输入安装密码',
                  'DEFAULT': '未知错误'
                  }
        filepath = CmdKit.download(file_or_url)
        self._log("包下载路径：" + filepath)
        if not app_info:
            app_info = self.get_app_data(filepath)
        device_app_version = self.get_app_version(app_info.app_id)
        if device_app_version:
            self._log("已安装应用的版本号：" + device_app_version)
            self._log("待测应用的版本号：" + app_info.version)
        if not over_install:
            self.uninstall_apk(app_info.app_id)  # 先卸载，再安装
            result = self._install_apk(filepath, over_install, downgrade)
        else:
            result = self._install_apk(filepath, over_install, downgrade)
        if 'INSTALL_PARSE_FAILED_INCONSISTENT_CERTIFICATES' in result or 'INSTALL_FAILED_VERSION_DOWNGRADE' in result \
                or 'INSTALL_PARSE_FAILED_UNEXPECTED_EXCEPTION' in result:
            # 必须卸载安装
            return self.install_apk(filepath, False, False)
        elif 'INSTALL_FAILED_ALREADY_EXISTS' in result:
            # 卸载成功依然有可能在安装时报这个错误
            return self.install_apk(filepath, False, True)
        if result.find('Success') >= 0:
            self._log("Clear package path...")
            shutil.rmtree(filepath, ignore_errors=True)
            return app_info, 'Success'
        elif self.is_app_installed(app_info.app_id):
            return app_info, 'Success'
        elif result.find('Failure [') >= 0:
            key = result.split('Failure [')[1]

            if ':' in key:
                key = key.split(':')[0]
            else:
                key = key.split(']')[0]
            try:
                self._log('Install Failure >> %s' % errors[key])
                return app_info, errors[key]
            except KeyError:
                self._log('Install KeyError Failure >> %s' % key)
                return app_info, result
        elif result.find('[ERROR]Timeout Error') >= 0:
            return app_info, "安装超时"
        else:
            return app_info, result

    def uninstall_apk(self, pkg_name, timeout=3 * 60):
        """卸载应用
        """
        if self.is_connected():
            if self.is_app_installed(package=pkg_name):
                result = self.run_adb_cmd('uninstall %s' % pkg_name, timeout=timeout)
                self._log("----注意看下面----")
                self._log(result)
                return result.find('Success') >= 0
            else:
                self._log('不存在该应用')

    @staticmethod
    def get_app_data(file_or_url) -> AppInfo:
        filepath = CmdKit.download(file_or_url)
        try:
            from androguard.core.bytecodes import apk
            apk_obj = apk.APK(filepath)
            if apk_obj.is_valid_APK():
                version_code = apk_obj.get_androidversion_code()
                app_id = apk_obj.get_package()
                package_name = apk_obj.get_app_name()
                version_name = apk_obj.get_androidversion_name()
                main_activitys = apk_obj.get_main_activities()
                main_activity = ''
                for i in main_activitys:
                    if 'leakcanary' not in i:
                        main_activity = i
                return AppInfo(app_id=app_id, version=version_name, name=package_name, bundle_version=version_code,
                               main_activity=main_activity)
        except Exception as err:
            logger.debug(err)
            try:
                m = parse_apk(filepath)
                return AppInfo(app_id=m.package_name, version=m.version_name, name=m.package_name,
                               bundle_version=m.version_code, main_activity=m.main_activity)
            except Exception as e:
                logger.debug(e)
                return AppInfo()

    @staticmethod
    def save_to_file(file_name, contents):
        fh = open(file_name, 'w')
        fh.write(contents)
        fh.close()

    @time_cost(info='dump页面树')
    def dump_xml(self, optimization: bool = False, brand=None):
        """
        获取当前Activity控件树
        """
        _key = str(int(time.time() * 1000))
        for i in range(3):
            self._log('第{0}次尝试dump页面树'.format(i))
            if optimization:
                out = self.run_adb_cmd(
                    "exec-out uiautomator dump /dev/tty")
                if "UI hierchary dumped to" in out:
                    out = out.split('UI hierchary dumped to')[0]
                    return out
            else:
                out = self.run_shell_cmd("uiautomator dump /data/local/tmp/uidump-{0}-{1}.xml".format(_key, self._sn))
                if "UI hierchary dumped to" in out:
                    self.run_adb_cmd("pull /data/local/tmp/uidump-{0}-{1}.xml .".format(_key, self._sn))
                    self.delete_file("/data/local/tmp/uidump-{0}-{1}.xml".format(_key, self._sn))
                    return "uidump-{0}-{1}.xml".format(_key, self._sn)

        for i in range(3):
            try:
                self._log('第{0}次尝试u2-dump页面树'.format(i))
                import uiautomator2 as u2
                if not self.device_proxy_ip and brand not in ['OPPO', 'realme', 'vivo', 'OnePlus']:
                    d = u2.connect()
                    out = d.dump_hierarchy()
                    return self.save_to_file(file_name="uidump-{0}-{1}.xml".format(_key, self._sn), contents=out)
            except Exception as e:
                self._log(e)

        return False

    def _element(self, attrib, name, xml):
        """
        同属性单个元素，返回单个坐标元组
        """
        if os.path.isfile(xml):
            tree = ET.ElementTree(file=xml)
            tree_iter = tree.iter(tag="node")
            for elem in tree_iter:
                if elem.attrib[attrib] == name:
                    bounds = elem.attrib["bounds"]
                    coord = self.pattern.findall(bounds)
                    x_point = (int(coord[2]) - int(coord[0])) / 2.0 + int(coord[0])
                    y_point = (int(coord[3]) - int(coord[1])) / 2.0 + int(coord[1])
                    self._log("find" + name)
                    return x_point, y_point
        elif xml and len(xml) > 100:
            tree = ET.fromstring(text=xml)
            tree_iter = tree.iter(tag="node")
            for elem in tree_iter:
                if elem.attrib[attrib] == name:
                    bounds = elem.attrib["bounds"]
                    coord = self.pattern.findall(bounds)
                    x_point = (int(coord[2]) - int(coord[0])) / 2.0 + int(coord[0])
                    y_point = (int(coord[3]) - int(coord[1])) / 2.0 + int(coord[1])
                    self._log("find" + name)
                    return x_point, y_point
        return None, None

    def _element_text(self, attrib, name, xml):
        if os.path.isfile(xml):
            tree = ET.ElementTree(file=xml)
            tree_iter = tree.iter(tag="node")
            for elem in tree_iter:
                if elem.attrib[attrib] == name:
                    text = elem.attrib["text"]
                    self._log("find" + name)
                    return text
        elif xml and len(xml) > 100:
            tree = ET.fromstring(text=xml)
            tree_iter = tree.iter(tag="node")
            for elem in tree_iter:
                if elem.attrib[attrib] == name:
                    text = elem.attrib["text"]
                    self._log("find" + name)
                    return text
        return None

    def find_element_by_name(self, name: str, out: str):
        """
        通过元素名称定位
        usage: findElementByName(u"设置")
        """
        return self._element("text", name, out)

    def find_element_by_class(self, class_name: str, out: str):
        """
        通过元素类名定位
        usage: findElementByClass("android.widget.TextView")
        """
        return self._element("class", class_name, out)

    def find_element_by_id(self, resource_id: str, out: str):
        """
        通过元素的resource-id定位
        usage: findElementsById("com.android.deskclock:id/imageview")
        """
        return self._element("resource-id", resource_id, out)

    def find_element_text_by_id(self, resource_id: str, out: str):
        """
        通过元素的resource-id定位
        usage: findElementsById("com.android.deskclock:id/imageview")
        """
        return self._element_text("resource-id", resource_id, out)

    def touch(self, dx, dy):
        """
        触摸事件
        usage: touch(500, 500)
        """
        if dx and dy:
            res = self.run_shell_cmd("input tap " + str(dx) + " " + str(dy))
            self.logger.info(res)
            time.sleep(0.5)

    def set_proxy(self, proxy):
        """
        设置代理
        :param proxy:
        :return:
        """
        try:
            set_proxy_cmd = "settings put global http_proxy {0}".format(proxy)
            self.run_shell_cmd(set_proxy_cmd)
        except Exception as e:
            self._log(e)

    def clear_proxy(self):
        """
        清空代理
        :return:
        """
        try:
            clear_proxy_cmd = "settings put global http_proxy :0"
            self.run_shell_cmd(clear_proxy_cmd)
        except Exception as e:
            self._log(e)

    def set_dns(self, dns):
        try:
            client = AdbClient(host="127.0.0.1", port=5037)
            device = client.device(self._sn)
            device.shell("setprop net.dns1 {0}".format(dns))
            device.shell("setprop net.dns2 {0}".format(dns))
        except Exception as e:
            self._log(e)

    def get_app_cpu(self, package):
        cpu = self._top_cpuinfo(package)
        idle_rate = cpu.idle_rate
        device_cpu_rate = cpu.device_cpu_rate
        total_pid_cpu = cpu.total_pid_cpu

        res = (float(total_pid_cpu) / (float(idle_rate) + float(device_cpu_rate))) * 100
        return str('%.2f%%' % res)

    def _top_cpuinfo(self, package):
        """
        CPU占用
        :param package:
        :return:
        """
        top_cmd = 'top -b -n 1 -d 1'
        ret = self.run_shell_cmd(top_cmd)
        if ret and 'Invalid argument "-b"' in ret:
            logger.debug("top -b not support")
            top_cmd = 'top -n 1 -d 1'
        _top_pipe = self.run_shell_cmd(top_cmd, sync=False)
        out = _top_pipe
        out.replace('\r', '')
        top_file = os.path.join('top_cpuinfo_%s.txt' % self._sn)
        with open(top_file, "a+", encoding="utf-8") as writer:
            writer.write(TimeUtils.getCurrentTime() + " top info:\n")
            writer.write(out + "\n\n")
        # 避免文件过大，超过100M清理
        if FileUtils.get_FileSize(top_file) > 100:
            os.remove(top_file)
        sdk = int(self.get_sdk_version())
        return PckCpuinfo(package, out, sdk)

    def get_app_memory(self, package):
        """
        dump 进程详细内存
        :param package:
        :return:
        """
        process = self.get_pid_from_pck(package)
        return self._dumpsys_process_meminfo(str(process))

    def _dumpsys_process_meminfo(self, process):
        """
        dump 进程详细内存 耗时 1s以内
        :param process:
        :return:
        """
        time_old = time.time()
        out = self.run_shell_cmd('dumpsys meminfo %s' % process)
        # self.num = self.num + 1
        # if self.num % 10 == 0:
        # 避免：在windows 无法创建文件名，不能有冒号:
        process_rename = process.replace(":", "_")
        print(process_rename)
        meminfo_file = os.path.join('dumpsys_meminfo_%s.txt' % process_rename)
        with open(meminfo_file, "a+", encoding="utf-8") as writer:
            writer.write(TimeUtils.getCurrentTime() + " dumpsys meminfo package info:\n")
            if out:
                writer.write(out + "\n\n")

        passedtime = time.time() - time_old  # 测试meminfo这个命令的耗时，执行的时长在400多ms
        self._log("dumpsys meminfo package time consume:" + str(passedtime))
        out.replace('\r', '')
        return MemInfoPackage(dump=out)

    @time_cost(info='图片融合')
    def merge_images(self, image_list):
        """
        图片融合

        :param image_list:
        :return:
        """
        try:
            image_merge_name = "image_merge_{0}.png".format(str(int(time.time() * 1000)))
            merged_url = None
            # todo

            for image in image_list:
                shutil.rmtree(image, ignore_errors=True)
            return merged_url
        except Exception as e:
            self._log("========VisionError========")
            self._log(e)
            return self.screenshot(oss=True)

    @time_cost(info='截长图')
    def get_long_image(self, times=3, display=None):
        image_list = []
        if not display:
            _display = self.get_wm_size()
        else:
            _display = display
        if _display != '暂无':
            width = float(_display.split('x')[0])
            height = float(_display.split('x')[1])
            # 开始截图，向上滑动25%
            for _ in range(times):
                img_name = str(int(time.time() * 1000)) + ".png"
                self.screenshot(filename=img_name)
                if os.path.exists(img_name) and os.path.getsize(img_name) > 0 and imghdr.what(file=img_name):
                    image_list.append(img_name)
                x1 = int(width * 0.5)
                x2 = int(width * 0.5)
                y1 = int(height * 0.5)
                y2 = int(height * 0.25)
                self.run_shell_cmd('input swipe {0} {1} {2} {3} 900'.format(x1, y1, x2, y2))

            # 图片融合
            img_url = self.merge_images(image_list)
            return img_url
        else:
            return self.screenshot(oss=True)

    def get_app_version(self, package_name):
        output = self.run_shell_cmd("pm dump '%s'|grep versionName" % package_name)
        try:
            pattern = re.compile(r"\s*versionName=(.*)")
            version_name = pattern.match(output).group(1)
            return version_name
        except Exception:
            return None

    def get_apk_path(self, package_name):
        output = self.run_shell_cmd('pm path %s' % package_name)
        try:
            pattern = re.compile(r"package:(.+?)\n")
            path = pattern.match(output).group(1)
            return path
        except Exception as e:
            self._log(e)
            return None

    def start_record(self, name=None):
        if name is None:
            _key = str(int(time.time() * 1000))
        else:
            _key = name
        CmdKit.run_sysCmd('killall scrcpy')
        CmdKit.run_sys_cmd_async(
            'scrcpy -s {0} --no-display --record "{1}.mp4"'.format(self._sn, _key))
        self._log('{0}.mp4'.format(_key))
        return '{0}.mp4'.format(_key)

    @staticmethod
    def stop_record():
        CmdKit.run_sysCmd('killall scrcpy')

    @time_cost(info='杀掉第三方进程')
    def kill_other_packages(self):
        try:
            white_list = [
                "com.android.jarvis",
                "com.mi.health",
                "com.mfashiongallery.emag",
                "com.miui.virtualsim",
                "com.miui.compass",
                "com.miui.screenrecorder",
                "com.miui.notes",
                "com.miui.calculator",
                "com.xiaomi.gamecenter",
                "com.miui.weather2",
                "com.xiaomi.scanner",
                "com.duokan.reader",
                "com.android.email",
                "com.miui.smarttravel",
                "com.android.midrive",
                "com.miui.cleanmaster",
                "com.github.uiautomator",
                "com.github.uiautomator.test",
                "com.xiaomi.pass",
                "com.heytap.reader",
                "com.oppo.community",
                "com.nearme.gamecenter",
                "com.xiaomi.drivemode",
                "com.coloros.personalassistant",
                "com.heytap.book",
                "com.emoji.keyboard.touchpal",
                "com.cootek.smartinputv5.skin.defaultwhite",
                "com.coloros.apprecover",
                "com.coloros.wallet",
                "com.nearme.note",
                "com.coloros.compass",
                "com.coloros.weather",
                "com.oppo.reader",
                "com.android.calculator2"
            ]
            third_packages = self.list_installed_app()
            for p in third_packages:
                if p not in white_list:
                    self.stop_package(p)
        except Exception as e:
            self._log(e)

    @time_cost(info='清理第三方应用')
    def clear_third_packages(self):
        try:
            white_list = [
                "com.tencent.qnet",
                "com.bilibili.lottie",
                "com.android.jarvis",
                "com.mi.health",
                "com.mfashiongallery.emag",
                "com.miui.virtualsim",
                "com.miui.compass",
                "com.miui.screenrecorder",
                "com.miui.notes",
                "com.miui.calculator",
                "com.xiaomi.gamecenter",
                "com.miui.weather2",
                "com.xiaomi.scanner",
                "com.duokan.reader",
                "com.android.email",
                "com.miui.smarttravel",
                "com.android.midrive",
                "com.miui.cleanmaster",
                "com.github.uiautomator",
                "com.github.uiautomator.test",
                "com.xiaomi.pass",
                "com.heytap.reader",
                "com.oppo.community",
                "com.nearme.gamecenter",
                "com.xiaomi.drivemode",
                "com.coloros.personalassistant",
                "com.heytap.book",
                "com.emoji.keyboard.touchpal",
                "com.cootek.smartinputv5.skin.defaultwhite",
                "com.coloros.apprecover",
                "com.coloros.wallet",
                "com.nearme.note",
                "com.coloros.compass",
                "com.coloros.weather",
                "com.oppo.reader",
                "com.android.calculator2"
            ]
            third_packages = self.list_installed_app()
            for p in third_packages:
                if p not in white_list:
                    self.uninstall_apk(p, timeout=10)
        except Exception as e:
            self._log(e)

    def exec_remote_command(self, command, timeout: float = 20.0):
        data = {
            "command": command,
            "timeout": timeout,
            "env": "base",
            "env_vars": [{"env_name": "JAVA_HOME", "env_value": "/root/jdk1.8.0_281"}]
        }
        response = RequestUtils.safe_post(url='http://{0}:6821/exec'.format(self.device_proxy_ip), json=data,
                                          verify=False)
        return response

    def set_screen_brightness_mode(self):
        self.run_shell_cmd("settings put system screen_brightness_mode 0")

    def set_screen_brightness(self, value=1):
        self.run_shell_cmd("settings put system screen_brightness {0}".format(value))

    def get_wifi_state(self):
        """
        获取WiFi连接状态
        :return:
        """
        return 'wlan0' in self.run_shell_cmd('ip -f inet addr').strip()

    def get_battery_level(self):
        """
        返回电池电量等级
        :return:
        """
        try:
            res = self.run_shell_cmd("dumpsys battery | grep level | awk -F: '{print $2}'")
            result = float(res.strip())
            return result
        except Exception as e:
            self._log(e)
            return 100

    def get_battery_temperature(self):
        """
        返回电池温度
        :return:
        """
        try:
            res = self.run_shell_cmd("dumpsys battery | grep temperature | awk -F: '{print $2}'")
            result = float(res.strip()) / 10
            return result
        except Exception as e:
            self._log(e)
            return 20

    def get_system_available_size(self):
        res = self.run_shell_cmd("df | grep emulated | grep -v denied | head -n 1 | awk '{print $4}'")
        try:
            if "M" in res:
                res = res.split("M")[0]
                size = float(res) / 1024
                self._log(size)
                return size
            elif "K" in res:
                res = res.split("K")[0]
                size = float(res) / (1024 * 1024)
                self._log(size)
                return size
            elif "G" in res:
                res = res.split("G")[0]
                size = float(res)
                self._log(size)
                return size
            else:
                size = float(res) / (1024 * 1024)
                self._log(size)
                return size
        except Exception as e:
            self._log(e)
            return 0

    def reset_usb(self):
        """
        重置USB
        :return:
        """
        try:
            USBHelper(sn=self._sn).reset_usb()
        except Exception as e:
            logger.debug(e)

    def app_start(self, app_info: AppInfo, wait: bool = False, stop: bool = False):
        if stop:
            self.stop_package(app_info.app_id)

        self.run_shell_cmd(
            'am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {0}/{1}'.format(
                app_info.app_id, app_info.main_activity))

        if wait:
            self.app_wait(app_info.app_id)

    def app_wait(self,
                 package_name: str,
                 timeout: float = 20.0,
                 front=False) -> int:
        """ Wait until app launched
        Args:
            package_name (str): package name
            timeout (float): maxium wait time
            front (bool): wait until app is current app

        Returns:
            pid (int) 0 if launch failed
        """
        pid = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            if front:
                if self.app_current()['package'] == package_name:
                    pid = self.get_pid_from_pck(package_name)
                    break
            else:
                if package_name in self.app_list_running():
                    pid = self.get_pid_from_pck(package_name)
                    break
            time.sleep(1)

        return pid or 0

    @retry(OSError, delay=.3, tries=3, logger=logger)
    def app_current(self):
        """
        Returns:
            dict(package, activity, pid?)

        Raises:
            OSError
        """
        _focused_re = re.compile(
            r'mCurrentFocus=Window{.*\s+(?P<package>[^\s]+)/(?P<activity>[^\s]+)}'
        )
        m = _focused_re.search(self.run_shell_cmd('dumpsys window windows')[0])
        if m:
            return dict(package=m.group('package'),
                        activity=m.group('activity'))

        # try: adb shell dumpsys activity top
        _activity_re = re.compile(
            r'ACTIVITY (?P<package>[^\s]+)/(?P<activity>[^/\s]+) \w+ pid=(?P<pid>\d+)'
        )
        output = self.run_shell_cmd('dumpsys activity top')
        ms = _activity_re.finditer(output)
        ret = None
        for m in ms:
            ret = dict(package=m.group('package'),
                       activity=m.group('activity'),
                       pid=int(m.group('pid')))
        if ret:  # get last result
            return ret
        raise OSError("Couldn't get focused app")

    def app_list_running(self) -> list:
        """
        Returns:
            list of running apps
        """
        output = self.run_shell_cmd('pm list packages')
        packages = re.findall(r'package:([^\s]+)', output)
        process_names = re.findall(r'([^\s]+)$',
                                   self.run_shell_cmd('ps; ps -A'), re.M)
        return list(set(packages).intersection(process_names))

    def check_anr(self):
        res = self.run_shell_cmd('wm size')
        if "Can't connect to window manager; is the system running?" in res:
            return True
        else:
            return False


class Property:
    def __init__(self, d: ADBKit):
        self._d = d

    def get(self, name: str, cache=True) -> str:
        try:
            if cache and name in self._d._properties:
                return self._d._properties[name]
            value = self._d._properties[name] = self._d.run_shell_cmd('getprop {0}'.format(name)).strip()
            return value
        except Exception as e:
            self._d._log(e)
            return ""


class MNCInstaller(object):
    """ install minicap for android devices """

    def __init__(self, kit: ADBKit):
        self.kit = kit
        if not self.kit.is_connected():
            return
        try:
            self.abi = self.kit.get_cpu_abi().split(',')[0]
            self.sdk = self.kit.get_sdk_version()
            if not self.is_mnc_installed():
                self.download_target_mnc()
                self.download_target_mnc_so()
        except Exception as e:
            logger.debug(e)

    def download_target_mnc(self):
        mnc_path = app_path() + '/device/static/stf_libs/{0}/minicap'.format(self.abi)

        # push and grant
        self.kit.push_file(src_path=mnc_path, dst_path=MNC_HOME)
        self.kit.run_shell_cmd('chmod 777 {0}'.format(MNC_HOME))

    def download_target_mnc_so(self):
        mnc_so_path = app_path() + '/device/static/stf_libs/minicap-shared/aosp/libs/android-{0}/{1}/minicap.so'.format(
            self.sdk, self.abi)

        # push and grant
        self.kit.push_file(src_path=mnc_so_path, dst_path=MNC_SO_HOME)
        self.kit.run_shell_cmd('chmod 777 {0}'.format(MNC_SO_HOME))

    def is_installed(self, name):
        """ check if is existed in /data/local/tmp """
        return bool(self.kit.run_shell_cmd('find /data/local/tmp -name {0}'.format(name)))

    def is_mnc_installed(self):
        """ check if minicap installed """
        return self.is_installed('minicap') and self.is_installed('minicap.so')


class FastBotInstaller:
    """ install FastBot for android devices """

    def __init__(self, kit: ADBKit):
        self.kit = kit
        if not self.kit.is_connected():
            return
        try:
            if not self.is_fastbot_installed():
                self.install_fastbot()
        except Exception:
            logger.exception("install FastBot error")

    def install_fastbot(self):
        libs_path = app_path() + "/device/static/fastbot/*"
        self.kit.push_file(src_path=libs_path, dst_path="/data/local/tmp")

    def is_fastbot_installed(self):
        return bool(self.kit.run_shell_cmd(f'find /data/local/tmp -name fastbot-thirdpart.jar'))

