# APP基础操作库（Android & iOS）

# **adbkit**：Android设备操作指令方法

**Property**：封装adb获取设备指定属性值, 如 CPU架构 / 系统版本 / SDK版本等

**MNCInstaller**：Android设备安装 [minicap](https://github.com/openstf/minicap) 工具，即从项目指定目录推送至设备指定临时路径(/data/local/tmp)，其中minicap可用于实时截屏，且通过socket通信传送截屏数据

**FastBotInstaller**：Android设备安装APP稳定性测试工具 [fastbot](https://github.com/bytedance/Fastbot_Android)

**ADBKit**：

[androguard](https://github.com/androguard/androguard)：获取APK包信息

[scrcpy](https://github.com/Genymobile/scrcpy)：Android投屏工具

```shell
adb kill-server
adb start-server

adb bugreport ~/Downloads/bugreport.zip

# 远程代理IP
adb -H 127.0.0.1 -P 5037 -s xxxx xxx

# 屏幕分辨率, eg: Physical size: 1080x2280
adb shell wm size

# 截图
adb shell
- 优化（图片导出在本地中）: exec-out screencap -p > filename.png
- 原始（图片生成在设备上）: screencap -p /sdcard/filename

# 获取设备属性
adb shell getprop xxx
- 获取设备CPU架构 ro.product.cpu.abilist 或 ro.product.cpu.abi
- 获取设备CPU Hardware ro.hardware
- 获取系统版本 ro.build.version.release
- 获取SDK版本 ro.build.version.sdk
- 获取手机品牌 ro.product.brand
- 获取手机型号 ro.product.model
- 获取设备ROM名 ro.build.display.id
- 获取屏幕大小 ro.product.screensize

# 通过dumpsys activity top 获取当前activity名
adb shell
- android8.0以下: dumpsys activity top | grep ACTIVITY
- android8.0以上(MOVE_TO_FOREGROUND倒数第一条记录): dumpsys usagestats | grep MOVE_TO_FOREGROUND | tail -1 | awk -F' ' '{print $5}' | awk -F'=' '{print $2}'
 
# 获取进程信息
adb shell ps | grep packagename

# app启动
adb shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {app_id}/{main_activity}
adb shell am start -W -n {app_id}/.MainActivityV2

# 杀死指定包的进程
adb shell am force-stop {packagename}
# 杀死包含指定进程
adb shell kill {pid}

# 获取已安装app列表(非系统APP)
adb shell pm list packages -3

# 重启手机, boot_type: "bootloader", "recovery", or "None"
adb reboot (+boot_type)

# 磁盘可用存储大小
adb shell df | grep emulated | grep -v denied | head -n 1 | awk '{print $4}'

# 返回电池信息, 包括电量level / 温度temperature / 等
adb shell dumpsys battery

# 获取WiFi连接状态
adb shell ip -f inet addr | grep wlan0

# APP信息获取
adb shell 
- 获取设备apk包地址: pm path {app_id}
- 包信息: pm dump {app_id}，比如 APP版本versionName

# 获取APP性能数据
adb shell 
- 进程内存（应用进程pid）: dumpsys meminfo {pid}
- CPU占用: top -b -n 1 -d 1 或 top -n 1 -d 1

# Wi-Fi或数据流量开关（ROOT权限）
adb shell 
- 开Wi-Fi：svc wifi enable
- 关Wi-Fi：svc wifi disable
- 开流量：svc data enable
- 关流量：svc data disable

# 代理设置/清空
adb shell
- 设置代理: settings put global http_proxy 192.168.31.160
- 清空代理: settings put global http_proxy :0

# 坐标触摸事件
adb shell input tap 300 300

# 获取当前Activity控件树
adb shell 
- dump页面树: exec-out uiautomator dump /dev/tty
- 其它方式: uiautomator dump /data/local/tmp/uidump-{0}-{1}.xml
```

# **ioskit**: iOS设备操作指令方法

**IDBKit**: 

[tidevice](https://github.com/alibaba/taobao-iphone-device): 开源iOS设备操作工具包

[biplist](https://github.com/wooster/biplist): 基于python的二进制解析和生产工具

```shell
# 获取设备信息, 包括设备类型(iPhone｜iPad) / 系统版本 / cpu架构
tidevice --udid {sn} info | grep -E 'ProductType|ProductVersion|CPUArchitecture' | awk -F: '{print $2}'

# 获取APP信息: 解析ipa包中的 ".*.app/Info.plist" 二进制文件获取
- CFBundleDisplayName 应用展示的名称
- CFBundleShortVersionString
- CFBundleIdentifier ipa包名, 应用的唯一标识
- CFBundleVersion 版本号, 项目版本号

# APP 卸载/安装
tidevice --udid {sn} uninstall/install {BundleId}

# 重启设备
idevicediagnostics restart -u {sn}


```
