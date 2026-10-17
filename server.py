import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from config import settings
from core.rpc_signer import RpcSigner
try:
    from core.unidbg_signer import UnidbgSigner
except ImportError:
    UnidbgSigner = None
from core.mtop_client import MtopClient
from core.parser import ProductDetail, SearchItem, ProductReview

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-ready Android RPC Farm & Unidbg ARM CPU Emulation API for Taobao (Search, Detail, Full SKU Matrix, Customer Reviews)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MtopClient()

@app.on_event("startup")
async def startup_event():
    import os
    if os.path.exists("working_cookie.txt"):
        try:
            with open("working_cookie.txt", "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c:
                    settings.COOKIE = c
        except Exception:
            pass
    signer = RpcSigner.get_instance()
    signer.connect()

@app.get("/health", tags=["System"])
async def health_check():
    unidbg_avail = False
    unidbg_ep = ""
    if UnidbgSigner:
        try:
            unidbg = UnidbgSigner.get_instance()
            unidbg_avail = unidbg.is_available()
            unidbg_ep = unidbg.endpoint
        except Exception:
            pass
    signer = RpcSigner.get_instance()
    is_connected = signer.is_connected()
    return {
        "status": "online",
        "engine": "taobao-mtop-h5-crawler",
        "unidbg_native_arm_operational": unidbg_avail,
        "unidbg_endpoint": unidbg_ep,
        "securityguard_version": "6.8.260901",
        "rpc_node_connected": is_connected,
        "device": settings.ADB_DEVICE,
        "proxy_pool_size": len(settings.PROXIES),
        "has_active_cookie": bool(settings.COOKIE)
    }

@app.post("/api/v1/config/cookie", tags=["System Configuration"])
async def set_system_cookie(
    cookie: str = Query(..., description="Chuỗi Cookie Taobao để lưu cố định cho toàn bộ hệ thống")
):
    """
    Cài đặt chuỗi Cookie Taobao dùng chung cho toàn bộ Server.
    Sau khi cài đặt ở đây, bạn không cần phải nhập cookie ở từng API riêng lẻ nữa.
    """
    settings.COOKIE = cookie
    try:
        with open("working_cookie.txt", "w", encoding="utf-8") as f:
            f.write(cookie)
    except Exception:
        pass
    return {"status": "success", "message": "Cookie has been saved successfully and persisted to disk!"}

@app.get("/api/v1/search", response_model=List[SearchItem], tags=["Taobao Product API"])
async def search_products(
    q: str = Query(..., description="Từ khóa tìm kiếm sản phẩm (ví dụ: shoes, phone, áo thun, ipad pro m1)"),
    page: int = Query(1, ge=1, description="Số trang tìm kiếm (mặc định: 1)"),
    cookie: Optional[str] = Query(None, description="Chuỗi Cookie Taobao (tùy chọn, dán vào đây để tìm kiếm LIVE 100%)")
):
    """
    Tìm kiếm sản phẩm trên Taobao theo từ khóa.
    Trả về danh sách: item_id, tiêu đề, giá tiền, số lượng bán, ảnh thumb, tên shop.
    """
    try:
        results = client.search(keyword=q, page=page, cookie=cookie)
        return results
    except ValueError as e:
        status_code = 403 if "WAF" in str(e) else 404
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/detail", response_model=ProductDetail, tags=["Taobao Product API"])
async def get_product_detail(
    item_id: str = Query(..., description="Mã sản phẩm Taobao (item_id / itemNumId, ví dụ: 601444443407)"),
    cookie: Optional[str] = Query(None, description="Chuỗi Cookie Taobao (tùy chọn)")
):
    """
    Lấy thông tin chi tiết sản phẩm Taobao.
    Trả về: Tiêu đề, danh sách ảnh chất lượng cao, tên shop, khoảng giá, và toàn bộ ma trận biến thể SKU (phân loại, màu sắc, size, giá từng loại, ảnh phân loại, số lượng tồn kho).
    """
    try:
        detail = client.get_detail(item_id=item_id, cookie=cookie)
        return detail
    except ValueError as e:
        status_code = 403 if "WAF" in str(e) else 404
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/reviews", response_model=List[ProductReview], tags=["Taobao Product API"])
async def get_product_reviews(
    item_id: str = Query(..., description="Mã sản phẩm Taobao (item_id)"),
    page: int = Query(1, ge=1, description="Trang đánh giá (mặc định: 1)"),
    cookie: Optional[str] = Query(None, description="Chuỗi Cookie Taobao (tùy chọn)")
):
    """
    Lấy đánh giá (review) của khách hàng về sản phẩm.
    Trả về: Tên người mua, nội dung đánh giá gốc tiếng Trung, số sao, ngày đánh giá, phân loại đã mua, ảnh khách chụp.
    """
    try:
        reviews = client.get_reviews(item_id=item_id, page=page, cookie=cookie)
        return reviews
    except ValueError as e:
        status_code = 403 if "WAF" in str(e) else 404
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=False)
