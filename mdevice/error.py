class AdbError(Exception):
    def __init__(self, info=''):
        self.info = info

    def __str__(self):
        return "[AdbError Error] %s" % self.info


class GracefulExitException(Exception):
    def __init__(self, info=''):
        self.info = info

    def __str__(self):
        return "[GracefulExitException Error] %s" % self.info


class YuuCommonIllegalArgumentError(Exception):
    pass
