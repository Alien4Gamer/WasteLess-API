from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from datetime import datetime, timedelta, date
from jose import JWTError, jwt
import bcrypt
from typing import Optional, List
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ----------- ENV & SETUP -----------

# Get Supabase URL and key from environment variables
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
SECRET_KEY = os.environ.get("JWT_SECRET", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Ensure required environment variables are set
if not url or not key:
    raise RuntimeError("Please set SUPABASE_URL and SUPABASE_KEY in your environment or .env file")

# Initialize Supabase client
supabase: Client = create_client(url, key)

# Set up FastAPI app
app = FastAPI(title="WasteLess API")
bearer_scheme = HTTPBearer()

# ----------- SECURITY SETUP -----------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> int:
    """
    Extracts the current user's ID from the provided JWT token.
    """
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

class RecipeCreate(BaseModel):
    title: str
    description: Optional[str] = None
    ingredients: List[FoodItemCreate]

# ----------- HELPER FUNCTIONS -----------

def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.
    """
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies that a plain-text password matches a hashed password.
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates an access token with an optional expiration time.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def normalize_name(s: str) -> str:
    """
    Normalizes a name by stripping whitespace and converting to lowercase.
    """
    return s.strip().lower()

# ----------- DATABASE HELPERS -----------

def create_user_in_db(user: UserCreate):
    """
    Creates a new user in the database.
    """
    password_hash = hash_password(user.password)
    response = supabase.table("users").insert({
        "username": user.username,
        "email": user.email,
        "password_hash": password_hash
    }).execute()
    return response

def get_user_by_username(username: str):
    """
    Retrieves a user from the database by their username.
    """
    response = supabase.table("users").select("*").eq("username", username).limit(1).execute()
    return response.data[0] if response.data else None

def find_existing_food_row(user_id: int, name: str, unit: str, expiration_date: date):
    """
    Checks if a food item already exists in the user's food inventory.
    """
    response = supabase.table("food_stock").select("*").eq("user_id", user_id).eq("name_norm", normalize_name(name)).eq("unit", unit).eq("expiration_date", str(expiration_date)).limit(1).execute()
    return response.data[0] if response.data else None

def add_or_update_food_item(user_id: int, item: FoodItemCreate):
    """
    Adds a new food item to the user's inventory or updates the quantity if the item already exists.
    """
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
    """
    Retrieves all food items in the user's inventory.
    """
    return supabase.table("food_stock").select("*").eq("user_id", user_id).execute()

def get_food_item_detail(user_id: int, item_id: int):
    """
    Retrieves details of a specific food item from the user's inventory.
    """
    response = supabase.table("food_stock").select("*").eq("user_id", user_id).eq("id", item_id).limit(1).execute()
    return response.data[0] if response.data else None

def delete_user_food_from_db(user_id: int):
    """
    Deletes all food items from the user's inventory.
    """
    response = supabase.table("food_stock").delete().eq("user_id", user_id).execute()
    return response


def compute_recipe_suggestions(user_id: int):
    """
    Suggests recipes based on the user's available food items.
    """
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

@app.post("/users/", tags=["auth"])
def create_user(user: UserCreate):
    """
    Endpoint to create a new user.
    """
    # Check if the username already exists
    if get_user_by_username(user.username):
        raise HTTPException(status_code=409, detail="Username already exists")
    response = create_user_in_db(user)
    if response.data:
        return {"message": "User created", "data": response.data}
    else:
        raise HTTPException(status_code=500, detail="Error creating user")

@app.post("/login/", tags=["auth"])
def login_user(user: UserLogin):
    """
    Endpoint for user login, returns an access token.
    """
    # Verify username and password
    user_record = get_user_by_username(user.username)
    if not user_record or not verify_password(user.password, user_record["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token = create_access_token(data={"user_id": user_record["id"]})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/users/{user_id}/food", tags=["food"])
def add_food_item(user_id: int, item: FoodItemCreate, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to add a food item to the user's inventory or update its quantity if it already exists.
    """
    # Access control: Ensure the user is authorized to modify their own inventory
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Add or update the food item in the inventory
    resp, status = add_or_update_food_item(user_id, item)

    if resp.data is None:
        raise HTTPException(status_code=400, detail="Error adding/updating item")

    # Return success message with the response data
    return {"message": f"Item {status}", "data": resp.data}


@app.get("/users/{user_id}/food", tags=["food"])
def list_food_items(user_id: int, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to list all food items in the user's inventory.
    """
    # Access control: Ensure the user is authorized to view their inventory
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Retrieve all food items from the user's inventory
    response = get_all_food_items(user_id)

    # Return the list of food items or an empty list if none exist
    return {"items": response.data or []}


@app.get("/users/{user_id}/food/{item_id}", tags=["food"])
def food_item_detail(user_id: int, item_id: int, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to get the details of a specific food item in the user's inventory.
    """
    # Access control: Ensure the user is authorized to view their food item details
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Retrieve the food item details by ID
    item = get_food_item_detail(user_id, item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Return the details of the food item
    return item


@app.post("/users/{user_id}/food/{item_id}/consume", tags=["food"])
def consume_item(user_id: int, item_id: int, body: FoodItemConsume, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to reduce the quantity of a food item in the user's inventory.
    If the quantity reaches zero or below, the item will be deleted.
    """
    # Access control: Ensure the user is authorized to modify their inventory
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Retrieve the food item by ID
    item = get_food_item_detail(user_id, item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Calculate the new quantity after consumption
    new_qty = float(item["quantity"]) - float(body.quantity)

    if new_qty <= 0:
        # If the item quantity is zero or negative, delete the item
        supabase.table("food_stock").delete().eq("id", item_id).eq("user_id", user_id).execute()
        return {"message": "Item consumed and removed"}
    else:
        # Otherwise, update the quantity of the item
        resp = supabase.table("food_stock").update({"quantity": new_qty}).eq("id", item_id).eq("user_id",
                                                                                               user_id).execute()
        return {"message": "Item quantity updated", "data": resp.data}


@app.delete("/users/{user_id}/food/{item_id}", tags=["food"])
def delete_item(user_id: int, item_id: int, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to delete a food item from the user's inventory.
    """
    # Access control: Ensure the user is authorized to delete the item
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete the food item by ID
    supabase.table("food_stock").delete().eq("id", item_id).eq("user_id", user_id).execute()

    # Return a confirmation message
    return {"message": "Item deleted"}


@app.delete("/users/{user_id}/food", tags=["food"])
def delete_user_food(user_id: int, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to delete all food items from the user's inventory.
    """
    # Access control: Ensure the user is authorized to delete all items from their inventory
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete all food items from the user's inventory
    response = delete_user_food_from_db(user_id)

    # Return a confirmation message
    return {"message": f"All food items for user {user_id} deleted."}


@app.get("/users/{user_id}/food/expiring", tags=["food"])
def expiring_items(user_id: int, days: int = 5, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to list food items that are expiring within a specified number of days (default is 5 days).
    """
    # Access control: Ensure the user is authorized to view their food items
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get the current date and the date until which to check for expiration
    today = date.today()
    until = today + timedelta(days=days)

    # Retrieve food items expiring within the specified date range
    resp = (supabase.table("food_stock")
            .select("*")
            .eq("user_id", user_id)
            .gte("expiration_date", str(today))
            .lte("expiration_date", str(until))
            .order("expiration_date", desc=False)
            .execute())

    # Return the list of expiring items or an empty list if none exist
    return {"items": resp.data or []}


@app.get("/users/{user_id}/recipes/suggest", tags=["recipes"])
def suggest_recipes(user_id: int, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to suggest recipes based on the user's food inventory.
    """
    # Access control: Ensure the user is authorized to view recipe suggestions
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Call the function to compute recipe suggestions based on the user's food inventory
    return {"suggestions": compute_recipe_suggestions(user_id)}


@app.post("/users/{user_id}/recipes", tags=["recipes"])
def save_recipe(user_id: int, payload: RecipeCreate, current_user_id: int = Depends(get_current_user)):
    """
    Endpoint to save a new recipe along with its ingredients in the database.
    """
    # Access control: Ensure the user is authorized to save recipes
    if current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Insert the recipe into the database
    recipe_resp = supabase.table("recipes").insert({
        "user_id": user_id,
        "title": payload.title,
        "description": payload.description or ""
    }).execute()

    if not recipe_resp.data:
        raise HTTPException(status_code=400, detail="Error creating recipe")

    recipe_id = recipe_resp.data[0]["id"]

    # Prepare the ingredient rows to insert into the database
    ingredient_rows = [{
        "recipe_id": recipe_id,
        "name": ing.name,
        "name_norm": normalize_name(ing.name),
        "quantity": ing.quantity,
        "unit": ing.unit
    } for ing in payload.ingredients]

    # Insert the ingredients for the recipe into the database
    ing_resp = supabase.table("recipe_ingredients").insert(ingredient_rows).execute()

    # Return the response with the saved recipe and its ingredients
    return {"message": "Recipe saved", "recipe": recipe_resp.data[0], "ingredients": ing_resp.data}
