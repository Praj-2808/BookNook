from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import requests
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_pymongo import PyMongo
from datetime import datetime
from flask_cors import CORS
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure key
CORS(app)  

# Use the same database name across configurations
app.config["MONGO_URI"] = "mongodb://localhost:27017/BooknookNEW"  
mongo = PyMongo(app)

# Collections
users_collection = mongo.db.users
books_collection = mongo.db.books
playlists_collection = mongo.db.playlists
posts_collection = mongo.db.posts

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Check if email exists
        if users_collection.find_one({'email': email}):
            return {'error': 'Email already registered. Please log in.'}, 400

        # Hash password and store user
        hashed_password = generate_password_hash(password)
        new_user = users_collection.insert_one({
            'name': name,
            'email': email,
            'password': hashed_password,
            'preferences': {}
        })

        # Store user ID in session & redirect to create_account
        session['user_id'] = str(new_user.inserted_id)
        session['username'] = name  # You can choose to store the username or not

        return redirect(url_for('create_account'))  # Redirect to the create_account page

    return render_template('signup.html')

@app.route("/create_account", methods=["GET", "POST"])
def create_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    user_id = session['user_id']
    user_data = users_collection.find_one({'_id': ObjectId(user_id)})

    if request.method == "POST":
        username = request.form.get("username")  # Collect username here
        name = user_data['name']  # Name is already stored
        birthday = request.form.get("birthday")
        gender = request.form.get("gender")
        bio = request.form.get("bio")
        currently_reading = request.form.get("currently_reading")

        # Handle profile picture
        file = request.files.get("profile_pic")
        if file and file.filename != "":
            image_data = "data:image/png;base64," + base64.b64encode(file.read()).decode('utf-8')
        else:
            with open("static/default-dp.png", "rb") as f:
                image_data = "data:image/png;base64," + base64.b64encode(f.read()).decode('utf-8')


        # Check if username exists in the database
        if users_collection.find_one({'username': username}):
            return {'error': 'Username already taken. Please choose another.'}, 400

        # Update user document with username and profile info
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'username': username,  # Store username here
                'birthday': birthday,
                'gender': gender,
                'bio': bio,
                'currently_reading': currently_reading,
                'profile_pic': image_data,
                'profile_completed': True
            }}
        )

        return redirect(url_for("preferences"))

    return render_template("create_account.html", username=user_data['name'])

@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    user_id = session['user_id']
    
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    if request.method == "POST":
        fiction_choice = request.form.get("fiction_choice")
        genres = request.form.getlist("genre")
        fav_author = request.form.get("fav_author")
        reading_goal = request.form.get("reading_goal")
        fav_book = request.form.get("fav_book")

        # Update preferences in the database
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'preferences': {
                    'fiction_choice': fiction_choice,
                    'genres': genres,
                    'fav_author': fav_author,
                    'reading_goal': reading_goal,
                    'fav_book': fav_book
                }
            }}
        )

        return redirect(url_for("feed"))

    return render_template("preferences.html")

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        print("🔍 Raw form data:", request.form)  # Debugging

        email = request.form.get('email')
        password = request.form.get('password')

        print(f"🔍 Extracted Email: {email}, Password: {password}")

        if not email or not password:
            print("❌ Missing email or password")
            return "Missing email or password", 400

        user = users_collection.find_one({"email": email})
        
        if not user:
            print("❌ User not found")
            return "User not found", 400
        
        if not check_password_hash(user['password'], password):
            print("❌ Incorrect password")
            return "Incorrect password", 400

        print("✅ Login Successful")
        session['username'] = user['username']
        return redirect(url_for('feed'))

    return render_template('login.html')

@app.route('/feed')
def feed():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = users_collection.find_one({'username': session['username']})
    if not user:
        return redirect(url_for('login'))

    return render_template('feed.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

#Everything is perfect till Logout. Other than feed post wala thingy
 
# Open Library API URL
@app.route("/search")
def search_book():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    # Fetch the user details from the database
    user = users_collection.find_one({'username': session['username']})
    if not user:
        return redirect(url_for('login'))  # Redirect if no user is found

    # Get the query from the URL parameters
    query = request.args.get("query", "").strip()

    if not query:
        return render_template("search.html", books=[], user=user)  # Return empty list if no query

    # 🔍 Fetch books from Open Library API
    api_url = f"https://openlibrary.org/search.json?q={query}&limit=10"
    response = requests.get(api_url)

    if response.status_code != 200:
        return render_template("search.html", books=[], user=user)  # Return empty list if API call fails

    # Parse response data and prepare books list
    data = response.json()
    books = []

    for book in data.get("docs", []):
        books.append({
            "title": book.get("title", "Unknown Title"),
            "author": book.get("author_name", ["Unknown Author"])[0],
            "cover_url": f"https://covers.openlibrary.org/b/id/{book.get('cover_i', '')}-M.jpg" if book.get("cover_i") else "https://via.placeholder.com/150",
            "more_info_url": f"https://openlibrary.org{book.get('key', '')}"
        })

    return render_template("search.html", books=books, user=user)  # Pass user context to template

@app.route('/book-detail/<path:book_key>')
def book_detail(book_key):
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in

    # Fetch the user details from the database
    user = users_collection.find_one({'username': session['username']})
    if not user:
        return redirect(url_for('login'))  
    
    return render_template('book-detail.html', book_key=book_key, user=user)

if __name__ == '__main__':
    app.run(debug=True)