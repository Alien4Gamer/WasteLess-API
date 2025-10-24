from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import bcrypt

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
if not url or not key:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY")

supabase: Client = create_client(url, key)

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def wipe():
    # Order: recipe_ingredients -> recipes -> food_stock -> users
    supabase.table("recipe_ingredients").delete().neq("id", -1).execute()
    supabase.table("recipes").delete().neq("id", -1).execute()
    supabase.table("food_stock").delete().neq("id", -1).execute()
    supabase.table("users").delete().neq("id", -1).execute()

def seed():
    # Users
    u1 = supabase.table("users").insert({"username": "alice", "email": "alice@example.com", "password_hash": hash_pw("alice123")}).execute().data[0]
    u2 = supabase.table("users").insert({"username": "bob", "email": "bob@example.com", "password_hash": hash_pw("bob123")}).execute().data[0]

    today = date.today()
    # Stock for Alice
    foods = [
        {"user_id": u1["id"], "name": "Tomato", "name_norm": "tomato", "quantity": 4, "unit": "pcs", "expiration_date": str(today + timedelta(days=3))},
        {"user_id": u1["id"], "name": "Pasta", "name_norm": "pasta", "quantity": 500, "unit": "g", "expiration_date": str(today + timedelta(days=180))},
        {"user_id": u1["id"], "name": "Cashew Nuts", "name_norm": "cashew nuts", "quantity": 200, "unit": "g", "expiration_date": str(today + timedelta(days=7))},  # Cashew nuts as cheese alternative
        {"user_id": u1["id"], "name": "Olive Oil", "name_norm": "olive oil", "quantity": 250, "unit": "ml", "expiration_date": str(today + timedelta(days=365))},
    ]
    supabase.table("food_stock").insert(foods).execute()

    # Alice's recipe: Pasta Pomodoro
    recipe = supabase.table("recipes").insert({"user_id": u1["id"], "title": "Pasta Pomodoro", "description": "Simple pasta with tomatoes and cashew nuts"}).execute().data[0]
    supabase.table("recipe_ingredients").insert([
        {"recipe_id": recipe["id"], "name": "Pasta", "name_norm": "pasta", "quantity": 200, "unit": "g"},
        {"recipe_id": recipe["id"], "name": "Tomato", "name_norm": "tomato", "quantity": 2, "unit": "pcs"},
        {"recipe_id": recipe["id"], "name": "Cashew Nuts", "name_norm": "cashew nuts", "quantity": 50, "unit": "g"},  # Cashew nuts as cheese substitute
        {"recipe_id": recipe["id"], "name": "Olive Oil", "name_norm": "olive oil", "quantity": 10, "unit": "ml"},
    ]).execute()

    # Bob's data
    foods_bob = [
        {"user_id": u2["id"], "name": "Oat Milk", "name_norm": "oat milk", "quantity": 1, "unit": "l", "expiration_date": str(today + timedelta(days=2))},  # Oat milk instead of regular milk
    ]
    supabase.table("food_stock").insert(foods_bob).execute()

if __name__ == "__main__":
    wipe()
    seed()
    print("Database wiped and demo data inserted.")
