import os
from supabase import create_client
from pydantic import EmailStr
from datetime import datetime, timedelta
from dotenv import load_dotenv
import bcrypt

# Load environment variables
load_dotenv()

# Supabase client initialization
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

# Helper function to hash passwords
def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Seed data for users and food items
def seed_data():
    # Create test users
    users = [
        {"username": "john_doe", "email": "john.doe@example.com", "password": "password123"},
        {"username": "jane_doe", "email": "jane.doe@example.com", "password": "password456"},
        {"username": "alice_smith", "email": "alice.smith@example.com", "password": "password789"},
    ]

    for user in users:
        # Hash the password and insert into the users table
        password_hash = hash_password(user['password'])
        response = supabase.table("users").insert({
            "username": user['username'],
            "email": user['email'],
            "password_hash": password_hash
        }).execute()

        if response.data:
            print(f"User created: {user['username']}")
        else:
            print(f"Failed to create user: {user['username']}")

    # Create test food items for each user
    food_items = [
        {"name": "Apples", "quantity": 10, "unit": "kg", "expiration_date": "2025-11-01"},
        {"name": "Bananas", "quantity": 5, "unit": "bunch", "expiration_date": "2025-10-20"},
        {"name": "Milk", "quantity": 2, "unit": "liters", "expiration_date": "2025-10-15"},
        {"name": "Carrots", "quantity": 7, "unit": "kg", "expiration_date": "2025-10-30"},
    ]

    # Assuming user IDs for testing (replace with actual IDs from your database)
    user_ids = [1, 2, 3]  # These should match your existing test users

    for user_id in user_ids:
        for item in food_items:
            response = supabase.table("food_stock").insert({
                "user_id": user_id,
                "name": item['name'],
                "quantity": item['quantity'],
                "unit": item['unit'],
                "expiration_date": item['expiration_date']
            }).execute()

            if response.data:
                print(f"Food item added for user {user_id}: {item['name']}")
            else:
                print(f"Failed to add food item for user {user_id}: {item['name']}")

# Run the seed data function
if __name__ == "__main__":
    seed_data()
