#!/usr/bin/env python
# -*- coding: utf-8 -*-
import encodings.utf_8
from typing import Optional, Any

import requests
from requests.structures import CaseInsensitiveDict

from mdevice.tools.log import LogUtils

UTF8: str = encodings.utf_8.getregentry().name

logger = LogUtils.LOGGER_DEBUG


class RequestUtils:

    @staticmethod
    def _safe_req(method: str, url: str, timeout: int, **kwargs) -> Optional[requests.Response]:
        for i in range(3):
            try:
                res = requests.request(method, url, timeout=timeout, **kwargs)
                logger.info(f'{res.status_code}; {res.elapsed.total_seconds():.3f}s; {method.upper()}: {url}')
                # might be '201 Created' or something like that
                if res.status_code < 200 or res.status_code > 207:
                    raise requests.RequestException()
                return res
            except requests.RequestException:
                logger.warning(f'{method.upper()} fails {(i + 1)}: {url}')

    @classmethod
    def safe_head_ori(cls, url: str, timeout: int = 10, **kwargs) -> Optional[requests.Response]:
        """
        HEAD 请求

        :param url: URL
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: Response 对象
        """
        kwargs.setdefault('allow_redirects', False)
        return cls._safe_req(
            method='head',
            url=url,
            timeout=timeout,
            **kwargs)

    @classmethod
    def safe_head(cls, url: str, timeout: int = 10, **kwargs) -> Optional[CaseInsensitiveDict]:
        """
        HEAD 请求

        :param url: URL
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: Headers
        """
        res = cls.safe_head_ori(
            url=url,
            timeout=timeout,
            **kwargs)
        return (res and res.status_code == 200 and res.headers) or None

    @classmethod
    def safe_get_ori(cls, url: str, params: dict = None, timeout: int = 10, headers: dict = None, data: Any = None,
                     json: Any = None, **kwargs) -> Optional[requests.Response]:
        """
        GET 请求

        :param url: URL
        :param params: 请求参数
        :param headers: 请求头
        :param data: 请求体 (JSON 字串, 文件等)
        :param json: 请求体 (字典)
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: Response 对象
        """
        kwargs.setdefault('allow_redirects', True)
        return cls._safe_req(
            method='get',
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            **kwargs)

    @classmethod
    def safe_get_raw(cls, url: str, params: dict = None, timeout: int = 10, headers: dict = None, data: Any = None,
                     json: Any = None, **kwargs) -> Optional[bytes]:
        """
        GET 请求

        默认允许重定向

        :param url: URL
        :param params: 请求参数
        :param headers: 请求头
        :param data: 请求体 (JSON 字串, 文件等)
        :param json: 请求体 (字典)
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: 响应体 (bytes)
        """
        res = cls.safe_get_ori(
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            **kwargs)
        return (res and res.status_code == 200 and res.content) or None

    @classmethod
    def safe_get_str(cls, url: str, params: dict = None, timeout: int = 10, headers: dict = None, data: Any = None,
                     json: Any = None, **kwargs) -> Optional[str]:
        """
        GET 请求

        默认允许重定向

        :param url: URL
        :param params: 请求参数
        :param headers: 请求头
        :param data: 请求体 (JSON 字串, 文件等)
        :param json: 请求体 (字典)
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: 响应体 (UTF-8 字串)
        """
        raw: Optional[bytes] = cls.safe_get_raw(
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            **kwargs
        )
        if not raw:
            return
        try:
            return raw.decode(encoding=UTF8)
        except UnicodeError as e:
            logger.debug(e)

    @classmethod
    def safe_get(cls, url: str, params: dict = None, timeout: int = 10, headers: dict = None, data: Any = None,
                 json: Any = None, **kwargs) -> Optional[dict]:
        """
        GET 请求

        默认允许重定向

        :param url: URL
        :param params: 请求参数
        :param headers: 请求头
        :param data: 请求体 (JSON 字串, 文件等)
        :param json: 请求体 (字典)
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: 响应体 (JSON)
        """
        res = cls.safe_get_ori(
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            **kwargs)
        if res and res.status_code == 200:
            res_body = res.json()
            # might be a JSON-array
            if isinstance(res_body, dict):
                # bilibili standard
                res_code = res_body.get('code')
                res_msg = res_body.get('message')
                if res_code:
                    logger.debug(f'code: {res_code}; msg: {res_msg}')
            return res_body

    safe_get_json = safe_get

    @staticmethod
    def safe_post_ori(url: str, data: Any = None, json: Any = None, timeout: int = 10, headers: dict = None,
                      params: dict = None, **kwargs) -> requests.Response:
        """
        POST 请求

        :param url: URL
        :param params: 请求参数
        :param headers: 请求头
        :param data: 请求体 (JSON 字串, 文件等)
        :param json: 请求体 (字典)
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: Response 对象
        """
        return RequestUtils._safe_req(
            method='post',
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            **kwargs
        )

    @classmethod
    def safe_post(cls, url: str, data: Any = None, json: Any = None, timeout: int = 10, headers: dict = None,
                  params: dict = None, **kwargs) -> Optional[dict]:
        """
        POST 请求

        :param url: URL
        :param params: 请求参数
        :param headers: 请求头
        :param data: 请求体 (JSON 字串, 文件等)
        :param json: 请求体 (字典)
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: 响应体
        """
        res = cls.safe_post_ori(
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            timeout=timeout,
            **kwargs
        )
        if res and res.status_code == 200:
            res_body = res.json()
            # might be a JSON-array
            if isinstance(res_body, dict):
                # bilibili standard
                res_code = res_body.get('code')
                res_msg = res_body.get('message')
                if res_code:
                    logger.debug(f'code: {res_code}; msg: {res_msg}')
            return res_body
        else:
            return None

    @staticmethod
    def safe_delete(url: str, timeout: int = 10, **kwargs) -> Optional[dict]:
        """
        DELETE 请求

        :param url: URL
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: 响应体
        """
        res = RequestUtils._safe_req(
            method='delete',
            url=url,
            timeout=timeout,
            **kwargs
        )
        return (res and res.status_code == 200 and res.json()) or None

    @staticmethod
    def safe_put(url: str, timeout: int = 10, **kwargs) -> Optional[dict]:
        """
        PUT 请求

        :param url: URL
        :param timeout: 超时时长
        :param kwargs: 其余 kv 参数
        :return: 响应体
        """
        res = RequestUtils._safe_req(
            method='put',
            url=url,
            timeout=timeout,
            **kwargs
        )
        return (res and res.status_code == 200 and res.json()) or None
