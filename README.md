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

## 📦Installation

### 1. Clone the Repository

Clone the project repository to your local machine:


git clone [https://github.com/your-username/wasteless-api.git](https://github.com/Alien4Gamer/WasteLess-API)
cd wasteless-api

### 2. Install requirements

pip install -r requirements.txt

### 3. Start the FastAPI server locally with the following command:

uvicorn main:app --reload

### 4. Access the API Documentation

Once the server is running, you can interact with the API via Swagger UI at:

