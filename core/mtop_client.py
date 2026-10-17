import json
import time
import random
import logging
from typing import Dict, Any, List, Optional
from curl_cffi import requests

from config import settings
from core.rpc_signer import RpcSigner
from core.parser import (
    parse_search_response, 
    parse_detail_response, 
    parse_review_response,
    ProductDetail,
    SearchItem,
    ProductReview
)

logger = logging.getLogger("mtop_client")

class MtopClient:
    def __init__(self):
        self.signer = RpcSigner.get_instance()
        self.proxies = settings.PROXIES

    def get_proxy(self) -> Optional[Dict[str, str]]:
        if not self.proxies:
            return None
        p = random.choice(self.proxies)
        return {"http": p, "https": p}

    def search(self, keyword: str, page: int = 1) -> List[SearchItem]:
        api = "mtop.taobao.wsearch.appsearch"
        v = "1.0"
        data = {
            "q": keyword,
            "page": page,
            "tab": "all",
            "sort": "default"
        }

        # Check if proxy pool is configured
        proxy = self.get_proxy()
        if proxy:
            # Send via Python HTTP using Proxy + Frida RPC Signer
            t_str = str(int(time.time()))
            data_str = json.dumps(data, separators=(',', ':'))
            sign_meta = self.signer.sign_payload(api, v, data_str, t_str)
            signs = sign_meta.get("signs", {})

            url = f"https://guide-acs.m.taobao.com/gw/{api}/{v}/"
            headers = {
                "x-appkey": sign_meta["appKey"],
                "x-t": t_str,
                "x-pv": "6.3",
                "x-sign": signs.get("x-sign", ""),
                "x-mini-wua": signs.get("x-mini-wua", ""),
                "x-sgext": signs.get("x-sgext", ""),
                "x-umt": signs.get("x-umt", ""),
                "x-ttid": sign_meta["ttid"],
                "x-utdid": sign_meta["utdid"],
                "x-devid": sign_meta["deviceId"],
                "x-app-ver": "10.66.40",
                "User-Agent": "MTOPSDK/3.1.1.7 (Android;12;samsung;SM-A546E)",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            }
            resp = requests.post(url, headers=headers, data={"data": data_str}, proxies=proxy, timeout=settings.REQUEST_TIMEOUT)
            raw = resp.json()
        else:
            # Direct Node Execution via Android RPC
            rpc_res = self.signer.execute_api(api, v, data)
            body = rpc_res.get("body", "{}")
            raw = json.loads(body) if body else {}

        return parse_search_response(raw)

    def get_detail(self, item_id: str) -> ProductDetail:
        api = "mtop.taobao.detail.getdetail"
        v = "6.0"
        data = {"itemNumId": str(item_id)}

        proxy = self.get_proxy()
        if proxy:
            t_str = str(int(time.time()))
            data_str = json.dumps(data, separators=(',', ':'))
            sign_meta = self.signer.sign_payload(api, v, data_str, t_str)
            signs = sign_meta.get("signs", {})

            url = f"https://guide-acs.m.taobao.com/gw/{api}/{v}/"
            headers = {
                "x-appkey": sign_meta["appKey"],
                "x-t": t_str,
                "x-pv": "6.3",
                "x-sign": signs.get("x-sign", ""),
                "x-mini-wua": signs.get("x-mini-wua", ""),
                "x-sgext": signs.get("x-sgext", ""),
                "x-umt": signs.get("x-umt", ""),
                "x-ttid": sign_meta["ttid"],
                "x-utdid": sign_meta["utdid"],
                "x-devid": sign_meta["deviceId"],
                "x-app-ver": "10.66.40",
                "User-Agent": "MTOPSDK/3.1.1.7 (Android;12;samsung;SM-A546E)",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            }
            resp = requests.post(url, headers=headers, data={"data": data_str}, proxies=proxy, timeout=settings.REQUEST_TIMEOUT)
            raw = resp.json()
        else:
            rpc_res = self.signer.execute_api(api, v, data)
            body = rpc_res.get("body", "{}")
            raw = json.loads(body) if body else {}

        return parse_detail_response(raw)

    def get_reviews(self, item_id: str, page: int = 1) -> List[ProductReview]:
        api = "mtop.taobao.detail.getrate"
        v = "1.0"
        data = {
            "auctionNumId": str(item_id),
            "pageNo": page,
            "pageSize": 20
        }

        proxy = self.get_proxy()
        if proxy:
            t_str = str(int(time.time()))
            data_str = json.dumps(data, separators=(',', ':'))
            sign_meta = self.signer.sign_payload(api, v, data_str, t_str)
            signs = sign_meta.get("signs", {})

            url = f"https://guide-acs.m.taobao.com/gw/{api}/{v}/"
            headers = {
                "x-appkey": sign_meta["appKey"],
                "x-t": t_str,
                "x-pv": "6.3",
                "x-sign": signs.get("x-sign", ""),
                "x-mini-wua": signs.get("x-mini-wua", ""),
                "x-sgext": signs.get("x-sgext", ""),
                "x-umt": signs.get("x-umt", ""),
                "x-ttid": sign_meta["ttid"],
                "x-utdid": sign_meta["utdid"],
                "x-devid": sign_meta["deviceId"],
                "x-app-ver": "10.66.40",
                "User-Agent": "MTOPSDK/3.1.1.7 (Android;12;samsung;SM-A546E)",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
            }
            resp = requests.post(url, headers=headers, data={"data": data_str}, proxies=proxy, timeout=settings.REQUEST_TIMEOUT)
            raw = resp.json()
        else:
            rpc_res = self.signer.execute_api(api, v, data)
            body = rpc_res.get("body", "{}")
            raw = json.loads(body) if body else {}

        return parse_review_response(raw)
