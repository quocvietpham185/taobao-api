# 🚀 TÀI LIỆU BÀN GIAO HỆ THỐNG TAOBAO ANDROID RPC FARM API

Hệ thống cung cấp dịch vụ RESTful API hoàn chỉnh để khai thác dữ liệu từ Taobao Android App thông qua kỹ thuật **Android RPC Farm (Remote Procedure Call)**, tích hợp bộ xử lý chữ ký bảo mật cấp thấp (`libsgmain` / MTOP SDK) và chuẩn hóa dữ liệu đầu ra theo định dạng JSON sạch.

---

## 📌 1. Danh sách Endpoints API

Tất cả các endpoint đều hỗ trợ xem tài liệu trực quan (Interactive Swagger UI) tại địa chỉ:  
👉 **`http://localhost:8000/docs`**

### 1.1. Tìm kiếm sản phẩm (`GET /api/v1/search`)
- **Mô tả:** Tìm kiếm danh sách sản phẩm Taobao theo từ khóa.
- **Tham số:**
  - `q` (bắt buộc): Từ khóa tìm kiếm (ví dụ: `shoes`, `phone`, `áo thun`).
  - `page` (tùy chọn): Trang tìm kiếm (mặc định: `1`).
- **Đầu ra mẫu (JSON):**
```json
[
  {
    "item_id": "601444443407",
    "title": "2026 新款男士春季透气休闲运动鞋",
    "price": 89.9,
    "sales": "1000+ 人付款",
    "image": "https://img.alicdn.com/bao/uploaded/i1/TB1xxx.jpg",
    "shop_name": "官方旗舰店",
    "location": "浙江 杭州",
    "detail_url": "https://item.taobao.com/item.htm?id=601444443407"
  }
]
```

---

### 1.2. Chi tiết sản phẩm & Full ma trận SKU (`GET /api/v1/detail`)
- **Mô tả:** Lấy thông tin chi tiết của 1 sản phẩm: Tên, ảnh album chất lượng cao, tên shop, khoảng giá, và **toàn bộ ma trận biến thể SKU** (phân loại màu sắc, size, giá tiền từng loại, tồn kho, ảnh của từng loại).
- **Tham số:**
  - `item_id` (bắt buộc): Mã sản phẩm (ví dụ: `601444443407`).
- **Đầu ra mẫu (JSON):**
```json
{
  "item_id": "601444443407",
  "title": "2026 新款男士春季透气休闲运动鞋",
  "shop_name": "官方旗舰店",
  "seller_id": "22005481829",
  "main_images": [
    "https://img.alicdn.com/imgextra/i1/TB1xxx.jpg",
    "https://img.alicdn.com/imgextra/i2/TB1yyy.jpg"
  ],
  "min_price": 89.9,
  "max_price": 129.9,
  "total_sales": "1000+",
  "skus": [
    {
      "sku_id": "48192837192",
      "properties": "Màu đen / Size 40",
      "price": 89.9,
      "stock": 450,
      "image": "https://img.alicdn.com/imgextra/i1/variant_black.jpg"
    },
    {
      "sku_id": "48192837193",
      "properties": "Màu trắng / Size 41",
      "price": 99.9,
      "stock": 210,
      "image": "https://img.alicdn.com/imgextra/i2/variant_white.jpg"
    }
  ]
}
```

---

### 1.3. Đánh giá của khách hàng (`GET /api/v1/reviews`)
- **Mô tả:** Lấy danh sách đánh giá của khách hàng về sản phẩm (bình luận nguyên bản tiếng Trung, số sao, ngày đánh giá, tag phân loại đã mua, ảnh review khách chụp).
- **Tham số:**
  - `item_id` (bắt buộc): Mã sản phẩm.
  - `page` (tùy chọn): Trang đánh giá (mặc định: `1`).
- **Đầu ra mẫu (JSON):**
```json
[
  {
    "author": "t***8",
    "content": "鞋子穿着很舒服，尺码很标准，透气性非常好，物超所值！",
    "rating": 5,
    "date": "2026-03-15",
    "sku_info": "颜色:黑色;尺码:41",
    "images": [
      "https://img.alicdn.com/imgextra/i1/review_pic1.jpg"
    ]
  }
]
```

---

## 🛡️ 2. Hướng dẫn cấu hình Proxy Pool (Zero Ban Rate)

Để hệ thống hoạt động 24/7 với tốc độ cao mà **không cần đăng nhập bất kỳ tài khoản nào** và **không lo bị khóa nick**, chỉ cần điền danh sách Proxy vào file [`config.py`](file:///f:/Nam4/job-remote/taobao/config.py):

```python
# config.py
settings = Settings(
    PROXIES=[
        "http://username:password@hk-proxy1.com:8080",
        "socks5://username:password@cn-proxy2.com:1080",
    ]
)
```

- **Khuyến nghị loại Proxy:** Proxy xoay vòng (Rotating Residential Proxy) tại khu vực **Hong Kong** hoặc **Trung Quốc đại lục**.
- Cơ chế của hệ thống sẽ tự động cân bằng tải và luân chuyển giữa các Proxy để tránh bị giới hạn tần suất (Rate Limit) của Alibaba.

---

## 💻 3. Hướng dẫn khởi động hệ thống

1. Đảm bảo máy ảo Android (MuMu Player) đã mở và app Taobao đang chạy nền.
2. Chạy server FastAPI:
```bash
python server.py
```
3. Truy cập Swagger UI tại trình duyệt:  
`http://localhost:8000/docs` để kiểm tra trực tiếp các API.
