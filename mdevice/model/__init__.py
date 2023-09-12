class AppInfo:
    """
    Class AppInfo
    store info of an app

    You can expand this class for future,
    but remember to set a default value and add more attrs in the end of params list
    """

    def __init__(self, app_id: str = "", version: str = "", name: str = "", bundle_version: str = "",
                 main_activity: str = ""):
        """
        :param app_id:       bundle_id of app
        :param version:         app's version (e.g. 6.12.0)
        :param name:            app's name
        :param bundle_version:  app's bundle version (e.g. 10320)
        """
        self.app_id = app_id
        self.version = version
        self.name = name
        self.bundle_version = bundle_version
        self.main_activity = main_activity


class DeviceInfo:
    """
    Class DeviceInfo:
    store information of a device

    You can expand this class for future,
    but remember to set a default value and add more attrs in the end of params list
    """

    def __init__(self, sn: str = "", model: str = "", brand: str = "", os_type: str = "", task_type: str = "",
                 market_name: str = "", cpu_abi: str = "", os_version: str = "", sdk_version: str = "",
                 rom_version: str = "", cpu_hardware: str = "", device_hub_ip: str = "", display: str = ""):
        """
        :param sn:            sn for iPhone, use "idevice_id -l" to check
        :param model:           model of phone, e.g. iPhoneX
        :param brand:           brand of phone, e.g. iPhone
        :param os_type:         operating system, e.g. iOS
        :param task_type:       device rank, belongs to [low-perf, middle-perf, high-perf]
        """
        self.sn = sn
        self.model = model
        self.brand = brand
        self.os_type = os_type
        self.task_type = task_type
        self.market_name = market_name
        self.cpu_abi = cpu_abi
        self.os_version = os_version
        self.sdk_version = sdk_version
        self.rom_version = rom_version
        self.cpu_hardware = cpu_hardware
        self.device_hub_ip = device_hub_ip
        self.display = display
