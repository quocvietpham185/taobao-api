import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class SkuVariant(BaseModel):
    sku_id: str
    properties: str
    price: float
    stock: int
    image: Optional[str] = None

class ProductDetail(BaseModel):
    item_id: str
    title: str
    shop_name: Optional[str] = None
    seller_id: Optional[str] = None
    main_images: List[str] = []
    min_price: float = 0.0
    max_price: float = 0.0
    total_sales: Optional[str] = None
    skus: List[SkuVariant] = []
    raw_props: Dict[str, Any] = {}

class SearchItem(BaseModel):
    item_id: str
    title: str
    price: float
    sales: Optional[str] = None
    image: str
    shop_name: Optional[str] = None
    location: Optional[str] = None
    detail_url: str

class ProductReview(BaseModel):
    author: str
    content: str
    rating: int = 5
    date: str
    sku_info: Optional[str] = None
    images: List[str] = []

def parse_search_response(raw_json: Dict[str, Any]) -> List[SearchItem]:
    items = []
    data = raw_json.get("data", {})
    
    # Try different search result structures
    items_array = (
        data.get("itemsArray") or 
        data.get("listItem") or 
        data.get("items") or 
        []
    )
    
    for it in items_array:
        try:
            item_id = str(it.get("item_id") or it.get("nid") or it.get("itemId") or "")
            title = it.get("title") or it.get("name") or ""
            # Strip HTML tags
            title = title.replace("<span class=H>", "").replace("</span>", "")
            price = float(it.get("price") or it.get("view_price") or it.get("realPrice") or 0.0)
            sales = str(it.get("sales") or it.get("sold") or it.get("totalSoldQuantity") or "")
            image = it.get("pic_path") or it.get("picUrl") or it.get("img") or ""
            if image and not image.startswith("http"):
                image = "https:" + image
            shop_name = it.get("nick") or it.get("shopTitle") or it.get("shopName") or ""
            loc = it.get("item_loc") or it.get("provcity") or ""
            
            if item_id:
                items.append(SearchItem(
                    item_id=item_id,
                    title=title,
                    price=price,
                    sales=sales,
                    image=image,
                    shop_name=shop_name,
                    location=loc,
                    detail_url=f"https://item.taobao.com/item.htm?id={item_id}"
                ))
        except Exception:
            continue
            
    return items

def parse_detail_response(raw_json: Dict[str, Any]) -> ProductDetail:
    data = raw_json.get("data", {})
    item_info = data.get("item", {}) or {}
    seller = data.get("seller", {}) or {}
    sku_base = data.get("skuBase", {}) or {}
    sku_core = data.get("skuCore", {}) or {}
    
    item_id = str(item_info.get("itemId") or item_info.get("id") or "")
    title = item_info.get("title") or ""
    shop_name = seller.get("shopName") or seller.get("sellerNick") or ""
    seller_id = str(seller.get("userId") or "")
    
    # Main images
    images = item_info.get("images") or []
    main_images = []
    for img in images:
        if img and not img.startswith("http"):
            img = "https:" + img
        main_images.append(img)
        
    # Build property lookup map: propId:valueId -> prop name
    prop_map = {}
    props_list = sku_base.get("props", []) or []
    for p in props_list:
        pid = str(p.get("pid", ""))
        values = p.get("values", []) or []
        for v in values:
            vid = str(v.get("vid", ""))
            vname = v.get("name") or ""
            img_url = v.get("image") or None
            if img_url and not img_url.startswith("http"):
                img_url = "https:" + img_url
            prop_map[f"{pid}:{vid}"] = {"name": vname, "image": img_url}
            
    # Parse SKU list
    skus = []
    skus_raw = sku_base.get("skus", []) or []
    sku_2_info = sku_core.get("sku2info", {}) or {}
    prices = []
    
    for s in skus_raw:
        sku_id = str(s.get("skuId", ""))
        prop_path = s.get("propPath", "")  # e.g. "1627207:28338;20509:28315"
        
        # Resolve names
        names = []
        variant_img = None
        for path_seg in prop_path.split(";"):
            if path_seg in prop_map:
                names.append(prop_map[path_seg]["name"])
                if not variant_img and prop_map[path_seg].get("image"):
                    variant_img = prop_map[path_seg]["image"]
        props_str = " / ".join(names) if names else prop_path
        
        # Get price and stock from sku2info
        core_info = sku_2_info.get(sku_id, {})
        price_info = core_info.get("price", {})
        price_val = 0.0
        try:
            price_val = float(price_info.get("priceText") or price_info.get("priceMoney") or 0.0)
            if price_val > 0:
                prices.append(price_val)
        except Exception:
            pass
            
        stock_val = int(core_info.get("quantity", 0) or 0)
        
        skus.append(SkuVariant(
            sku_id=sku_id,
            properties=props_str,
            price=price_val,
            stock=stock_val,
            image=variant_img
        ))
        
    min_p = min(prices) if prices else 0.0
    max_p = max(prices) if prices else 0.0
    
    return ProductDetail(
        item_id=item_id,
        title=title,
        shop_name=shop_name,
        seller_id=seller_id,
        main_images=main_images,
        min_price=min_p,
        max_price=max_p,
        skus=skus,
        raw_props=prop_map
    )

def parse_review_response(raw_json: Dict[str, Any]) -> List[ProductReview]:
    reviews = []
    data = raw_json.get("data", {})
    rate_list = data.get("rateList", []) or data.get("rates", []) or []
    
    for r in rate_list:
        try:
            author = r.get("userName") or r.get("userNick") or "Ẩn danh"
            content = r.get("feedback") or r.get("content") or ""
            date_str = r.get("feedbackDate") or r.get("date") or ""
            sku_info = r.get("auctionSku") or r.get("sku") or ""
            images = r.get("images") or []
            clean_images = []
            for img in images:
                if img and not img.startswith("http"):
                    img = "https:" + img
                clean_images.append(img)
                
            reviews.append(ProductReview(
                author=author,
                content=content,
                rating=5,
                date=date_str,
                sku_info=sku_info,
                images=clean_images
            ))
        except Exception:
            continue
            
    return reviews
