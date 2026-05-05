import asyncio
import argparse
from app.database import connect_db, get_db, close_db

async def make_admin(email: str):
    await connect_db()
    db = get_db()
    
    user = await db.users.find_one({"email": email.lower()})
    if not user:
        print(f"❌ User with email '{email}' not found.")
        await close_db()
        return
        
    if user.get("is_admin", False):
        print(f"⚠️ User '{email}' is already an admin.")
        await close_db()
        return
        
    result = await db.users.update_one(
        {"email": email.lower()},
        {"$set": {"is_admin": True}}
    )
    
    if result.modified_count > 0:
        print(f"✅ Successfully promoted '{email}' to Admin!")
    else:
        print(f"❌ Failed to promote '{email}'.")
        
    await close_db()
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a user to Admin")
    parser.add_argument("email", type=str, help="The email of the user to promote")
    args = parser.parse_args()
    
    asyncio.run(make_admin(args.email))
