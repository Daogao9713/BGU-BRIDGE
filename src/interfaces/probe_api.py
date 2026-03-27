import httpx
import asyncio

BASE = "http://127.0.0.1:6099"
paths = [
    "/",
    "/docs",
    "/openapi.json",
    "/get_login_info",
    "/send_private_msg",
    "/send_msg",
    "/api/send_private_msg",
    "/api/send_msg",
    "/v1/send_private_msg",
    "/v1/send_msg",
]

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        for p in paths:
            url = BASE + p
            try:
                r = await client.get(url)
                print(p, r.status_code, r.text[:200])
            except Exception as e:
                print(p, "ERR", e)

asyncio.run(main())