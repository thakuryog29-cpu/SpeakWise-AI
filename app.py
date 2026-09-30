
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


app = Flask(__name__)

# Use an environment secret in real deployments.
# A temporary random key keeps local development working.
app.secret_key = os.getenv("SPEAKWISE_SECRET_KEY") or os.urandom(32)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SPEAKWISE_HTTPS", "0") == "1",
)

DATABASE = "speakwise.db"
QUESTIONS_FILE = "questions.json"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    db.commit()
    db.close()


# =========================================================
# QUESTIONS
# =========================================================

def load_questions():

    if not os.path.exists(QUESTIONS_FILE):
        return []

    try:

        with open(
            QUESTIONS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return []


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required():

    return "user_id" in session


# =========================================================
# HOME
# =========================================================

@app.route("/")
def index():

    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email or not password:

            flash("Please fill all fields.")

            return redirect(
                url_for("register")
            )

        if (
            len(name) > 100
            or len(email) > 254
            or len(password) > 128
        ):

            flash("Input is too long.")

            return redirect(
                url_for("register")
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters."
            )

            return redirect(
                url_for("register")
            )

        db = get_db()

        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:

            db.close()

            flash(
                "Email already registered."
            )

            return redirect(
                url_for("login")
            )

        hashed_password = generate_password_hash(
            password
        )

        db.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password
            )
        )

        db.commit()
        db.close()

        flash(
            "Registration successful. Please login."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if (
            len(email) > 254
            or len(password) > 128
        ):

            flash(
                "Invalid email or password."
            )

            return redirect(
                url_for("login")
            )

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        db.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]

            return redirect(
                url_for("dashboard")
            )

        flash(
            "Invalid email or password."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not login_required():

        return redirect(
            url_for("login")
        )

    questions = load_questions()

    return render_template(
        "dashboard.html",
        name=session.get("user_name"),
        question_count=len(questions)
    )


# =========================================================
# GRAMMAR
# =========================================================

@app.route("/grammar")
def grammar():

    if not login_required():

        return redirect(
            url_for("login")
        )

    return render_template(
        "grammar.html"
    )


# =========================================================
# SPEAKING PRACTICE
# =========================================================

@app.route("/speaking")
def speaking():

    if not login_required():

        return redirect(
            url_for("login")
        )

    return render_template(
        "speaking.html"
    )


# =========================================================
# MOCK TESTS
# =========================================================

@app.route("/mock-tests")
def mock_tests():

    if not login_required():

        return redirect(
            url_for("login")
        )

    return render_template(
        "mock_tests.html"
    )


# =========================================================
# QUESTIONS API
# =========================================================

@app.route("/api/questions")
def api_questions():

    if not login_required():

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    questions = load_questions()

    return jsonify(
        questions
    )


# =========================================================
# QUESTION COUNT
# =========================================================

@app.route("/api/question-count")
def question_count():

    questions = load_questions()

    return jsonify({
        "count": len(questions)
    })


# =========================================================
# USER API
# =========================================================

@app.route("/api/user")
def api_user():

    if not login_required():

        return jsonify({
            "success": False,
            "message": "Login required"
        }), 401

    return jsonify({
        "success": True,
        "id": session.get("user_id"),
        "name": session.get("user_name"),
        "email": session.get("user_email")
    })


# =========================================================
# AI GRAMMAR CORRECTION PAGE
# =========================================================

@app.route("/grammar-correction")
def grammar_correction():

    if not login_required():

        return redirect(
            url_for("login")
        )

    return render_template(
        "grammar_correction.html"
    )


# =========================================================
# AI GRAMMAR CORRECTION API
# =========================================================

@app.route(
    "/api/grammar-correction",
    methods=["POST"]
)
def api_grammar_correction():

    if not login_required():

        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request."
        }), 400

    sentence = data.get(
        "sentence",
        ""
    ).strip()

    if not sentence:

        return jsonify({
            "success": False,
            "message": "Please enter a sentence."
        }), 400

    if len(sentence) > 3000:

        return jsonify({
            "success": False,
            "message": (
                "Sentence is too long. "
                "Please keep it under 3000 characters."
            )
        }), 400

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:

        return jsonify({
            "success": False,
            "message": (
                "OPENAI_API_KEY is not configured."
            )
        }), 500

    if OpenAI is None:

        return jsonify({
            "success": False,
            "message": (
                "OpenAI package is not installed."
            )
        }), 500

    try:

        client = OpenAI(
            api_key=api_key
        )

        prompt = f"""
You are an English grammar teacher.

Analyze the following English sentence:

"{sentence}"

Return ONLY valid JSON.

Use exactly this structure:

{{
    "corrected_sentence": "correct sentence",
    "is_correct": true,
    "score": 90,
    "mistakes": [
        {{
            "mistake": "wrong part",
            "correction": "correct part",
            "explanation": "simple explanation"
        }}
    ],
    "grammar_explanation": "simple explanation",
    "better_version": "more natural sentence",
    "tips": [
        "tip 1",
        "tip 2"
    ]
}}

The score must be between 0 and 100.

Keep explanations simple for a beginner English learner.
"""

        response = client.responses.create(
            model="gpt-5",
            input=prompt,
            store=False
        )

        result_text = (
            response.output_text.strip()
        )

        result = json.loads(
            result_text
        )

        result["success"] = True

        return jsonify(
            result
        )

    except json.JSONDecodeError:

        return jsonify({
            "success": False,
            "message": (
                "AI returned an invalid response."
            )
        }), 500

    except Exception:

        app.logger.exception(
            "AI grammar correction failed"
        )

        return jsonify({
            "success": False,
            "message": (
                "The AI service is temporarily "
                "unavailable. Please try again later."
            )
        }), 500


# =========================================================
# AI SPEAKING ANALYSIS
# =========================================================

@app.route(
    "/api/speaking-analysis",
    methods=["POST"]
)
def api_speaking_analysis():

    if not login_required():

        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    data = request.get_json()

    if not data:

        return jsonify({
            "success": False,
            "message": "Invalid request."
        }), 400

    transcript = data.get(
        "transcript",
        ""
    ).strip()

    topic = data.get(
        "topic",
        "General English Speaking"
    ).strip()

    if not transcript:

        return jsonify({
            "success": False,
            "message": (
                "Please speak something first."
            )
        }), 400

    if (
        len(transcript) > 5000
        or len(topic) > 200
    ):

        return jsonify({
            "success": False,
            "message": "Input is too long."
        }), 400

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:

        return jsonify({
            "success": False,
            "message": (
                "OPENAI_API_KEY is not configured."
            )
        }), 500

    if OpenAI is None:

        return jsonify({
            "success": False,
            "message": (
                "OpenAI package is not installed."
            )
        }), 500

    try:

        client = OpenAI(
            api_key=api_key
        )

        prompt = f"""
You are an English speaking coach.

A student is practicing spoken English.

Topic:
"{topic}"

Student's spoken transcript:
"{transcript}"

Analyze the student's English speaking performance.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "overall_score": 78,

    "grammar_score": 75,

    "vocabulary_score": 80,

    "fluency_score": 76,

    "communication_score": 82,

    "grammar_mistakes": [
        {{
            "wrong": "wrong sentence or phrase",
            "correct": "correct sentence or phrase",
            "explanation": "simple explanation"
        }}
    ],

    "vocabulary_feedback":
        "Explain the vocabulary quality in simple English.",

    "fluency_feedback":
        "Explain fluency in simple English.",

    "communication_feedback":
        "Explain communication quality in simple English.",

    "better_version":
        "Rewrite the student's answer in more natural English while keeping the same meaning.",

    "strengths": [
        "strength 1",
        "strength 2"
    ],

    "improvements": [
        "improvement 1",
        "improvement 2",
        "improvement 3"
    ],

    "tips": [
        "tip 1",
        "tip 2",
        "tip 3"
    ]
}}

All scores must be between 0 and 100.

Do not judge the student's intelligence,
personality, or character.

Focus only on English speaking performance.

Keep feedback simple and useful for a beginner BCA student.
"""

        response = client.responses.create(
            model="gpt-5",
            input=prompt,
            store=False
        )

        result_text = (
            response.output_text.strip()
        )

        result = json.loads(
            result_text
        )

        result["success"] = True

        return jsonify(
            result
        )

    except json.JSONDecodeError:

        return jsonify({
            "success": False,
            "message": (
                "AI returned an invalid response."
            )
        }), 500

    except Exception:

        app.logger.exception(
            "AI speaking analysis failed"
        )

        return jsonify({
            "success": False,
            "message": (
                "The AI service is temporarily "
                "unavailable. Please try again later."
            )
        }), 500


# =========================================================
# VOCABULARY
# =========================================================

@app.route("/vocabulary")
def vocabulary():

    if not login_required():

        return redirect(
            url_for("login")
        )

    return render_template(
        "vocabulary.html"
    )


# =========================================================
# INTERVIEW
# =========================================================

@app.route("/interview")
def interview():

    if not login_required():

        return redirect(
            url_for("login")
        )

    return render_template(
        "interview.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return """
    <h1>404 - Page Not Found</h1>
    <p>The requested page does not exist.</p>
    <a href="/">Go Home</a>
    """, 404


@app.errorhandler(500)
def internal_error(error):

    return """
    <h1>500 - Internal Server Error</h1>
    <p>Something went wrong. Please return to the home page and try again.</p>
    <a href="/">Go Home</a>
    """, 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    questions = load_questions()

    print("=" * 50)
    print("SpeakWise AI Started")
    print("=" * 50)

    print("Questions Loaded:", len(questions))
    print("Question Bank Ready")
    print("Grammar Practice Ready")
    print("Speaking Practice Ready")
    print("Mock Tests Ready")
    print("AI Grammar Correction Ready")
    print("AI Speaking Analysis Ready")
    print("Login/Register Ready")

    print("=" * 50)
    print("Website: http://127.0.0.1:5000/")
    print("Network: http://10.95.9.135:5000/")
    print("=" * 50)

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )