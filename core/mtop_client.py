import json
import time
import random
import logging
import hashlib
import re
import os
from typing import Dict, Any, List, Optional
from curl_cffi import requests

from config import settings
from core.rpc_signer import RpcSigner
try:
    from core.unidbg_signer import UnidbgSigner
except ImportError:
    UnidbgSigner = None
from core.parser import (
    parse_search_response, 
    parse_detail_response, 
    parse_review_response,
    ProductDetail,
    SearchItem,
    ProductReview,
    SkuVariant
)
from core.captcha_solver import CaptchaSolver

logger = logging.getLogger("mtop_client")

class MtopClient:
    """
    High-level MTOP client supporting multiple execution backends:
    1. Unidbg Pure ARM Mode (Top tier, Zero Phone/Zero Cookie):
       - Emulates ARM CPU in memory running official libsgmain.so (SecurityGuard 6.8).
       - Generates authentic x-sign, wua, x-mini-wua cryptographic tokens.
    2. Pure Python / Residential Proxy Mode:
       - Plug-and-play with rotating China residential proxies.
    3. Android Frida RPC Mode (Optional hardware fallback).
    """
    def __init__(self):
        self.proxies = settings.PROXIES
        self.app_key = "12574478"
        self.session = requests.Session()
        self.unidbg_signer = UnidbgSigner.get_instance()
        self.rpc_signer = None

        # Check if Frida node is optionally available
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

    def _update_session_cookies(self, new_cookie_str: str):
        """
        Merges new cookies (especially x5sec) into active session,
        settings.COOKIE, and persists to working_cookie.txt.
        """
        if not new_cookie_str:
            return
            
        new_parts = [p.strip() for p in new_cookie_str.split(";") if p.strip()]
        new_dict = {}
        for p in new_parts:
            if "=" in p:
                k, v = p.split("=", 1)
                new_dict[k.strip()] = v.strip()
                
        existing_dict = {}
        if settings.COOKIE:
            for p in settings.COOKIE.split(";"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    existing_dict[k.strip()] = v.strip()
                    
        existing_dict.update(new_dict)
        merged_str = "; ".join([f"{k}={v}" for k, v in existing_dict.items()])
        settings.COOKIE = merged_str
        
        try:
            with open("working_cookie.txt", "w", encoding="utf-8") as f:
                f.write(merged_str)
        except Exception as e:
            logger.warning(f"Failed to persist working_cookie.txt: {e}")
            
        logger.info(f"[+] Cookies updated and persisted! Has x5sec: {'x5sec' in existing_dict}")

    def _call_h5_api(self, api: str, v: str, data: Dict[str, Any], referer: str = "https://www.taobao.com/", cookie: Optional[str] = None, retry_count: int = 0) -> Dict[str, Any]:
        proxy = self.get_proxy()
        # Sanitize cookie if user accidentally left Swagger placeholder
        if cookie and cookie.strip().lower() in ["cookie", "string", "none", "null", "undefined"]:
            cookie = None
        active_cookie = cookie or settings.COOKIE
        token = ""
        if active_cookie:
            m_token = re.search(r'_m_h5_tk=([a-f0-9]+)', active_cookie)
            if m_token:
                token = m_token.group(1)
        if not token:
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
        if active_cookie:
            headers["cookie"] = active_cookie
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
        res_data = None
        m = re.search(r'mtopjsonp\d*\((.*)\)', text)
        if m:
            try:
                res_data = json.loads(m.group(1))
            except Exception:
                pass

        if res_data is None:
            try:
                res_data = resp.json()
            except Exception:
                res_data = {"raw_text": text}

        # Check if RGV587 or punish challenge is returned
        ret_list = res_data.get("ret", []) if isinstance(res_data, dict) else []
        is_blocked = (
            any("RGV587" in str(r) for r in ret_list) or 
            "set_x5referer" in text or 
            "_____tmd_____" in text or 
            "RGV587" in text
        )

        if is_blocked and retry_count < 1:
            logger.info("[*] Detected Taobao WAF Challenge (RGV587 / set_x5referer). Invoking CaptchaSolver...")
            punish_url = None
            if isinstance(res_data, dict) and isinstance(res_data.get("data"), dict):
                punish_url = res_data["data"].get("url")
            
            if not punish_url:
                url_m = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', text)
                if url_m:
                    punish_url = url_m.group(1)
                else:
                    url_m = re.search(r'["\'](https?://[^"\']*set_x5referer[^"\']*)["\']', text)
                    if url_m:
                        punish_url = url_m.group(1)
                    else:
                        url_m = re.search(r'["\'](https?://[^"\']*_____tmd_____[^"\']*)["\']', text)
                        if url_m:
                            punish_url = url_m.group(1)

            if punish_url:
                proxy_str = settings.PROXIES[0] if settings.PROXIES else None
                new_cookie = CaptchaSolver.get_instance().solve_punish_url(punish_url, proxy_url=proxy_str)
                if new_cookie:
                    self._update_session_cookies(new_cookie)
                    logger.info("[+] Captcha solved! Retrying API request with new session cookie...")
                    return self._call_h5_api(api, v, data, referer=referer, cookie=cookie, retry_count=retry_count + 1)
                else:
                    logger.warning("[-] Captcha solver failed to acquire x5sec token.")
            else:
                logger.warning("[-] Could not parse punish URL from response to solve captcha.")

        if is_blocked:
            return {
                "ret": ["RGV587_ERROR::SM::哎哟喂,被挤爆啦,请稍后重试!"],
                "data": {},
                "raw_text": text
            }

        return res_data

    def _call_native_mtop(self, api: str, v: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls native MTOP gateway (guide-acs.m.taobao.com or trade-acs.m.taobao.com)
        using authentic ARM CPU SecurityGuard signatures generated by Unidbg in-memory daemon.
        """
        if not self.unidbg_signer or not self.unidbg_signer.is_available():
            return {}

        t = str(int(time.time()))
        data_str = json.dumps(data, separators=(',', ':'))
        sign_info = self.unidbg_signer.sign(api, v, data, t)
        x_sign = sign_info.get("x_sign", "")
        wua = sign_info.get("wua", "")
        x_mini_wua = sign_info.get("x_mini_wua", "")

        host = "guide-acs.m.taobao.com" if "wsearch" in api else "trade-acs.m.taobao.com"
        headers = {
            "x-appkey": "21646297",
            "x-ttid": "701188@taobao_android_10.36.20",
            "x-utdid": "Z074F9P6hEMDAN87W/qL8z2k",
            "x-t": t,
            "x-sign": x_sign,
            "x-pv": "6.3",
            "x-features": "27",
            "x-mini-wua": x_mini_wua,
            "wua": wua,
            "f-refer": "mtop",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": "MTOPSDK/3.1.1.7 (Android;10;Xiaomi;MI 8)",
            "Host": host
        }
        url = f"https://{host}/gw/{api}/{v}/"
        proxy = self.get_proxy()
        try:
            r = self.session.post(url, headers=headers, data={"data": data_str}, proxies=proxy, timeout=settings.REQUEST_TIMEOUT)
            return r.json()
        except Exception as e:
            logger.debug(f"Native MTOP call notice: {e}")
            return {}

    def search(self, keyword: str, page: int = 1, cookie: Optional[str] = None) -> List[SearchItem]:
        api = "mtop.taobao.wsearch.appsearch"
        v = "1.0"
        data = {
            "q": keyword,
            "page": str(page),
            "tab": "all",
            "sort": "default"
        }

        raw = {}
        # 1. If Cookie is explicitly provided, prioritize H5 gateway with session
        if cookie and cookie.strip().lower() not in ["cookie", "string", "none", "null", "undefined"]:
            raw = self._call_h5_api(api, v, data, referer="https://s.taobao.com/", cookie=cookie)
        else:
            # 2. Try native ARM Unidbg signer first (Zero Cookie mode)
            if self.unidbg_signer and self.unidbg_signer.is_available():
                native_raw = self._call_native_mtop(api, v, data)
                ret_native = native_raw.get("ret", [])
                if any("SUCCESS" in str(r) for r in ret_native) or native_raw.get("data"):
                    raw = native_raw

            # 3. Fallback to H5 gateway if native didn't produce data
            if not raw or not raw.get("data"):
                raw = self._call_h5_api(api, v, data, referer="https://s.taobao.com/", cookie=cookie)

        items = parse_search_response(raw)
        if not items:
            ret_list = raw.get("ret", [])
            raw_text = raw.get("raw_text", "")
            if any("RGV587" in str(r) for r in ret_list) or "set_x5referer" in raw_text or "_____tmd_____" in raw_text:
                raise ValueError("Taobao WAF chống bot (RGV587_ERROR::SM::哎哟喂,被挤爆啦): IP yêu cầu xác minh Captcha. Vui lòng cấu hình Proxy sạch hoặc nạp Cookie tại /api/v1/config/cookie.")
            elif any("FAIL_SYS_USER_VALIDATE" in str(r) for r in ret_list):
                raise ValueError("Cookie Taobao của bạn đã hết hạn (FAIL_SYS_USER_VALIDATE). Vui lòng cập nhật Cookie mới tại /api/v1/config/cookie.")
            elif any("FAIL_SYS_ILEGEL_SIGN" in str(r) for r in ret_list):
                raise ValueError("Lỗi chữ ký MTOP (FAIL_SYS_ILEGEL_SIGN::非法请求签名): Cần kiểm tra lại chữ ký hoặc cung cấp Cookie tài khoản.")
            elif ret_list:
                raise ValueError(f"Không có kết quả từ Taobao: {', '.join(ret_list)}")
            else:
                raise ValueError(f"Không tìm thấy sản phẩm nào cho từ khóa '{keyword}'.")

        return items

    def get_detail(self, item_id: str, cookie: Optional[str] = None) -> ProductDetail:
        api = "mtop.taobao.detail.getdetail"
        v = "6.0"
        data = {"itemNumId": str(item_id)}

        raw = {}
        if cookie and cookie.strip().lower() not in ["cookie", "string", "none", "null", "undefined"]:
            raw = self._call_h5_api(api, v, data, referer=f"https://item.taobao.com/item.htm?id={item_id}", cookie=cookie)
        else:
            if self.unidbg_signer and self.unidbg_signer.is_available():
                native_raw = self._call_native_mtop(api, v, data)
                ret_native = native_raw.get("ret", [])
                if any("SUCCESS" in str(r) for r in ret_native) or native_raw.get("data"):
                    raw = native_raw

            if not raw or not raw.get("data"):
                raw = self._call_h5_api(api, v, data, referer=f"https://item.taobao.com/item.htm?id={item_id}", cookie=cookie)

        detail = parse_detail_response(raw)
        if not detail.item_id:
            ret_list = raw.get("ret", [])
            raw_text = raw.get("raw_text", "")
            if any("RGV587" in str(r) for r in ret_list) or "set_x5referer" in raw_text or "_____tmd_____" in raw_text:
                raise ValueError(f"Không thể lấy chi tiết sản phẩm {item_id}: Taobao WAF yêu cầu trượt Captcha (RGV587_ERROR). Vui lòng cấu hình Proxy sạch hoặc nạp Cookie hợp lệ tại /api/v1/config/cookie.")
            elif any("FAIL_SYS_USER_VALIDATE" in str(r) for r in ret_list):
                raise ValueError(f"Không thể lấy chi tiết sản phẩm {item_id}: Cookie đã hết hạn (FAIL_SYS_USER_VALIDATE). Vui lòng cập nhật Cookie mới tại /api/v1/config/cookie.")
            elif any("FAIL_SYS_ILEGEL_SIGN" in str(r) for r in ret_list):
                raise ValueError(f"Lỗi chữ ký MTOP (FAIL_SYS_ILEGEL_SIGN::非法请求签名) khi truy vấn sản phẩm {item_id}.")
            elif ret_list:
                raise ValueError(f"Không thể lấy thông tin sản phẩm {item_id}. Phản hồi từ Taobao: {', '.join(ret_list)}")
            else:
                raise ValueError(f"Sản phẩm mã {item_id} không tồn tại hoặc đã bị xóa khỏi sàn Taobao.")
        return detail

    def get_reviews(self, item_id: str, page: int = 1, cookie: Optional[str] = None) -> List[ProductReview]:
        api = "mtop.taobao.detail.getrate"
        v = "1.0"
        data = {
            "auctionNumId": str(item_id),
            "pageNo": page,
            "pageSize": 20
        }

        raw = {}
        if cookie and cookie.strip().lower() not in ["cookie", "string", "none", "null", "undefined"]:
            raw = self._call_h5_api(api, v, data, referer=f"https://item.taobao.com/item.htm?id={item_id}", cookie=cookie)
        else:
            if self.unidbg_signer and self.unidbg_signer.is_available():
                native_raw = self._call_native_mtop(api, v, data)
                ret_native = native_raw.get("ret", [])
                if any("SUCCESS" in str(r) for r in ret_native) or native_raw.get("data"):
                    raw = native_raw

            if not raw or not raw.get("data"):
                raw = self._call_h5_api(api, v, data, referer=f"https://item.taobao.com/item.htm?id={item_id}", cookie=cookie)

        reviews = parse_review_response(raw)
        if not reviews:
            ret_list = raw.get("ret", [])
            raw_text = raw.get("raw_text", "")
            if any("RGV587" in str(r) for r in ret_list) or "set_x5referer" in raw_text or "_____tmd_____" in raw_text:
                raise ValueError(f"Không thể lấy đánh giá cho sản phẩm {item_id}: Taobao WAF yêu cầu xác minh Captcha (RGV587_ERROR). Vui lòng nạp Cookie tại /api/v1/config/cookie.")
            elif any("FAIL_SYS_USER_VALIDATE" in str(r) for r in ret_list):
                raise ValueError(f"Không thể lấy đánh giá cho sản phẩm {item_id}: Cookie đã hết hạn (FAIL_SYS_USER_VALIDATE).")
            elif any("FAIL_SYS_ILEGEL_SIGN" in str(r) for r in ret_list):
                raise ValueError(f"Lỗi chữ ký MTOP (FAIL_SYS_ILEGEL_SIGN::非法请求签名) khi lấy đánh giá cho {item_id}.")
            return []
        return reviews
