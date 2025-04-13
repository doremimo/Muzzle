import sqlite3
import random
import csv
import os
from faker import Faker
from werkzeug.security import generate_password_hash
from datetime import datetime

# Initialize Faker
fake = Faker()

# Path to profile pics
PROFILE_PIC_DIR = "static/profilepics"
profile_pics = [f for f in os.listdir(PROFILE_PIC_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

# Constants
NUM_USERS = min(116, len(profile_pics))
password = "testpass"
hashed_password = generate_password_hash(password)

# Tag & field pools
dog_free_reasons = [
    "Allergic to dogs", "Prefer cats", "Fear of dogs", "Dogs too loud",
    "Bad past experience", "Love reptiles", "Travel too much", "Can't handle fur"
]
favorite_animals = ["Cat", "Snake", "Rabbit", "Parrot", "Turtle", "Lizard", "Ferret", "Guinea Pig"]
genders = ["Male", "Female", "Nonbinary", "Prefer not to say"]
sexualities = ["Straight", "Gay", "Bisexual", "Pansexual", "Asexual", "Prefer not to say"]
interests_pool = ["reading", "hiking", "gaming", "cooking", "traveling", "painting", "music", "photography"]

main_tag_pool = [
    "Fully Pet-Free", "Allergic to Everything", "No Bark Zone", "Reptile Roomie",
    "Bug Buddy", "My Pet’s a Vibe", "Plant Person"
]
extra_tags_pool = [
    "Neurodivergent", "Child-Free", "Creative at Heart", "Career-Focused",
    "Monogamous", "Open to ENM", "Just Looking for Friends", "Turtle Tenant", "Cat Companion"
]

# Store login credentials for testing
credentials = []

# Connect to the database
conn = sqlite3.connect("users.db")
c = conn.cursor()

# Generate Tokyo or random coordinates
def generate_location_coords():
    if random.random() < 0.7:  # 70% near Tokyo
        lat = round(random.uniform(35.65, 35.75), 6)
        lon = round(random.uniform(139.65, 139.75), 6)
    else:  # Farther cities
        lat = round(random.uniform(34.0, 36.5), 6)
        lon = round(random.uniform(135.0, 137.5), 6)
    return lat, lon

# Generate and insert users
for i in range(NUM_USERS):
    username = f"testuser{i+1:03}"
    email = f"{username}@example.com"
    display_name = fake.first_name()

    # Realistic birthday (18–50 years old)
    age = random.randint(18, 50)
    birth_year = datetime.now().year - age
    birthday = f"{birth_year}-{random.randint(1,12):02}-{random.randint(1,28):02}"

    favorite_animal = random.choice(favorite_animals)
    dog_free_reason = random.choice(dog_free_reasons)
    profile_pic = f"profilepics/{profile_pics[i % len(profile_pics)]}"
    gender = random.choice(genders)
    sexuality = random.choice(sexualities)
    show_gender = 1
    show_sexuality = 0
    interests = ", ".join(random.sample(interests_pool, k=random.randint(2, 4)))
    bio = fake.sentence(nb_words=12)
    lat, lon = generate_location_coords()
    location = fake.city()
    main_tag = random.choice(main_tag_pool)
    tags = random.sample(extra_tags_pool, k=random.randint(1, 3))
    tags_string = ",".join(tags)
    email_verified = 1
    last_login = datetime.now().isoformat()

    try:
        c.execute("""
            INSERT INTO users (
                username, email, password, display_name, birthday, location, favorite_animal,
                dog_free_reason, profile_pic, bio, gender, sexuality,
                show_sexuality, show_gender, interests,
                main_tag, tags, latitude, longitude,
                email_verified, last_login
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            username, email, hashed_password, display_name, birthday, location, favorite_animal,
            dog_free_reason, profile_pic, bio, gender, sexuality,
            show_sexuality, show_gender, interests,
            main_tag, tags_string, lat, lon,
            email_verified, last_login
        ))
        credentials.append([username, password])
    except sqlite3.IntegrityError:
        continue  # skip if username or email already exists

# Finalize and save
conn.commit()
conn.close()

# Delete old CSV if it exists
if os.path.exists("data/user_credentials.csv"):
    os.remove("data/user_credentials.csv")

# Save login credentials
os.makedirs("data", exist_ok=True)
with open("data/user_credentials.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["username", "password"])
    writer.writerows(credentials)

print("✅ Successfully created fake users.")
print("📄 Credentials saved to data/user_credentials.csv.")
