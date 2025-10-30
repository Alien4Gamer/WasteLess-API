# WasteLess API

A **FastAPI-based** RESTful API that allows users to:

- Manage their food inventory
- Track expiration dates (best-before dates)
- Save and manage recipes
- Receive suggestions for recipes based on available ingredients
- Authenticate and authorize users securely using JWT tokens

## 🚀 Features

- CRUD operations for food items and recipes
- Expiration date tracking for food items (including items that are about to expire)
- Recipe management with ingredients and descriptions
- Suggestions for recipes based on food inventory (missing ingredients)
- User authentication with JWT-based tokens
- Secure and customizable access to each user's data

## 🛠️ Planned V2 Features

- AI-powered recipe suggestions from soon-to-expire ingredients (e.g., via GPT API)
- Consolidated shopping lists based on available food inventory
- Integration with other services (e.g., grocery delivery platforms)

## 🧑‍💻 Tech Stack

- **Backend:** Python (FastAPI)
- **Database:** Supabase (PostgreSQL)
- **Authentication:** JWT-based authentication
- **Deployment:** Docker + (AWS EC2 / Heroku / Render)

## 📦 Installation

### 1. Create a Supabase Database

Go to [Supabase](https://supabase.com) and create a new project.

Then, create the necessary tables in the database using the following SQL script:

```sql
-- Erstelle Sequenzen für Auto-Increment
CREATE SEQUENCE IF NOT EXISTS items_id_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS recipe_ingredients_id_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS recipes_id_seq START WITH 1;
CREATE SEQUENCE IF NOT EXISTS users_id_seq START WITH 1;

-- Erstelle die "users"-Tabelle (wird von anderen Tabellen referenziert)
CREATE TABLE public.users (
  id integer NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  username character varying NOT NULL UNIQUE,
  email character varying NOT NULL UNIQUE,
  password_hash text NOT NULL,
  CONSTRAINT users_pkey PRIMARY KEY (id)
);

-- Erstelle die "recipes"-Tabelle
CREATE TABLE public.recipes (
  id integer NOT NULL DEFAULT nextval('recipes_id_seq'::regclass),
  user_id integer NOT NULL,
  title character varying NOT NULL,
  description text,
  CONSTRAINT recipes_pkey PRIMARY KEY (id),
  CONSTRAINT recipes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);

-- Erstelle die "recipe_ingredients"-Tabelle
CREATE TABLE public.recipe_ingredients (
  id integer NOT NULL DEFAULT nextval('recipe_ingredients_id_seq'::regclass),
  recipe_id integer NOT NULL,
  name character varying NOT NULL,
  quantity character varying,
  unit text,
  name_norm text,
  CONSTRAINT recipe_ingredients_pkey PRIMARY KEY (id),
  CONSTRAINT recipe_ingredients_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id) ON DELETE CASCADE
);

-- Erstelle die "food_stock"-Tabelle
CREATE TABLE public.food_stock (
  id integer NOT NULL DEFAULT nextval('items_id_seq'::regclass),
  user_id integer NOT NULL,
  name character varying NOT NULL,
  quantity real,
  unit character varying,
  expiration_date date,
  name_norm text,
  CONSTRAINT food_stock_pkey PRIMARY KEY (id),
  CONSTRAINT items_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
```
### 2. Obtain Your Supabase API Key and Create the `.env`-File

Edit the `.env`-file and add your own Supabase keys.

Here’s how to find your Supabase API keys in the Supabase Dashboard:

1. Open the **Supabase Dashboard** and select your project.
2. Go to **Settings → API**.
3.Under the **Data API** section, you will find the following information:
  - **Project URL**
4. Under the **Project API keys** section, you will find the following information:
   - **anon public key** (this is the `SUPABASE_ANON_KEY`, which can be safely used in client-side code when RLS is enabled).
5. Copy the **URL and anon public key** to your `.env`-file.

### 3. Clone the Repository

Clone the project repository to your local machine:

```bash
git clone https://github.com/Alien4Gamer/WasteLess-API.git
cd wasteless-api
```

### 4. Install Dependencies

Run the following command to install all the required Python packages:

```bash
pip install -r requirements.txt
```

### 5. Start the FastAPI Server Locally

To start the FastAPI server locally, run the following command:

```bash
uvicorn main:app --reload
```

### 6. Access the API Documentation

Once the server is running, you can interact with the API via the Swagger UI. Open the following link in your browser:

[http://127.0.0.1:8000/docs#/](http://127.0.0.1:8000/docs#/)


