from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta, date
from jose import JWTError, jwt
import bcrypt
import os
from typing import Optional, List
from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file


# ----------- ENV & SETUP -----------
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
SECRET_KEY = os.environ.get("JWT_SECRET", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

if not url or not key:
    raise RuntimeError("Please set SUPABASE_URL and SUPABASE_KEY in your environment or .env file")

# Initialize Supabase client
supabase: Client = create_client(url, key)

# Set up FastAPI and Security
app = FastAPI(title="WasteLess API")
bearer_scheme = HTTPBearer()

# ----------- SECURITY SETUP -----------
def get_current_user(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> int:
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
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class FoodItemCreate(BaseModel):
    name: str
    quantity: float
    unit: str
    expiration_date: date

class FoodItemConsume(BaseModel):
    quantity: float

class RecipeCreate(BaseModel):  # Added missing RecipeCreate model
    title: str
    description: Optional[str] = None
    ingredients: List[FoodItemCreate]

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

def normalize_name(s: str) -> str:
    return s.strip().lower()

# ----------- DATABASE HELPERS -----------
def create_user_in_db(user: UserCreate):
    password_hash = hash_password(user.password)
    response = supabase.table("users").insert({
        "username": user.username,
        "email": user.email,
        "password_hash": password_hash
    }).execute()
    return response

def get_user_by_username(username: str):
    response = supabase.table("users").select("*").eq("username", username).limit(1).execute()
    return response.data[0] if response.data else None

def find_existing_food_row(user_id: int, name: str, unit: str, expiration_date: date):
    response = supabase.table("food_stock").select("*").eq("user_id", user_id).eq("name_norm", normalize_name(name)).eq("unit", unit).eq("expiration_date", str(expiration_date)).limit(1).execute()
    return response.data[0] if response.data else None

def add_or_update_food_item(user_id: int, item: FoodItemCreate):
    existing = find_existing_food_row(user_id, item.name, item.unit, item.expiration_date)
    if existing:
        new_qty = float(existing["quantity"]) + float(item.quantity)
        resp = supabase.table("food_stock").update({"quantity": new_qty}).eq("id", existing["id"]).eq("user_id", user_id).execute()
        return resp, "updated"
    else:
        resp = supabase.table("food_stock").insert({
            "user_id": user_id,
            "name": item.name,
            "name_norm": normalize_name(item.name),
            "quantity": item.quantity,
            "unit": item.unit,
            "expiration_date": str(item.expiration_date)
        }).execute()
        return resp, "created"

def get_all_food_items(user_id: int):
    return supabase.table("food_stock").select("*").eq("user_id", user_id).execute()

def get_food_item_detail(user_id: int, item_id: int):
    response = supabase.table("food_stock").select("*").eq("user_id", user_id).eq("id", item_id).limit(1).execute()
    return response.data[0] if response.data else None

def delete_user_food_from_db(user_id: int):
    response = supabase.table("food_stock").delete().eq("user_id", user_id).execute()
    return response


def compute_recipe_suggestions(user_id: int):
    # Step 1: Retrieve all food items in the user's inventory
    food_items_response = get_all_food_items(user_id)
    user_food_items = {item["name_norm"]: item for item in food_items_response.data or []}

    # Step 2: Retrieve all recipes from the database
    recipes_response = supabase.table("recipes").select("*").eq("user_id", user_id).execute()
    if not recipes_response.data:
        return {"suggestions": []}  # No recipes found for the user

    recipes = recipes_response.data
    suggested_recipes = []

    # Step 3: Iterate through each recipe and check if it can be made with the user's food items
    for recipe in recipes:
        recipe_id = recipe["id"]
        ingredients_response = supabase.table("recipe_ingredients").select("*").eq("recipe_id", recipe_id).execute()

        if not ingredients_response.data:
            continue  # Skip recipes that don't have ingredients

        recipe_ingredients = ingredients_response.data
        missing_ingredients = []
        can_make_recipe = True

        # Check if the user has the necessary ingredients
        for ingredient in recipe_ingredients:
            ingredient_name = ingredient["name_norm"]
            if ingredient_name not in user_food_items:
                missing_ingredients.append(ingredient["name"])
                can_make_recipe = False

        # If the recipe can be made (all ingredients are available)
        if can_make_recipe:
            suggested_recipes.append({
                "title": recipe["title"],
                "description": recipe["description"],
                "ingredients": [ingredient["name"] for ingredient in recipe_ingredients]
            })
        elif missing_ingredients:
            suggested_recipes.append({
                "title": recipe["title"],
                "description": recipe["description"],
                "missing_ingredients": missing_ingredients
            })

    # Step 4: Return the list of suggested recipes
    return {"suggestions": suggested_recipes}


# ----------- ROUTES -----------
# 1) Registrierung
@app.post("/users/", tags=["auth"])
def create_user(user: UserCreate):
    # Überprüfe, ob der Benutzername bereits existiert
    if get_user_by_username(user.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    response = create_user_in_db(user)
    if response.data:
        return {"message": "User created", "data": response.data}
    else:
        raise HTTPException(status_code=500, detail="Error creating user")

# 2) Login / JWT
@app.post("/login/", tags=["auth"])
def login_user(user: UserLogin):
    # Überprüfe Benutzer und Passwort
    user_record = get_user_by_username(user.username)
    if not user_record or not verify_password(user.password, user_record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token = create_access_token(data={"user_id": user_record["id"]})
    return {"access_token": access_token, "token_type": "bearer"}

# 3) Lebensmittel anlegen (oder Menge erhöhen, falls vorhanden)
@app.post("/users/{user_id}/food", tags=["food"])
def add_food_item(user_id: int, item: FoodItemCreate, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    resp, status = add_or_update_food_item(user_id, item)
    if resp.data is None:
        raise HTTPException(status_code=400, detail="Error adding/updating item")
    return {"message": f"Item {status}", "data": resp.data}

# 4) Vorrat listen
@app.get("/users/{user_id}/food", tags=["food"])
def list_food_items(user_id: int, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    response = get_all_food_items(user_id)
    return {"items": response.data or []}

# 5) Detailansicht eines Items
@app.get("/users/{user_id}/food/{item_id}", tags=["food"])
def food_item_detail(user_id: int, item_id: int, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    item = get_food_item_detail(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# 6) Item verbrauchen (Menge reduzieren; <=0 => löschen)
@app.post("/users/{user_id}/food/{item_id}/consume", tags=["food"])
def consume_item(user_id: int, item_id: int, body: FoodItemConsume, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    item = get_food_item_detail(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    new_qty = float(item["quantity"]) - float(body.quantity)
    if new_qty <= 0:
        supabase.table("food_stock").delete().eq("id", item_id).eq("user_id", user_id).execute()
        return {"message": "Item consumed and removed"}
    else:
        resp = supabase.table("food_stock").update({"quantity": new_qty}).eq("id", item_id).eq("user_id", user_id).execute()
        return {"message": "Item quantity updated", "data": resp.data}

# 7) Item endgültig löschen
@app.delete("/users/{user_id}/food/{item_id}", tags=["food"])
def delete_item(user_id: int, item_id: int, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    supabase.table("food_stock").delete().eq("id", item_id).eq("user_id", user_id).execute()
    return {"message": "Item deleted"}

# 8) Vorrat leeren
@app.delete("/users/{user_id}/food", tags=["food"])
def delete_user_food(user_id: int, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    response = delete_user_food_from_db(user_id)
    return {"message": f"All food items for user {user_id} deleted."}

# 9) Bald ablaufend (default 5 Tage)
@app.get("/users/{user_id}/food/expiring", tags=["food"])
def expiring_items(user_id: int, days: int = 5, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    today = date.today()
    until = today + timedelta(days=days)
    resp = (supabase.table("food_stock")
            .select("*")
            .eq("user_id", user_id)
            .gte("expiration_date", str(today))
            .lte("expiration_date", str(until))
            .order("expiration_date", desc=False)
            .execute())
    return {"items": resp.data or []}

# 10) Rezept-Vorschläge aus Vorräten
@app.get("/users/{user_id}/recipes/suggest", tags=["recipes"])
def suggest_recipes(user_id: int, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"suggestions": compute_recipe_suggestions(user_id)}

# 11) Rezept speichern (inkl. Zutaten)
@app.post("/users/{user_id}/recipes", tags=["recipes"])
def save_recipe(user_id: int, payload: RecipeCreate, current_user_id: int = Depends(get_current_user)):
    # Zugriffsschutz
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    recipe_resp = supabase.table("recipes").insert({
        "user_id": user_id,
        "title": payload.title,
        "description": payload.description or ""
    }).execute()
    if not recipe_resp.data:
        raise HTTPException(status_code=400, detail="Error creating recipe")
    recipe_id = recipe_resp.data[0]["id"]
    ingredient_rows = [{
        "recipe_id": recipe_id,
        "name": ing.name,
        "name_norm": normalize_name(ing.name),
        "quantity": ing.quantity,
        "unit": ing.unit
    } for ing in payload.ingredients]
    ing_resp = supabase.table("recipe_ingredients").insert(ingredient_rows).execute()
    return {"message": "Recipe saved", "recipe": recipe_resp.data[0], "ingredients": ing_resp.data}
