import json
import time
import random
import logging
import hashlib
import re
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
    """
    High-level MTOP client supporting two operating modes:
    1. Pure Python Mode (Default, Plug-and-Play):
       - Requires NO Android device, NO Frida, NO phone setup.
       - Signs requests via pure MD5 and rotates residential proxies.
    2. Android RPC Mode (Advanced):
       - Uses connected Android Frida node to generate WUA device signatures.
    """
    def __init__(self):
        self.proxies = settings.PROXIES
        self.app_key = "12574478"
        self.session = requests.Session()
        self.rpc_signer = None

        # Check if Frida node is available
        try:
            self.rpc_signer = RpcSigner.get_instance()
            if not self.rpc_signer.connect():
                self.rpc_signer = None
        except Exception:
            self.rpc_signer = None

    def get_proxy(self) -> Optional[Dict[str, str]]:
        if not self.proxies:
            return None
        p = random.choice(self.proxies)
        return {"http": p, "https": p}

    def _ensure_h5_token(self, proxy: Optional[Dict[str, str]]) -> str:
        cookies = self.session.cookies.get_dict()
        if "_m_h5_tk" in cookies:
            return cookies["_m_h5_tk"].split("_")[0]

        # Init token via lightweight handshake
        init_url = "https://h5api.m.taobao.com/h5/mtop.taobao.wsearch.appsearch/1.0/?data=%7B%7D"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://www.taobao.com/"
        }
        try:
            r = self.session.get(init_url, headers=headers, proxies=proxy, timeout=settings.REQUEST_TIMEOUT, impersonate="chrome124")
            cookies = self.session.cookies.get_dict()
            if "_m_h5_tk" in cookies:
                return cookies["_m_h5_tk"].split("_")[0]
        except Exception as e:
            logger.warning(f"Error initializing H5 token: {e}")

        return ""

    def _call_h5_api(self, api: str, v: str, data: Dict[str, Any], referer: str = "https://www.taobao.com/") -> Dict[str, Any]:
        proxy = self.get_proxy()
        token = self._ensure_h5_token(proxy)

        data_str = json.dumps(data, separators=(',', ':'))
        t = str(int(time.time() * 1000))
        sign_str = f"{token}&{t}&{self.app_key}&{data_str}"
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        url = f"https://h5api.m.taobao.com/h5/{api}/{v}/"
        headers = {
            "Host": "h5api.m.taobao.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": referer,
            "Accept": "*/*"
        }
        params = {
            "jsv": "2.7.2",
            "appKey": self.app_key,
            "t": t,
            "sign": sign,
            "api": api,
            "v": v,
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": "mtopjsonp1",
            "data": data_str
        }

        resp = self.session.get(url, params=params, headers=headers, proxies=proxy, timeout=settings.REQUEST_TIMEOUT, impersonate="chrome124")
        
        # Parse JSONP or JSON response
        text = resp.text
        m = re.search(r'mtopjsonp\d*\((.*)\)', text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        try:
            return resp.json()
        except Exception:
            return {"raw_text": text}

    def search(self, keyword: str, page: int = 1) -> List[SearchItem]:
        api = "mtop.taobao.wsearch.appsearch"
        v = "1.0"
        data = {
            "q": keyword,
            "page": str(page),
            "tab": "all",
            "sort": "default"
        }

        # If RPC node connected and no proxy specified, use RPC
        if self.rpc_signer and not self.proxies:
            rpc_res = self.rpc_signer.execute_api(api, v, data)
            body = rpc_res.get("body", "{}")
            raw = json.loads(body) if body else {}
        else:
            raw = self._call_h5_api(api, v, data, referer="https://s.taobao.com/")

        return parse_search_response(raw)

    def get_detail(self, item_id: str) -> ProductDetail:
        api = "mtop.taobao.detail.getdetail"
        v = "6.0"
        data = {"itemNumId": str(item_id)}

        if self.rpc_signer and not self.proxies:
            rpc_res = self.rpc_signer.execute_api(api, v, data)
            body = rpc_res.get("body", "{}")
            raw = json.loads(body) if body else {}
        else:
            raw = self._call_h5_api(api, v, data, referer=f"https://item.taobao.com/item.htm?id={item_id}")

        return parse_detail_response(raw)

    def get_reviews(self, item_id: str, page: int = 1) -> List[ProductReview]:
        api = "mtop.taobao.detail.getrate"
        v = "1.0"
        data = {
            "auctionNumId": str(item_id),
            "pageNo": page,
            "pageSize": 20
        }

        if self.rpc_signer and not self.proxies:
            rpc_res = self.rpc_signer.execute_api(api, v, data)
            body = rpc_res.get("body", "{}")
            raw = json.loads(body) if body else {}
        else:
            raw = self._call_h5_api(api, v, data, referer=f"https://item.taobao.com/item.htm?id={item_id}")

        return parse_review_response(raw)
