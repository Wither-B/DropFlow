from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, re, secrets, uuid, json, hmac, hashlib
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None
from pathlib import Path
from functools import wraps
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dropflow.db"
app = Flask(__name__)
app.secret_key = os.environ.get("DROPFlow_SECRET")
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)  # local development only
    app.config["EPHEMERAL_SECRET"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]

app.jinja_env.globals["csrf_token"] = csrf_token

@app.before_request
def csrf_protection():
    if request.method in ("POST","PUT","PATCH","DELETE"):
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
        expected = session.get("csrf_token")
        if not expected or not sent or not hmac.compare_digest(str(sent), str(expected)):
            return "CSRF token inválido.", 400

def _postgres_enabled():
    return bool(os.environ.get("DATABASE_URL", "").strip())

class DBCompat:
    """Small compatibility layer so the existing app can use ? placeholders on PostgreSQL or SQLite."""
    def __init__(self, conn, postgres=False):
        self.conn = conn
        self.postgres = postgres
    def __enter__(self):
        self.conn.__enter__()
        return self
    def __exit__(self, *args):
        return self.conn.__exit__(*args)
    def execute(self, sql, params=()):
        if self.postgres:
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

def db():
    if _postgres_enabled():
        if psycopg is None:
            raise RuntimeError("psycopg não está instalado.")
        conn = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
        return DBCompat(conn, postgres=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return DBCompat(conn, postgres=False)

def init_db():
    if _postgres_enabled():
        with db() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS users(
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                balance DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS products(
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                cost DOUBLE PRECISION NOT NULL,
                price DOUBLE PRECISION NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                emoji TEXT NOT NULL DEFAULT '📦',
                active INTEGER NOT NULL DEFAULT 1
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS stores(
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE REFERENCES users(id),
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                logo_emoji TEXT NOT NULL DEFAULT '🛍️',
                primary_color TEXT NOT NULL DEFAULT '#6c4cff',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                custom_domain TEXT
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS store_products(
                store_id BIGINT NOT NULL REFERENCES stores(id),
                product_id BIGINT NOT NULL REFERENCES products(id),
                custom_name TEXT,
                custom_price DOUBLE PRECISION,
                active INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(store_id, product_id)
            )""")
            con.execute("""CREATE TABLE IF NOT EXISTS orders(
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id),
                product_id BIGINT NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL,
                total DOUBLE PRECISION NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            count = con.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
            if count == 0:
                con.executemany("INSERT INTO products(name,category,cost,price,stock,emoji) VALUES(%s,%s,%s,%s,%s,%s)", [
                    ("Fone Bluetooth Pro","Eletrônicos",29.90,59.90,128,"🎧"),
                    ("Smartwatch Fit X","Tecnologia",48.00,89.90,76,"⌚"),
                    ("Mochila Urban","Acessórios",38.50,74.90,54,"🎒"),
                    ("Luminária LED","Casa",17.00,39.90,213,"💡"),
                    ("Garrafa térmica","Casa",22.00,49.90,96,"🧴"),
                    ("Suporte para celular","Acessórios",8.50,24.90,180,"📱")
                ])
        return

    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            cost REAL NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            emoji TEXT NOT NULL DEFAULT '📦',
            active INTEGER NOT NULL DEFAULT 1
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS stores(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            logo_emoji TEXT NOT NULL DEFAULT '🛍️',
            primary_color TEXT NOT NULL DEFAULT '#6c4cff',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS store_products(
            store_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            custom_name TEXT,
            custom_price REAL,
            active INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(store_id, product_id),
            FOREIGN KEY(store_id) REFERENCES stores(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")
        try:
            con.execute("ALTER TABLE stores ADD COLUMN custom_domain TEXT")
        except sqlite3.OperationalError:
            pass
        count = con.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
        if count == 0:
            con.executemany("INSERT INTO products(name,category,cost,price,stock,emoji) VALUES(?,?,?,?,?,?)", [
                ("Fone Bluetooth Pro","Eletrônicos",29.90,59.90,128,"🎧"),
                ("Smartwatch Fit X","Tecnologia",48.00,89.90,76,"⌚"),
                ("Mochila Urban","Acessórios",38.50,74.90,54,"🎒"),
                ("Luminária LED","Casa",17.00,39.90,213,"💡"),
                ("Garrafa térmica","Casa",22.00,49.90,96,"🧴"),
                ("Suporte para celular","Acessórios",8.50,24.90,180,"📱")
            ])

# Initialize/migrate the database when the web process starts (works with Gunicorn/Render).
init_db()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Entre na sua conta para continuar.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    with db() as con:
        products = con.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC LIMIT 4").fetchall()
    return render_template("home.html", products=products)

@app.route("/cadastro", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or len(password) < 8:
            flash("Preencha todos os campos. A senha precisa ter pelo menos 8 caracteres.", "error")
        else:
            try:
                with db() as con:
                    cur = con.execute("INSERT INTO users(name,email,password_hash) VALUES(?,?,?) RETURNING id",
                                (name,email,generate_password_hash(password)))
                    uid = cur.fetchone()["id"]
                    base_name = name.strip() or "Minha Loja"
                    slug_base = re.sub(r"[^a-z0-9]+", "-", base_name.lower()).strip("-") or "minha-loja"
                    slug = slug_base
                    n = 2
                    while con.execute("SELECT 1 FROM stores WHERE slug=?", (slug,)).fetchone():
                        slug = f"{slug_base}-{n}"
                        n += 1
                    con.execute("INSERT INTO stores(user_id,name,slug,description) VALUES(?,?,?,?)",
                                (uid, base_name, slug, "Minha loja online"))
                flash("Conta criada! Agora entre com seu e-mail e senha.", "success")
                return redirect(url_for("login"))
            except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation if psycopg else sqlite3.IntegrityError):
                flash("Este e-mail já está cadastrado.", "error")
    return render_template("auth.html", mode="register")

@app.route("/entrar", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("E-mail ou senha incorretos.", "error")
    return render_template("auth.html", mode="login")

@app.route("/sair")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/painel")
@login_required
def dashboard():
    uid = session["user_id"]
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        store = con.execute("SELECT * FROM stores WHERE user_id=?", (uid,)).fetchone()
        products = con.execute("SELECT * FROM products WHERE active=1 ORDER BY name").fetchall()
        orders = con.execute("""SELECT o.*, p.name AS product_name, p.emoji FROM orders o
                             JOIN products p ON p.id=o.product_id WHERE o.user_id=?
                             ORDER BY o.id DESC LIMIT 8""", (uid,)).fetchall()
        stats = con.execute("""SELECT COUNT(*) AS count, COALESCE(SUM(total),0) AS total
                               FROM orders WHERE user_id=?""", (uid,)).fetchone()
    return render_template("dashboard.html", user=user, store=store, products=products, orders=orders, stats=stats)

@app.route("/pedido/<int:product_id>", methods=["POST"])
@login_required
def create_order(product_id):
    try:
        quantity = max(1, min(99, int(request.form.get("quantity","1"))))
    except ValueError:
        quantity = 1
    with db() as con:
        product = con.execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
        if not product:
            flash("Produto não encontrado.", "error")
        elif product["stock"] < quantity:
            flash("Estoque insuficiente para essa quantidade.", "error")
        else:
            total = product["price"] * quantity
            con.execute("INSERT INTO orders(user_id,product_id,quantity,total,status) VALUES(?,?,?,?,?)",
                        (session["user_id"], product_id, quantity, total, "Demonstração"))
            con.execute("UPDATE products SET stock=stock-? WHERE id=?", (quantity, product_id))
            flash("Pedido de demonstração criado. Nenhum pagamento ou envio foi realizado.", "success")
    return redirect(url_for("dashboard"))

@app.route("/catalogo")
def catalog():
    q = request.args.get("q","").strip()
    with db() as con:
        products = con.execute("SELECT * FROM products WHERE active=1 AND name LIKE ? ORDER BY name", (f"%{q}%",)).fetchall()
    return render_template("catalog.html", products=products, q=q)


@app.route("/loja", methods=["GET", "POST"])
@login_required
def store_settings():
    uid = session["user_id"]
    with db() as con:
        store = con.execute("SELECT * FROM stores WHERE user_id=?", (uid,)).fetchone()
        products = con.execute("""SELECT p.*, sp.active AS store_active, sp.custom_name, sp.custom_price
                                  FROM products p LEFT JOIN store_products sp
                                  ON sp.product_id=p.id AND sp.store_id=?
                                  WHERE p.active=1 ORDER BY p.name""", (store["id"],)).fetchall()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        description = request.form.get("description","").strip()
        color = request.form.get("primary_color","#6c4cff").strip()
        emoji = request.form.get("logo_emoji","🛍️").strip()[:8]
        requested_slug = request.form.get("slug","").strip().lower()
        requested_slug = re.sub(r"[^a-z0-9-]+", "-", requested_slug).strip("-")
        if not name or not requested_slug:
            flash("Nome e endereço da loja são obrigatórios.", "error")
            return redirect(url_for("store_settings"))
        with db() as con:
            other = con.execute("SELECT id FROM stores WHERE slug=? AND id<>?", (requested_slug, store["id"])).fetchone()
            if other:
                flash("Esse endereço já está sendo usado por outra loja.", "error")
            else:
                con.execute("""UPDATE stores SET name=?,slug=?,description=?,logo_emoji=?,primary_color=?
                               WHERE id=?""",
                            (name, requested_slug, description, emoji, color, store["id"]))
                for p in products:
                    active = 1 if request.form.get(f"product_{p['id']}") == "on" else 0
                    custom_name = request.form.get(f"name_{p['id']}","").strip() or None
                    raw_price = request.form.get(f"price_{p['id']}","").strip().replace(",", ".")
                    custom_price = None
                    if raw_price:
                        try:
                            custom_price = float(raw_price)
                            if custom_price < 0: custom_price = None
                        except ValueError:
                            custom_price = None
                    con.execute("""INSERT INTO store_products(store_id,product_id,custom_name,custom_price,active)
                                   VALUES(?,?,?,?,?)
                                   ON CONFLICT(store_id,product_id) DO UPDATE SET
                                   custom_name=excluded.custom_name,custom_price=excluded.custom_price,active=excluded.active""",
                                (store["id"], p["id"], custom_name, custom_price, active))
                flash("Sua loja foi atualizada.", "success")
        return redirect(url_for("store_settings"))
    return render_template("store_settings.html", store=store, products=products)

@app.route("/minha-loja")
@login_required
def my_store():
    with db() as con:
        store = con.execute("SELECT * FROM stores WHERE user_id=?", (session["user_id"],)).fetchone()
    return redirect(url_for("public_store", slug=store["slug"]))

@app.route("/loja/<slug>")
def public_store(slug):
    with db() as con:
        store = con.execute("SELECT * FROM stores WHERE slug=?", (slug,)).fetchone()
        if not store:
            return render_template("404.html"), 404
        products = con.execute("""SELECT p.*, sp.custom_name, sp.custom_price
                                  FROM store_products sp JOIN products p ON p.id=sp.product_id
                                  WHERE sp.store_id=? AND sp.active=1 AND p.active=1
                                  ORDER BY p.name""", (store["id"],)).fetchall()
    return render_template("public_store.html", store=store, products=products)

@app.route("/loja/<slug>/produto/<int:product_id>", methods=["POST"])
def public_store_order(slug, product_id):
    # Real checkout is deliberately not enabled yet. This route prevents
    # accidental real transactions while the payment provider is not configured.
    flash("Checkout público ainda não está habilitado. A loja está em modo de catálogo.", "error")
    return redirect(url_for("public_store", slug=slug))

@app.route("/admin")
@login_required
def admin():
    # Acesso administrativo não é habilitado por padrão.
    if not session.get("is_admin"):
        flash("O painel administrativo precisa ser configurado pelo responsável pelo sistema.", "error")
        return redirect(url_for("dashboard"))
    with db() as con:
        products = con.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
        users = con.execute("SELECT id,name,email,created_at FROM users ORDER BY id DESC").fetchall()
        orders = con.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 20").fetchall()
    return render_template("admin.html", products=products, users=users, orders=orders)


def get_cart():
    return session.get("cart", {})

def cart_items():
    cart = get_cart()
    if not cart:
        return []
    ids = [int(x) for x in cart.keys()]
    marks = ",".join("?" for _ in ids)
    with db() as con:
        rows = con.execute(f"SELECT * FROM products WHERE id IN ({marks}) AND active=1", ids).fetchall()
    by_id = {str(r["id"]): r for r in rows}
    result = []
    for pid, qty in cart.items():
        p = by_id.get(str(pid))
        if not p: continue
        qty = max(1, min(99, int(qty)))
        result.append({"product":p, "quantity":qty, "total":round(p["price"]*qty,2)})
    return result

@app.context_processor
def global_store_context():
    return {"cart_count": sum(get_cart().values()) if get_cart() else 0}

@app.route("/carrinho")
def cart():
    items = cart_items()
    total = round(sum(x["total"] for x in items),2)
    return render_template("cart.html", items=items, total=total)

@app.route("/carrinho/adicionar/<int:product_id>", methods=["POST"])
def add_cart(product_id):
    qty = max(1, min(99, int(request.form.get("quantity","1") or 1)))
    with db() as con:
        p = con.execute("SELECT id,stock FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
    if not p:
        flash("Produto não encontrado.", "error")
    else:
        current = int(get_cart().get(str(product_id),0))
        if current + qty > p["stock"]:
            flash("Quantidade maior que o estoque disponível.", "error")
        else:
            cart = get_cart()
            cart[str(product_id)] = current + qty
            session["cart"] = cart
            session.modified = True
            flash("Produto adicionado ao carrinho.", "success")
    return redirect(request.referrer or url_for("catalog"))

@app.route("/carrinho/remover/<int:product_id>", methods=["POST"])
def remove_cart(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET","POST"])
@login_required
def checkout():
    items = cart_items()
    total = round(sum(x["total"] for x in items),2)
    if request.method == "POST":
        if not items:
            flash("Seu carrinho está vazio.", "error")
            return redirect(url_for("cart"))
        # Payment provider adapter point. No charge is made without credentials.
        provider = os.environ.get("PAYMENT_PROVIDER","disabled")
        if provider != "mercadopago":
            flash("Checkout real ainda não está ativado neste ambiente. Configure PAYMENT_PROVIDER=mercadopago e as credenciais de produção.", "error")
            return redirect(url_for("checkout"))
        flash("O adaptador de pagamento está preparado, mas requer credenciais da conta comercial responsável.", "error")
        return redirect(url_for("checkout"))
    return render_template("checkout.html", items=items, total=total, user_id=session["user_id"])

@app.route("/pagamento/webhook/mercadopago", methods=["POST"])
def mercadopago_webhook():
    # Production implementation must verify the provider signature and
    # query the order/payment API before changing local order state.
    payload = request.get_json(silent=True) or {}
    return jsonify({"received": True}), 200

@app.route("/politica-de-privacidade")
def privacy():
    return render_template("legal.html", kind="privacy")

@app.route("/termos")
def terms():
    return render_template("legal.html", kind="terms")

@app.route("/dominio", methods=["GET","POST"])
@login_required
def domain_settings():
    with db() as con:
        store = con.execute("SELECT * FROM stores WHERE user_id=?", (session["user_id"],)).fetchone()
    if request.method == "POST":
        domain = request.form.get("domain","").strip().lower()
        valid = bool(re.fullmatch(r"(?!-)([a-z0-9-]+\.)+[a-z]{2,63}", domain))
        if not valid:
            flash("Digite um domínio válido, como loja.exemplo.com.", "error")
        else:
            # Store custom domain field is added by migration below.
            with db() as con:
                con.execute("UPDATE stores SET custom_domain=? WHERE id=?", (domain, store["id"]))
            flash("Domínio salvo. Ainda falta apontar o DNS e configurar TLS no servidor.", "success")
    with db() as con:
        store = con.execute("SELECT * FROM stores WHERE user_id=?", (session["user_id"],)).fetchone()
    return render_template("domain.html", store=store)

@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
