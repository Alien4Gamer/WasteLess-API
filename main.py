from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os
from supabase import create_client, Client

# Load env
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI(title="WasteLess API")


# ----------- MODELS -----------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str  # später speichern ( mit Hashing?)


class FoodItemCreate(BaseModel):
    name: str
    quantity: float
    unit: str  # "kg", "g", "l", "ml", "pcs"
    expiration_date: str  # YYYY-MM-DD


# ----------- DATABASE FUNCTIONS -----------

def create_user_in_db(user: UserCreate):
    """Insert user into the database"""
    response = supabase.table("users").insert({
        "username": user.username,
        "email": user.email,
        "password_hash": user.password  # Hashing?
    }).execute()

    return response


def check_username_exists(username):
    """Check if username already exists"""
    response = supabase.table('users').select('*').eq('username', username).execute()

    # Accessing 'data' from the response
    if response.data:  # The data attribute holds the actual response content
        return True
    return False


def add_food_item_to_db(user_id: int, item: FoodItemCreate):
    """Insert food item into the food_stock table"""
    response = supabase.table("food_stock").insert({
        "user_id": user_id,
        "name": item.name,
        "quantity": item.quantity,
        "unit": item.unit,
        "expiration_date": item.expiration_date
    }).execute()

    return response


def delete_user_food_from_db(user_id: int):
    """Delete all food items for a specific user"""
    response = supabase.table("food_stock").delete().eq("user_id", user_id).execute()

    return response


# ----------- ROUTES -----------

@app.post("/users/")
def create_user(user: UserCreate):
    # username check
    if check_username_exists(user.username):
        # duplicated username
        raise HTTPException(status_code=409, detail="Username already exists")

    # Proceed to create the user in the database
    response = create_user_in_db(user)

    # Check if user creation was successful
    if response.data:
        return {"message": "User created", "data": response.data}
    else:
        raise HTTPException(status_code=500, detail="Error creating user")


@app.post("/users/{user_id}/food")
def add_food_item(user_id: int, item: FoodItemCreate):
    response = add_food_item_to_db(user_id, item)

    # simple success check
    if response.data:
        return {"message": "Item added", "data": response.data}
    else:
        raise HTTPException(status_code=400, detail="Error adding item")

@app.delete("/users/{user_id}/food")
def delete_user_food(user_id: int):
    response = delete_user_food_from_db(user_id)

    # simple success check
    if response.data:
        return {"message": f"All items for User {user_id} deleted."}
    else:
        raise HTTPException(status_code=400, detail="Error deleting food items")
