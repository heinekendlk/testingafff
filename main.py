from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import quote, unquote, urlparse, parse_qs
import re
import aiohttp
from bs4 import BeautifulSoup

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
        r's\.shopee'
    ]
    
    pattern = '|'.join(shopee_domains)
    return bool(re.search(pattern, url))


def is_short_link(url: str) -> bool:
    """
    Kiểm tra có phải short link (s.shopee.vn) không
    """
    return 's.shopee.vn' in url or 's.shopee' in url


def extract_product_id_from_url(url: str) -> tuple:
    """
    Extract shop_id và product_id từ URL
    
    Hỗ trợ các format:
    - https://shopee.vn/product/123/456
    - https://shopee.vn/Tên-Sản-Phẩm-i.123.456
    - https://shopee.vn/...?itemid=456&shopid=123
    
    Return: (shop_id, product_id) hoặc (None, None)
    """
    patterns = [
        # Format 1: /product/shop_id/product_id
        (r'shopee\.\w+/product/(\d+)/(\d+)', (1, 2)),
        # Format 2: -i.shop_id.product_id
        (r'shopee\.\w+/.*?-i\.(\d+)\.(\d+)', (1, 2)),
        # Format 3: ?itemid=xxx&shopid=xxx
        (r'itemid=(\d+).*?shopid=(\d+)', (2, 1)),
        # Format 4: ?itemid=xxx (lấy từ URL parameters)
        (r'[?&]itemid=(\d+)', None),
    ]
    
    for pattern, groups in patterns:
        match = re.search(pattern, url)
        if match:
            if groups:
                shop_id = match.group(groups[0])
                product_id = match.group(groups[1])
                return (shop_id, product_id)
            else:
                # Trích xuất từ parameters
                product_id = match.group(1)
                return (None, product_id)
    
    return (None, None)


async def extract_origin_link_from_short(url: str) -> str:
    """
    Giải mã short link để lấy origin_link
    
    VD: https://s.shopee.vn/3B2qsVvyNN
        → https://shopee.vn/product/123/456
    """
    try:
        print(f"🔍 Starting to decode: {url}")
        
        # ========== Cách 1: Nếu là link redirect an_redir, extract origin_link ==========
        if 'an_redir' in url and 'origin_link=' in url:
            print("✅ Phát hiện link redirect (an_redir)")
            match = re.search(r'origin_link=([^&]+)', url)
            if match:
                encoded_link = match.group(1)
                origin_link = unquote(encoded_link)
                print(f"✅ Extract origin_link: {origin_link}")
                return origin_link
        
        # ========== Cách 2: Follow redirect để lấy link gốc ==========
        print("🌐 Following redirect...")
        
        async with aiohttp.ClientSession() as session:
            try:
                # Disable SSL verification (cho s.shopee.vn)
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector) as session:
                    # Follow redirect
                    async with session.get(
                        url,
                        allow_redirects=True,
                        timeout=aiohttp.ClientTimeout(total=15),
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                    ) as response:
                        final_url = str(response.url)
                        print(f"📍 Final URL after redirect: {final_url}")
                        
                        # ========== Kiểm tra origin_link trong URL ==========
                        if 'origin_link=' in final_url:
                            match = re.search(r'origin_link=([^&]+)', final_url)
                            if match:
                                return unquote(match.group(1))
                        
                        # ========== Kiểm tra itemid & shopid trong URL ==========
                        shop_id, product_id = extract_product_id_from_url(final_url)
                        if product_id:
                            print(f"✅ Found product_id: {product_id}, shop_id: {shop_id}")
                            if shop_id:
                                reconstructed = f"https://shopee.vn/product/{shop_id}/{product_id}"
                            else:
                                reconstructed = f"https://shopee.vn/product/{product_id}"
                            print(f"✅ Reconstructed URL: {reconstructed}")
                            return reconstructed
                        
                        # ========== Nếu final URL hợp lệ, return nó ==========
                        if validate_shopee_url(final_url):
                            print(f"✅ Valid Shopee URL: {final_url}")
                            return final_url
                        
                        # ========== Lấy HTML để tìm productId & shopId ==========
                        print("📄 Fetching HTML to extract product info...")
                        text = await response.text()
                        
                        # Tìm trong HTML
                        # Pattern 1: "__INITIAL_STATE__": {"item":{"itemid":"123",...
                        match = re.search(r'"itemid"\s*:\s*"?(\d+)"?', text)
                        if match:
                            product_id = match.group(1)
                            print(f"✅ Found itemid in HTML: {product_id}")
                            
                            # Tìm shopid
                            match_shop = re.search(r'"shopid"\s*:\s*"?(\d+)"?', text)
                            shop_id = match_shop.group(1) if match_shop else None
                            
                            if shop_id:
                                reconstructed = f"https://shopee.vn/product/{shop_id}/{product_id}"
                            else:
                                reconstructed = f"https://shopee.vn/product/{product_id}"
                            
                            print(f"✅ Reconstructed from HTML: {reconstructed}")
                            return reconstructed
                        
                        return None
                        
            except asyncio.TimeoutError:
                print("❌ Timeout when following redirect")
                return None
            except Exception as e:
                print(f"❌ Error following redirect: {e}")
                return None
        
    except Exception as e:
        print(f"❌ Error extracting origin link: {e}")
        import traceback
        traceback.print_exc()
        return None


def extract_product_id(url: str) -> tuple:
    """
    Extract shop_id và product_id từ URL
    
    Return: (shop_id, product_id) hoặc (None, None)
    """
    return extract_product_id_from_url(url)


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

@app.post("/create-link")
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
        print(f"\n{'='*50}")
        print(f"🔍 Giải mã short link: {origin_link}")
        print(f"{'='*50}")
        
        decoded_link = await extract_origin_link_from_short(origin_link)
        
        if not decoded_link:
            raise HTTPException(
                status_code=400, 
                detail="❌ Không thể giải mã short link. Vui lòng kiểm tra lại link hoặc thử lại sau"
            )
        
        origin_link = decoded_link
        print(f"✅ Link gốc: {origin_link}\n")
    
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
        "message": "✅ Đã tạo link thành công" + (" (giải mã từ short link)" if decoded_from_short_link else ""),
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
        "message": "✅ URL hợp lệ"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "Shopee Affiliate Link Generator",
        "version": "1.0.2",
        "affiliateId": FIXED_AFFILIATE_ID,
        "subId": FIXED_SUB_ID,
        "features": ["decode_short_link", "create_affiliate_link", "extract_from_html"]
    }


if __name__ == "__main__":
    import uvicorn
    import asyncio
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
