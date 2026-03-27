import httpx
import asyncio

BASE_URL = "http://127.0.0.1:6099"
TOKEN = "wo66RtvBdFBY9Q8P"

headers_list = [
    {"Authorization": f"Bearer {TOKEN}"},
    {"Authorization": TOKEN},
    {"access_token": TOKEN},
    {"authorization": TOKEN},
    {"authorization": f"Bearer {TOKEN}"},
]

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        for i, headers in enumerate(headers_list, 1):
            try:
                r = await client.post(
                    f"{BASE_URL}/api/send_private_msg",
                    headers=headers,
                    json={
                        "user_id": 2833864997,
                        "message": f"auth test {i}"
                    }
                )
                print("case", i, headers)
                print("status:", r.status_code)
                print("resp:", r.text)
                print("-" * 40)
            except Exception as e:
                print("case", i, "ERR", e)

asyncio.run(main())