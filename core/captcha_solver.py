import time
import random
import re
import logging
import urllib.parse
import concurrent.futures
from typing import Optional, Dict
from playwright.sync_api import sync_playwright

logger = logging.getLogger("captcha_solver")

def human_drag(page, slider_element, distance: float = 280.0) -> bool:
    """
    Simulates human-like mouse drag movement with acceleration, 
    deceleration near the end, and slight vertical jitter.
    """
    try:
        box = slider_element.bounding_box()
        if not box:
            return False
            
        start_x = box["x"] + box["width"] / 2
        start_y = box["y"] + box["height"] / 2
        
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        time.sleep(random.uniform(0.1, 0.2))
        
        current_x = start_x
        current_y = start_y
        remaining = distance
        
        while remaining > 0:
            step = random.uniform(8, 22)
            if remaining < 40:
                step = random.uniform(2, 7)  # Slow down as approaching target
            if step > remaining:
                step = remaining
                
            current_x += step
            current_y += random.uniform(-1.0, 1.0)  # Human hand jitter
            remaining -= step
            
            page.mouse.move(current_x, current_y)
            time.sleep(random.uniform(0.008, 0.022))
            
        time.sleep(random.uniform(0.15, 0.3))
        page.mouse.up()
        time.sleep(1.5)
        return True
    except Exception as e:
        logger.warning(f"human_drag error: {e}")
        return False

class CaptchaSolver:
    """
    Automated Headless Solver for Alibaba Baxia NC Slider (x5sec challenge).
    Intercepts RGV587 Punish URLs, solves slider, and extracts fresh x5sec cookie.
    """
    _instance: Optional['CaptchaSolver'] = None
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    @classmethod
    def get_instance(cls) -> 'CaptchaSolver':
        if cls._instance is None:
            cls._instance = CaptchaSolver()
        return cls._instance

    def solve_punish_url(self, punish_url: str, proxy_url: Optional[str] = None) -> Optional[str]:
        """
        Submits solver task to dedicated background thread pool to prevent
        asyncio event loop conflicts with Playwright Sync API.
        """
        try:
            future = self._executor.submit(self._do_solve, punish_url, proxy_url)
            return future.result(timeout=45)
        except Exception as e:
            logger.error(f"[-] CaptchaSolver thread error: {e}")
            return None

    def _do_solve(self, punish_url: str, proxy_url: Optional[str] = None) -> Optional[str]:
        """
        Navigates to the punish challenge URL, drags the slider, 
        and extracts the newly minted x5sec cookie.
        """
        if punish_url.startswith("//"):
            punish_url = "https:" + punish_url
        elif punish_url.startswith("/"):
            punish_url = "https://h5api.m.taobao.com" + punish_url

        logger.info(f"[*] CaptchaSolver activated for URL: {punish_url[:120]}...")
        
        proxy_dict = None
        if proxy_url:
            parsed = urllib.parse.urlparse(proxy_url)
            server_host = f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port}"
            proxy_dict = {"server": server_host}
            if parsed.username:
                proxy_dict["username"] = parsed.username
            if parsed.password:
                proxy_dict["password"] = parsed.password

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--disable-dev-shm-usage"
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    locale="zh-CN",
                    proxy=proxy_dict
                )
                
                # Cloak webdriver fingerprint
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                """)
                
                page = context.new_page()
                page.goto(punish_url, wait_until="domcontentloaded", timeout=25000)
                
                # Wait for slider to render
                found_slider = None
                active_frame = page
                slider_selectors = ["#nc_1_n1z", ".nc_iconfont.btn_slide", "span.btn_slide", ".btn_slide"]
                
                for _ in range(10):  # poll up to 5 seconds
                    for sel in slider_selectors:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            found_slider = el
                            break
                    if found_slider:
                        break
                        
                    for frame in page.frames:
                        for sel in slider_selectors:
                            try:
                                el = frame.query_selector(sel)
                                if el and el.is_visible():
                                    found_slider = el
                                    active_frame = frame
                                    break
                            except Exception:
                                pass
                        if found_slider:
                            break
                    time.sleep(0.5)
                            
                if found_slider:
                    logger.info("[*] Found Alibaba NC Slider. Executing human drag...")
                    # Calculate distance from track if possible
                    distance = 280.0
                    track = active_frame.query_selector("#nc_1__scale_text") or active_frame.query_selector(".nc_scale")
                    if track:
                        tbox = track.bounding_box()
                        sbox = found_slider.bounding_box()
                        if tbox and sbox:
                            distance = tbox["width"] - sbox["width"] - 2
                    
                    human_drag(active_frame, found_slider, distance=distance)
                    
                # Poll context cookies for x5sec
                x5sec_val = None
                all_cookies = []
                start_wait = time.time()
                while time.time() - start_wait < 8:
                    all_cookies = context.cookies()
                    for c in all_cookies:
                        if c.get("name") == "x5sec":
                            x5sec_val = c.get("value")
                            break
                    if x5sec_val:
                        break
                    time.sleep(0.5)
                    
                browser.close()
                
                if x5sec_val:
                    logger.info(f"[🎉] Successfully solved Captcha! Acquired x5sec: {x5sec_val[:20]}...")
                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in all_cookies])
                    return cookie_str
                else:
                    logger.warning("[-] Captcha drag finished but x5sec cookie was not found in context.")
                    return None
                    
            except Exception as e:
                logger.error(f"[-] CaptchaSolver error: {e}")
                return None
