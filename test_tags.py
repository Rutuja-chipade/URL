import httpx
import asyncio

BASE_URL = "http://127.0.0.1:8000"

async def test_tags():
    async with httpx.AsyncClient() as client:
        # 1. Register a new user
        user_email = f"test_{asyncio.get_event_loop().time()}@example.com"
        register_resp = await client.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Test User",
            "email": user_email,
            "password": "password123"
        })
        print(f"Register status: {register_resp.status_code}")
        token = register_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create work link
        work_resp = await client.post(f"{BASE_URL}/api/shorten", json={
            "original_url": "https://google.com",
            "tags": ["work"]
        }, headers=headers)
        print(f"Work link status: {work_resp.status_code}")

        # 3. Create personal link
        personal_resp = await client.post(f"{BASE_URL}/api/shorten", json={
            "original_url": "https://youtube.com",
            "tags": ["personal"]
        }, headers=headers)
        print(f"Personal link status: {personal_resp.status_code}")

        # 4. List all links
        all_resp = await client.get(f"{BASE_URL}/api/user/urls", headers=headers)
        print(f"All links count: {all_resp.json()['total']}")

        # 5. Filter by 'work'
        work_filter_resp = await client.get(f"{BASE_URL}/api/user/urls?tag=work", headers=headers)
        work_data = work_filter_resp.json()
        print(f"Work filtered count: {work_data['total']}")
        
        # 6. Verify result
        if work_data['total'] == 1 and work_data['urls'][0]['tags'] == ['work']:
            print("✅ Tagging and Filtering Verification PASSED!")
        else:
            print("❌ Tagging and Filtering Verification FAILED!")
            print(f"Debug: {work_data}")

if __name__ == "__main__":
    asyncio.run(test_tags())
