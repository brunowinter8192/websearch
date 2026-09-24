__author__ = 'JHao'

import re
from requests import head
from curl_cffi import requests as cffi_requests
from util.six import withMetaclass
from util.singleton import Singleton
from handler.configHandler import ConfigHandler

conf = ConfigHandler()

HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
          'Accept': '*/*',
          'Connection': 'keep-alive',
          'Accept-Language': 'zh-CN,zh;q=0.8'}

IP_REGEX = re.compile(r"(.*:.*@)?\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}")


class ProxyValidator(withMetaclass(Singleton)):
    pre_validator = []
    http_validator = []
    https_validator = []

    @classmethod
    def addPreValidator(cls, func):
        cls.pre_validator.append(func)
        return func

    @classmethod
    def addHttpValidator(cls, func):
        cls.http_validator.append(func)
        return func

    @classmethod
    def addHttpsValidator(cls, func):
        cls.https_validator.append(func)
        return func


@ProxyValidator.addPreValidator
def formatValidator(proxy):
    return True if IP_REGEX.fullmatch(proxy) else False


def httpTimeOutValidator(proxy):
    proxies = {"http": "http://{proxy}".format(proxy=proxy), "https": "https://{proxy}".format(proxy=proxy)}
    try:
        r = head(conf.httpUrl, headers=HEADER, proxies=proxies, timeout=conf.verifyTimeout)
        return True if r.status_code == 200 else False
    except Exception as e:
        return False


def httpsTimeOutValidator(proxy):
    proxies = {"http": "http://{proxy}".format(proxy=proxy), "https": "https://{proxy}".format(proxy=proxy)}
    try:
        r = head(conf.httpsUrl, headers=HEADER, proxies=proxies, timeout=conf.verifyTimeout, verify=False)
        return True if r.status_code == 200 else False
    except Exception as e:
        return False


def customValidatorExample(proxy):
    return True


@ProxyValidator.addHttpValidator
def theblockValidator(proxy):
    purl = "http://%s" % proxy
    try:
        s = cffi_requests.Session(impersonate="chrome")
        r = s.get(
            "https://www.theblock.co/sitemap_tbco_index.xml",
            proxies={"http": purl, "https": purl},
            timeout=15,
        )
        head_bytes = r.content[:500]
        return r.status_code == 200 and (
            b"<?xml" in head_bytes
            or b"<sitemapindex" in head_bytes
            or b"<urlset" in head_bytes
            or b"<sitemap>" in head_bytes
        )
    except Exception:
        return False
