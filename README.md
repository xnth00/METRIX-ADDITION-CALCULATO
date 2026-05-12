# Matrix Addition Calculator

A web app where users can sign up, log in, and add two matrices together.
Calculation history is saved to a SQLite database per user.

---

## How to run

1. Install Python 3.8 or newer.
2. Install the required packages:

   ```
   pip install -r requirements.txt
   ```

3. Start the server:

   ```
   python app.py
   ```

4. Open your browser to **http://localhost:5000**

The first time you run it, a file called `matrix_app.db` is created
automatically — that's the SQLite database.

---

## Project structure

```
matrix_calculator/
├── app.py              # Entry point — run this
├── auth.py             # Login / signup / logout routes
├── calculator.py       # Matrix routes + JSON API
├── matrix_ops.py       # Pure matrix math (no Flask)
├── database.py         # All SQLite code
├── requirements.txt
├── templates/
│   ├── login.html
│   ├── signup.html
│   ├── forgot.html
│   └── calculator.html
└── matrix_app.db       # Created on first run
```

### What each file does

| File              | Role                                                        |
|-------------------|-------------------------------------------------------------|
| `app.py`          | Creates the Flask app and registers all routes              |
| `auth.py`         | Everything for accounts: login, signup, logout, forgot      |
| `calculator.py`   | Calculator page + JSON endpoints (calculate, history, etc.) |
| `matrix_ops.py`   | Pure math: validate + add matrices. No web stuff here.      |
| `database.py`     | All SQL queries — change DB later by editing only this file |

---

## How the parts talk to each other

```
Browser  ─── POST /api/calculate ──>  calculator.py
                                          │
                                          ├──> matrix_ops.add_matrices()
                                          ├──> database.save_calculation()
                                          └──> returns JSON to browser
```

The frontend JavaScript calls `/api/calculate`, `/api/history`, etc.
The backend does the actual math, saves it, and returns the result as JSON.

---

## Database schema

Two tables:

**`users`**
- `id` (auto), `email` (unique), `password_hash`, `first_name`, `last_name`, `created_at`

**`calculations`**
- `id` (auto), `user_id` (foreign key), `rows`, `cols`, `matrix_a`, `matrix_b`, `result`, `created_at`

Matrices are stored as JSON text inside `matrix_a`, `matrix_b`, `result`.

---

## Features

- Sign up with first name, last name, email, password (with strength meter)
- Passwords hashed with Werkzeug (never stored in plain text)
- Log in / log out with session cookies
- "Forgot password" placeholder page (real reset flow is out of scope)
- Matrix calculator from 1×1 up to 8×8
- Backend validates matrices (size match, numeric values)
- History saved per user, newest first, with delete + clear-all
- Session caches recent history for speed; DB is the source of truth
- Toast notifications for errors and successes
- Login-required protection on the calculator page

---

## Testing the math without the server

You can run the matrix module on its own to confirm the math works:

```
python matrix_ops.py
```

This runs a few built-in tests and prints the results.

---

## Notes for the group

- **Backend:** all logic is in `auth.py`, `calculator.py`, `matrix_ops.py`
- **Frontend:** templates in `templates/`. The design from `interface.py`
  is preserved and now wired to real backend endpoints.
- **Database:** if you want to switch from SQLite to MySQL/PostgreSQL,
  you only need to change `database.py` — the rest of the project uses
  its functions and won't need to change.
