# ENGO 551 Lab 1 

## Overview
This project is a book review website built with Python (Flask) and a local PostgreSQL database. Users can register, log in, search for books from a dataset, view book details, and leave reviews with a star rating and a written comment.

## Features of Site
- **Registration:** Users can create an account 
- **Login/Logout:** Users can log in and log out
- **Import:** A separate import.py script imports the provided books.csv into PostgreSQL
- **Search:** Logged-in users can search by ISBN, title, or author
- **Book Page:** Displays book details suchas title, author, year, ISBN
- **Reviews:** Logged-in users can submit a review of number of stars and a comment, as well as view other users reviews.
- **Raw SQL:** Uses SQL queries
- **API:**  Provides an endpoint that returns book details 

## Project Structure
- `backend/application.py` — Flask app 
- `backend/import.py` — Imports books.csv into the books table
- `backend/templates/` — HTML templates (login.html, register.html, search.html, book.html, error.html)
- `backend/static/` — CSS styling
- `books.csv` — Dataset of 5000 books 

## Instructions for Running the Site

### 1. Install dependencies
Go to the project root and open terminal and go to powershell.
Then perform this: 

pip install -r requirements.txt

### 2. Set up Database URL
Set your PostgreSQL connectino string as something below:

$env:DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@localhost/engo551_lab1"

### 3. Import books into the database
If your books.csv is in the project root, copy it into backend once:

Copy-Item ".\books.csv" ".\backend\books.csv"

Then run import from the backend folder:

cd backend
python import.py

### 4. Run the Flask app
In the same powershell terminal run this: 

$env:FLASK_APP="application.py"
flask run


### 5. Finally open in browsr
Open in your browser:

http://127.0.0.1:5000







