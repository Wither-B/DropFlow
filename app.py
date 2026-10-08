import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
# Chave secreta necessária para gerir sessões e mensagens flash
app.secret_key = os.environ.get("SECRET_KEY", "dropflow_chave_secreta_123")

DATABASE = "dropflow.db"

# --- GESTÃO DA BASE DE DADOS ---

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Permite aceder às colunas pelo nome
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        
        # Tabela de Utilizadores
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                name TEXT
            )
        """)
        
        # Tabela de Produtos
        db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL
            )
        """)
        
        # Tabela de Encomendas / Pedidos
        db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT NOT NULL,
                total REAL NOT NULL
            )
        """)
        
        # Tabela de Lojas
        db.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT
            )
        """)
        
        # Insere dados de exemplo nos produtos (se estiver vazio)
        cur = db.execute("SELECT COUNT(*) as count FROM products")
        if cur.fetchone()["count"] == 0:
            products = [
                ("Fone Bluetooth Pro", "Eletrónicos", 45.00, 100),
                ("Smartwatch Fit X", "Tecnologia", 85.00, 50),
                ("Mochila Urban", "Acessórios", 35.00, 80),
                ("Luminária LED", "Casa", 17.00, 49),
                ("Garrafa térmica", "Casa", 22.00, 59),
                ("Suporte para celular", "Acessórios", 12.00, 25)
            ]
            for row in products:
                db.execute("INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)", row)
        
        # Insere loja de exemplo (se estiver vazio)
        cur = db.execute("SELECT COUNT(*) as count FROM stores")
        if cur.fetchone()["count"] == 0:
            db.execute("INSERT INTO stores (name, location) VALUES (?, ?)", ("Loja Principal", "Simões Filho - BA"))
            
        db.commit()

# Inicializa a base de dados ao arrancar o servidor
init_db()

# --- DECORADOR DE VERIFICAÇÃO DE LOGIN ---

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

# --- ROTAS DA APLICAÇÃO ---

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
