DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS books CASCADE;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE books (
    isbn VARCHAR(20) PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    year INT NOT NULL
);

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    isbn VARCHAR(20) NOT NULL REFERENCES books(isbn) ON DELETE CASCADE,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, isbn)
);


CREATE INDEX idx_reviews_isbn ON reviews(isbn);
CREATE INDEX idx_reviews_user_id ON reviews(user_id);
