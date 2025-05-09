import os, random, sqlite3, traceback
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
from country_list import countries_for_language
from database import setup_database

setup_database()

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
# ✅ Configure Flask-Mail for Zoho
app.config['MAIL_SERVER'] = 'smtp.zoho.jp'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False  # ✅ Make sure this is explicitly False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

# Upload folders
PROFILE_PIC_FOLDER = 'static/profilepics/'
GALLERY_FOLDER = 'static/gallery/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['PROFILE_PIC_FOLDER'] = PROFILE_PIC_FOLDER
app.config['GALLERY_FOLDER'] = GALLERY_FOLDER



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

def calculate_age(birthday_str):
    from datetime import datetime
    try:
        if not birthday_str or birthday_str.strip() == "":
            return None
        birthday = datetime.strptime(birthday_str, "%Y-%m-%d")
        today = datetime.today()
        return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
    except Exception as e:
        print("AGE CALC FAIL:", birthday_str, "->", e)
        return None


@app.errorhandler(500)
def internal_error(error):
    print("500 error:", error)
    traceback.print_exc()
    return "Internal Server Error", 500

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
        # Retrieve form data
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        dog_free = request.form.get("dog_free")

        profile_pic_file = request.files.get("profile_pic")
        profile_pic_path = ""

        if profile_pic_file and allowed_file(profile_pic_file.filename):
            filename = secure_filename(f"{username}_profile_{profile_pic_file.filename}")
            filepath = os.path.join(app.config['PROFILE_PIC_FOLDER'], filename)
            profile_pic_file.save(filepath)
            profile_pic_path = f'profilepics/{filename}'


        # Validate password complexity
        import re
        if not re.match(r'^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[\W_]).{8,}$', password):
            flash("Password must be at least 8 characters long and include an uppercase letter, a lowercase letter, a number, and a special character.", "danger")
            return redirect(url_for("signup"))

        # Ensure the user agrees to the dog-free oath
        if dog_free != "on":
            flash("You must agree to the Dog-Free Oath to join Muzzle.", "danger")
            return redirect(url_for("signup"))

        # Retrieve additional form data
        display_name = request.form.get("display_name", "")
        birthday = request.form.get("birthday")
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")
        favorite_animal = request.form.get("favorite_animal", "")
        dog_free_reason = request.form.get("dog_free_reason", "")
        bio = request.form.get("bio", "")
        gender = request.form.get("gender", "")
        sexuality = request.form.get("sexuality", "")
        show_gender = 1 if request.form.get("show_gender") == "on" else 0
        show_sexuality = 1 if request.form.get("show_sexuality") == "on" else 0
        interests = request.form.get("interests", "")
        main_tag = request.form.get("main_tag", "")
        tags = request.form.getlist("tags")
        all_tags = [main_tag] + tags
        tags_string = ",".join(tags)
        show_gender = 1 if request.form.get("show_gender") == "on" else 0
        show_sexuality = 1 if request.form.get("show_sexuality") == "on" else 0

        # Validate that at least one pet-related tadefg is selected
        pet_tags = {
            "Fully Pet-Free", "Allergic to Everything", "Reptile Roomie", "Cat Companion",
            "Rodent Roomie", "Bird Bestie", "Fish Friend", "Turtle Tenant", "Plant Person",
            "Bug Buddy", "My Pet’s a Vibe", "No Bark Zone", "Clean House > Cute Paws"
        }
        if not any(tag in pet_tags for tag in all_tags):
            flash("You must select at least one pet-related tag (main or additional).", "danger")
            return redirect(url_for("signup"))

        try:
            conn = sqlite3.connect("users.db")
            c = conn.cursor()

            # Check if the email is already registered
            c.execute("SELECT 1 FROM users WHERE email = ?", (email,))
            if c.fetchone():
                flash("Email is already registered.", "danger")
                return redirect(url_for("signup"))

            # Check if the username is already taken
            c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if c.fetchone():
                flash("Username already taken.", "danger")
                return redirect(url_for("signup"))

            # Hash the password
            hashed_password = generate_password_hash(password)

            # Insert the new user into the database
            c.execute("""
                INSERT INTO users (
                    username, email, password, display_name, birthday, latitude, longitude,
                    favorite_animal, dog_free_reason, profile_pic, bio,
                    gender, sexuality, show_gender, show_sexuality, interests, main_tag, tags,
                    email_verified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                username, email, hashed_password, display_name, birthday, latitude, longitude,
                favorite_animal, dog_free_reason, profile_pic_path, bio,
                gender, sexuality, show_gender, show_sexuality, interests, main_tag, tags_string
            ))

            conn.commit()
            conn.close()

            # ✅ Send verification email after successful signup
            send_verification_email(email)

            flash("Account created successfully! Please check your email to verify.", "success")
            return redirect(url_for("login"))


        except sqlite3.IntegrityError:
            conn.rollback()
            conn.close()
            flash("An account with this email or username already exists.", "danger")
            return redirect(url_for("signup"))

    country_list = dict(countries_for_language('en'))
    return render_template("signup.html", username=request.form.get("username", ""), country_list=country_list)



@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = c.fetchone()

        if result and check_password_hash(result[0], password):
            session["username"] = username
            c.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            session["is_admin"] = (row[0] == 1) if row else False

            login_time = datetime.now()
            session["login_time"] = login_time.isoformat()

            # ✅ Update last login timestamp in users table
            c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = ?", (username,))

            # ✅ Insert login event into session_logs
            c.execute("INSERT INTO session_logs (username, login_time) VALUES (?, ?)", (username, login_time))

            conn.commit()
            conn.close()
            return redirect(url_for("profile"))

        else:
            conn.close()
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
    adjectives = [
        "Bold", "Witty", "Chill", "Thick", "Sly", "Clever",
        "Gentle", "Zesty", "Brave", "Loyal", "Sleepy", "Hyperactive",
        "Bouncy", "Inflatable", "The", "Endangered", "Immortal", "Real", "Lefthanded",
        "Assistant", "Crusty", "Feral", "Wandering", "Lucky", "Unstoppable", "Lonely",
        "Single", "Professional", "Legendary", "Part-time", "Little", "Big",
        "Awkward", "Electric", "Quantum", "Cursed", "Shiny", "Suspicious",
        "Curious", "Grumpy", "Haunted", "Speedy", "Snacky", "Mysterious", "Buff",
        "Quantum", "Loopy", "Obscure", "Nocturnal", "Unicorned", "Educated", "Entitled",
        "Radical", "Spicy", "Sweet", "Salty", "Delusional", "Enlightened", "Jaded"
    ]

    animals = [
        "Koala", "Gecko", "Iguana", "Cat", "Turtle", "Ferret", "Fox", "Hedgehog",
        "Rabbit", "Tiger", "Giraffe", "Penguin", "Llama", "Otter", "Snake", "Platypus",
        "Tarantula", "Spider", "Lizard", "Dragon", "Owl", "Axolotl", "Chameleon",
        "Sloth", "Fennec", "Panther", "Panda", "Frog", "Skink", "Mantis", "Octopus",
        "Kangaroo", "Newt", "Moth", "Caterpillar", "Raccoon", "Possum", "Snail",
        "Gekko", "Jackalope", "Phoenix", "Tapir", "Capybara", "Shrimp", "Mole",
        "Stingray", "Cobra", "Worm", "Beetle", "Cricket", "Phoenix", "LochNessMonster",
        "Unicorn", "Basilisk", "Kraken", "Cerberus", "Pegasus", "Chimera", "Hydra",
        "Sphinx", "Yeti", "Faun", "Mermaid", "Minotaur", "Gorgon", "Banshee", "Tanuki",
        "Qilin", "Zhulong", "Viper", "NineTailedFox"
    ]

    return random.choice(adjectives) + random.choice(animals)

def generate_username(base_name):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    while True:
        random_number = random.randint(100, 999)
        new_username = f"{base_name}{random_number}"
        c.execute("SELECT 1 FROM users WHERE username = ?", (new_username,))
        if not c.fetchone():
            conn.close()
            return new_username


@app.route('/login/google/callback')
def google_callback():
    token = google.authorize_access_token()
    user_info = google.get('https://openidconnect.googleapis.com/v1/userinfo').json()
    email = user_info['email']

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Check by email since username will now be random
    c.execute("SELECT username FROM users WHERE email = ?", (email,))
    existing_user = c.fetchone()

    if not existing_user:
        display_name = generate_display_name()
        username = generate_username(display_name)

        c.execute("""
            INSERT INTO users (username, email, password, display_name, email_verified)
            VALUES (?, ?, ?, ?, 1)
        """, (username, email, generate_password_hash("google_oauth_login"), display_name))
        conn.commit()
        session["needs_profile_completion"] = True

        # ✅ Send welcome email
        send_welcome_email(email)

        # ✅ Make first user admin
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        if user_count == 1:
            c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
    else:
        # Fetch the correct username for existing user
        username = existing_user[0]

    # ✅ Set login time and session
    login_time = datetime.now()
    session["username"] = username
    session["login_time"] = login_time.isoformat()

    # ✅ Check if user is admin
    c.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    session["is_admin"] = (row[0] == 1) if row else False

    # ✅ Update last login + log the session
    c.execute("UPDATE users SET last_login = ? WHERE username = ?", (login_time, username))
    c.execute("INSERT INTO session_logs (username, login_time) VALUES (?, ?)", (username, login_time))

    conn.commit()
    conn.close()

    flash("Logged in with Google!", "success")
    if session.pop("needs_profile_completion", False):
        return redirect(url_for("google_terms"))
    return redirect(url_for("profile"))



@app.route("/google-terms", methods=["GET", "POST"])
def google_terms():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if not request.form.get("agree_terms") or not request.form.get("dog_free"):
            flash("You must agree to both to continue.", "danger")
            return redirect(url_for("google_terms"))

        session["agreed_google_terms"] = True
        return redirect(url_for("complete_profile"))

    return render_template("google_terms.html")



def update_last_login(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Set the current timestamp for last_login
    c.execute("UPDATE users SET last_login = ? WHERE username = ?", (datetime.now(), username))
    conn.commit()
    conn.close()

@app.route('/verify/<token>')
def verify_email(token):
    email = confirm_verification_token(token)
    if not email:
        flash('Verification link expired or invalid.', 'danger')
        return redirect(url_for('home'))

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT email_verified FROM users WHERE email = ?", (email,))
    user = c.fetchone()

    if user:
        if user[0] == 1:
            flash('Email already verified!', 'info')
        else:
            c.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))
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

@app.route("/check-username")
def check_username():
    username = request.args.get("username", "").strip()
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    taken = c.fetchone() is not None
    conn.close()
    return jsonify({"taken": taken})


# Sending the verification
from flask_mail import Message

def send_welcome_email(user_email):
    msg = Message('Welcome to Muzzle 🐾', recipients=[user_email])
    msg.body = f'''
Hi there!

Thanks for signing up for Muzzle — the dating app for dog-free singles 🐶🚫

You're all set to start meeting like-minded people.

Start browsing now and don’t forget to complete your profile!

Cheers,  
The Muzzle Team
'''
    mail.send(msg)


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

    username = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT email, email_verified FROM users WHERE username = ?", (username,))
    result = c.fetchone()

    if not result:
        flash("User not found.", "danger")
        conn.close()
        return redirect(url_for("profile"))

    email, email_verified = result
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
        c.execute("""
            SELECT display_name, birthday, location, favorite_animal,
       dog_free_reason, profile_pic, bio, gender, sexuality,
       interests, main_tag, tags,
       gallery_image_1, gallery_image_2, gallery_image_3,
       gallery_image_4, gallery_image_5,
       email_verified, show_gender, show_sexuality

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

        (display_name, birthday, location, favorite_animal, dog_free_reason,
         profile_pic, bio, gender, sexuality, interests, main_tag, tags_string,
         g1, g2, g3, g4, g5, email_verified, show_gender, show_sexuality) = result or (None,) * 20

        age = calculate_age(birthday) if birthday else "?"

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
                               sexuality=sexuality,
                               interests=interests,
                               main_tag=main_tag,
                               tags=tags,
                               unread_count=unread_count,
                               gallery_images=gallery_images,
                               email_verified=email_verified,
                               show_gender=show_gender,
                               show_sexuality=show_sexuality,
                               )

    else:
        return redirect(url_for("login"))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    profile_pic_file = request.files.get("profile_pic")
    if profile_pic_file and allowed_file(profile_pic_file.filename):
        filename = secure_filename(f"{username}_profile_{profile_pic_file.filename}")
        filepath = os.path.join(app.config['PROFILE_PIC_FOLDER'], filename)
        profile_pic_file.save(filepath)
        c.execute("UPDATE users SET profile_pic = ? WHERE username = ?", (f'profilepics/{filename}', username))


    if request.method == "POST":
        # === Text fields ===
        new_username = request.form.get("new_username", "").strip()
        display_name = request.form.get("display_name", "")
        birthday = request.form.get("birthday")
        location = request.form.get("location", "")
        country = request.form.get("country", "")
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")
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
            conn.close()
            return redirect(url_for("settings"))

        # === Check username availability ===
        if new_username != username:
            c.execute("SELECT 1 FROM users WHERE username = ?", (new_username,))
            if c.fetchone():
                flash("Username already taken.", "danger")
                conn.close()
                return redirect(url_for("settings"))

            # ✅ Update username in DB
            c.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, username))
            session["username"] = new_username
            username = new_username  # update for subsequent DB updates


        # === Update profile info ===
        c.execute("""
            UPDATE users SET
                display_name = ?, birthday = ?, location = ?, country = ?, latitude = ?, longitude = ?,
                favorite_animal = ?, dog_free_reason = ?, bio = ?, gender = ?, sexuality = ?,
                show_gender = ?, show_sexuality = ?, interests = ?, main_tag = ?, tags = ?
            WHERE username = ?
        """, (
            display_name, birthday, location, country, latitude, longitude,
            favorite_animal, dog_free_reason, bio, gender, sexuality,
            show_gender, show_sexuality, interests, main_tag, tags_string, username
        ))

        # === Handle gallery image uploads ===
        os.makedirs(app.config['GALLERY_FOLDER'], exist_ok=True)
        for i in range(1, 6):
            file = request.files.get(f'gallery_image_{i}')
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{username}_gallery_{i}_{file.filename}")
                filepath = os.path.join(app.config['GALLERY_FOLDER'], filename)
                file.save(filepath)
                c.execute(f"UPDATE users SET gallery_image_{i} = ? WHERE username = ?", (f'gallery/{filename}', username))

        conn.commit()
        conn.close()
        flash("Profile updated!", "success")
        return redirect(url_for("profile"))

    # === GET request: load current data ===
    c.execute("""
        SELECT username, email, display_name, birthday, location, latitude, longitude, favorite_animal, dog_free_reason,
       bio, gender, sexuality, interests, main_tag, tags, country, show_gender, show_sexuality

        FROM users WHERE username = ?
    """, (username,))
    data = c.fetchone()

    c.execute("SELECT profile_pic FROM users WHERE username = ?", (username,))
    profile_row = c.fetchone()
    profile_pic = profile_row[0] if profile_row else None

    conn.close()

    country_list = dict(countries_for_language("en"))
    return render_template("settings.html", data=data, country_list=country_list, profile_pic=profile_pic)




@app.route("/complete-profile", methods=["GET", "POST"])
def complete_profile():
    if "username" not in session or not session.get("needs_profile_completion"):
        return redirect(url_for("profile"))

    username = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    if session.get("google_user"):
        # Don't allow changing email for Google users — fetch from DB
        c.execute("SELECT email FROM users WHERE username = ?", (username,))
        email_row = c.fetchone()
        email = email_row[0] if email_row else ""
    else:
        email = request.form.get("email", "").strip()

    if request.method == "POST":
        if not request.form.get("agree_terms"):
            flash("You must agree to the Terms of Use to continue.", "danger")
            return redirect(url_for("complete_profile"))

        new_username = request.form.get("new_username", "").strip()
        display_name = request.form.get("display_name", "").strip()
        birthday = request.form.get("birthday")  # ✅ new birthday field
        location = request.form.get("location", "")
        country = request.form.get("country")
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")
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

        # Username check
        c.execute("SELECT 1 FROM users WHERE username = ? AND username != ?", (new_username, username))
        if c.fetchone():
            flash("Username already taken.", "danger")
            return redirect(url_for("complete_profile"))

        c.execute("SELECT 1 FROM users WHERE email = ? AND username != ?", (email, username))
        if c.fetchone():
            flash("Email is already in use.", "danger")
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
                username = ?, email = ?, display_name = ?, birthday = ?, location = ?, country = ?, latitude = ?, longitude = ?,
                favorite_animal = ?, dog_free_reason = ?, bio = ?, gender = ?, sexuality = ?, show_gender = ?, show_sexuality = ?,
                interests = ?, main_tag = ?, tags = ?
            WHERE username = ?
        """, (
            new_username, email, display_name, birthday, location, country, latitude, longitude,
            favorite_animal, dog_free_reason, bio, gender, sexuality, show_gender, show_sexuality,
            interests, main_tag, tags_string, username
        ))

        conn.commit()
        conn.close()

        session["username"] = new_username
        session.pop("needs_profile_completion", None)
        flash("Profile completed!", "success")
        return redirect(url_for("profile"))

    # Pre-fill display_name from DB
    c.execute("SELECT display_name, email FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    display_name = row[0] if row else ""
    email = row[1] if row else ""
    conn.close()

    country_list = dict(countries_for_language("en"))
    return render_template(
        "complete_profile.html",
        display_name=display_name,
        email=email,
        username=username,
        country_list=country_list
    )




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
    gender_input = request.form.get("gender", "").strip().lower()

    preferred_tags = request.form.getlist("preferred_tags")
    preferred_tags = [tag.strip().lower() for tag in preferred_tags if tag.strip()]

    dealbreaker_tags = request.form.getlist("dealbreaker_tags")
    dealbreaker_tags = [tag.strip().lower() for tag in dealbreaker_tags if tag.strip()]

    # New: location filter from form
    target_lat = request.form.get("target_latitude")
    target_lon = request.form.get("target_longitude")
    radius_km = request.form.get("radius_km")

    # Get liked and blocked users
    c.execute("SELECT liked FROM likes WHERE liker = ?", (session["username"],))
    liked_usernames = {row[0] for row in c.fetchall()}

    c.execute("SELECT blocked FROM blocks WHERE blocker = ?", (session["username"],))
    you_blocked = {row[0] for row in c.fetchall()}

    c.execute("SELECT blocker FROM blocks WHERE blocked = ?", (session["username"],))
    blocked_you = {row[0] for row in c.fetchall()}

    def infer_attracted_genders(user_gender, user_sexuality):
        if not user_gender or not user_sexuality:
            return []  # No filtering
        g = user_gender.lower()
        s = user_sexuality.lower()
        if s == "straight":
            return ["Female"] if g == "male" else ["Male"]
        elif s == "gay":
            return ["Male"] if g == "male" else ["Female"] if g == "female" else []
        elif s == "lesbian":
            return ["Female"] if g == "female" else []
        elif s == "bisexual":
            return ["Male", "Female"]
        elif s == "pansexual":
            return ["Male", "Female", "Nonbinary", "Trans Man", "Trans Woman", "Other"]
        else:
            return []  # Asexual, Other, Prefer not to say

    # Get current user's gender and sexuality
    c.execute("SELECT gender, sexuality FROM users WHERE username = ?", (session["username"],))
    row = c.fetchone()
    user_gender, user_sexuality = row if row else (None, None)
    attracted_genders = infer_attracted_genders(user_gender, user_sexuality)

    # Fetch all other users
    c.execute("""
        SELECT display_name, username, birthday, location, favorite_animal, 
               dog_free_reason, profile_pic, bio, gender, interests, main_tag, tags,
               latitude, longitude
        FROM users
        WHERE username != ?
    """, (session["username"],))
    all_users_raw = c.fetchall()

    # Filter out liked and blocked users
    all_users = [
        user for user in all_users_raw
        if user[1] not in liked_usernames
           and user[1] not in you_blocked
           and user[1] not in blocked_you
    ]

    # Distance calculator
    from math import radians, cos, sin, asin, sqrt
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371  # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return R * 2 * asin(sqrt(a))


    def score_user(user):
        score = 0
        (display_name, username, birthday, loc, _, _, _, _, gender, _, _, tags_str,
         lat, lon) = user

        user_age = calculate_age(birthday)

        if min_age and user_age and user_age >= int(min_age):
            score += 1
        if max_age and user_age and user_age <= int(max_age):
            score += 1

        if gender_input and gender and gender_input == gender.lower():
            score += 1

        user_tags = tags_str.lower().split(",") if tags_str else []

        if any(tag in user_tags for tag in dealbreaker_tags):
            return -1

        for tag in preferred_tags:
            if tag in user_tags:
                score += 1

        # 🌍 Location filter + proximity boost
        if radius_km and target_lat and target_lon and lat and lon:
            try:
                dist = haversine(float(target_lat), float(target_lon), float(lat), float(lon))
                if dist > float(radius_km):
                    return -1  # too far, exclude
                if dist < 20:
                    score += 2
                elif dist < 50:
                    score += 1
            except:
                pass

        return score

    # Build final list
    scored_users = []
    for user in all_users:
        if attracted_genders:
            their_gender = user[8]  # gender field from user tuple
            if their_gender not in attracted_genders:
                continue  # skip user
        score = score_user(user)
        ...

        if score >= 0:
            birthday = user[2]
            age = calculate_age(birthday) if birthday else "?"
            scored_users.append((user, score, age))

    scored_users.sort(key=lambda x: x[1], reverse=True)
    conn.close()

    country_list = dict(countries_for_language('en'))  # ✅ add this

    return render_template("browse.html", users=scored_users, country_list=country_list)  # ✅ updated


@app.route("/next-user", methods=["POST"])
def next_user():
    if "username" not in session:
        return "", 401

    current_user = session["username"]
    shown_usernames = request.json.get("shown_usernames", [])

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get liked users
    c.execute("SELECT liked FROM likes WHERE liker = ?", (current_user,))
    liked_usernames = {row[0] for row in c.fetchall()}

    # Combine with already shown on frontend
    exclude_usernames = set(shown_usernames) | liked_usernames | {current_user}

    # Fetch next best user
    placeholders = ",".join("?" for _ in exclude_usernames)
    query = f"""
        SELECT display_name, username, birthday, location, favorite_animal, 
               dog_free_reason, profile_pic, bio, gender, interests, main_tag, tags,
               latitude, longitude
        FROM users
        WHERE username NOT IN ({placeholders})
        LIMIT 1
    """
    c.execute(query, tuple(exclude_usernames))
    result = c.fetchone()
    conn.close()

    if not result:
        return "", 204  # No more users

    # Render a partial HTML card for this user
    rendered_card = render_template("partials/user_card.html", user=result, score=0)
    return rendered_card


@app.route("/user/<username>")
def view_user_profile(username):
    if "username" not in session:
        return redirect(url_for("login"))

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get user info
    c.execute("""
        SELECT display_name, birthday, location, favorite_animal,
        dog_free_reason, profile_pic, bio, gender, sexuality, interests, main_tag, tags,
        gallery_image_1, gallery_image_2, gallery_image_3,
        gallery_image_4, gallery_image_5,
        show_gender, show_sexuality

        FROM users WHERE username = ?
    """, (username,))
    result = c.fetchone()

    conn.close()

    if not result:
        flash("User not found.", "danger")
        return redirect(url_for("browse"))

    (display_name, birthday, location, favorite_animal, dog_free_reason,
     profile_pic, bio, gender, sexuality, interests, main_tag, tags_string,
     g1, g2, g3, g4, g5, show_gender, show_sexuality) = result or (None,) * 18

    age = calculate_age(birthday) if birthday else "?"

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
                           sexuality=sexuality,
                           interests=interests,
                           main_tag=main_tag,
                           tags=tags,
                           gallery_images=gallery_images,
                           show_gender=show_gender,
                           show_sexuality=show_sexuality,
                           )



@app.route("/matches", methods=["GET", "POST"])
def matches():
    if "username" not in session:
        return redirect(url_for("login"))

    current_user = session["username"]
    sort_by = request.args.get("sort_by", "recent")  # Default to "recent"

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Get users who liked the current user and vice versa
    c.execute("SELECT liked FROM likes WHERE liker = ?", (current_user,))
    liked_users = [row[0] for row in c.fetchall()]

    c.execute("SELECT liker FROM likes WHERE liked = ?", (current_user,))
    liked_by_users = [row[0] for row in c.fetchall()]

    # Find mutual matches
    mutual_matches = set(liked_users).intersection(liked_by_users)

    # Exclude blocked users (either blocked by or blocked the current user)
    c.execute("""
        SELECT blocked FROM blocks WHERE blocker = ?
        UNION
        SELECT blocker FROM blocks WHERE blocked = ?
    """, (current_user, current_user))
    blocked_usernames = {row[0] for row in c.fetchall()}

    mutual_matches = mutual_matches - blocked_usernames

    # Fetch details for those matched users
    match_list = []
    if mutual_matches:
        placeholders = ",".join("?" * len(mutual_matches))
        c.execute(f"""
            SELECT display_name, username, birthday, location, favorite_animal, profile_pic, main_tag, last_login, latitude, longitude
            FROM users WHERE username IN ({placeholders})
        """, tuple(mutual_matches))

        rows = c.fetchall()
        for row in rows:
            display_name, username, birthday, location, favorite_animal, profile_pic, main_tag, last_login, lat, lon = row
            age = calculate_age(birthday) if birthday else "?"
            match_list.append((display_name, username, age, location, favorite_animal, profile_pic, main_tag, last_login, lat, lon))

    # Sort the match list based on the selected sorting method
    if sort_by == "name":
        match_list.sort(key=lambda x: x[0].lower())
    elif sort_by == "recent":
        match_list.sort(key=lambda x: x[7] or datetime.min, reverse=True)
    elif sort_by == "distance":
        c.execute("SELECT latitude, longitude FROM users WHERE username = ?", (current_user,))
        current_coords = c.fetchone()
        current_lat, current_lon = current_coords if current_coords else (None, None)

        def haversine(lat1, lon1, lat2, lon2):
            from math import radians, cos, sin, sqrt, asin
            if None in [lat1, lon1, lat2, lon2]:
                return float('inf')
            R = 6371
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
            return R * 2 * asin(sqrt(a))

        match_list.sort(key=lambda x: haversine(current_lat, current_lon, x[8], x[9]))

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

    # First check if this like already exists
    c.execute("SELECT 1 FROM likes WHERE liker = ? AND liked = ?", (liker, liked))
    already_liked = c.fetchone()

    # If not already liked, check like count and maybe insert
    if not already_liked:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        c.execute("""
            SELECT COUNT(*) FROM likes
            WHERE liker = ? AND timestamp >= ?
        """, (liker, start_of_day))
        likes_today = c.fetchone()[0]

        if likes_today >= 10:
            conn.close()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"error": "Daily like limit reached"}), 429
            else:
                flash("You’ve reached your 10 likes for today!", "warning")
                return redirect(url_for("browse"))

        # Insert new like
        c.execute("INSERT INTO likes (liker, liked) VALUES (?, ?)", (liker, liked))
        conn.commit()
        flash(f"You liked @{liked}!")

    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return "", 204

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

    # 🚫 Block check
    c.execute("""
        SELECT 1 FROM blocks
        WHERE (blocker = ? AND blocked = ?) OR (blocker = ? AND blocked = ?)
    """, (current_user, username, username, current_user))
    blocked = c.fetchone()

    if blocked:
        conn.close()
        flash("You cannot message this user.")
        return redirect(url_for("browse"))

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
    reason = request.form.get("reason", "")
    comments = request.form.get("comments", "")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO reports (reported_user, reporter, reason, comments)
        VALUES (?, ?, ?, ?)
    """, (username, reporter, reason, comments))
    conn.commit()
    conn.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return "", 204  # No Content for AJAX

    flash(f"You reported @{username} for: {reason}")
    return redirect(url_for("browse"))


@app.route("/block/<username>", methods=["POST"])
def block_user(username):
    if "username" not in session:
        return redirect(url_for("login"))

    blocker = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Create block table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blocker TEXT NOT NULL,
            blocked TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert block entry
    c.execute("INSERT INTO blocks (blocker, blocked) VALUES (?, ?)", (blocker, username))
    conn.commit()
    conn.close()

    return "", 204  # No content needed for fetch success


@app.route("/logout")
def logout():
    username = session.get("username")
    login_time_str = session.get("login_time")

    if username and login_time_str:
        try:
            from datetime import datetime
            logout_time = datetime.now()
            login_time = datetime.fromisoformat(login_time_str)
            duration_seconds = int((logout_time - login_time).total_seconds())

            conn = sqlite3.connect("users.db")
            c = conn.cursor()
            c.execute("""
                UPDATE session_logs
                SET logout_time = ?, duration_seconds = ?
                WHERE username = ? AND login_time = ?
            """, (logout_time, duration_seconds, username, login_time))
            conn.commit()
            conn.close()
        except Exception as e:
            print("Error logging session duration:", e)

    # Clear session
    session.pop("username", None)
    session.pop("login_time", None)
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

@app.route("/admin/stats")
def admin_stats():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # ✅ Check if current user is admin
    c.execute("SELECT is_admin FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row or row[0] != 1:
        conn.close()
        return "Unauthorized", 403

    # ✅ Gather analytics
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM session_logs")
    total_sessions = c.fetchone()[0]

    c.execute("SELECT AVG(duration_seconds) FROM session_logs WHERE duration_seconds IS NOT NULL")
    avg_duration = round(c.fetchone()[0] or 0)

    c.execute("""
        SELECT username, COUNT(*) as session_count
        FROM session_logs
        GROUP BY username
        ORDER BY session_count DESC
        LIMIT 5
    """)
    top_users = c.fetchall()

    conn.close()

    return render_template("admin_stats.html", total_users=total_users,
                           total_sessions=total_sessions,
                           avg_duration=avg_duration,
                           top_users=top_users)


@app.route("/test")
def test_mobile():
    return render_template("test_mobile.html")



if __name__ == "__main__":
    app.run(debug=True)