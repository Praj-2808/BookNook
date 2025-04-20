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
bookshelves_collection = mongo.db.bookshelves
posts_collection = mongo.db.posts
reviews_collection=mongo.db.reviews


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

    reviews = reviews_collection.find({'book_key': book_key}) 
    
    return render_template('book-detail.html', book_key=book_key, user=user, reviews=reviews)

#Everything is perfect till here

def get_book_data(book_key):
    # Fetch detailed book data using the Open Library API
    api_url = f"https://openlibrary.org{book_key}.json"
    response = requests.get(api_url)

    if response.status_code == 200:
        return response.json()  # Return the book data if successful
    else:
        return None  # Return None if the request fails

@app.route("/submit-review", methods=["POST"])
def submit_review():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirect to login if the user is not logged in
    
    # Fetch the user details from the database
    user = users_collection.find_one({'username': session['username']})
    if not user:
        return redirect(url_for('login'))  # Redirect if no user is found

    # Get review details from the form
    book_key = request.form.get('book_key')  # Use .get() to avoid KeyError
    if not book_key:
        return "Book key is required", 400  # Return a proper error message if no book_key

    try:
        rating = float(request.form['rating'])  # Ensure the rating is a valid float
    except ValueError:
        return "Invalid rating value", 400  # Handle invalid rating input gracefully
    
    review_text = request.form['review_text']
    tags = request.form.getlist('tags')  # This allows multiple tags

    # Save the review in the database
    review = {
        "username": user['username'],
        "book_key": book_key,
        "rating": rating,
        "review_text": review_text,
        "tags": tags,
        "created_at": datetime.utcnow()
    }
    reviews_collection.insert_one(review)

    print("Form Data Received:", request.form)

    return redirect(url_for('book_detail', book_key=book_key))  # Redirect to the book's detail page

@app.route("/reviews") 
def my_reviews():
    if 'username' not in session:
        return redirect(url_for('login'))

    sort = request.args.get('sort', 'newest')
    user = users_collection.find_one({'username': session['username']})

    sort_query = [('created_at', -1)]  # Default: newest
    if sort == 'oldest':
        sort_query = [('created_at', 1)]
    elif sort == 'highest':
        sort_query = [('rating', -1)]
    elif sort == 'lowest':
        sort_query = [('rating', 1)]

    reviews = list(reviews_collection.find({'username': session['username']}).sort(sort_query))

    # Attach fallback and book detail URL, and fetch book title + cover
    for review in reviews:
        book_key = review.get('book_key', 'OL0000000M')
        review['book_key'] = book_key
        review['book_url'] = f"/book/{book_key}"
        
        try:
            res = requests.get(f"https://openlibrary.org/{book_key}.json")
            if res.status_code == 200:
                data = res.json()
                review['book_title'] = data.get('title', 'Unknown Title')

                # Try to get cover from "covers" field
                if 'covers' in data and len(data['covers']) > 0:
                    cover_id = data['covers'][0]
                    review['book_cover_url'] = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                else:
                    review['book_cover_url'] = "/static/default_cover.jpg"
            else:
                review['book_title'] = 'Unknown Title'
                review['book_cover_url'] = "/static/default_cover.jpg"
        except Exception as e:
            print(f"Error fetching data for {book_key}: {e}")
            review['book_title'] = 'Unknown Title'
            review['book_cover_url'] = "/static/default_cover.jpg"

    return render_template("my-reviews.html", user=user, reviews=reviews, sort=sort)


@app.route("/delete_review/<review_id>", methods=["POST"])
def delete_review(review_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    review = reviews_collection.find_one({"_id": ObjectId(review_id)})
    if review and review['username'] == session['username']:
        reviews_collection.delete_one({"_id": ObjectId(review_id)})
        flash("Review deleted successfully!", "success")
    else:
        flash("You can only delete your own reviews.", "error")

    return redirect(url_for("my_reviews"))

@app.route('/bookshelves')
def bookshelves():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    user_shelves = list(bookshelves_collection.find({'username': username}))

    all_bookshelves = []

    for shelf in user_shelves:
        shelf_name = shelf['shelf_name']
        book_keys = shelf.get('books', [])

        detailed_books = []

        for key in book_keys:
            book_data = fetch_book_details(key)
            detailed_books.append(book_data)

        all_bookshelves.append({
            'shelf_name': shelf_name,
            'books': detailed_books
        })

    user = users_collection.find_one({'username': username})

    return render_template('bookshelves.html', bookshelves=all_bookshelves, user=user)


@app.route('/add-to-shelf', methods=['POST'])
def add_to_shelf():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    data = request.json
    shelf_name = data.get('shelf')
    book_key = data.get('book_key')

    if not shelf_name or not book_key:
        return jsonify({'success': False, 'message': 'Invalid data'}), 400

    username = session['username']

    # Check if the shelf already exists
    bookshelf = bookshelves_collection.find_one({
        'username': username,
        'shelf_name': shelf_name
    })

    if bookshelf:
        if book_key not in bookshelf['books']:
            bookshelves_collection.update_one(
                {'_id': bookshelf['_id']},
                {
                    '$push': {'books': book_key},
                    '$set': {'updated_at': datetime.utcnow()}
                }
            )
    else:
        # Create new shelf with the book
        bookshelves_collection.insert_one({
            'username': username,
            'shelf_name': shelf_name,
            'books': [book_key],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        })

    # ✅ Success response for frontend (or redirect if you're not using fetch)
    return jsonify({'success': True, 'message': f'Book added to "{shelf_name}"!'})

@app.route('/delete-shelf', methods=['POST'])
def delete_shelf():
    if 'username' not in session:
        return redirect(url_for('login'))

    # Get the shelf name from the request
    data = request.get_json()
    shelf_name = data.get('shelf_name')
    if not shelf_name:
        return jsonify({'success': False, 'message': 'Shelf name is required'}), 400

    # Find the bookshelf document by username and shelf name
    bookshelf = bookshelves_collection.find_one({'username': session['username'], 'shelf_name': shelf_name})
    if not bookshelf:
        return jsonify({'success': False, 'message': 'Shelf not found'}), 404

    # Delete the shelf from the bookshelves collection
    bookshelves_collection.delete_one({'_id': bookshelf['_id']})

    return jsonify({'success': True, 'message': f'Shelf "{shelf_name}" deleted successfully'})

@app.route("/remove-from-bookshelf", methods=["POST"])
def remove_from_bookshelf():
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401  # Return JSON for errors

    user = users_collection.find_one({'username': session['username']})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404  # Return JSON for errors

    data = request.get_json()
    if not data or 'book_key' not in data or 'shelf_name' not in data:
        return jsonify({'success': False, 'message': 'Missing book_key or shelf_name'}), 400  # Return JSON for errors

    book_key = data['book_key']
    bookshelf_name = data['shelf_name']

    # Find the bookshelf in the bookshelves_collection and remove the book
    bookshelf = bookshelves_collection.find_one({'shelf_name': bookshelf_name, 'username': session['username']})

    if bookshelf:
        # Remove the book from the shelf
        updated_books = [book for book in bookshelf['books'] if book['key'] != book_key]

        # Update the bookshelf in the database
        result = bookshelves_collection.update_one(
            {'shelf_name': bookshelf_name, 'username': session['username']},
            {'$set': {'books': updated_books}}
        )

        if result.modified_count > 0:
            return jsonify({'success': True})

    return jsonify({'success': False, 'message': 'Bookshelf not found or error occurred'}), 400  # Return JSON for errors

def fetch_book_details(work_key):
    try:
        # Extract the actual ID from "works/OL82563W"
        work_id = work_key.split("/")[-1]
        work_url = f"https://openlibrary.org/works/{work_id}.json"
        work_data = requests.get(work_url).json()

        title = work_data.get('title', 'Unknown Title')

        # Get author name
        author_name = "Unknown Author"
        if 'authors' in work_data and len(work_data['authors']) > 0:
            author_key = work_data['authors'][0].get('author', {}).get('key')
            if author_key:
                author_url = f"https://openlibrary.org{author_key}.json"
                author_data = requests.get(author_url).json()
                author_name = author_data.get('name', 'Unknown Author')

        # Get cover image
        cover_id = work_data.get('covers', [None])[0]
        if cover_id:
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        else:
            cover_url = "https://via.placeholder.com/150x200?text=No+Cover"

        return {
            'key': work_key,
            'title': title,
            'author': author_name,
            'cover': cover_url
        }

    except Exception as e:
        print(f"Error fetching book details: {e}")
        return {
            'key': work_key,
            'title': 'Unknown Title',
            'author': 'Unknown Author',
            'cover': "https://via.placeholder.com/150x200?text=No+Cover"
        }

# Fetch user profile data
@app.route('/my-account')
def my_account():
    if 'username' not in session:
        return redirect('/login')

    username = session['username']
    user = users_collection.find_one({'username': username})

    # Fetch up to 3 most recent reviews
    reviews = list(reviews_collection.find({'username': username}).sort('created_at', -1).limit(3))

    for review in reviews:
        # Get book_key and other relevant details
        book_key = review.get('book_key', 'OL0000000M')
        review['book_key'] = book_key
        review['book_url'] = f"/book/{book_key}"

        # Fetch book details from OpenLibrary API
        try:
            res = requests.get(f"https://openlibrary.org/{book_key}.json")
            if res.status_code == 200:
                data = res.json()
                review['book_title'] = data.get('title', 'Unknown Title')
                if 'covers' in data and len(data['covers']) > 0:
                    cover_id = data['covers'][0]
                    review['book_cover_url'] = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                else:
                    review['book_cover_url'] = "/static/default_cover.jpg"
            else:
                review['book_title'] = 'Unknown Title'
                review['book_cover_url'] = "/static/default_cover.jpg"
        except:
            review['book_title'] = 'Unknown Title'
            review['book_cover_url'] = "/static/default_cover.jpg"

    # Fetch bookshelves (same as before)
    user_shelves = list(bookshelves_collection.find({'username': username}))
    all_bookshelves = []
    for shelf in user_shelves:
        shelf_name = shelf['shelf_name']
        book_keys = shelf.get('books', [])
        detailed_books = [fetch_book_details(key) for key in book_keys]
        all_bookshelves.append({
            'shelf_name': shelf_name,
            'books': detailed_books
        })

    return render_template('my-account.html', user=user, bookshelves=all_bookshelves, reviews=reviews)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    print(f"Session data: {session}")
    
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    user = users_collection.find_one({'username': username})
    if not user:
        return "User not found", 404

    if request.method == 'POST':
        name = request.form.get('name')
        bio = request.form.get('bio')
        currently_reading = request.form.get('currently_reading')
        profile_pic = user.get('profile_picture_url')

        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != "":
                encoded_image = base64.b64encode(file.read()).decode('utf-8')
                mimetype = file.content_type
                profile_pic = f"data:{mimetype};base64,{encoded_image}"

        users_collection.update_one(
            {'username': username},
            {'$set': {
                'name': name,
                'bio': bio,
                'currently_reading': currently_reading,
                'profile_picture_url': profile_pic
            }}
        )

        session.permanent = True
        session.modified = True

        return redirect(url_for('my_account'))

    return render_template('edit_profile.html', user=user)

@app.route("/submit-post", methods=["POST"])
def submit_post():
    if 'username' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    user = users_collection.find_one({'username': session['username']})
    if not user:
        return redirect(url_for('login'))

    content = request.form['content']
    book_key = request.form.get('book_key')  # Optional book reference
    post_data = {
        'user_id': user['_id'],
        'content': content,
        'book_key': book_key,
        'created_at': datetime.utcnow()
    }
    
    posts_collection.insert_one(post_data)
    return redirect(url_for('feed'))  # Redirect to the feed


if __name__ == '__main__':
    app.run(debug=True)

