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
app.config["MONGO_URI"] = "mongodb://localhost:27017/Booknook"  
mongo = PyMongo(app)

# Collections
users_collection = mongo.db.users
books_collection = mongo.db.books
playlists_collection = mongo.db.playlists
posts_collection = mongo.db.posts

# Routes
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
            image_data = base64.b64encode(file.read()).decode('utf-8')
        else:
            with open("static/default-dp.png", "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

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
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    user_id = session['user_id']

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

# Logout Route
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

from app import app, users_collection  # Adjust imports based on your file structure

@app.route("/account")
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in

    user_id = session['user_id']
    
    # Fetch user data from database
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    
    if not user:
        return redirect(url_for('login'))  # Ensure the user exists
    
    # Fetch the user's bookshelf, favorite books, and posts
    user_books = user.get('bookshelf', [])
    favorite_books = user.get('preferences', {}).get('fav_books', [])
    posts = user.get('posts', [])  # Assuming posts are stored in the user document

    return render_template("account.html", 
                           user=user, 
                           user_books=user_books, 
                           favorite_books=favorite_books, 
                           posts=posts)

# Fetch user profile data
@app.route('/my-account')
def my_account():
    # Assuming user is logged in and we have user ID in session
    user_id = session['user_id'] # Replace with actual session data
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    
    if not user:
        return redirect(url_for('login'))  # Redirect if user not found
    
    return render_template('my-account.html', user=user)

# Update user profile data
@app.route('/edit-profile', methods=["GET", "POST"])
def edit_profile():
    user_id = session['user_id'] # Replace with actual session data
    user = users_collection.find_one({'_id': ObjectId(user_id)})
    
    if request.method == "POST":
        updated_bio = request.form['bio']
        updated_currently_reading = request.form['currently_reading']
        
        mongo.db.users.update_one(
            {"_id": user_id},
            {"$set": {
                "bio": updated_bio,
                "currently_reading": updated_currently_reading
            }}
        )
        return redirect(url_for('my_account'))  # Redirect to profile page after update
    
    return render_template('edit-profile.html', user=user)

@app.route('/user/<username>')
def view_user(username):
    user = mongo.db.users.find_one({"username": username})
    if not user:
        return "User not found", 404

    current_username = session.get("username")
    current_user = mongo.db.users.find_one({"username": current_username}) if current_username else None

    is_following = False
    if current_user and "following" in current_user:
        is_following = username in current_user["following"]

    followers = user.get("followers", [])
    following = user.get("following", [])
    
    return render_template("view-user.html", user=user, is_following=is_following,
                           follower_count=len(followers), following_count=len(following), current_user=current_user)


@app.route('/follow/<username>', methods=["POST"])
def follow_user(username):
    current_username = session.get("username")
    if not current_username or current_username == username:
        return redirect(url_for("view_user", username=username))

    current_user = mongo.db.users.find_one({"username": current_username})
    target_user = mongo.db.users.find_one({"username": username})

    if not target_user:
        return "User not found", 404

    # Initialize lists if not present
    mongo.db.users.update_one({"username": current_username}, {"$setOnInsert": {"following": []}}, upsert=True)
    mongo.db.users.update_one({"username": username}, {"$setOnInsert": {"followers": []}}, upsert=True)

    # Follow / Unfollow logic
    if username in current_user.get("following", []):
        mongo.db.users.update_one({"username": current_username}, {"$pull": {"following": username}})
        mongo.db.users.update_one({"username": username}, {"$pull": {"followers": current_username}})
    else:
        mongo.db.users.update_one({"username": current_username}, {"$addToSet": {"following": username}})
        mongo.db.users.update_one({"username": username}, {"$addToSet": {"followers": current_username}})

    return redirect(url_for("view_user", username=username))
 

# Open Library API URL

@app.route("/search-book")
def search_book():
    query = request.args.get("query", "").strip()
    if not query:
        return render_template("search.html", books=[])

    # 🔍 Fetch books from Open Library API
    api_url = f"https://openlibrary.org/search.json?q={query}&limit=10"
    response = requests.get(api_url)

    if response.status_code != 200:
        return render_template("search.html", books=[])

    data = response.json()
    books = []

    for book in data.get("docs", []):
        books.append({
            "title": book.get("title", "Unknown Title"),
            "author": book.get("author_name", ["Unknown Author"])[0],
            "cover_url": f"https://covers.openlibrary.org/b/id/{book.get('cover_i', '')}-M.jpg" if book.get("cover_i") else "https://via.placeholder.com/150",
            "more_info_url": f"https://openlibrary.org{book.get('key', '')}"
        })

    return render_template("search.html", books=books)

@app.route('/feed')
def feed():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = users_collection.find_one({'username': session['username']})

    # Sample dummy posts until you have DB logic
    posts = [
        {
            'user': {
                'username': 'anya_reads',
                'profile_pic': 'https://i.pravatar.cc/50?img=1'
            },
            'created_at': 'Just now',
            'content': 'Just finished “The Secret History” and my brain is melting 😭',
            'quote': '“Beauty is terror. Whatever we call beautiful, we quiver before it.”',
            'rating': '★★★★★',
            'genre': 'Dark Academia'
        },
        {
            'user': {
                'username': 'leo_books',
                'profile_pic': 'https://i.pravatar.cc/50?img=2'
            },
            'created_at': '2 hours ago',
            'content': 'Started “A Little Life.” Wish me luck…',
            'quote': '',
            'rating': '★★★★☆',
            'genre': 'Contemporary Fiction'
        }
    ]

    return render_template('feed.html', user=user, posts=posts)


if __name__ == '__main__':
    app.run(debug=True)