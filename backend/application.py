import os
import requests

from flask import Flask, session, request, redirect, url_for, render_template, jsonify
from flask_session import Session
from sqlalchemy import create_engine, text
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


def require_login():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return None


def google_books_info(isbn):
    try:
        r = requests.get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}", timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        items = data.get("items", [])

        for it in items:
            info = it.get("volumeInfo", {})
            avg = info.get("averageRating")
            count = info.get("ratingsCount")
            link = info.get("infoLink") or info.get("previewLink")

            thumb = None
            imgs = info.get("imageLinks")
            if imgs:
                thumb = imgs.get("thumbnail")

            if avg is not None or count is not None or link or thumb:
                return {"avg": avg, "count": count, "link": link, "thumb": thumb}

        return None
    except Exception:
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    gate = require_login()
    if gate:
        return gate

    if request.method == "POST":
        q = (request.form.get("q") or "").strip()
        if not q:
            return render_template("search.html", message="Type something to search")

        like = f"%{q}%"
        books = db.execute(
            text(
                "SELECT isbn, title, author, year FROM books "
                "WHERE isbn ILIKE :like OR title ILIKE :like OR author ILIKE :like "
                "ORDER BY title LIMIT 50"
            ),
            {"like": like}
        ).fetchall()

        if not books:
            return render_template("search.html", q=q, books=[], message="No matches found")

        return render_template("search.html", q=q, books=books)

    return render_template("search.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        return render_template("register.html", message="Username and password required")

    existing = db.execute(
        text("SELECT id FROM users WHERE username = :u"),
        {"u": username}
    ).fetchone()

    if existing:
        return render_template("register.html", message="Username already taken")

    pw_hash = generate_password_hash(password)

    user_id = db.execute(
        text("INSERT INTO users (username, password_hash) VALUES (:u, :p) RETURNING id"),
        {"u": username, "p": pw_hash}
    ).fetchone()[0]

    db.commit()

    session["user_id"] = user_id
    session["username"] = username
    return redirect(url_for("index"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        session.clear()
        return render_template("login.html")

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = db.execute(
        text("SELECT id, username, password_hash FROM users WHERE username = :u"),
        {"u": username}
    ).fetchone()

    if not user or not check_password_hash(user.password_hash, password):
        return render_template("login.html", message="Invalid username or password")

    session["user_id"] = user.id
    session["username"] = user.username
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/book/<string:isbn>", methods=["GET", "POST"])
def book_page(isbn):
    gate = require_login()
    if gate:
        return gate

    book = db.execute(
        text("SELECT isbn, title, author, year FROM books WHERE isbn = :isbn"),
        {"isbn": isbn}
    ).fetchone()

    if not book:
        return render_template("error.html", error="Book not found")

    ginfo = google_books_info(isbn)
    gb_avg = ginfo["avg"] if ginfo else None
    gb_count = ginfo["count"] if ginfo else None

    if request.method == "POST":
        rating_raw = request.form.get("rating")
        review_text = (request.form.get("review_text") or "").strip()

        try:
            rating = int(rating_raw)
        except Exception:
            rating = 0

        if rating < 1 or rating > 5 or not review_text:
            reviews = db.execute(
                text(
                    "SELECT u.username, r.rating, r.review_text, r.created_at "
                    "FROM reviews r JOIN users u ON r.user_id = u.id "
                    "WHERE r.isbn = :isbn ORDER BY r.created_at DESC"
                ),
                {"isbn": isbn}
            ).fetchall()

            stats = db.execute(
                text(
                    "SELECT COUNT(*) AS count, COALESCE(AVG(rating), 0) AS avg "
                    "FROM reviews WHERE isbn = :isbn"
                ),
                {"isbn": isbn}
            ).fetchone()

            return render_template(
                "book.html",
                book=book,
                reviews=reviews,
                stats=stats,
                gb_avg=gb_avg,
                gb_count=gb_count,
                ginfo=ginfo,
                message="Please select 1–5 stars and write a comment."
            )

        existing = db.execute(
            text("SELECT id FROM reviews WHERE user_id = :uid AND isbn = :isbn"),
            {"uid": session["user_id"], "isbn": isbn}
        ).fetchone()

        if existing:
            db.execute(
                text(
                    "UPDATE reviews SET rating = :r, review_text = :t, created_at = NOW() "
                    "WHERE user_id = :uid AND isbn = :isbn"
                ),
                {"r": rating, "t": review_text, "uid": session["user_id"], "isbn": isbn}
            )
        else:
            db.execute(
                text(
                    "INSERT INTO reviews (user_id, isbn, rating, review_text) "
                    "VALUES (:uid, :isbn, :r, :t)"
                ),
                {"uid": session["user_id"], "isbn": isbn, "r": rating, "t": review_text}
            )

        db.commit()
        return redirect(url_for("book_page", isbn=isbn))

    reviews = db.execute(
        text(
            "SELECT u.username, r.rating, r.review_text, r.created_at "
            "FROM reviews r JOIN users u ON r.user_id = u.id "
            "WHERE r.isbn = :isbn ORDER BY r.created_at DESC"
        ),
        {"isbn": isbn}
    ).fetchall()

    stats = db.execute(
        text(
            "SELECT COUNT(*) AS count, COALESCE(AVG(rating), 0) AS avg "
            "FROM reviews WHERE isbn = :isbn"
        ),
        {"isbn": isbn}
    ).fetchone()

    return render_template(
        "book.html",
        book=book,
        reviews=reviews,
        stats=stats,
        gb_avg=gb_avg,
        gb_count=gb_count,
        ginfo=ginfo
    )


@app.route("/api/<string:isbn>")
def api(isbn):
    book = db.execute(
        text("SELECT isbn, title, author, year FROM books WHERE isbn = :isbn"),
        {"isbn": isbn}
    ).fetchone()

    if not book:
        return jsonify({"error": "Book not found"}), 404

    stats = db.execute(
        text(
            "SELECT COUNT(*) AS count, COALESCE(AVG(rating), 0) AS avg "
            "FROM reviews WHERE isbn = :isbn"
        ),
        {"isbn": isbn}
    ).fetchone()

    ginfo = google_books_info(isbn)
    gb_avg = ginfo["avg"] if ginfo else None
    gb_count = ginfo["count"] if ginfo else None
    gb_link = ginfo["link"] if ginfo else None
    gb_thumb = ginfo["thumb"] if ginfo else None

    return jsonify({
        "isbn": book.isbn,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "review_count": int(stats.count),
        "average_score": float(stats.avg),
        "google_average_rating": gb_avg,
        "google_ratings_count": gb_count,
        "google_link": gb_link,
        "google_thumbnail": gb_thumb
    })


print(app.url_map)
