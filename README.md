# Cenedese Demo

Django + Alpine.js demo of the Cenedese factory management system.

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in the environment file
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# 3. Create the database (PostgreSQL)
createdb cenedese_demo

# 4. Generate and run migrations
python manage.py makemigrations core
python manage.py migrate

# 5. Create Django admin superuser (optional)
python manage.py createsuperuser

# 6. Seed mock data (14 batches covering all test cases)
python manage.py seed_db

# 7. Start the server
python manage.py runserver
```

Open http://127.0.0.1:8000

## Demo credentials

| Username    | Password | Type       |
| ----------- | -------- | ---------- |
| operatore_d | pass123  | Dipanatura |
| operatore_r | pass123  | Roccatura  |

## What's covered in the seed data

| Batch | Test case                                | Calendar colour |
| ----- | ---------------------------------------- | --------------- |
| B001  | SPEDIT='S' (shipped)                     | Verde           |
| B002  | Last lav STATO=1 (macchina 1)            | Azzurro         |
| B003  | Last lav STATO=D (dip. da stribbiare)    | Arancione       |
| B004  | Last lav STATO=A (roccatura AC6)         | Giallo          |
| B005  | Last lav STATO=C (camera)                | Rosa            |
| B006  | Last lav STATO=R (riroccare)             | Viola           |
| B007  | Last lav STATO=S (sospeso)               | Grigio          |
| B008  | DATCON set, no lavorazioni               | Rosso           |
| B009  | No DATCON, no lavorazioni                | Fermo           |
| B010  | SPEDIT='S' overrides lavorazione         | Verde           |
| B011  | Multiple lavs — latest on macchina 2     | Azzurro         |
| B012  | CODART contains '+' → CAMERA default='S' | Azzurro         |
| B013  | Pre-existing Dipanatura disposition      | Azzurro         |
| B014  | Pre-existing Roccatura disposition       | Giallo          |
