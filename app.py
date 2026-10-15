import os
import requests
from datetime import datetime
from functools import wraps

import click
from dotenv import load_dotenv
from flask import (
    Flask, abort, flash, redirect, render_template, request,
    session, url_for
)
from flask_login import (
    LoginManager, UserMixin, current_user, login_required,
    login_user, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
db_url = os.getenv("DATABASE_URL", "sqlite:///dark2light.db")
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
    # Flask-SQLAlchemy resolves relative SQLite paths under the instance folder.
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = 3600

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Order place karne ya account use karne ke liye pehle login karein."
login_manager.login_message_category = "info"

CATEGORIES = [
    "LED Lights", "Switches & Sockets", "Wires & Cables",
    "Circuit Breakers", "Extension Boards", "Fans & Accessories"
]

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30), default="")
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    orders = db.relationship("Order", back_populates="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Integer, nullable=False)  # PKR whole rupees
    stock = db.Column(db.Integer, default=0, nullable=False)
    image_url = db.Column(db.String(500), default="")
    featured = db.Column(db.Boolean, default=False, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(80), nullable=False)
    notes = db.Column(db.Text, default="")
    total = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(30), default="COD", nullable=False)
    status = db.Column(db.String(30), default="Pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    product_name = db.Column(db.String(160), nullable=False)
    unit_price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order = db.relationship("Order", back_populates="items")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    cart_count = sum(int(q) for q in cart.values())
    return {"cart_count": cart_count, "categories": CATEGORIES}

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped

def cart_details():
    cart = session.get("cart", {})
    rows, total = [], 0
    for product_id, quantity in cart.items():
        product = db.session.get(Product, int(product_id))
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if product and product.active and quantity > 0:
            subtotal = product.price * quantity
            rows.append({"product": product, "quantity": quantity, "subtotal": subtotal})
            total += subtotal
    return rows, total

def seed_products():
    if Product.query.count():
        return
    samples = [
        ("LED Bulb 12W Cool White", "LED Lights", "Energy-saving 12W LED bulb for home and office.", 450, 80, True,
         "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=80"),
        ("Premium Modular Switch", "Switches & Sockets", "Modern wall switch with a clean, durable finish.", 280, 120, True,
         "https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=900&q=80"),
        ("Universal 4-Socket Extension", "Extension Boards", "Four outlets for common home and office devices.", 1850, 35, True,
         "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?auto=format&fit=crop&w=900&q=80"),
        ("MCB Circuit Breaker 32A", "Circuit Breakers", "32A miniature circuit breaker. Check suitability with an electrician.", 1250, 24, True,
         "https://images.unsplash.com/photo-1621905251189-08b45d6a269e?auto=format&fit=crop&w=900&q=80"),
        ("Copper Wire 1.5mm (Coil)", "Wires & Cables", "Electrical copper wire coil; confirm length and specification before use.", 7200, 12, False,
         "https://images.unsplash.com/photo-1558618047-3c8c76ca7d13?auto=format&fit=crop&w=900&q=80"),
        ("LED Panel Light 18W", "LED Lights", "Slim 18W LED panel for indoor lighting.", 1600, 42, True,
         "https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?auto=format&fit=crop&w=900&q=80"),
        ("Double Socket Outlet", "Switches & Sockets", "Double outlet for compatible household electrical installations.", 650, 60, False,
         "https://images.unsplash.com/photo-1558002038-1055907df827?auto=format&fit=crop&w=900&q=80"),
        ("Ceiling Fan Regulator", "Fans & Accessories", "Fan speed regulator for compatible installations.", 950, 28, False,
         "https://images.unsplash.com/photo-1621905251918-48416bd8575a?auto=format&fit=crop&w=900&q=80"),
    ]
    for i, (name, category, description, price, stock, featured, image) in enumerate(samples, start=1):
        db.session.add(Product(
            name=name, slug=f"sample-product-{i}", category=category,
            description=description, price=price, stock=stock,
            featured=featured, image_url=image, active=True
        ))
    db.session.commit()

@app.cli.command("init-db")
def init_db_command():
    """Create tables and add sample products."""
    with app.app_context():
        db.create_all()
        seed_products()
    click.echo("Database ready. Sample products added if the store was empty.")

@app.cli.command("create-admin")
@click.option("--name", prompt="Admin name")
@click.option("--email", prompt="Admin email")
@click.option("--password", prompt="Admin password", hide_input=True, confirmation_prompt=True)
def create_admin_command(name, email, password):
    """Create an administrator account."""
    email = email.strip().lower()
    if len(password) < 10:
        raise click.ClickException("Password kam az kam 10 characters ka rakhein.")
    if User.query.filter_by(email=email).first():
        raise click.ClickException("Is email ka account pehle se mojood hai.")
    user = User(name=name.strip(), email=email, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Admin account created: {email}")

@app.route("/")
def home():
    featured = Product.query.filter_by(active=True, featured=True).order_by(Product.created_at.desc()).limit(8).all()
    if not featured:
        featured = Product.query.filter_by(active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template("home.html", featured=featured)

@app.route("/products")
def products():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest")
    page = request.args.get("page", 1, type=int)
    listing = Product.query.filter_by(active=True)
    if query:
        like = f"%{query}%"
        listing = listing.filter(or_(Product.name.ilike(like), Product.description.ilike(like), Product.category.ilike(like)))
    if category in CATEGORIES:
        listing = listing.filter_by(category=category)
    if sort == "price_low":
        listing = listing.order_by(Product.price.asc())
    elif sort == "price_high":
        listing = listing.order_by(Product.price.desc())
    elif sort == "name":
        listing = listing.order_by(Product.name.asc())
    else:
        listing = listing.order_by(Product.created_at.desc())
    pagination = listing.paginate(page=page, per_page=12, error_out=False)
    return render_template("products.html", pagination=pagination, query=query, selected_category=category, sort=sort)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        abort(404)
    return render_template("product_detail.html", product=product)

@app.route("/cart")
def cart():
    rows, total = cart_details()
    return render_template("cart.html", rows=rows, total=total)

@app.post("/cart/add/<int:product_id>")
def add_to_cart(product_id):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        abort(404)
    quantity = request.form.get("quantity", 1, type=int)
    if not quantity or quantity < 1:
        flash("Quantity kam az kam 1 honi chahiye.", "error")
        return redirect(url_for("product_detail", product_id=product.id))
    cart_data = session.get("cart", {})
    current_quantity = int(cart_data.get(str(product.id), 0))
    if current_quantity + quantity > product.stock:
        flash(f"Available stock sirf {product.stock} hai.", "error")
    else:
        cart_data[str(product.id)] = current_quantity + quantity
        session["cart"] = cart_data
        session.modified = True
        flash("Product cart mein add ho gaya.", "success")
    return redirect(request.referrer or url_for("cart"))

@app.post("/cart/update")
def update_cart():
    cart_data = session.get("cart", {})
    for product_id in list(cart_data.keys()):
        qty = request.form.get(f"qty_{product_id}", 0, type=int)
        product = db.session.get(Product, int(product_id))
        if not product or not product.active or qty <= 0:
            cart_data.pop(product_id, None)
        elif qty > product.stock:
            cart_data[product_id] = product.stock
            flash(f"{product.name}: quantity available stock tak adjust ki gayi.", "info")
        else:
            cart_data[product_id] = qty
    session["cart"] = cart_data
    session.modified = True
    flash("Cart update ho gaya.", "success")
    return redirect(url_for("cart"))

@app.post("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    cart_data = session.get("cart", {})
    cart_data.pop(str(product_id), None)
    session["cart"] = cart_data
    session.modified = True
    flash("Product cart se remove ho gaya.", "info")
    return redirect(url_for("cart"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Naam/email dein aur password kam az kam 8 characters ka rakhein.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Is email se account pehle se mojood hai.", "error")
        else:
            user = User(name=name, email=email, phone=phone)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account ban gaya. Khush aamdeed!", "success")
            return redirect(url_for("home"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Aap login ho gaye.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("home"))
        flash("Email ya password durust nahi.", "error")
    return render_template("login.html")

@app.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Aap logout ho gaye.", "info")
    return redirect(url_for("home"))

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    rows, total = cart_details()
    if not rows:
        flash("Checkout se pehle cart mein products add karein.", "info")
        return redirect(url_for("products"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        notes = request.form.get("notes", "").strip()
        if not all([name, email, phone, address, city]):
            flash("Naam, email, phone, address aur city sab fill karein.", "error")
            return render_template("checkout.html", rows=rows, total=total)
        # Re-check stock immediately before saving the order.
        for row in rows:
            product = db.session.get(Product, row["product"].id)
            if not product or not product.active or product.stock < row["quantity"]:
                db.session.rollback()
                flash(f"{row['product'].name} ka stock change ho gaya. Cart check karein.", "error")
                return redirect(url_for("cart"))
        order = Order(
            order_number=f"D2L-{datetime.utcnow().strftime('%y%m%d%H%M%S')}-{current_user.id}",
            user_id=current_user.id, customer_name=name, email=email, phone=phone,
            address=address, city=city, notes=notes, total=total, payment_method="COD",
            status="Pending"
        )
        for row in rows:
            product = db.session.get(Product, row["product"].id)
            product.stock -= row["quantity"]
            order.items.append(OrderItem(
                product_id=product.id, product_name=product.name,
                unit_price=product.price, quantity=row["quantity"]
            ))
        db.session.add(order)
        db.session.commit()
        
        try:
            webhook_url = os.getenv("N8N_WEBHOOK_URL")
            webhook_key = os.getenv("N8N_WEBHOOK_KEY")

            if webhook_url and webhook_key:
                payload = {
                    "order_id": order.order_number,
                    "customer": order.customer_name,
                    "total": float(order.total),
                    "status": order.status,
                    "items": [
                        {
                            "product": item.product_name,
                            "quantity": item.quantity,
                            "price": float(item.unit_price)
                        }
                        for item in order.items
                    ]
                }

                response = requests.post(
                    webhook_url,
                    json=payload,
                    headers={"X-Dark2Light-Key": webhook_key},
                    timeout=5
                )
                response.raise_for_status()
        except requests.RequestException as error:
            app.logger.error("n8n webhook failed: %s", error)
        session["cart"] = {}
        flash("Order place ho gaya! Order number: " + order.order_number, "success")
        return redirect(url_for("order_detail", order_id=order.id))
    return render_template("checkout.html", rows=rows, total=total)

@app.route("/account/orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("my_orders.html", orders=orders)

@app.route("/order/<int:order_id>")
@login_required
def order_detail(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template("order_detail.html", order=order)

@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    return render_template(
        "admin/dashboard.html",
        product_count=Product.query.count(),
        order_count=Order.query.count(),
        pending_count=Order.query.filter_by(status="Pending").count(),
        sales=db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).filter(Order.status != "Cancelled").scalar(),
        orders=orders
    )

@app.route("/admin/products")
@admin_required
def admin_products():
    items = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("admin/products.html", products=items)

@app.route("/admin/products/new", methods=["GET", "POST"])
@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_form(product_id=None):
    product = db.session.get(Product, product_id) if product_id else None
    if product_id and not product:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        image_url = request.form.get("image_url", "").strip()
        price = request.form.get("price", 0, type=int)
        stock = request.form.get("stock", 0, type=int)
        featured = bool(request.form.get("featured"))
        active = bool(request.form.get("active"))
        if not name or category not in CATEGORIES or price < 0 or stock < 0:
            flash("Product name/category durust hon aur price/stock negative na ho.", "error")
            return render_template("admin/product_form.html", product=product, categories=CATEGORIES)
        slug_base = "-".join(name.lower().split())[:150] or "product"
        slug = slug_base
        counter = 2
        while Product.query.filter(Product.slug == slug, Product.id != (product.id if product else 0)).first():
            slug = f"{slug_base}-{counter}"
            counter += 1
        if not product:
            product = Product(name=name, slug=slug, category=category, price=price, stock=stock)
            db.session.add(product)
        product.name, product.slug, product.category = name, slug, category
        product.description, product.image_url = description, image_url
        product.price, product.stock = price, stock
        product.featured, product.active = featured, active
        db.session.commit()
        flash("Product save ho gaya.", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=product, categories=CATEGORIES)

@app.post("/admin/products/<int:product_id>/delete")
@admin_required
def admin_product_delete(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    product.active = False  # Soft-delete preserves order history.
    db.session.commit()
    flash("Product store se hide kar diya gaya.", "info")
    return redirect(url_for("admin_products"))

@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template("admin/orders.html", orders=orders)

@app.post("/admin/orders/<int:order_id>/status")
@admin_required
def admin_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    status = request.form.get("status", "")
    allowed = {"Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"}
    if status not in allowed:
        flash("Order status valid nahi.", "error")
        return redirect(url_for("admin_orders"))
    if status == "Cancelled" and order.status != "Cancelled":
        # Restore stock only once when an order is cancelled.
        for item in order.items:
            if item.product_id:
                product = db.session.get(Product, item.product_id)
                if product:
                    product.stock += item.quantity
    elif order.status == "Cancelled" and status != "Cancelled":
        # Reserve stock again if an admin re-opens a cancelled order.
        for item in order.items:
            if item.product_id:
                product = db.session.get(Product, item.product_id)
                if product and product.stock >= item.quantity:
                    product.stock -= item.quantity
                else:
                    flash("Stock kam hai; order status change nahi hua.", "error")
                    return redirect(url_for("admin_orders"))
    order.status = status
    db.session.commit()
    flash("Order status update ho gaya.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="Is page ko access karne ki permission nahi."), 403

@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="Yeh page nahi mila."), 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_products()
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
