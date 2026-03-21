from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import quote, unquote
import re
import aiohttp
import os
from dotenv import load_dotenv
import asyncio
import json

load_dotenv()

app = FastAPI(title="Shopee Affiliate Link Generator")

# ========== CORS Configuration ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

FIXED_AFFILIATE_ID = "17323090153"
FIXED_SUB_ID = "addlivetag-ductoan"
FIXED_SHARE_CHANNEL_CODE = "4"

# ========== Config Endpoint ==========
@app.get("/config", response_class=JSONResponse)
async def get_config():
    """Trả về config cho frontend - JSON format"""
    try:
        api_url = os.getenv("API_URL", "https://shopee-affiliate-api-ymtu.onrender.com")
        
        config = {
            "apiUrl": api_url,
            "version": "1.0.5",
            "features": ["decode_short_link", "create_affiliate_link"],
            "status": "ok"
        }
        
        print(f"✅ Config endpoint called - returning: {config}")
        
        return JSONResponse(
            status_code=200,
            content=config,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        print(f"❌ Config error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
            headers={"Content-Control-Allow-Origin": "*"}
        )

# ========== Helper Functions ==========

def validate_shopee_url(url: str) -> bool:
    """Kiểm tra URL có phải từ Shopee không"""
    shopee_domains = [
        r'shopee\.vn', r'shopee\.ph', r'shopee\.sg', 
        r'shopee\.my', r'shopee\.com\.my', r'shopee\.co\.th',
        r'shopee\.tw', r'shopee\.id', r's\.shopee'
    ]
    pattern = '|'.join(shopee_domains)
    return bool(re.search(pattern, url))


def is_short_link(url: str) -> bool:
    """Kiểm tra có phải short link không"""
    return 's.shopee' in url and 'an_redir' not in url


async def extract_origin_link_from_short(url: str) -> str:
    """Giải mã short link để lấy link gốc"""
    try:
        print(f"\n{'='*60}")
        print(f"🔍 GIẢI MÃ SHORT LINK")
        print(f"{'='*60}")
        print(f"📥 Input: {url}")
        
        # Cách 1: Nếu là link redirect an_redir
        if 'an_redir' in url and 'origin_link=' in url:
            print("✅ Phát hiện: Link redirect (an_redir)")
            match = re.search(r'origin_link=([^&]+)', url)
            if match:
                origin_link = unquote(match.group(1))
                print(f"✅ Extracted: {origin_link}")
                return origin_link
        
        # Cách 2: Follow redirect
        print("🌐 Follow redirect để lấy link gốc...")
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as response:
                final_url = str(response.url)
                print(f"📍 Final URL: {final_url}")
                
                if 'origin_link=' in final_url:
                    print("✅ Tìm thấy 'origin_link=' parameter")
                    match = re.search(r'origin_link=([^&]+)', final_url)
                    if match:
                        origin_link = unquote(match.group(1))
                        print(f"✅ Extracted: {origin_link}")
                        return origin_link
                
                if validate_shopee_url(final_url):
                    print(f"✅ Valid Shopee URL: {final_url}")
                    return final_url
                
                print("❌ Không tìm được link gốc")
                return None
        
    except asyncio.TimeoutError:
        print("❌ Timeout")
        return None
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        print(f"{'='*60}\n")


def create_affiliate_link(origin_link: str) -> str:
    """Tạo affiliate link từ link gốc"""
    encoded_link = quote(origin_link, safe='')
    affiliate_link = (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded_link}"
        f"&affiliate_id={FIXED_AFFILIATE_ID}"
        f"&sub_id={FIXED_SUB_ID}"
        f"&share_channel_code={FIXED_SHARE_CHANNEL_CODE}"
    )
    return affiliate_link


# ========== API Endpoints ==========

@app.get("/create-link", response_class=JSONResponse)
async def create_link(origin_link: str = Query(...)):
    """Tạo affiliate link từ Shopee URL hoặc short link"""
    
    try:
        # Validation
        if not origin_link:
            return JSONResponse(
                status_code=400,
                content={"detail": "origin_link không được để trống"}
            )
        
        origin_link = origin_link.strip()
        
        print(f"\n🚀 === PROCESS TẠO LINK ===")
        print(f"📥 Input: {origin_link}")
        
        if not validate_shopee_url(origin_link):
            return JSONResponse(
                status_code=400,
                content={"detail": "❌ URL không phải từ Shopee"}
            )
        
        decoded_from_short_link = False
        original_input = origin_link
        
        # Nếu là short link, giải mã
        if is_short_link(origin_link):
            decoded_from_short_link = True
            print(f"🔄 Phát hiện: SHORT LINK")
            print(f"⏳ Đang giải mã...")
            
            decoded_link = await extract_origin_link_from_short(origin_link)
            
            if not decoded_link:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "❌ Không thể giải mã short link"}
                )
            
            origin_link = decoded_link
            print(f"✅ Link gốc: {origin_link}")
        else:
            print(f"📌 Link thường (không phải short link)")
        
        # Validate link gốc
        if not validate_shopee_url(origin_link):
            return JSONResponse(
                status_code=400,
                content={"detail": "❌ Link gốc không hợp lệ"}
            )
        
        # Tạo Link Affiliate Mới
        print(f"🔗 Tạo link affiliate mới...")
        affiliate_link = create_affiliate_link(origin_link)
        print(f"✅ Hoàn thành!")
        print(f"{'='*60}\n")
        
        response_data = {
            "success": True,
            "message": "✅ Đã tạo link thành công" + (" (giải mã từ short link)" if decoded_from_short_link else ""),
            "affiliateLink": affiliate_link,
            "originLink": origin_link,
            "originalInput": original_input,
            "decodedFromShortLink": decoded_from_short_link,
            "affiliateId": FIXED_AFFILIATE_ID,
            "subId": FIXED_SUB_ID,
            "shareChannelCode": FIXED_SHARE_CHANNEL_CODE
        }
        
        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi server: {str(e)}"}
        )


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "service": "Shopee Affiliate Link Generator",
            "version": "1.0.5",
            "affiliateId": FIXED_AFFILIATE_ID,
            "subId": FIXED_SUB_ID,
            "shareChannelCode": FIXED_SHARE_CHANNEL_CODE
        }
    )


# ========== Root endpoint ==========
@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse(
        status_code=200,
        content={
            "message": "Shopee Affiliate Link Generator API",
            "version": "1.0.5",
            "endpoints": {
                "POST /create-link": "Tạo link affiliate",
                "GET /config": "Lấy config",
                "GET /health": "Health check"
            }
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
