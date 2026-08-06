from flask import Flask, render_template, request, session, redirect, url_for, flash
import os
import pandas as pd
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import IntegrityError
from extension import db
from models import User, Contact, Campaign
from email_service import send_email

app = Flask(__name__)

# Secret key for sessions
app.secret_key = "my_super_secret_key"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
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

    total_contacts = Contact.query.filter_by(
        created_by=session["user_id"]
    ).count()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total_contacts=total_contacts
    )

@app.route("/contacts", methods=["GET", "POST"])
def contacts():

    if "user_id" not in session:
        return redirect(url_for("login"))

    # When the user submits the form
    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]

        new_contact = Contact(
            name=name,
            email=email,
            created_by=session["user_id"]
        )

        try:
            db.session.add(new_contact)
            db.session.commit()

            return redirect(url_for("contacts"))

        except IntegrityError:
            db.session.rollback()
            return "❌ This email already exists."

    # Display all contacts
    contacts = Contact.query.filter_by(
        created_by=session["user_id"]
    ).all()

    return render_template(
        "contacts.html",
        contacts=contacts
    )

@app.route("/import_csv", methods=["POST"])
def import_csv():

    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Check if a file was uploaded
    if "csv_file" not in request.files:
        return "❌ No file selected."

    file = request.files["csv_file"]

    # Check if the filename is empty
    if file.filename == "":
        return "❌ Please choose a CSV file."

    # Save the uploaded file
    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    # Read the CSV
    # Read the CSV
    df = pd.read_csv(filepath)

    imported = 0
    duplicates = 0
    invalid = 0

    for _, row in df.iterrows():

        # Combine first and last name
        name = f"{row['First name']} {row['Last name']}".strip()

        email = str(row["Email"]).strip().lower()

        # Skip blank emails
        if email == "":
            invalid += 1
            continue

        # Check if this contact already exists for this user
        existing_contact = Contact.query.filter_by(
            email=email,
            created_by=session["user_id"]
        ).first()

        if existing_contact:
            duplicates += 1
            continue

        # Create a new contact
        contact = Contact(
            name=name,
            email=email,
            created_by=session["user_id"]
        )

        db.session.add(contact)
        imported += 1

    # Save all new contacts
    db.session.commit()

    print(f"✅ Imported: {imported}")
    print(f"⚠️ Duplicates skipped: {duplicates}")
    print(f"❌ Invalid rows: {invalid}")

    return redirect(url_for("contacts"))

@app.route("/delete_contact/<int:contact_id>")
def delete_contact(contact_id):

    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Find the contact that belongs to this user
    contact = Contact.query.filter_by(
        id=contact_id,
        created_by=session["user_id"]
    ).first()

    if contact:
        db.session.delete(contact)
        db.session.commit()

    return redirect(url_for("contacts"))

@app.route("/edit_contact/<int:contact_id>", methods=["GET", "POST"])
def edit_contact(contact_id):

    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Find the contact belonging to this user
    contact = Contact.query.filter_by(
        id=contact_id,
        created_by=session["user_id"]
    ).first()

    # If the contact doesn't exist
    if not contact:
        return "❌ Contact not found."

    # If the user submits the form
    if request.method == "POST":

        contact.name = request.form["name"]
        contact.email = request.form["email"]

        try:
            db.session.commit()
            return redirect(url_for("contacts"))

        except IntegrityError:
            db.session.rollback()
            return "❌ Email already exists."

    return render_template(
        "edit_contact.html",
        contact=contact
    )

@app.route("/campaigns", methods=["GET", "POST"])
def campaigns():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        subject = request.form["subject"]
        message = request.form["message"]

        new_campaign = Campaign(
            subject=subject,
            message=message,
            created_by=session["user_id"]
        )

        db.session.add(new_campaign)
        db.session.commit()

        return redirect(url_for("campaigns"))

    campaigns = Campaign.query.filter_by(
        created_by=session["user_id"]
    ).all()

    return render_template(
        "campaigns.html",
        campaigns=campaigns
    )

@app.route("/campaign/<int:campaign_id>")
def preview_campaign(campaign_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=session["user_id"]
    ).first_or_404()

    return render_template(
        "preview_campaign.html",
        campaign=campaign
    )

@app.route("/campaign/<int:campaign_id>/test")
def send_test_email(campaign_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=session["user_id"]
    ).first_or_404()

    send_email(
        subject=campaign.subject,
        body=campaign.message,
        recipient="officialfizzlefit@gmail.com"
    )

    return """
    <h2>✅ Test email sent successfully!</h2>
    <br>
    <a href="/campaigns">Back to Campaigns</a>
    """

@app.route("/campaign/<int:campaign_id>/send")
def send_campaign(campaign_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get the campaign
    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=session["user_id"]
    ).first_or_404()

    # Get all contacts for this user
    contacts = Contact.query.filter_by(
        created_by=session["user_id"]
    ).all()

    sent = 0
    failed = 0

    for contact in contacts:

        try:

            send_email(
                subject=campaign.subject,
                body=campaign.message,
                recipient=contact.email
            )

            sent += 1

        except Exception as e:

            print(f"Failed to send to {contact.email}")
            print(e)

            failed += 1

    flash(
        f"Campaign completed! Sent: {sent} | Failed: {failed}",
        "success"
    )

    return redirect(url_for("campaigns"))
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)