import functools
import time

from mdevice.tools.log import LogUtils

logger = LogUtils.LOGGER


def time_cost(info="函数function"):
    """
    打印函数执行时间的装饰器
    :param info:
    :return:
    """
    def _time_me(fn):
        @functools.wraps(fn)
        def _wrapper(*args, **kwargs):
            # 返回性能计数器的值（以小数秒为单位）作为浮点数，包含sleep()休眠时间，适用测量短持续时间
            start = time.perf_counter()
            res = fn(*args, **kwargs)
            logger.debug("%s 耗时：%s" % (info, round(time.perf_counter() - start, 2)), "second")
            return res

        return _wrapper

    return _time_me
