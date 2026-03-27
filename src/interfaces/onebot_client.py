import httpx
from config.config import NAPCAT_API, ONEBOT_TOKEN

BASE_URL = NAPCAT_API.rstrip("/")

headers = {}
if ONEBOT_TOKEN:
    headers["Authorization"] = f"Bearer {ONEBOT_TOKEN}"

async def send_private_text(user_id: int, text: str):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/send_private_msg",
            headers=headers,
            json={
                "user_id": str(user_id),
                "message": text
            }
        )
        r.raise_for_status()
        return r.json()

async def send_group_text(group_id: int, text: str):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/send_group_msg",
            headers=headers,
            json={
                "group_id": str(group_id),
                "message": text
            }
        )
        r.raise_for_status()
        return r.json()

async def send_private_record(user_id: int, file_path: str):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/send_private_msg",
            headers=headers,
            json={
                "user_id": str(user_id),
                "message": [
                    {
                        "type": "record",
                        "data": {
                            "file": f"file:///{file_path.replace('\\', '/')}"
                        }
                    }
                ]
            }
        )
        r.raise_for_status()
        return r.json()

async def send_group_record(group_id: int, file_path: str):
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/send_group_msg",
            headers=headers,
            json={
                "group_id": str(group_id),
                "message": [
                    {
                        "type": "record",
                        "data": {
                            "file": f"file:///{file_path.replace('\\', '/')}"
                        }
                    }
                ]
            }
        )
        r.raise_for_status()
        return r.json()

async def send_private_image(user_id: int, file_path: str):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/send_private_msg",
            headers=headers,
            json={
                "user_id": str(user_id),
                "message": [
                    {
                        "type": "image",
                        "data": {
                            "file": f"file:///{file_path.replace('\\', '/')}"
                        }
                    }
                ]
            }
        )
        r.raise_for_status()
        return r.json()

async def send_group_image(group_id: int, file_path: str):
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/send_group_msg",
            headers=headers,
            json={
                "group_id": str(group_id),
                "message": [
                    {
                        "type": "image",
                        "data": {
                            "file": f"file:///{file_path.replace('\\', '/')}"
                        }
                    }
                ]
            }
        )
        r.raise_for_status()
        return r.json()

async def send_group_poke(group_id: int, user_id: int):
    """
    发送群戳一戳
    
    Args:
        group_id: 群号
        user_id: 被戳的用户QQ号
    
    Returns:
        API 响应
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/group_poke",
            headers=headers,
            json={
                "group_id": str(group_id),
                "user_id": str(user_id)
            }
        )
        r.raise_for_status()
        return r.json()

async def send_private_poke(user_id: int):
    """
    发送私聊戳一戳
    
    Args:
        user_id: 被戳的用户QQ号
    
    Returns:
        API 响应
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/poke",
            headers=headers,
            json={
                "user_id": str(user_id)
            }
        )
        r.raise_for_status()
        return r.json()