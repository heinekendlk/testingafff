from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from urllib.parse import quote, unquote
import re
import aiohttp
import os
from dotenv import load_dotenv
import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ========== APP SETUP ==========
app = FastAPI(
    title="Shopee Affiliate Link Generator",
    version="1.0.0",
    description="Convert Shopee links to affiliate links"
)

# ========== CORS - Allow All ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ========== Constants ==========
AFFILIATE_ID = "17323090153"
SUB_ID = "addlivetag-ductoan"
SHARE_CHANNEL = "4"

logger.info("=" * 60)
logger.info("🚀 Shopee Affiliate API Started")
logger.info(f"Affiliate ID: {AFFILIATE_ID}")
logger.info("=" * 60)

# ========== HELPER FUNCTIONS ==========

def is_shopee_url(url: str) -> bool:
    """Check if URL is from Shopee"""
    patterns = ['shopee.vn', 'shopee.ph', 'shopee.sg', 'shopee.my', 
                'shopee.tw', 'shopee.id', 'shopee.th', 's.shopee']
    return any(pattern in url for pattern in patterns)


def is_short_link(url: str) -> bool:
    """Check if URL is short link"""
    return 's.shopee' in url and 'an_redir' not in url


async def decode_short_link(short_url: str) -> str:
    """Decode short link to get origin link"""
    try:
        logger.info(f"🔍 Decoding: {short_url}")
        
        connector = aiohttp.TCPConnector(ssl=False)
        session = aiohttp.ClientSession(connector=connector)
        
        try:
            async with session.get(
                short_url,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            ) as response:
                final_url = str(response.url)
                logger.info(f"✅ Decoded to: {final_url}")
                return final_url
        finally:
            await session.close()
            
    except Exception as e:
        logger.error(f"❌ Decode error: {e}")
        return None


def create_affiliate_link(origin_url: str) -> str:
    """Create affiliate link from origin URL"""
    encoded = quote(origin_url, safe='')
    return (
        f"https://s.shopee.vn/an_redir?"
        f"origin_link={encoded}"
        f"&affiliate_id={AFFILIATE_ID}"
        f"&sub_id={SUB_ID}"
        f"&share_channel_code={SHARE_CHANNEL}"
    )


# ========== ROOT ENDPOINT ==========
@app.get("/")
async def root():
    """Root endpoint"""
    logger.info("GET / - Root")
    return {
        "message": "Shopee Affiliate API",
        "version": "1.0.0",
        "status": "running"
    }


# ========== HEALTH CHECK ==========
@app.get("/health")
async def health():
    """Health check endpoint"""
    logger.info("GET /health - Health check")
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "Shopee Affiliate Link Generator"
    }


# ========== MAIN ENDPOINT - CREATE LINK ==========
@app.post("/create-link")
async def create_link(origin_link: str = Query(...)):
    """
    POST /create-link
    
    Query Parameters:
    - origin_link: Shopee URL (short or normal)
    
    Returns:
    {
        "success": true,
        "message": "...",
        "affiliateLink": "...",
        "originLink": "...",
        ...
    }
    """
    
    logger.info("=" * 60)
    logger.info("📥 POST /create-link called")
    
    try:
        # ========== Validate Input ==========
        if not origin_link or not origin_link.strip():
            logger.warning("❌ Empty link received")
            return JSONResponse(
                status_code=400,
                content={"detail": "Link không được để trống"}
            )
        
        origin_link = origin_link.strip()
        logger.info(f"📝 Input: {origin_link}")
        
        # ========== Check Shopee URL ==========
        if not is_shopee_url(origin_link):
            logger.warning(f"❌ Not a Shopee URL: {origin_link}")
            return JSONResponse(
                status_code=400,
                content={"detail": "Link phải từ Shopee"}
            )
        
        logger.info("✅ Valid Shopee URL")
        
        # ========== Variables ==========
        decoded_from_short = False
        final_origin_link = origin_link
        input_link = origin_link
        
        # ========== Decode Short Link if Needed ==========
        if is_short_link(origin_link):
            logger.info("🔄 Short link detected - decoding...")
            decoded_from_short = True
            
            decoded = await decode_short_link(origin_link)
            
            if not decoded:
                logger.error("❌ Failed to decode")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Không thể giải mã short link"}
                )
            
            if not is_shopee_url(decoded):
                logger.error(f"❌ Decoded URL not Shopee: {decoded}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Link giải mã không hợp lệ"}
                )
            
            final_origin_link = decoded
            logger.info(f"✅ Decoded successfully")
        
        logger.info(f"✅ Final origin link: {final_origin_link}")
        
        # ========== Create Affiliate Link ==========
        logger.info("🔗 Creating affiliate link...")
        affiliate_link = create_affiliate_link(final_origin_link)
        logger.info(f"✅ Affiliate link created")
        
        # ========== Prepare Response ==========
        response_data = {
            "success": True,
            "message": "Tạo link thành công" + (" (giải mã từ short link)" if decoded_from_short else ""),
            "affiliateLink": affiliate_link,
            "originLink": final_origin_link,
            "inputLink": input_link,
            "decodedFromShort": decoded_from_short,
            "affiliateId": AFFILIATE_ID,
            "subId": SUB_ID,
            "shareChannelCode": SHARE_CHANNEL
        }
        
        logger.info("✅ Response prepared")
        logger.info("=" * 60)
        
        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        logger.info("=" * 60)
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi server: {str(e)}"}
        )


# ========== CATCH-ALL OPTIONS (CORS Preflight) ==========
@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle CORS preflight"""
    logger.info(f"OPTIONS /{path}")
    return JSONResponse(
        status_code=200,
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting Uvicorn server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
