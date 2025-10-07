from fastapi import FastAPI, HTTPException, Depends, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from jose import JWTError, jwt
from datetime import datetime, timedelta
from supabase import create_client, Client
from fastapi.openapi.utils import get_openapi
import bcrypt
import os
from typing import Optional

# ----------- ENV & SETUP -----------
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
SECRET_KEY = os.environ.get("JWT_SECRET", "secret")  # Fallback für dev
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

supabase: Client = create_client(url, key)
app = FastAPI(title="WasteLess API")

# ----------- SECURITY SETUP -----------
bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> int:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


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
    unit: str
    expiration_date: str  # format: YYYY-MM-DD


# ----------- HELPER FUNCTIONS -----------

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ----------- DATABASE FUNCTIONS -----------

def check_username_exists(username: str) -> bool:
    response = supabase.table('users').select('*').eq('username', username).execute()
    return bool(response.data)

def create_user_in_db(user: UserCreate):
    password_hash = hash_password(user.password)
    response = supabase.table("users").insert({
        "username": user.username,
        "email": user.email,
        "password_hash": password_hash
    }).execute()
    return response

def add_food_item_to_db(user_id: int, item: FoodItemCreate):
    response = supabase.table("food_stock").insert({
        "user_id": user_id,
        "name": item.name,
        "quantity": item.quantity,
        "unit": item.unit,
        "expiration_date": item.expiration_date
    }).execute()
    return response

def delete_user_food_from_db(user_id: int):
    response = supabase.table("food_stock").delete().eq("user_id", user_id).execute()
    return response


# ----------- ROUTES -----------

@app.post("/users/")
def create_user(user: UserCreate):
    if check_username_exists(user.username):
        raise HTTPException(status_code=409, detail="Username already exists")

    response = create_user_in_db(user)
    if response.data:
        return {"message": "User created", "data": response.data}
    else:
        raise HTTPException(status_code=500, detail="Error creating user")

@app.post("/login/")
def login_user(user: UserLogin):
    response = supabase.table("users").select("*").eq("username", user.username).execute()

    if not response.data:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_record = response.data[0]
    stored_hash = user_record["password_hash"]

    if not verify_password(user.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"user_id": user_record["id"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/{user_id}/food")
def add_food_item(user_id: int, item: FoodItemCreate, current_user_id: int = Depends(get_current_user)):
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    response = add_food_item_to_db(user_id, item)
    if response.data:
        return {"message": "Item added", "data": response.data}
    else:
        raise HTTPException(status_code=400, detail="Error adding item")

@app.delete("/users/{user_id}/food")
def delete_user_food(user_id: int, current_user_id: int = Depends(get_current_user)):
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    response = delete_user_food_from_db(user_id)
    if response.data:
        return {"message": f"All items for User {user_id} deleted."}
    else:
        raise HTTPException(status_code=400, detail="Error deleting food items")


# ----------- CUSTOM OPENAPI FOR AUTH BUTTON -----------

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="WasteLess API",
        version="1.0.0",
        description="API for WasteLess with JWT Authentication",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    for path in openapi_schema["paths"].values():
        for method in path.values():
            method["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
