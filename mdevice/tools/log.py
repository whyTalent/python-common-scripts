#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from typing import ClassVar, Dict, Optional

from logzero import LogFormatter, setup_logger
from logzero.colors import Fore as ForegroundColors


# 功能: 日志输出模块, 基于开源项目: https://github.com/metachris/logzero
class LogUtils:
    _DEFAULT_FORMAT: ClassVar[str] = \
        '%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s'
    _DEFAULT_DATE_FORMAT: ClassVar[str] = '%y-%m-%d %H:%M:%S'
    _DEFAULT_COLORS: ClassVar[Dict] = {
        logging.DEBUG: ForegroundColors.CYAN,
        logging.INFO: ForegroundColors.GREEN,
        logging.WARNING: ForegroundColors.YELLOW,
        logging.ERROR: ForegroundColors.RED
    }
    # 彩色模式
    _COLOR_FORMATTER: ClassVar[LogFormatter] = LogFormatter(color=True, fmt=_DEFAULT_FORMAT,
                                                            datefmt=_DEFAULT_DATE_FORMAT, colors=_DEFAULT_COLORS)
    # 黑白模式
    _BW_FORMATTER: ClassVar[LogFormatter] = LogFormatter(color=False, fmt=_DEFAULT_FORMAT, datefmt=_DEFAULT_DATE_FORMAT)

    LEVEL_DEBUG: ClassVar[int] = logging.DEBUG
    LEVEL_INFO: ClassVar[int] = logging.INFO
    LEVEL_WARNING: ClassVar[int] = logging.WARNING
    LEVEL_ERROR: ClassVar[int] = logging.ERROR

    @classmethod
    def get_logger(cls, name: Optional[str] = None, logfile: Optional[str] = None,
                   level: int = logging.INFO) -> logging.Logger:
        """
        创建新 logger; 向控制台输出带色彩, 向文件输出为黑白

        :param name: logger 名称
        :param logfile: 日志文件路径, 有此参数会向相应文件追加日志, 且日志不带色彩
        :param level: 日志最低显示级别
        :return: logger
        """
        if logfile is None:
            return setup_logger(name=name, level=level, formatter=cls._COLOR_FORMATTER)
        else:
            return setup_logger(name=name, logfile=logfile, level=level, formatter=cls._BW_FORMATTER)

    LOGGER: ClassVar[logging.Logger] = setup_logger(name='LogUtils_info', level=LEVEL_INFO, formatter=_COLOR_FORMATTER)
    """info 级别 logger"""

    LOGGER_DEBUG: ClassVar[logging.Logger] = setup_logger(name='LogUtils_debug', level=LEVEL_DEBUG,
                                                          formatter=_COLOR_FORMATTER)
    """debug 级别 logger"""

    LOGGER_WARNING: ClassVar[logging.Logger] = setup_logger(name='LogUtils_warning', level=LEVEL_WARNING,
                                                            formatter=_COLOR_FORMATTER)
    """warning 级别 logger"""
