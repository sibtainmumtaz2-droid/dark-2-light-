# Dark2Light.com — Flask E-commerce Starter

Roman Urdu setup guide aur local development project.

## Features
- Responsive storefront and category/search/sort
- Product details, session cart, stock checks
- Customer registration/login with hashed passwords
- Checkout with Cash on Delivery (COD)
- Customer order history and order detail
- Admin-only dashboard, product management, inventory and order status
- SQLite database, CSRF protection, soft-hide products

## Requirements
- Python 3.10 or newer
- VS Code
- Internet connection for Google Fonts and sample remote product images (site logic works without them)

## Windows setup (VS Code terminal)
Open this folder in VS Code, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use Command Prompt terminal:
```bat
.venv\Scripts\activate.bat
```

Open `.env` and replace `SECRET_KEY` with a long random secret. Then initialize database:
```powershell
flask --app app init-db
```

Create your admin account:
```powershell
flask --app app create-admin
```
Enter the admin name, email and a strong password when prompted.

Run the website:
```powershell
flask --app app run --debug
```
Open http://127.0.0.1:5000 in your browser. Stop the server with Ctrl+C.

Alternative: `python app.py` also creates the tables and sample products, but use the Flask CLI for creating the admin.

## Admin pages
- Admin dashboard: http://127.0.0.1:5000/admin
- Products: http://127.0.0.1:5000/admin/products
- Orders: http://127.0.0.1:5000/admin/orders

Login using the account created with `flask --app app create-admin`. Do not add an `is_admin` registration field to public forms.

## Important before a real launch
This is a runnable starter, not a fully audited production commerce platform. Before accepting real orders:
1. Set a unique long `SECRET_KEY`; never deploy with the development fallback.
2. Set `FLASK_DEBUG=0`, use HTTPS, configure a production WSGI server and hosting.
3. Use a production database/backups, rate-limit login, add email verification/password reset and privacy/returns policies.
4. Replace sample products/images/prices with accurate stock and specifications. Confirm image rights.
5. Add real courier integration, delivery fees, order notifications and verified business contact details.
6. Payment is COD only; no card, bank or wallet payment is processed.
7. Sample products/prices are illustrative only. Electrical product specifications and installation must be checked by a qualified professional.

## Troubleshooting
- `py` not recognized: install Python from python.org and enable “Add Python to PATH”, then reopen VS Code.
- `flask` not recognized: activate `.venv` and run `pip install -r requirements.txt`.
- `No module named flask`: the virtual environment may not be active.
- Admin page gives 403: log in with the admin account, not a regular customer account.
- Sample remote images may fail to load if offline; replace image URLs with your own product photos.
- To reset demo data, stop Flask and delete the SQLite database file under the `instance` folder, then rerun `flask --app app init-db`. This permanently deletes local demo users and orders.
