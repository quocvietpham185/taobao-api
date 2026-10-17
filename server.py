import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from config import settings
from core.rpc_signer import RpcSigner
from core.mtop_client import MtopClient
from core.parser import ProductDetail, SearchItem, ProductReview

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Production-ready Android RPC Farm API for Taobao (Search, Detail, Full SKU Matrix, Customer Reviews)"
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
    signer = RpcSigner.get_instance()
    signer.connect()

@app.get("/health", tags=["System"])
async def health_check():
    signer = RpcSigner.get_instance()
    is_connected = signer.is_connected()
    return {
        "status": "online",
        "rpc_node_connected": is_connected,
        "device": settings.ADB_DEVICE,
        "target_package": settings.TARGET_PACKAGE,
        "proxy_pool_size": len(settings.PROXIES)
    }

@app.get("/api/v1/search", response_model=List[SearchItem], tags=["Taobao Product API"])
async def search_products(
    q: str = Query(..., description="Từ khóa tìm kiếm sản phẩm (ví dụ: shoes, phone, áo thun)"),
    page: int = Query(1, ge=1, description="Số trang tìm kiếm (mặc định: 1)")
):
    """
    Tìm kiếm sản phẩm trên Taobao theo từ khóa.
    Trả về danh sách: item_id, tiêu đề, giá tiền, số lượng bán, ảnh thumb, tên shop.
    """
    try:
        results = client.search(keyword=q, page=page)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/detail", response_model=ProductDetail, tags=["Taobao Product API"])
async def get_product_detail(
    item_id: str = Query(..., description="Mã sản phẩm Taobao (item_id / itemNumId, ví dụ: 601444443407)")
):
    """
    Lấy thông tin chi tiết sản phẩm Taobao.
    Trả về: Tiêu đề, danh sách ảnh chất lượng cao, tên shop, khoảng giá, và toàn bộ ma trận biến thể SKU (phân loại, màu sắc, size, giá từng loại, ảnh phân loại, số lượng tồn kho).
    """
    try:
        detail = client.get_detail(item_id=item_id)
        return detail
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/reviews", response_model=List[ProductReview], tags=["Taobao Product API"])
async def get_product_reviews(
    item_id: str = Query(..., description="Mã sản phẩm Taobao (item_id)"),
    page: int = Query(1, ge=1, description="Trang đánh giá (mặc định: 1)")
):
    """
    Lấy đánh giá (review) của khách hàng về sản phẩm.
    Trả về: Tên người mua, nội dung đánh giá gốc tiếng Trung, số sao, ngày đánh giá, phân loại đã mua, ảnh khách chụp.
    """
    try:
        reviews = client.get_reviews(item_id=item_id, page=page)
        return reviews
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host=settings.HOST, port=settings.PORT, reload=False)
