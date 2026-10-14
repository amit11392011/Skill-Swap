from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "skillswap.db"

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT DEFAULT '',
            location TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('offer', 'learn')),
            level TEXT DEFAULT 'Beginner',
            description TEXT DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        );
    """)
    conn.commit()

    # Demo users/skills for a fresh install
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        demo_users = [
            ("Aarav Sharma", "aarav@skillswap.demo", generate_password_hash("123456"), "Frontend developer who loves UI design.", "Lucknow"),
            ("Priya Singh", "priya@skillswap.demo", generate_password_hash("123456"), "Python learner and photography enthusiast.", "Prayagraj"),
            ("Rahul Verma", "rahul@skillswap.demo", generate_password_hash("123456"), "Java developer and public speaking mentor.", "Kanpur"),
        ]
        conn.executemany(
            "INSERT INTO users(name,email,password,bio,location) VALUES(?,?,?,?,?)",
            demo_users
        )
        ids = [r["id"] for r in conn.execute("SELECT id FROM users ORDER BY id").fetchall()]
        demo_skills = [
            (ids[0], "HTML & CSS", "offer", "Advanced", "Modern responsive UI development"),
            (ids[0], "Python", "offer", "Intermediate", "Flask and scripting"),
            (ids[0], "Graphic Design", "learn", "Beginner", "Want to learn visual design"),
            (ids[1], "Photography", "offer", "Advanced", "Portrait and mobile photography"),
            (ids[1], "Python", "learn", "Beginner", "Looking for a Python mentor"),
            (ids[2], "Java", "offer", "Advanced", "Core Java and OOP"),
            (ids[2], "Public Speaking", "offer", "Intermediate", "Interview and presentation practice"),
            (ids[2], "React", "learn", "Beginner", "Want to learn React basics"),
        ]
        conn.executemany(
            "INSERT INTO skills(user_id,name,type,level,description) VALUES(?,?,?,?,?)",
            demo_skills
        )
        conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": session.get("user_name")}


@app.route("/")
def index():
    conn = get_db()
    stats = {
        "users": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "skills": conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
        "offers": conn.execute("SELECT COUNT(*) FROM skills WHERE type='offer'").fetchone()[0],
    }
    latest = conn.execute("""
        SELECT skills.*, users.name, users.location
        FROM skills JOIN users ON users.id = skills.user_id
        ORDER BY skills.id DESC LIMIT 6
    """).fetchall()
    conn.close()
    return render_template("index.html", stats=stats, latest=latest)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or len(password) < 6:
            flash("Please enter valid details. Password must be at least 6 characters.", "error")
            return redirect(url_for("register"))

        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            session["user_id"] = cur.lastrowid
            session["user_name"] = name
            flash("Account created successfully!", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("Email is already registered.", "error")
            return redirect(url_for("register"))
        finally:
            conn.close()

    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    uid = session["user_id"]

    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    my_skills = conn.execute(
        "SELECT * FROM skills WHERE user_id=? ORDER BY id DESC", (uid,)
    ).fetchall()

    # Matching logic:
    # My learning skills are matched against another user's offered skills.
    matches = conn.execute("""
        SELECT DISTINCT u.id, u.name, u.location, u.bio, s.name AS skill_name, s.level
        FROM skills mine
        JOIN skills s ON LOWER(s.name)=LOWER(mine.name)
        JOIN users u ON u.id=s.user_id
        WHERE mine.user_id=? AND mine.type='learn'
          AND s.type='offer' AND s.user_id != ?
        ORDER BY s.id DESC
        LIMIT 8
    """, (uid, uid)).fetchall()

    conn.close()
    return render_template("dashboard.html", user=user, my_skills=my_skills, matches=matches)


@app.route("/skills", methods=["GET", "POST"])
@login_required
def skills():
    if request.method == "POST":
        name = request.form["name"].strip()
        skill_type = request.form["type"]
        level = request.form["level"]
        description = request.form.get("description", "").strip()

        if name and skill_type in ("offer", "learn"):
            conn = get_db()
            conn.execute(
                "INSERT INTO skills(user_id,name,type,level,description) VALUES(?,?,?,?,?)",
                (session["user_id"], name, skill_type, level, description)
            )
            conn.commit()
            conn.close()
            flash("Skill added!", "success")
        return redirect(url_for("skills"))

    q = request.args.get("q", "").strip()
    conn = get_db()
    if q:
        all_skills = conn.execute("""
            SELECT skills.*, users.name, users.location, users.id AS owner_id
            FROM skills JOIN users ON users.id=skills.user_id
            WHERE skills.name LIKE ? OR skills.description LIKE ?
            ORDER BY skills.id DESC
        """, (f"%{q}%", f"%{q}%")).fetchall()
    else:
        all_skills = conn.execute("""
            SELECT skills.*, users.name, users.location, users.id AS owner_id
            FROM skills JOIN users ON users.id=skills.user_id
            ORDER BY skills.id DESC
        """).fetchall()
    conn.close()
    return render_template("skills.html", skills=all_skills, q=q)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid = session["user_id"]
    conn = get_db()

    if request.method == "POST":
        name = request.form["name"].strip()
        bio = request.form.get("bio", "").strip()
        location = request.form.get("location", "").strip()
        conn.execute(
            "UPDATE users SET name=?, bio=?, location=? WHERE id=?",
            (name, bio, location, uid)
        )
        conn.commit()
        session["user_name"] = name
        flash("Profile updated.", "success")

    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    skill_count = conn.execute("SELECT COUNT(*) FROM skills WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()
    return render_template("profile.html", user=user, skill_count=skill_count)


@app.route("/message/<int:receiver_id>", methods=["POST"])
@login_required
def send_message(receiver_id):
    msg = request.form.get("message", "").strip()
    if msg:
        conn = get_db()
        conn.execute(
            "INSERT INTO messages(sender_id,receiver_id,message) VALUES(?,?,?)",
            (session["user_id"], receiver_id, msg)
        )
        conn.commit()
        conn.close()
        flash("Message sent.", "success")
    return redirect(request.referrer or url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
