from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os
import bcrypt
from supabase import create_client, Client

# ----------- ENV & SUPABASE SETUP -----------
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

app = FastAPI(title="WasteLess API")


# ----------- MODELS -----------

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class FoodItemCreate(BaseModel):
    name: str
    quantity: float
    unit: str  # "kg", "g", "l", "ml", "pcs"
    expiration_date: str  # YYYY-MM-DD


# ----------- HELPER FUNCTIONS -----------

def hash_password(plain_password: str) -> str:
    """Hashes a plain password using bcrypt"""
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed one"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ----------- DATABASE FUNCTIONS -----------

def create_user_in_db(user: UserCreate):
    """Insert user into the database"""
    password_hash = hash_password(user.password)

    response = supabase.table("users").insert({
        "username": user.username,
        "email": user.email,
        "password_hash": password_hash
    }).execute()

    return response


def check_username_exists(username: str) -> bool:
    """Check if username already exists"""
    response = supabase.table('users').select('*').eq('username', username).execute()
    return bool(response.data)


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
        raise HTTPException(status_code=409, detail="Username already exists")

    # create user
    response = create_user_in_db(user)

    if response.data:
        return {"message": "User created", "data": response.data}
    else:
        raise HTTPException(status_code=500, detail="Error creating user")


@app.post("/login/")
def login_user(user: UserLogin):
    # get user from db
    response = supabase.table("users").select("*").eq("username", user.username).execute()

    if not response.data:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_record = response.data[0]
    stored_hash = user_record["password_hash"]

    if not verify_password(user.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return {"message": "Login successful", "user_id": user_record["id"]}


@app.post("/users/{user_id}/food")
def add_food_item(user_id: int, item: FoodItemCreate):
    response = add_food_item_to_db(user_id, item)

    if response.data:
        return {"message": "Item added", "data": response.data}
    else:
        raise HTTPException(status_code=400, detail="Error adding item")


@app.delete("/users/{user_id}/food")
def delete_user_food(user_id: int):
    response = delete_user_food_from_db(user_id)

    if response.data:
        return {"message": f"All items for User {user_id} deleted."}
    else:
        raise HTTPException(status_code=400, detail="Error deleting food items")
