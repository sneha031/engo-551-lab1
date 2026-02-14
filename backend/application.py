import os

from flask import Flask, session, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def page(title, body):
    return f"""
    <html>
    <head><meta charset="utf-8"><title>{title}</title></head>
    <body style="font-family: Arial; max-width: 800px; margin: 30px auto;">
      <div style="margin-bottom: 15px;">
        {nav()}
      </div>
      {body}
    </body>
    </html>
    """

def nav():
    if session.get("user_id"):
        u = session.get("username", "")
        return f'Logged in as <b>{u}</b> | <a href="{url_for("index")}">Search</a> | <a href="{url_for("logout")}">Logout</a>'
    return f'<a href="{url_for("login")}">Login</a> | <a href="{url_for("register")}">Register</a>'

def require_login():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return None

@app.route("/", methods=["GET", "POST"])
def index():
    gate = require_login()
    if gate:
        return gate

    if request.method == "POST":
        q = (request.form.get("q") or "").strip()
        if not q:
            return page("Search", "<h2>Search</h2><p>Please type something.</p>" + search_form())

        like = f"%{q}%"
        books = db.execute(
            "SELECT isbn, title, author, year FROM books "
            "WHERE isbn ILIKE :like OR title ILIKE :like OR author ILIKE :like "
            "ORDER BY title LIMIT 50",
            {"like": like}
        ).fetchall()

        if not books:
            return page("Results", f"<h2>Results</h2><p>No matches for <b>{q}</b>.</p>" + search_form())

        items = ""
        for b in books:
            items += f'<li><a href="{url_for("book_page", isbn=b.isbn)}">{b.title}</a> by {b.author} ({b.year}) — {b.isbn}</li>'

        return page("Results", f"<h2>Results for “{q}”</h2><ul>{items}</ul>" + search_form())

    return page("Search", "<h2>Search Books</h2>" + search_form())

def search_form():
    return f"""
    <form method="post">
      <input name="q" placeholder="ISBN, title, or author" style="width: 70%; padding: 8px;">
      <button type="submit" style="padding: 8px 12px;">Search</button>
    </form>
    """

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            return page("Register", "<h2>Register</h2><p>Username and password are required.</p>" + register_form())

        existing = db.execute(
            "SELECT id FROM users WHERE username = :u",
            {"u": username}
        ).fetchone()

        if existing:
            return page("Register", "<h2>Register</h2><p>That username is already taken.</p>" + register_form())

        pw_hash = generate_password_hash(password)
        user_id = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (:u, :p) RETURNING id",
            {"u": username, "p": pw_hash}
        ).fetchone()[0]
        db.commit()

        session["user_id"] = user_id
        session["username"] = username
        return redirect(url_for("index"))

    return page("Register", "<h2>Register</h2>" + register_form())

def register_form():
    return f"""
    <form method="post">
      <div style="margin: 8px 0;">Username<br><input name="username" style="width: 60%; padding: 8px;"></div>
      <div style="margin: 8px 0;">Password<br><input name="password" type="password" style="width: 60%; padding: 8px;"></div>
      <button type="submit" style="padding: 8px 12px;">Create account</button>
    </form>
    """

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        session.clear()

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = :u",
            {"u": username}
        ).fetchone()

        if not user or not check_password_hash(user.password_hash, password):
            return page("Login", "<h2>Login</h2><p>Invalid username or password.</p>" + login_form())

        session["user_id"] = user.id
        session["username"] = user.username
        return redirect(url_for("index"))

    return page("Login", "<h2>Login</h2>" + login_form())

def login_form():
    return f"""
    <form method="post">
      <div style="margin: 8px 0;">Username<br><input name="username" style="width: 60%; padding: 8px;"></div>
      <div style="margin: 8px 0;">Password<br><input name="password" type="password" style="width: 60%; padding: 8px;"></div>
      <button type="submit" style="padding: 8px 12px;">Login</button>
    </form>
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/book/<string:isbn>", methods=["GET", "POST"])
def book_page(isbn):
    gate = require_login()
    if gate:
        return gate

    book_row = db.execute(
        "SELECT isbn, title, author, year FROM books WHERE isbn = :isbn",
        {"isbn": isbn}
    ).fetchone()

    if not book_row:
        return page("Book", "<h2>Book not found</h2><p>That ISBN does not exist in the database.</p>")

    if request.method == "POST":
        rating_raw = request.form.get("rating")
        review_text = (request.form.get("review_text") or "").strip()

        try:
            rating = int(rating_raw)
        except Exception:
            rating = 0

        if rating < 1 or rating > 5 or not review_text:
            return render_book_page(book_row, "Please enter 1–5 stars and a comment.")

        existing = db.execute(
            "SELECT id FROM reviews WHERE user_id = :uid AND isbn = :isbn",
            {"uid": session["user_id"], "isbn": isbn}
        ).fetchone()

        if existing:
            db.execute(
                "UPDATE reviews SET rating = :r, review_text = :t, created_at = NOW() "
                "WHERE user_id = :uid AND isbn = :isbn",
                {"r": rating, "t": review_text, "uid": session["user_id"], "isbn": isbn}
            )
        else:
            db.execute(
                "INSERT INTO reviews (user_id, isbn, rating, review_text) VALUES (:uid, :isbn, :r, :t)",
                {"uid": session["user_id"], "isbn": isbn, "r": rating, "t": review_text}
            )

        db.commit()
        return redirect(url_for("book_page", isbn=isbn))

    return render_book_page(book_row, None)

def render_book_page(book_row, message):
    isbn = book_row.isbn

    reviews = db.execute(
        "SELECT r.rating, r.review_text, r.created_at, u.username "
        "FROM reviews r JOIN users u ON r.user_id = u.id "
        "WHERE r.isbn = :isbn "
        "ORDER BY r.created_at DESC",
        {"isbn": isbn}
    ).fetchall()

    stats = db.execute(
        "SELECT COUNT(*) AS count, COALESCE(AVG(rating), 0) AS avg "
        "FROM reviews WHERE isbn = :isbn",
        {"isbn": isbn}
    ).fetchone()

    msg_html = f"<p style='color: red;'>{message}</p>" if message else ""

    review_list = ""
    if reviews:
        for r in reviews:
            stars = "★" * int(r.rating) + "☆" * (5 - int(r.rating))
            review_list += f"<div style='padding: 10px; border: 1px solid #ddd; margin: 10px 0;'>" \
                           f"<div><b>{r.username}</b> | {stars}</div>" \
                           f"<div style='margin-top: 6px;'>{escape_html(r.review_text)}</div>" \
                           f"</div>"
    else:
        review_list = "<p>No reviews yet.</p>"

    avg = float(stats.avg)
    count = int(stats.count)

    body = f"""
    <h2>{escape_html(book_row.title)}</h2>
    <p><b>Author:</b> {escape_html(book_row.author)}<br>
       <b>Year:</b> {book_row.year}<br>
       <b>ISBN:</b> {book_row.isbn}</p>

    <p><b>Class reviews:</b> {count} review(s), average {avg:.2f}/5</p>

    <h3>Leave a review</h3>
    {msg_html}
    <form method="post">
      <div style="margin: 8px 0;">
        Stars (1 to 5)<br>
        <input name="rating" style="width: 120px; padding: 8px;" placeholder="1-5">
      </div>
      <div style="margin: 8px 0;">
        Comment<br>
        <textarea name="review_text" rows="4" style="width: 90%; padding: 8px;" placeholder="Write your review..."></textarea>
      </div>
      <button type="submit" style="padding: 8px 12px;">Submit</button>
    </form>

    <h3>Other reviews</h3>
    {review_list}
    """
    return page("Book", body)

def escape_html(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
