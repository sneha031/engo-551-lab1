import os
import csv

from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    with open("books.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db.execute(
                text(
                    "INSERT INTO books (isbn, title, author, year) "
                    "VALUES (:isbn, :title, :author, :year) "
                    "ON CONFLICT (isbn) DO NOTHING"
                ),
                {
                    "isbn": row["isbn"].strip(),
                    "title": row["title"].strip(),
                    "author": row["author"].strip(),
                    "year": int(row["year"])
                }
            )
    db.commit()
    print("Import complete")

if __name__ == "__main__":
    main()
