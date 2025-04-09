import os, random, sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
# Configure Flask mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
app.config['UPLOAD_FOLDER'] = 'static/uploads'


mail = Mail(app)


# 🌐 Set up OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


@app.route("/")
def home():
    if "username" in session:
        return redirect(url_for("profile"))
    return redirect(url_for("login_options"))  # always show consistent login choices

@app.route("/login")
def login_options():
    return render_template("login_options.html")  # ← rename your old welcome.html to this

@app.route("/manual-login", methods=["GET", "POST"])
def manual_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        conn.close()

        if result and check_password_hash(result[0], password):
            session["username"] = username
            return redirect(url_for("profile"))
        else:
            flash("Invalid username or password!", "danger")

    return render_template("manual_login.html", username=request.form.get("username", ""))


# Functions for reset password
def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(app.secret_key)
    return serializer.dumps(email, salt='password-reset')

def confirm_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.secret_key)
    try:
        email = serializer.loads(token, salt='password-reset', max_age=expiration)
    except:
        return False
    return email

def send_reset_email(user_email, reset_url):
    msg = Message('Reset your password for Muzzle', recipients=[user_email])
    msg.body = f'''
Hi there!

We received a request to reset your password for your Muzzle account.

Click the link below to reset your password:

{reset_url}

If you didn't request a password reset, please ignore this email.

Cheers,
The Muzzle Team
'''
    mail.send(msg)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if the email exists in the database
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT email FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()

        if user:
            # Generate a password reset token (or send email with link)
            reset_token = generate_reset_token(email)
            reset_url = url_for('reset_password', token=reset_token, _external=True)
            send_reset_email(email, reset_url)
            flash('Password reset email has been sent!', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email not found!', 'danger')
            return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')



@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    email = confirm_reset_token(token)
    if email:
        if request.method == 'POST':
            new_password = request.form['password']
            # Update the password in the database
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            hashed_password = generate_password_hash(new_password)
            c.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
            conn.commit()
            conn.close()
            flash('Your password has been reset!', 'success')
            return redirect(url_for('login'))

        return render_template('reset_password.html')
    else:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))


@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        dog_free = request.form.get("dog_free")

        import re

        if not re.match(r'^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[\W_]).{8,}$', password):
            flash(
                "Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a number, and a special character.",
                "danger")
            return redirect(url_for("signup"))

        if dog_free != "on":
            flash("You must agree to the Dog-Free Oath to join Muzzle.", "danger")
            return redirect(url_for("signup"))

        # Get all form data
        display_name = request.form.get("display_name", "")
        age = request.form.get("age", None)
        location = request.form.get("location", "")
        favorite_animal = request.form.get("favorite_animal", "")
        dog_free_reason = request.form.get("dog_free_reason", "")
        bio = request.form.get("bio", "")
        gender = request.form.get("gender", "")
        interests = request.form.get("interests", "")
        main_tag = request.form.get("main_tag", "")
        tags = request.form.getlist("tags")
        all_tags = [main_tag] + tags
        tags_string = ",".join(tags)

        # Validation: must include at least one pet-related tag
        pet_tags = {
            "Fully Pet-Free", "Allergic to Everything", "Reptile Roomie", "Cat Companion",
            "Rodent Roomie", "Bird Bestie", "Fish Friend", "Turtle Tenant", "Plant Person",
            "Bug Buddy", "My Pet’s a Vibe", "No Bark Zone", "Clean House > Cute Paws"
        }
        if not any(tag in pet_tags for tag in all_tags):
            return "You must select at least one pet-related tag (main or additional)."

        try:
            conn = sqlite3.connect("users.db")
            c = conn.cursor()
            hashed_password = generate_password_hash(password)

            c.execute("""
                INSERT INTO users (
                    username, password, display_name, age, location,
                    favorite_animal, dog_free_reason, profile_pic, bio,
                    gender, sexuality, show_gender, show_sexuality, interests, main_tag, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                username, hashed_password, display_name, age, location,
                favorite_animal, dog_free_reason, "", bio,
                gender, "", 1, 0, interests, main_tag, tags_string
            ))

            conn.commit()
            conn.close()
            flash("Account created successfully!", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            return "Username already exists!"

    return render_template("signup.html", username=request.form.get("username", ""))



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        conn.close()

        if result and check_password_hash(result[0], password):
            session["username"] = username
            return redirect(url_for("profile"))
        else:
            flash("Invalid username or password!", "danger")
            return render_template("login_options.html", username=username)

    # Handle GET request
    return render_template("login_options.html", username="")

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    print("Redirect URI sent to Google:", redirect_uri)
    return google.authorize_redirect(redirect_uri)

def generate_display_name():
    adjectives = ["Bold", "Witty", "Chill", "Thick", "Sly", "Clever",
                  "Gentle", "Zesty", "Brave", "Loyal", "Sleepy", "Hyperactive",
                  "Bouncy", "Inflatable", "The", "Endangered", "Immortal", "Real", "Lefthanded",
                  "Assistant", "Crusty", "Feral", "Wandering", "Lucky", "Unstoppable", "Lonely",
                  "Single", "Professional", "Legendary", "Part-time", "Little", "Big"]
    animals = [
        "Koala", "Gecko", "Iguana", "Cat", "Turtle", "Ferret", "Fox", "Hedgehog",
        "Rabbit", "Tiger", "Giraffe", "Penguin", "Llama", "Otter", "Snake", "Platypus",
        "Tarantula", "Spider", "Lizard", "Dragon"
    ]
    return random.choice(adjectives) + random.choice(animals)

@app.route('/login/google/callback')
def google_callback():
    token = google.authorize_access_token()
    user_info = google.get('https://openidconnect.googleapis.com/v1/userinfo').json()
    email = user_info['email']

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (email,))
    existing_user = c.fetchone()

    if not existing_user:
        display_name = generate_display_name()
        c.execute("""
            INSERT INTO users (username, password, display_name, email_verified)
            VALUES (?, ?, ?, 0)
        """, (email, generate_password_hash("google_oauth_login"), display_name))
        conn.commit()
        send_verification_email(email)  # ← Send email verification
        session["needs_profile_completion"] = True

    conn.close()
    session["username"] = email
    flash("Logged in with Google!", "success")

    if session.pop("needs_profile_completion", False):
        return redirect(url_for("settings"))

    return redirect(url_for("profile"))


#Verification Route
@app.route('/verify/<token>')
def verify_email(token):
    email = confirm_verification_token(token)
    if not email:
        flash('Verification link expired or invalid.', 'danger')
        return redirect(url_for('home'))

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT email_verified FROM users WHERE username = ?", (email,))
    user = c.fetchone()

    if user:
        if user[0] == 1:
            flash('Email already verified!', 'info')
        else:
            c.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (email,))
            conn.commit()
            flash('Email successfully verified!', 'success')
    else:
        flash('User not found!', 'danger')

    conn.close()
    return redirect(url_for('profile'))



# Token Generation, help verify email
serializer = URLSafeTimedSerializer(app.secret_key)

def generate_verification_token(email):
    return serializer.dumps(email, salt='email-verify')

def confirm_verification_token(token, expiration=3600):
    try:
        email = serializer.loads(token, salt='email-verify', max_age=expiration)
    except:
        return False
    return email

# Sending the verification
from flask_mail import Message

def send_verification_email(user_email):
    token = generate_verification_token(user_email)
    verification_url = url_for('verify_email', token=token, _external=True)

    msg = Message('Verify your email for Muzzle', recipients=[user_email])
    msg.body = f'''
Hi there!

Thanks for signing up for Muzzle 🐾

Please verify your email address by clicking the link below:

{verification_url}

If you didn't sign up, you can safely ignore this email.

Cheers,  
The Muzzle Team
'''
    mail.send(msg)




@app.route('/resend-verification')
def resend_verification():
    if "username" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("login"))

    email = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT email_verified FROM users WHERE username = ?", (email,))
    result = c.fetchone()

    if not result:
        flash("User not found.", "danger")
        conn.close()
        return redirect(url_for("profile"))

    email_verified = result[0]
    conn.close()

    if email_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for("profile"))

    # Send the verification email again
    send_verification_email(email)
    flash("Verification email resent!", "success")
    return redirect(url_for("profile"))






@app.route("/profile")
def profile():
    if "username" in session:
        username = session["username"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()

        # 🧠 Get profile data
        # 🧠 Get profile data
        c.execute("""
            SELECT display_name, age, location, favorite_animal,
                   dog_free_reason, profile_pic, bio, gender,
                   interests, main_tag, tags,
                   gallery_image_1, gallery_image_2, gallery_image_3,
                   gallery_image_4, gallery_image_5,
                   email_verified
            FROM users WHERE username = ?
        """, (username,))
        result = c.fetchone()

        # ✅ Get count of unread messages
        c.execute("""
            SELECT COUNT(*) FROM messages 
            WHERE recipient = ? AND is_read = 0
        """, (username,))
        unread_count = c.fetchone()[0]

        conn.close()

        (display_name, age, location, favorite_animal, dog_free_reason,
         profile_pic, bio, gender, interests, main_tag, tags_string,
         g1, g2, g3, g4, g5, email_verified) = result or (None,) * 17

        gallery_images = [g for g in [g1, g2, g3, g4, g5] if g]

        tags = tags_string.split(",") if tags_string else []

        return render_template("profile.html",
                               username=username,
                               display_name=display_name,
                               age=age,
                               location=location,
                               favorite_animal=favorite_animal,
                               dog_free_reason=dog_free_reason,
                               profile_pic=profile_pic,
                               bio=bio,
                               gender=gender,
                               interests=interests,
                               main_tag=main_tag,
                               tags=tags,
                               unread_count=unread_count,
                               gallery_images=gallery_images,
                               email_verified=email_verified)

    else:
        return redirect(url_for("login"))


# Upload up to 5 Pictures
UPLOAD_FOLDER = 'static/gallery/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    if request.method == "POST":
        # === Text fields ===
        display_name = request.form.get("display_name", "")
        age = request.form.get("age", None)
        location = request.form.get("location", "")
        favorite_animal = request.form.get("favorite_animal", "")
        dog_free_reason = request.form.get("dog_free_reason", "")
        bio = request.form.get("bio", "")
        interests = request.form.get("interests", "")
        main_tag = request.form.get("main_tag", "")
        tags = request.form.getlist("tags")
        tags_string = ",".join(tags)
        gender = request.form.get("gender", "")
        sexuality = request.form.get("sexuality", "")
        show_gender = 1 if request.form.get("show_gender") == "on" else 0
        show_sexuality = 1 if request.form.get("show_sexuality") == "on" else 0

        # Pet tag validation
        pet_tags = {
            "Fully Pet-Free", "Allergic to Everything", "Reptile Roomie", "Cat Companion",
            "Rodent Roomie", "Bird Bestie", "Fish Friend", "Turtle Tenant", "Plant Person",
            "Bug Buddy", "My Pet’s a Vibe", "No Bark Zone", "Clean House > Cute Paws"
        }
        if not any(tag in pet_tags for tag in [main_tag] + tags):
            flash("You must select at least one pet-related tag.", "danger")
            return redirect(url_for("settings"))

        # === Update profile info ===
        c.execute("""
            UPDATE users SET
                display_name = ?, age = ?, location = ?, favorite_animal = ?,
                dog_free_reason = ?, bio = ?, gender = ?, sexuality = ?, show_gender = ?, 
                show_sexuality = ? interests = ?, main_tag = ?, tags = ?
            WHERE username = ?
        """, (
            display_name, age, location, favorite_animal, dog_free_reason,
            bio, gender, interests, main_tag, tags_string, username
        ))

        # === Handle gallery image uploads ===
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        for i in range(1, 6):
            file = request.files.get(f'gallery_image_{i}')
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{username}_gallery_{i}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                c.execute(f"UPDATE users SET gallery_image_{i} = ? WHERE username = ?", (f'gallery/{filename}', username))

        conn.commit()
        conn.close()
        flash("Profile updated!", "success")
        return redirect(url_for("profile"))

    # === GET request: load current data ===
    c.execute("""
        SELECT display_name, age, location, favorite_animal, dog_free_reason,
               bio, gender, interests, main_tag, tags
        FROM users WHERE username = ?
    """, (username,))
    data = c.fetchone()
    conn.close()

    return render_template("settings.html", data=data)

@app.route("/complete-profile", methods=["GET", "POST"])
def complete_profile():
    if "username" not in session or not session.get("needs_profile_completion"):
        return redirect(url_for("profile"))

    username = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    if request.method == "POST":
        new_username = request.form.get("new_username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        age = request.form.get("age")
        location = request.form.get("location", "")
        favorite_animal = request.form.get("favorite_animal", "")
        dog_free_reason = request.form.get("dog_free_reason", "")
        bio = request.form.get("bio", "")
        interests = request.form.get("interests", "")
        main_tag = request.form.get("main_tag", "")
        tags = request.form.getlist("tags")
        tags_string = ",".join(tags)
        gender = request.form.get("gender", "")
        sexuality = request.form.get("sexuality", "")
        show_gender = 1 if request.form.get("show_gender") == "on" else 0
        show_sexuality = 1 if request.form.get("show_sexuality") == "on" else 0

        # Check username uniqueness
        c.execute("SELECT 1 FROM users WHERE username = ? AND username != ?", (new_username, username))
        if c.fetchone():
            flash("Username already taken.", "danger")
            return redirect(url_for("complete_profile"))

        # Pet tag validation
        pet_tags = {
            "Fully Pet-Free", "Allergic to Everything", "Reptile Roomie", "Cat Companion",
            "Rodent Roomie", "Bird Bestie", "Fish Friend", "Turtle Tenant", "Plant Person",
            "Bug Buddy", "My Pet’s a Vibe", "No Bark Zone", "Clean House > Cute Paws"
        }
        if not any(tag in pet_tags for tag in [main_tag] + tags):
            flash("You must select at least one pet-related tag.", "danger")
            return redirect(url_for("complete_profile"))

        # Update user profile
        c.execute("""
            UPDATE users SET
                username = ?, display_name = ?, age = ?, location = ?,
                favorite_animal = ?, dog_free_reason = ?, bio = ?, gender = ?,
                interests = ?, main_tag = ?, tags = ?
            WHERE username = ?
        """, (
            new_username, display_name, age, location, favorite_animal,
            dog_free_reason, bio, gender, interests, main_tag, tags_string, username
        ))

        conn.commit()
        conn.close()

        session["username"] = new_username
        session.pop("needs_profile_completion", None)
        flash("Profile completed!", "success")
        return redirect(url_for("profile"))

    # Pre-fill display_name from DB
    c.execute("SELECT display_name FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    display_name = row[0] if row else ""
    conn.close()

    return render_template("complete_profile.html", display_name=display_name, username=username)


@app.route("/delete_gallery_image/<int:index>", methods=["POST"])
def delete_gallery_image(index):
    if "username" not in session:
        return redirect(url_for("login"))

    if not 1 <= index <= 5:
        flash("Invalid image index.", "danger")
        return redirect(url_for("profile"))

    username = session["username"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get current image path
    c.execute(f"SELECT gallery_image_{index} FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    image_path = result[0] if result else None

    if image_path:
        # Try to delete file
        try:
            os.remove(os.path.join("static", image_path))
        except Exception as e:
            print("Error deleting file:", e)

        # Remove from DB
        c.execute(f"UPDATE users SET gallery_image_{index} = NULL WHERE username = ?", (username,))
        conn.commit()

    conn.close()
    flash("Photo deleted.", "success")
    return redirect(url_for("profile"))


@app.route("/set_location", methods=["POST"])
def set_location():
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 403

    data = request.get_json()
    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        return jsonify({"error": "Missing coordinates"}), 400

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET latitude = ?, longitude = ? WHERE username = ?", (lat, lon, session["username"]))
    conn.commit()
    conn.close()

    return jsonify({"success": True})




@app.route("/browse", methods=["GET", "POST"])
def browse():
    if "username" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get filter inputs
    min_age = request.form.get("min_age")
    max_age = request.form.get("max_age")
    location_input = request.form.get("location", "").strip().lower()
    gender_input = request.form.get("gender", "").strip().lower()

    # Get preferred and dealbreaker tags from input
    preferred_tags = request.form.getlist("preferred_tags")
    preferred_tags = [tag.strip().lower() for tag in preferred_tags if tag.strip()]

    dealbreaker_tags = request.form.getlist("dealbreaker_tags")
    dealbreaker_tags = [tag.strip().lower() for tag in dealbreaker_tags if tag.strip()]

    # Fetch all other users including their coordinates
    c.execute("""
        SELECT display_name, username, age, location, favorite_animal, 
               dog_free_reason, profile_pic, bio, gender, interests, main_tag, tags,
               latitude, longitude
        FROM users
        WHERE username != ?
    """, (session["username"],))
    all_users = c.fetchall()

    # Get current user's coordinates
    c.execute("SELECT latitude, longitude FROM users WHERE username = ?", (session["username"],))
    current_coords = c.fetchone()
    user_lat, user_lon = current_coords if current_coords else (None, None)

    conn.close()

    # Score each user
    from math import radians, cos, sin, asin, sqrt

    def haversine(lat1, lon1, lat2, lon2):
        # Calculate great-circle distance (in km)
        R = 6371
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        return R * 2 * asin(sqrt(a))

    def score_user(user):
        score = 0
        (display_name, username, age, loc, _, _, _, _, gender, _, _, tags_str,
         lat, lon) = user

        if min_age and age and int(age) >= int(min_age):
            score += 1
        if max_age and age and int(age) <= int(max_age):
            score += 1
        if location_input and loc and location_input in loc.lower():
            score += 1
        if gender_input and gender and gender_input == gender.lower():
            score += 1

        user_tags = tags_str.lower().split(",") if tags_str else []

        if any(tag in user_tags for tag in dealbreaker_tags):
            return -1

        for tag in preferred_tags:
            if tag in user_tags:
                score += 1

        # 🌍 Boost score based on distance
        if user_lat and user_lon and lat and lon:
            try:
                dist = haversine(float(user_lat), float(user_lon), float(lat), float(lon))
                if dist < 20:
                    score += 2
                elif dist < 50:
                    score += 1
            except:
                pass

        return score

    # Pair users with their score and sort by best match
    scored_users = [
        (user, score) for user in all_users
        if (score := score_user(user)) >= 0
    ]
    scored_users.sort(key=lambda x: x[1], reverse=True)

    return render_template("browse.html", users=scored_users)

@app.route("/user/<username>")
def view_user_profile(username):
    if "username" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get user info
    c.execute("""
        SELECT display_name, age, location, favorite_animal,
       dog_free_reason, profile_pic, bio, gender, interests, main_tag, tags,
       gallery_image_1, gallery_image_2, gallery_image_3,
       gallery_image_4, gallery_image_5
        FROM users WHERE username = ?
    """, (username,))
    result = c.fetchone()

    conn.close()

    if not result:
        flash("User not found.", "danger")
        return redirect(url_for("browse"))

    (display_name, age, location, favorite_animal, dog_free_reason,
     profile_pic, bio, gender, interests, main_tag, tags_string,
     g1, g2, g3, g4, g5) = result or (None,) * 16

    gallery_images = [g for g in [g1, g2, g3, g4, g5] if g]
    tags = tags_string.split(",") if tags_string else []

    return render_template("public_profile.html",
                           username=username,
                           display_name=display_name,
                           age=age,
                           location=location,
                           favorite_animal=favorite_animal,
                           dog_free_reason=dog_free_reason,
                           profile_pic=profile_pic,
                           bio=bio,
                           gender=gender,
                           interests=interests,
                           main_tag=main_tag,
                           tags=tags,
                           gallery_images=gallery_images)



@app.route("/matches")
def matches():
    if "username" not in session:
        return redirect(url_for("login"))

    current_user = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get users who current_user liked
    c.execute("SELECT liked FROM likes WHERE liker = ?", (current_user,))
    liked_users = set([row[0] for row in c.fetchall()])

    # Get users who liked current_user
    c.execute("SELECT liker FROM likes WHERE liked = ?", (current_user,))
    liked_by_users = set([row[0] for row in c.fetchall()])

    # Find mutual matches
    mutual_matches = liked_users.intersection(liked_by_users)

    # Get display info for those matched users
    if mutual_matches:
        placeholders = ",".join("?" * len(mutual_matches))
        c.execute(f"""
            SELECT display_name, username, age, location, favorite_animal, dog_free_reason, profile_pic, main_tag
            FROM users WHERE username IN ({placeholders})
        """, tuple(mutual_matches))

        match_list = c.fetchall()
    else:
        match_list = []

    conn.close()

    return render_template("matches.html", matches=match_list)


@app.route("/like/<username>", methods=["POST"])
def like(username):
    if "username" not in session:
        return redirect(url_for("login"))

    liker = session["username"]
    liked = username

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT 1 FROM likes WHERE liker = ? AND liked = ?", (liker, liked))
    already_liked = c.fetchone()

    if not already_liked:
        c.execute("INSERT INTO likes (liker, liked) VALUES (?, ?)", (liker, liked))
        conn.commit()
        flash(f"You liked @{liked}!")

    conn.close()
    return redirect(url_for("browse"))

@app.route("/unmatch/<username>", methods=["POST"])
def unmatch(username):
    if "username" not in session:
        return redirect(url_for("login"))

    current_user = session["username"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Remove both sides of the match
    c.execute("DELETE FROM likes WHERE liker = ? AND liked = ?", (current_user, username))
    c.execute("DELETE FROM likes WHERE liker = ? AND liked = ?", (username, current_user))
    conn.commit()
    conn.close()

    flash(f"You unmatched with @{username}.", "info")
    return redirect(url_for("matches"))

@app.route("/messages")
def messages():
    if "username" not in session:
        return redirect(url_for("login"))

    current_user = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
           SELECT u.username, u.display_name, u.profile_pic,
                  MAX(m.timestamp) as last_message_time,
                  SUM(CASE WHEN m.recipient = ? AND m.is_read = 0 AND m.sender = u.username THEN 1 ELSE 0 END) as unread_count,
                  (
                      SELECT content
                      FROM messages
                      WHERE (sender = u.username AND recipient = ?)
                         OR (sender = ? AND recipient = u.username)
                      ORDER BY timestamp DESC
                      LIMIT 1
                  ) as last_message_text
           FROM users u
           JOIN messages m ON (u.username = m.sender OR u.username = m.recipient)
           WHERE ? IN (m.sender, m.recipient) AND u.username != ?
           GROUP BY u.username, u.display_name, u.profile_pic
           ORDER BY last_message_time DESC
       """, (current_user, current_user, current_user, current_user, current_user))

    chats = c.fetchall()
    conn.close()

    return render_template("message_list.html", chats=chats)





@app.route("/messages/<username>", methods=["GET", "POST"])
def message_thread(username):
    if "username" not in session:
        return redirect(url_for("login"))

    current_user = session["username"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Handle new message being sent
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        image = request.files.get("image")
        image_url = None

        # Save uploaded image if it exists and is valid
        if image and allowed_file(image.filename):
            os.makedirs("static/uploads", exist_ok=True)
            filename = secure_filename(image.filename)
            image_path = os.path.join("static/uploads", filename)
            image.save(image_path)
            image_url = "/" + image_path  # For web use

        if message or image_url:
            c.execute("""
                INSERT INTO messages (sender, recipient, content, image_url)
                VALUES (?, ?, ?, ?)
            """, (current_user, username, message, image_url))
            conn.commit()

        # Respond with the new message (for AJAX)
        return jsonify({
            'sender': current_user,
            'content': message,
            'image_url': image_url,
            'timestamp': "Just now",
            'is_read': 0,
            'message_id': c.lastrowid
        })

    # Fetch display name of the other user (runs on GET)
    c.execute("SELECT display_name FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    other_display_name = row[0] if row else username

    # Mark unread messages from the other user as read
    c.execute("""
        UPDATE messages
        SET is_read = 1
        WHERE sender = ? AND recipient = ? AND is_read = 0
    """, (username, current_user))

    # Fetch visible conversation messages
    c.execute("""
        SELECT sender, content, timestamp, is_read, id, image_url FROM messages
        WHERE (
            (sender = ? AND recipient = ? AND is_deleted_by_sender = 0)
            OR
            (sender = ? AND recipient = ? AND is_deleted_by_recipient = 0)
        )
        ORDER BY timestamp ASC
    """, (current_user, username, username, current_user))

    messages = c.fetchall()
    conn.close()

    starter_questions = [
        "What’s your favorite animal (non-dog edition)?",
        "If you had to live with a dog, what’s your survival plan?",
        "Tell me your most ridiculous dog encounter story.",
        "How do you respond to 'but my dog is friendly'?",
    ]

    return render_template("messages.html",
                           messages=messages,
                           other_user=username,
                           other_display_name=other_display_name,
                           starter_questions=starter_questions
                           )


@app.route("/delete_message/<int:message_id>", methods=["POST"])
def delete_message(message_id):
    if "username" not in session:
        return redirect(url_for("login"))

    current_user = session["username"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Check who sent/received this message
    c.execute("SELECT sender, recipient FROM messages WHERE id = ?", (message_id,))
    result = c.fetchone()

    if not result:
        conn.close()
        return "Message not found", 404

    sender, recipient = result

    if current_user == sender:
        c.execute("UPDATE messages SET is_deleted_by_sender = 1 WHERE id = ?", (message_id,))
    elif current_user == recipient:
        c.execute("UPDATE messages SET is_deleted_by_recipient = 1 WHERE id = ?", (message_id,))
    else:
        conn.close()
        return "Unauthorized", 403

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message_id": message_id})




@app.route("/report/<username>", methods=["POST"])
def report(username):
    if "username" not in session:
        return redirect(url_for("login"))

    reporter = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT INTO reports (reported_user, reporter) VALUES (?, ?)", (username, reporter))
    conn.commit()
    conn.close()

    flash(f"You reported @{username}.")
    return redirect(url_for("browse"))


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.context_processor
def inject_unread_count():
    if "username" in session:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM messages WHERE recipient = ? AND is_read = 0", (session["username"],))
        unread = c.fetchone()[0]
        conn.close()
        return {"global_unread_count": unread}
    return {"global_unread_count": 0}


@app.route("/dev-login")
def dev_login():
    # Automatically log in as a fake user
    session["username"] = "testuser111"
    return redirect(url_for("profile"))

@app.route("/dev-login-1")
def dev_login_1():
    session["username"] = "testuser1"
    return redirect(url_for("profile"))

@app.route("/dev-login-2")
def dev_login_2():
    session["username"] = "testuser2"
    return redirect(url_for("profile"))

@app.route("/debug-likes")
def debug_likes():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT liker, liked FROM likes")
    rows = c.fetchall()
    conn.close()

    return "<br>".join([f"{liker} liked {liked}" for liker, liked in rows])



if __name__ == "__main__":
    app.run(debug=True)