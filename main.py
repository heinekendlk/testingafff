from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote, unquote
import re
import aiohttp

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
    """
    shopee_domains = [
        r'shopee\.vn',
        r'shopee\.ph',
        r'shopee\.sg',
        r'shopee\.my',
        r'shopee\.com\.my',
        r'shopee\.co\.th',
        r'shopee\.tw',
        r'shopee\.id',
        r's\.shopee\.vn'  # Short link
    ]
    
    pattern = '|'.join(shopee_domains)
    return bool(re.search(pattern, url))


def is_short_link(url: str) -> bool:
    """
    Kiểm tra có phải short link (s.shopee.vn) không
    """
    return 's.shopee.vn' in url or 's.shopee' in url


async def extract_origin_link_from_short(url: str) -> str:
    """
    Giải mã short link để lấy origin_link
    
    VD: https://s.shopee.vn/3B2qsVvyNN
        → https://shopee.vn/product/123/456
    """
    try:
        # Cách 1: Nếu là link redirect an_redir, extract origin_link
        if 'an_redir' in url and 'origin_link=' in url:
            match = re.search(r'origin_link=([^&]+)', url)
            if match:
                encoded_link = match.group(1)
                origin_link = unquote(encoded_link)
                return origin_link
        
        # Cách 2: Nếu là short link, follow redirect
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url,
                    allow_redirects=True,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    final_url = str(response.url)
                    
                    # Lấy origin_link từ URL cuối cùng
                    if 'origin_link=' in final_url:
                        match = re.search(r'origin_link=([^&]+)', final_url)
                        if match:
                            return unquote(match.group(1))
                    
                    # Hoặc return URL cuối cùng nếu là link shopee thường
                    if validate_shopee_url(final_url):
                        return final_url
                        
            except Exception as e:
                print(f"Error following redirect: {e}")
        
        return None
        
    except Exception as e:
        print(f"Error extracting origin link: {e}")
        return None


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
    """
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
async def create_link(origin_link: str = Query(..., description="Link Shopee hoặc short link")):
    """
    Tạo affiliate link từ Shopee URL hoặc short link
    
    Nếu input là short link (s.shopee.vn), sẽ:
    1. Giải mã để lấy link gốc
    2. Tạo lại link affiliate mới
    
    Parameters:
    - origin_link: Link Shopee gốc hoặc short link
    
    Response:
    {
        "success": true,
        "message": "Đã tạo link thành công",
        "affiliateLink": "https://s.shopee.vn/an_redir?...",
        "originLink": "https://shopee.vn/product/123/456",
        "decodedFromShortLink": true,
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
            detail="URL không phải từ Shopee. Vui lòng nhập link Shopee hoặc short link hợp lệ"
        )
    
    decoded_from_short_link = False
    
    # ========== Nếu là short link, giải mã ==========
    if is_short_link(origin_link):
        decoded_from_short_link = True
        print(f"🔍 Giải mã short link: {origin_link}")
        
        decoded_link = await extract_origin_link_from_short(origin_link)
        
        if not decoded_link:
            raise HTTPException(
                status_code=400, 
                detail="Không thể giải mã short link. Vui lòng kiểm tra lại link"
            )
        
        origin_link = decoded_link
        print(f"✅ Link gốc: {origin_link}")
    
    # ========== Validate link gốc ==========
    if not validate_shopee_url(origin_link):
        raise HTTPException(
            status_code=400, 
            detail="Link gốc không hợp lệ. Vui lòng kiểm tra lại"
        )
    
    # Extract product info
    shop_id, product_id = extract_product_id(origin_link)
    if not product_id:
        raise HTTPException(
            status_code=400, 
            detail="Không thể lấy product ID từ URL. Vui lòng kiểm tra lại link"
        )
    
    # ========== Tạo Link Mới ==========
    affiliate_link = create_affiliate_link(origin_link)
    
    return {
        "success": True,
        "message": "Đã tạo link thành công" + (" (giải mã từ short link)" if decoded_from_short_link else ""),
        "affiliateLink": affiliate_link,
        "originLink": origin_link,
        "decodedFromShortLink": decoded_from_short_link,
        "affiliateId": FIXED_AFFILIATE_ID,
        "subId": FIXED_SUB_ID,
        "productId": product_id,
        "shopId": shop_id
    }


@app.get("/validate")
async def validate_url(origin_link: str = Query(...)):
    """
    Kiểm tra URL Shopee có hợp lệ không
    """
    
    origin_link = origin_link.strip()
    
    if not validate_shopee_url(origin_link):
        raise HTTPException(
            status_code=400, 
            detail="URL không phải từ Shopee"
        )
    
    decoded_from_short_link = False
    
    # Nếu là short link, giải mã
    if is_short_link(origin_link):
        decoded_from_short_link = True
        decoded_link = await extract_origin_link_from_short(origin_link)
        
        if not decoded_link:
            raise HTTPException(
                status_code=400, 
                detail="Không thể giải mã short link"
            )
        
        origin_link = decoded_link
    
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
        "originLink": origin_link,
        "decodedFromShortLink": decoded_from_short_link,
        "message": "URL hợp lệ"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Shopee Affiliate Link Generator",
        "version": "1.0.1",
        "affiliateId": FIXED_AFFILIATE_ID,
        "subId": FIXED_SUB_ID,
        "features": ["decode_short_link", "create_affiliate_link"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
