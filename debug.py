import asyncio
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

VTEX_ACCOUNT_NAME = os.getenv("VTEX_ACCOUNT_NAME")
VTEX_ENVIRONMENT = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")
VTEX_APP_KEY = os.getenv("VTEX_APP_KEY")
VTEX_APP_TOKEN = os.getenv("VTEX_APP_TOKEN")

BASE_URL = f"https://{VTEX_ACCOUNT_NAME}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-VTEX-API-AppKey": VTEX_APP_KEY,
    "X-VTEX-API-AppToken": VTEX_APP_TOKEN
}

async def debug():
    skus = ["8836962"]
    async with aiohttp.ClientSession() as session:
        for sku_id in skus:
            # Checa endpoint de EAN
            url_ean = f"{BASE_URL}/stockkeepingunit/{sku_id}/ean"
            async with session.get(url_ean, headers=HEADERS) as response:
                eans = await response.json()
                print(f"SKU {sku_id} - EANs: {eans}")

            # Checa dados completos do SKU
            url_sku = f"{BASE_URL}/stockkeepingunit/{sku_id}"
            async with session.get(url_sku, headers=HEADERS) as response:
                data = await response.json()
                print(f"SKU {sku_id} - RefId: {data.get('RefId', 'não encontrado')}")
                print("---")

asyncio.run(debug())