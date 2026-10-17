import os
from pydantic import BaseModel
from typing import List, Optional

class Settings(BaseModel):
    APP_NAME: str = "Taobao Android RPC Farm API"
    VERSION: str = "1.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ADB & Device settings
    ADB_DEVICE: str = "127.0.0.1:16384"
    TARGET_PACKAGE: str = "com.taobao.taobao"
    
    # Proxy configuration for Client Handover
    # Supports HTTP, HTTPS, SOCKS5 proxies
    # Example: "http://username:password@proxy_host:proxy_port"
    # When deployed in China or with a China/HK proxy, set here:
    PROXIES: List[str] = [
        # "http://username:password@hk-proxy.example.com:8080",
    ]
    
    # Request timeouts
    REQUEST_TIMEOUT: int = 15
    RETRY_TIMES: int = 3

settings = Settings()
