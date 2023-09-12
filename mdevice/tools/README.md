# 通用工具库

**log.LogUtils**：日志输出模块, 基于开源项目 [logzero](https://github.com/metachris/logzero) 实现

**usb.USBHelper**：基于指令 [lsusb](https://github.com/jlhonora/lsusb) 实现USB设备和属性管理模块(查询 & 重置)（PS：使用前需本地安装lsusb指令）
```shell
# lsusb: 用于显示本机的USB设备列表, 以及USB的详细信息
# Mac 安装: 
brew update && brew tap jlhonora/lsusb && brew install lsusb

# 使用简介: https://juejin.cn/post/7116329514107404319
```

**host.HostToolKit**：基于 [socket](https://docs.python.org/3/library/socket.html) 获取本机IP和计算机名称

**timer.time_cost**：基于time.perf_counter方法实现打印函数执行时间的装饰器，其他[统计方法参考](https://blog.csdn.net/qq_27283619/article/details/89280974)

**request.RequestUtils**：基于 [requests](https://requests.readthedocs.io/en/latest/) 模块的网络处理函数(重试3次), 包括 HEAD / GET / POST / DELETE / PUT

**apkparse.Manifest**：基于 [pyaxmlparser](https://github.com/appknox/pyaxmlparser/tree/master) 模块解析Android apk中AndroidManifest.xml文件获取包信息，包括包名 / 版本 / Main-activity名称，其它相似工具包[apkutils](https://github.com/kin9-0rz/apkutils)

**cmdit.CmdKit**：基于 [subprocess](https://docs.python.org/3/library/subprocess.html) 模块封装执行终端cmd指令(或下载http资源文件)，并返回命令输出的内容

**utils**：
* **TimeUtils**：格式化输出指定日期格式, 如：2023_09_12_16_10_30 / 2023-09-12 16:10:30
* **FileUtils**：文件操作方法集合, 包括 递归遍历目录，返回匹配的文件路径, 获取文件的大小(单位: MB) / 访问时间 / 创建时间 / 修改时间
* **ZipUtils**：基于 [zipfile](https://docs.python.org/3/library/zipfile.html) 模块实现zip文件解压缩
