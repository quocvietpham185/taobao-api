# Taobao Data API Microservice (MTOP REST Service)

Dịch vụ RESTful API hoàn chỉnh để khai thác dữ liệu từ Taobao:
1. **Tìm kiếm sản phẩm (`/api/v1/search`)**: Lấy danh sách sản phẩm, giá, ảnh, shop, lượt bán.
2. **Chi tiết & Full SKU Matrix (`/api/v1/detail`)**: Bóc tách tên sản phẩm, ảnh album, khoảng giá, và toàn bộ biến thể SKU (màu sắc, size, giá từng phân loại, tồn kho, ảnh SKU).
3. **Đánh giá khách hàng (`/api/v1/reviews`)**: Lấy đánh giá nguyên bản bằng tiếng Trung.

---

## 🚀 Hướng dẫn Cài đặt & Khởi động nhanh (Quick Start)

### 1. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 2. Cấu hình Proxy (config.py)
Để vượt qua tường lửa Alibaba khi cào từ ngoài Trung Quốc, cấu hình proxy dân cư Trung Quốc vào file `config.py`:
```python
PROXIES = [
    "http://username:password@your-cn-proxy.com:8080"
]
```

### 3. Khởi chạy Server
```bash
python server.py
```

Server sẽ lắng nghe tại: `http://localhost:8000`

---

## 📖 Tài liệu API Trực quan (Swagger UI)
Sau khi bật server, truy cập trực tiếp:
👉 **`http://localhost:8000/docs`**

Chi tiết cấu trúc JSON đầu ra và hướng dẫn chi tiết xem tại: [`CLIENT_DELIVERY.md`](CLIENT_DELIVERY.md)
