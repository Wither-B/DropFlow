import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dropflow-secret-key-2026")
DB_NAME = "dropflow.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_NAME)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    con = conn.cursor()

    con.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT
    )""")

    con.execute("""CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    con.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        cost REAL NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        emoji TEXT NOT NULL
    )""")

    con.execute("""CREATE TABLE IF NOT EXISTS store_products (
        store_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        custom_name TEXT,
        custom_price REAL,
        active INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(store_id, product_id),
        FOREIGN KEY(store_id) REFERENCES stores(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )""")

    con.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        total REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )""")

    try:
        con.execute("ALTER TABLE stores ADD COLUMN description TEXT")
    except sqlite3.OperationalError:
        pass

    count = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        products = [
            ("Fone Bluetooth Pro", "Eletrônicos", 45.00, 119.90, 15, "🎧"),
            ("Smartwatch Fit X", "Tecnologia", 85.00, 199.90, 10, "⌚"),
            ("Mochila Urban", "Acessórios", 35.00, 89.90, 20, "🎒"),
            ("Luminária LED", "Casa", 17.00, 49.90, 25, "💡"),
            ("Garrafa térmica", "Casa", 22.00, 59.90, 30, "🍼"),
            ("Suporte para celular", "Acessórios", 12.00, 39.90, 40, "📱")
        ]
        for row in products:
            con.execute("INSERT INTO products(name, category, cost, price, stock, emoji) VALUES(?,?,?,?,?,?)", row)

    conn.commit()
    conn.close()

# Inicializa/migra a base de dados ao arrancar o servidor web
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
        
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            flash("Usuário ou senha incorretos.")
            
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email", "")
        
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, password, email))
            db.commit()
            flash("Conta criada com sucesso! Faça login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Este nome de usuário já existe.")
            
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    products_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    orders_count = db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (session["user_id"],)).fetchone()[0]
    stores_count = db.execute("SELECT COUNT(*) FROM stores WHERE user_id = ?", (session["user_id"],)).fetchone()[0]
    
    return render_template("dashboard.html", products_count=products_count, orders_count=orders_count, stores_count=stores_count)

@app.route("/products")
@login_required
def products():
    db = get_db()
    items = db.execute("SELECT * FROM products").fetchall()
    return render_template("products.html", products=items)

@app.route("/stores")
@login_required
def stores():
    db = get_db()
    user_stores = db.execute("SELECT * FROM stores WHERE user_id = ?", (session["user_id"],)).fetchall()
    return render_template("stores.html", stores=user_stores)

@app.route("/store_settings", methods=["GET", "POST"])
@login_required
def store_settings():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description", "")
        
        existing = db.execute("SELECT id FROM stores WHERE user_id = ?", (session["user_id"],)).fetchone()
        if existing:
            db.execute("UPDATE stores SET name = ?, description = ? WHERE id = ?", (name, description, existing["id"]))
        else:
            db.execute("INSERT INTO stores (user_id, name, description) VALUES (?, ?, ?)", (session["user_id"], name, description))
        db.commit()
        flash("Configurações da loja salvas com sucesso!")
        
    store = db.execute("SELECT * FROM stores WHERE user_id = ?", (session["user_id"],)).fetchone()
    return render_template("store_settings.html", store=store)

@app.route("/orders")
@login_required
def orders():
    db = get_db()
    user_orders = db.execute("""
        SELECT o.*, p.name as product_name, p.emoji
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ?
        ORDER BY o.created_at DESC
    """, (session["user_id"],)).fetchall()
    return render_template("orders.html", orders=user_orders)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
