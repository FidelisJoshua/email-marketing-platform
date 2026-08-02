from flask import Flask, render_template, request, session, redirect, url_for
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import IntegrityError
from extension import db
from models import User, Contact

app = Flask(__name__)

# Secret key for sessions
app.secret_key = "my_super_secret_key"

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
bcrypt = Bcrypt(app)
db.init_app(app)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        new_user = User(
            name=name,
            email=email,
            password=hashed_password
        )

        try:
            db.session.add(new_user)
            db.session.commit()

            print("✅ User saved successfully!")
            print(f"Name: {name}")
            print(f"Email: {email}")

            return redirect(url_for("login"))

        except IntegrityError:
            db.session.rollback()
            return "❌ Email already exists."

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        # Find the user
        user = User.query.filter_by(email=email).first()

        if user:

            # Check password
            if bcrypt.check_password_hash(user.password, password):

                # Save user in session
                session["user_id"] = user.id
                session["user_name"] = user.name

                return redirect(url_for("dashboard"))

            else:
                return "❌ Incorrect password."

        else:
            return "❌ Email not found."

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        name=session["user_name"]
    )

@app.route("/contacts")
def contacts():

    if "user_id" not in session:
        return redirect(url_for("login"))

    contacts = Contact.query.filter_by(
        created_by=session["user_id"]
    ).all()

    return render_template(
        "contacts.html",
        contacts=contacts
    )

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)