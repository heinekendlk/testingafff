from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote
import re

app = FastAPI(title="Shopee Affiliate Link Generator")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Constants ==========
FIXED_AFFILIATE_ID = "17323090153"
FIXED_SUB_ID = "addlivetag-ductoan"

# ============ Helper Functions ============

def validate_shopee_url(url: str) -> bool:
    """
    Kiểm tra URL có phải từ Shopee không
    
    Valid formats:
    - https://s.shopee.vn/...
    - https://shopee.vn/product/shop_id/product_id
    - https://shopee.vn/Tên-Sản-Phẩm-i.shop_id.product_id
    - https://shopee.com.my/...
    - https://shopee.sg/...
    """
    shopee_domains = [
        r'shopee\.vn',
        r'shopee\.ph',
        r'shopee\.sg',
        r'shopee\.my',
        r'shopee\.com\.my',
        r'shopee\.co\.th',
        r'shopee\.tw',
        r'shopee\.id'
    ]
    
    pattern = '|'.join(shopee_domains)
    return bool(re.search(pattern, url))


def extract_product_id(url: str) -> tuple:
    """
    Extract shop_id và product_id từ URL
    
    Return: (shop_id, product_id) hoặc (None, None)
    """
    patterns = [
        r'shopee\.\w+/product/(\d+)/(\d+)',  # /product/shop_id/product_id
        r'shopee\.\w+/.*?-i\.(\d+)\.(\d+)',  # -i.shop_id.product_id
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            shop_id = match.group(1)
            product_id = match.group(2)
            return (shop_id, product_id)
    
    return (None, None)


def create_affiliate_link(origin_link: str) -> str:
    """
    Tạo Shopee affiliate link với redirect
    
    Format:
    https://s.shopee.vn/an_redir?origin_link={encoded_link}&affiliate_id=17323090153&sub_id=addlivetag-ductoan
    
    Affiliate ID và Sub ID đã được cố định
    """
    # Encode origin_link
    encoded_link = quote(origin_link, safe='')
    
    affiliate_link = (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded_link}"
        f"&affiliate_id={FIXED_AFFILIATE_ID}"
        f"&sub_id={FIXED_SUB_ID}"
    )
    
    return affiliate_link


# ============ API Endpoints ============

@app.get("/create-link")
async def create_link(origin_link: str = Query(..., description="Link Shopee từ form")):
    """
    Tạo affiliate link từ Shopee URL
    
    Parameters:
    - origin_link: Link sản phẩm Shopee gốc
    
    Response:
    {
        "success": true,
        "message": "Đã tạo link thành công",
        "affiliateLink": "https://s.shopee.vn/an_redir?origin_link=...&affiliate_id=17323090153&sub_id=addlivetag-ductoan",
        "affiliateId": "17323090153",
        "subId": "addlivetag-ductoan",
        "productId": "67890"
    }
    """
    
    # ========== Validation ==========
    if not origin_link:
        raise HTTPException(
            status_code=400, 
            detail="origin_link không được để trống"
        )
    
    origin_link = origin_link.strip()
    
    # Kiểm tra URL có phải Shopee không
    if not validate_shopee_url(origin_link):
        raise HTTPException(
            status_code=400, 
            detail="URL không phải từ Shopee. Vui lòng nhập link Shopee hợp lệ"
        )
    
    # Extract product info
    shop_id, product_id = extract_product_id(origin_link)
    if not product_id:
        raise HTTPException(
            status_code=400, 
            detail="Không thể lấy product ID từ URL. Vui lòng kiểm tra lại link"
        )
    
    # ========== Tạo Link ==========
    affiliate_link = create_affiliate_link(origin_link)
    
    return {
        "success": True,
        "message": "Đã tạo link thành công",
        "affiliateLink": affiliate_link,
        "affiliateId": FIXED_AFFILIATE_ID,
        "subId": FIXED_SUB_ID,
        "productId": product_id,
        "shopId": shop_id,
        "originLink": origin_link
    }


@app.get("/validate")
async def validate_url(origin_link: str = Query(...)):
    """
    Kiểm tra URL Shopee có hợp lệ không
    
    Response:
    {
        "valid": true,
        "productId": "67890",
        "shopId": "12345",
        "message": "URL hợp lệ"
    }
    """
    
    origin_link = origin_link.strip()
    
    if not validate_shopee_url(origin_link):
        raise HTTPException(
            status_code=400, 
            detail="URL không phải từ Shopee"
        )
    
    shop_id, product_id = extract_product_id(origin_link)
    
    if not product_id:
        raise HTTPException(
            status_code=400, 
            detail="Không thể lấy product ID từ URL"
        )
    
    return {
        "valid": True,
        "productId": product_id,
        "shopId": shop_id,
        "message": "URL hợp lệ",
        "url": origin_link
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Shopee Affiliate Link Generator",
        "version": "1.0.0",
        "affiliateId": FIXED_AFFILIATE_ID,
        "subId": FIXED_SUB_ID
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
