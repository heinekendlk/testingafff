from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import quote, urlparse, parse_qs, unquote
import re
import aiohttp
import logging

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "https://fb.teamduckien.com, https://teamduckien.com",
    # "http://localhost:5500", # Bỏ comment dòng này nếu muốn test ở máy cá nhân
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Chỉ cho phép danh sách trên
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== LOGGING SETUP ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== APP SETUP ==========
app = FastAPI(
    title="Shopee Affiliate Link Generator",
    version="1.0.0",
    description="Convert Shopee links to affiliate links with automatic short link decoding"
)

# ========== CORS MIDDLEWARE ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ========== CONSTANTS ==========
AFFILIATE_ID = "17323090153"
AFFILIATE_ID_2 = ""
SUB_ID = "dealsieutoc-duckien--"
SHARE_CHANNEL = "4"

logger.info("=" * 80)
logger.info("🚀 Shopee Affiliate Link Generator API Started")
logger.info(f"📋 Affiliate ID: {AFFILIATE_ID}")
logger.info(f"📋 Affiliate ID 2: {AFFILIATE_ID_2}")
logger.info(f"📋 Sub ID: {SUB_ID}")
logger.info(f"📋 Share Channel: {SHARE_CHANNEL}")
logger.info("=" * 80)

# ========== HELPER FUNCTIONS ==========

def is_shopee_url(url: str) -> bool:
    """Check if URL is from Shopee"""
    if not url:
        return False
    
    shopee_domains = [
        'shopee.vn', 'shopee.ph', 'shopee.sg', 'shopee.my',
        'shopee.tw', 'shopee.id', 'shopee.th', 's.shopee', 'vn.shp.ee',
    ]
    
    return any(domain in url for domain in shopee_domains)


def is_short_link(url: str) -> bool:
    """Check if URL is a Shopee short link"""
    return ('s.shopee' in url or 'vn.shp.ee' in url) and 'an_redir' not in url


def is_affiliate_link(url: str) -> bool:
    """
    Check if URL is an affiliate link (an_redir link)
    
    Example:
        https://s.shopee.vn/an_redir?origin_link=...&affiliate_id=...
    """
    return 's.shopee' in url and 'an_redir' in url


def extract_origin_from_affiliate(url: str) -> str:
    """
    Extract origin_link parameter from affiliate link
    
    Example:
        Input: https://s.shopee.vn/an_redir?origin_link=https%3A%2F%2Fshopee.vn%2Fproduct%2F123%2F456&affiliate_id=123
        Output: https://shopee.vn/product/123/456
    
    Returns:
        str: Origin link if found, None otherwise
    """
    try:
        logger.info(f"🔎 Extracting origin_link from affiliate URL")
        
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        if 'origin_link' in query_params:
            origin_link = query_params['origin_link'][0]
            # URL decode the origin_link
            origin_link = unquote(origin_link)
            logger.info(f"✅ Extracted origin_link: {origin_link}")
            return origin_link
        
        logger.warning(f"⚠️ No origin_link parameter found in URL")
        return None
    
    except Exception as e:
        logger.error(f"❌ Error extracting origin_link: {e}")
        return None


def clean_url(url: str) -> str:
    """Remove query parameters from URL"""
    try:
        parsed = urlparse(url)
        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        if url != clean:
            logger.info(f"🧹 Cleaned URL")
            logger.info(f"   Before: {url}")
            logger.info(f"   After:  {clean}")
        
        return clean
    
    except Exception as e:
        logger.warning(f"⚠️ Could not clean URL: {e}")
        return url


async def decode_short_link(short_url: str) -> str:
    """Decode Shopee short link by following redirects"""
    try:
        logger.info(f"🔍 Decoding short link")
        logger.info(f"   Input: {short_url}")
        
        connector = aiohttp.TCPConnector(ssl=False)
        session = aiohttp.ClientSession(connector=connector)
        
        try:
            async with session.get(
                short_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as response:
                final_url = str(response.url)
                logger.info(f"   Decoded (raw): {final_url}")
                
                cleaned_url = clean_url(final_url)
                
                logger.info(f"   ✅ Decoded (cleaned): {cleaned_url}")
                return cleaned_url
        
        finally:
            await session.close()
    
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout while decoding short link (>15s)")
        return None
    except Exception as e:
        logger.error(f"❌ Error decoding short link: {str(e)}")
        return None


def create_affiliate_link(origin_url: str, affiliate_id: str) -> str:
    """Create Shopee affiliate link from origin URL"""
    encoded = quote(origin_url, safe='')
    
    affiliate_link = (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded}"
        f"&affiliate_id={affiliate_id}"
        f"&sub_id={SUB_ID}"
        f"&share_channel_code={SHARE_CHANNEL}"
    )
    
    logger.info(f"🔗 Created affiliate link for ID: {affiliate_id}")
    logger.info(f"   Origin: {origin_url}")
    logger.info(f"   Affiliate: {affiliate_link[:100]}...")
    
    return affiliate_link


# ========== API ENDPOINTS ==========

@app.get("/")
async def root():
    """Root endpoint - API information"""
    logger.info("📍 GET / - Root endpoint")
    
    return JSONResponse(
        status_code=200,
        content={
            "message": "Shopee Affiliate Link Generator API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "GET /": "API information",
                "GET /health": "Health check",
                "POST /create-link": "Create affiliate link"
            },
            "docs": "/docs"
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.info("📍 GET /health - Health check")
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": "1.0.0",
            "service": "Shopee Affiliate Link Generator",
            "affiliateId": AFFILIATE_ID,
            "affiliateId2": AFFILIATE_ID_2,
            "uptime": "running"
        }
    )


@app.post("/create-link")
async def create_link(origin_link: str = Query(..., description="Shopee URL, short link, or affiliate link")):
    """
    Main endpoint - Create affiliate link
    
    Supports:
        1. Shopee product URL: https://shopee.vn/product/123/456
        2. Shopee short link: https://s.shopee.vn/3B2qsVvyNN
        3. Affiliate link (regenerate): https://s.shopee.vn/an_redir?origin_link=...
        4. Shopee App link: https://vn.shp.ee/96iRuXxc
    """
    
    logger.info("=" * 80)
    logger.info("📍 POST /create-link - Create Affiliate Link")
    logger.info(f"📝 Input: {origin_link}")
    
    try:
        # ========== STEP 1: Validate Input ==========
        if not origin_link or not origin_link.strip():
            logger.warning("❌ Empty link received")
            return JSONResponse(
                status_code=400,
                content={"detail": "Link không được để trống"}
            )
        
        origin_link = origin_link.strip()
        logger.info(f"✅ Input validated - Length: {len(origin_link)} chars")
        
        # ========== STEP 2: Check Shopee URL ==========
        if not is_shopee_url(origin_link):
            logger.warning(f"❌ Not a Shopee URL")
            return JSONResponse(
                status_code=400,
                content={"detail": "Link phải từ Shopee"}
            )
        
        logger.info(f"✅ Valid Shopee URL detected")
        
        # ========== STEP 3: Initialize Variables ==========
        decoded_from_short = False
        final_origin_link = origin_link
        input_link = origin_link
        
        # ========== STEP 4: Check if it's an AFFILIATE LINK (Re-generate) ==========
        if is_affiliate_link(origin_link):
            logger.info(f"🔄 AFFILIATE LINK detected - Extracting origin_link...")
            
            extracted_origin = extract_origin_from_affiliate(origin_link)
            
            if extracted_origin and is_shopee_url(extracted_origin):
                logger.info(f"✅ Successfully extracted origin from affiliate link")
                final_origin_link = clean_url(extracted_origin)
                decoded_from_short = False  # Not from short link, from affiliate extraction
            else:
                logger.error(f"❌ Could not extract valid origin from affiliate link")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Không thể trích xuất link gốc từ affiliate link"}
                )
        
        # ========== STEP 5: Check and Decode SHORT LINK ==========
        elif is_short_link(origin_link):
            logger.info(f"🔄 Short link (s.shopee/vn.shp.ee) detected - Starting decode process...")
            decoded_from_short = True
            
            decoded = await decode_short_link(origin_link)
            
            if not decoded:
                logger.error(f"❌ Failed to decode short link")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Không thể giải mã short link - vui lòng thử lại"}
                )
            
            if not is_shopee_url(decoded):
                logger.error(f"❌ Decoded URL is not a valid Shopee URL")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Link giải mã không hợp lệ"}
                )
            
            final_origin_link = decoded
            logger.info(f"✅ Short link decoded successfully")
        
        # ========== STEP 6: Regular SHOPEE PRODUCT LINK ==========
        else:
            logger.info(f"📌 Regular Shopee product link - Cleaning query parameters...")
            final_origin_link = clean_url(origin_link)
        
        # ========== STEP 7: Create Affiliate Link ==========
        logger.info(f"🔗 Creating affiliate link from: {final_origin_link}")
        affiliate_link_1 = create_affiliate_link(final_origin_link, AFFILIATE_ID)
        affiliate_link_2 = None
        if AFFILIATE_ID_2 and AFFILIATE_ID_2.strip():
            affiliate_link_2 = create_affiliate_link(final_origin_link, AFFILIATE_ID_2)
        logger.info(f"✅ Affiliate links created successfully")
        
        # ========== STEP 8: Prepare Response ==========
        response_data = {
            "success": True,
            "message": "Tạo link thành công" + (
                " (giải mã từ short link)" if decoded_from_short else ""
            ),
            "affiliateLink": affiliate_link_1,
            "affiliateLink2": affiliate_link_2,
            "originLink": final_origin_link,
            "inputLink": input_link,
            "decodedFromShort": decoded_from_short,
            "affiliateId": AFFILIATE_ID,
            "affiliateId2": AFFILIATE_ID_2,
            "subId": SUB_ID,
            "shareChannelCode": SHARE_CHANNEL
        }
        
        logger.info(f"=" * 80)
        logger.info(f"✅ SUCCESS - Affiliate link created")
        logger.info(f"=" * 80)
        
        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    
    except Exception as e:
        logger.error(f"=" * 80)
        logger.error(f"❌ UNEXPECTED ERROR: {str(e)}")
        logger.error(f"=" * 80)
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi server: {str(e)}"}
        )


# ========== CORS Preflight Handler ==========
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle CORS preflight requests"""
    logger.info(f"📍 OPTIONS /{full_path} - CORS preflight")
    
    return JSONResponse(
        status_code=200,
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


# ========== Startup Event ==========
@app.on_event("startup")
async def startup_event():
    """Called when app starts"""
    logger.info("\n")
    logger.info("🎉 API is ready to receive requests!")
    logger.info("📝 Documentation: /docs")
    logger.info("\n")


# ========== Main ==========
if __name__ == "__main__":
    import asyncio
    import uvicorn
    
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    logger.info("\n🚀 Starting Uvicorn server...\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
