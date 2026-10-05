import os
import time
from datetime import datetime, timezone
from itsdangerous import URLSafeTimedSerializer

import pandas as pd
from itsdangerous import URLSafeSerializer
from flask import Flask, render_template, request, session, redirect, url_for, flash
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text, inspect
from flask_bcrypt import Bcrypt
from sqlalchemy.exc import IntegrityError

from extension import db
from models import (
    User,
    Contact,
    Campaign,
    CampaignRecipient,
    Form,
    LandingPage,
    LandingPageTemplate,
    Template,
    EmailSettings
)
from email_service import (
    test_smtp_connection,
    send_email
)

# =========================================================
# APP CONFIGURATION

app = Flask(__name__)

app.secret_key = "my_super_secret_key"

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
def create_unsubscribe_token(contact_id):
    serializer = URLSafeSerializer(
        app.secret_key,
        salt="emailflow-unsubscribe"
    )

    return serializer.dumps({
        "contact_id": contact_id
    })


# =========================================================
# INITIALIZE EXTENSIONS
# =========================================================

bcrypt = Bcrypt(app)

db.init_app(app)
# =========================================================
# EMAIL VERIFICATION TOKEN
# =========================================================

def create_email_verification_token(user_id):

    serializer = URLSafeTimedSerializer(
        app.secret_key
    )

    return serializer.dumps(
        {
            "user_id": user_id
        },
        salt="emailflow-email-verification"
    )

def create_password_reset_token(user_id):

    serializer = URLSafeTimedSerializer(
        app.secret_key
    )

    return serializer.dumps(
        {
            "user_id": user_id
        },
        salt="emailflow-password-reset"
    )

@app.context_processor
def inject_current_user():

    user = None

    if "user_id" in session:

        user = db.session.get(
            User,
            session["user_id"]
        )

    return {
        "current_user": user
    }

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        if not name or not email or not password:

            flash(
                "All fields are required.",
                "warning"
            )

            return redirect(
                url_for("register")
            )

        hashed_password = (
            bcrypt
            .generate_password_hash(password)
            .decode("utf-8")
        )

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            email_verified=False
        )

        try:

            # =====================================================
            # SAVE USER
            # =====================================================

            db.session.add(new_user)

            db.session.commit()

            print("✅ User saved successfully!")

            print(f"Name: {name}")

            print(f"Email: {email}")


            # =====================================================
            # CREATE EMAIL VERIFICATION TOKEN
            # =====================================================

            verification_token = create_email_verification_token(
                new_user.id
            )


            # =====================================================
            # CREATE VERIFICATION LINK
            # =====================================================

            verification_link = url_for(
                "verify_email",
                token=verification_token,
                _external=True
            )


            # =====================================================
            # CREATE VERIFICATION EMAIL
            # =====================================================

            verification_email = f"""
            <!DOCTYPE html>

            <html>

            <head>

                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width, initial-scale=1.0"
                >

            </head>


            <body
                style="
                    margin:0;
                    padding:40px 20px;
                    background:#f5f7fb;
                    font-family:Arial, Helvetica, sans-serif;
                "
            >

                <div
                    style="
                        max-width:600px;
                        margin:0 auto;
                        background:white;
                        padding:40px;
                        border-radius:12px;
                        box-shadow:0 5px 20px rgba(0,0,0,0.08);
                    "
                >

                    <h1
                        style="
                            color:#4f46e5;
                            margin-top:0;
                        "
                    >
                        EmailFlow
                    </h1>


                    <h2>
                        Verify your email address
                    </h2>


                    <p
                        style="
                            color:#4b5563;
                            line-height:1.7;
                        "
                    >
                        Hi {new_user.name},
                    </p>


                    <p
                        style="
                            color:#4b5563;
                            line-height:1.7;
                        "
                    >
                        Thank you for creating an EmailFlow account.

                        Please click the button below to verify
                        your email address.
                    </p>


                    <p
                        style="
                            text-align:center;
                            margin:35px 0;
                        "
                    >

                        <a
                            href="{verification_link}"
                            style="
                                display:inline-block;
                                padding:14px 25px;
                                background:#4f46e5;
                                color:white;
                                text-decoration:none;
                                border-radius:8px;
                                font-weight:bold;
                            "
                        >
                            Verify My Email
                        </a>

                    </p>


                    <p
                        style="
                            color:#6b7280;
                            font-size:14px;
                            line-height:1.6;
                        "
                    >
                        If you did not create an EmailFlow account,
                        you can safely ignore this email.
                    </p>

                </div>

            </body>

            </html>
            """


            # =====================================================
            # SEND VERIFICATION EMAIL
            #
            # Uses EmailFlow's Gmail SMTP account.
            # This does NOT use the new user's EmailSettings.
            # =====================================================

            try:

                smtp_host = os.getenv(
                    "EMAILFLOW_SMTP_HOST"
                )

                smtp_port = os.getenv(
                    "EMAILFLOW_SMTP_PORT",
                    "465"
                )

                smtp_username = os.getenv(
                    "EMAILFLOW_SMTP_USERNAME"
                )

                smtp_password = os.getenv(
                    "EMAILFLOW_SMTP_PASSWORD"
                )

                smtp_encryption = os.getenv(
                    "EMAILFLOW_SMTP_ENCRYPTION",
                    "SSL"
                )

                sender_name = os.getenv(
                    "EMAILFLOW_SENDER_NAME",
                    "EmailFlow"
                )

                sender_email = os.getenv(
                    "EMAILFLOW_SENDER_EMAIL"
                )


                success, message = send_email(

                    smtp_host=smtp_host,

                    smtp_port=smtp_port,

                    smtp_username=smtp_username,

                    smtp_password=smtp_password,

                    smtp_encryption=smtp_encryption,

                    sender_name=sender_name,

                    sender_email=sender_email,

                    recipient_email=new_user.email,

                    subject=(
                        "Verify your EmailFlow email address"
                    ),

                    body=verification_email
                )


                if success:

                    print(
                        f"📧 Verification email sent to "
                        f"{new_user.email}"
                    )

                else:

                    print(
                        f"❌ Verification email failed: "
                        f"{message}"
                    )


            except Exception as e:

                print(
                    f"❌ Could not send verification email: "
                    f"{e}"
                )


            # =====================================================
            # REGISTRATION SUCCESS
            # =====================================================

            flash(
                "Account created! Please check your email and "
                "click the verification link before logging in.",
                "success"
            )

            return redirect(
                url_for("login")
            )


        # =========================================================
        # DUPLICATE EMAIL
        # =========================================================

        except IntegrityError:

            db.session.rollback()

            flash(
                "An account with this email already exists.",
                "warning"
            )

            return redirect(
                url_for("register")
            )


    # =============================================================
    # SHOW REGISTRATION PAGE
    # =============================================================

    return render_template(
        "register.html"
    )
# =========================================================
# LOGIN
# =========================================================

# =========================================================
# VERIFY EMAIL
# =========================================================

@app.route(
    "/verify-email/<token>"
)
def verify_email(token):

    serializer = URLSafeTimedSerializer(
        app.secret_key
    )

    try:

        data = serializer.loads(
            token,
            salt="emailflow-email-verification",
            max_age=3600
        )

    except Exception:

        return render_template(
            "verify_email.html",
            error=(
                "This verification link is invalid "
                "or has expired."
            )
        )

    user_id = data.get("user_id")

    if not user_id:

        return render_template(
            "verify_email.html",
            error="This verification link is invalid."
        )

    user = db.session.get(
        User,
        user_id
    )

    if not user:

        return render_template(
            "verify_email.html",
            error="We could not find this account."
        )

    if user.email_verified:

        return render_template(
            "verify_email.html",
            already_verified=True,
            user=user
        )

    user.email_verified = True

    user.email_verified_at = datetime.now(
        timezone.utc
    )

    db.session.commit()

    return render_template(
        "verify_email.html",
        success=True,
        user=user
    )

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )

        password = request.form.get("password", "")

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:

            flash(
                "Email not found.",
                "danger"
            )

            return redirect(url_for("login"))

        if not bcrypt.check_password_hash(
            user.password,
            password
        ):

            flash(
                "Incorrect password.",
                "danger"
            )

            return redirect(url_for("login"))

        if not user.email_verified:
            flash(
                "Please verify your email address before logging in.",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        session["user_id"] = user.id
        session["user_name"] = user.name
        session["user_email"] = user.email

        return redirect(url_for("dashboard"))

    return render_template("login.html")

# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = (
            request.form
            .get("email", "")
            .strip()
            .lower()
        )

        if not email:

            flash(
                "Please enter your email address.",
                "warning"
            )

            return redirect(
                url_for("forgot_password")
            )

        user = User.query.filter_by(
            email=email
        ).first()

        # -----------------------------------------------------
        # SECURITY:
        # Do not reveal whether an email exists.
        # -----------------------------------------------------

        if user:

            reset_token = create_password_reset_token(
                user.id
            )

            reset_link = url_for(
                "reset_password",
                token=reset_token,
                _external=True
            )

            reset_email = f"""
            <!DOCTYPE html>

            <html>

            <head>

                <meta charset="UTF-8">

                <meta
                    name="viewport"
                    content="width=device-width, initial-scale=1.0"
                >

            </head>

            <body
                style="
                    margin:0;
                    padding:40px 20px;
                    background:#f5f7fb;
                    font-family:Arial, Helvetica, sans-serif;
                "
            >

                <div
                    style="
                        max-width:600px;
                        margin:0 auto;
                        background:white;
                        padding:40px;
                        border-radius:12px;
                        box-shadow:0 5px 20px rgba(0,0,0,0.08);
                    "
                >

                    <h1
                        style="
                            color:#4f46e5;
                            margin-top:0;
                        "
                    >
                        EmailFlow
                    </h1>

                    <h2>
                        Reset your password
                    </h2>

                    <p
                        style="
                            color:#4b5563;
                            line-height:1.7;
                        "
                    >
                        Hi {user.name},
                    </p>

                    <p
                        style="
                            color:#4b5563;
                            line-height:1.7;
                        "
                    >
                        We received a request to reset the password
                        for your EmailFlow account.
                    </p>

                    <p
                        style="
                            text-align:center;
                            margin:35px 0;
                        "
                    >

                        <a
                            href="{reset_link}"
                            style="
                                display:inline-block;
                                padding:14px 25px;
                                background:#4f46e5;
                                color:white;
                                text-decoration:none;
                                border-radius:8px;
                                font-weight:bold;
                            "
                        >
                            Reset My Password
                        </a>

                    </p>

                    <p
                        style="
                            color:#6b7280;
                            font-size:14px;
                            line-height:1.6;
                        "
                    >
                        This password reset link will expire in
                        1 hour.
                    </p>

                    <p
                        style="
                            color:#6b7280;
                            font-size:14px;
                            line-height:1.6;
                        "
                    >
                        If you did not request a password reset,
                        you can safely ignore this email.
                    </p>

                </div>

            </body>

            </html>
            """

            # =================================================
            # EMAILFLOW SYSTEM SMTP
            # =================================================

            try:

                smtp_host = os.getenv(
                    "EMAILFLOW_SMTP_HOST"
                )

                smtp_port = os.getenv(
                    "EMAILFLOW_SMTP_PORT",
                    "465"
                )

                smtp_username = os.getenv(
                    "EMAILFLOW_SMTP_USERNAME"
                )

                smtp_password = os.getenv(
                    "EMAILFLOW_SMTP_PASSWORD"
                )

                smtp_encryption = os.getenv(
                    "EMAILFLOW_SMTP_ENCRYPTION",
                    "SSL"
                )

                sender_name = os.getenv(
                    "EMAILFLOW_SENDER_NAME",
                    "EmailFlow"
                )

                sender_email = os.getenv(
                    "EMAILFLOW_SENDER_EMAIL"
                )

                success, message = send_email(

                    smtp_host=smtp_host,

                    smtp_port=smtp_port,

                    smtp_username=smtp_username,

                    smtp_password=smtp_password,

                    smtp_encryption=smtp_encryption,

                    sender_name=sender_name,

                    sender_email=sender_email,

                    recipient_email=user.email,

                    subject="Reset your EmailFlow password",

                    body=reset_email
                )

                if success:

                    print(
                        f"📧 Password reset email sent to "
                        f"{user.email}"
                    )

                else:

                    print(
                        f"❌ Password reset email failed: "
                        f"{message}"
                    )

            except Exception as e:

                print(
                    f"❌ Could not send password reset email: "
                    f"{e}"
                )

        # -----------------------------------------------------
        # Always show the same message
        # -----------------------------------------------------

        flash(
            "If an account exists for that email address, "
            "we have sent a password reset link.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "forgot_password.html"
    )

# =========================================================
# RESET PASSWORD
# =========================================================

@app.route(
    "/reset-password/<token>",
    methods=["GET", "POST"]
)
def reset_password(token):

    serializer = URLSafeTimedSerializer(
        app.secret_key
    )

    try:

        data = serializer.loads(
            token,
            salt="emailflow-password-reset",
            max_age=3600
        )

    except Exception:

        return render_template(
            "reset_password.html",
            error=(
                "This password reset link is invalid "
                "or has expired."
            )
        )

    user_id = data.get("user_id")

    if not user_id:

        return render_template(
            "reset_password.html",
            error="This password reset link is invalid."
        )

    user = db.session.get(
        User,
        user_id
    )

    if not user:

        return render_template(
            "reset_password.html",
            error="We could not find this account."
        )

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not password or not confirm_password:

            return render_template(
                "reset_password.html",
                error="Both password fields are required.",
                token=token
            )

        if password != confirm_password:

            return render_template(
                "reset_password.html",
                error="The passwords do not match.",
                token=token
            )

        if len(password) < 8:

            return render_template(
                "reset_password.html",
                error=(
                    "Your password must be at least "
                    "8 characters long."
                ),
                token=token
            )

        # =====================================================
        # HASH NEW PASSWORD
        # =====================================================

        user.password = (
            bcrypt
            .generate_password_hash(password)
            .decode("utf-8")
        )

        db.session.commit()

        return render_template(
            "reset_password.html",
            success=True
        )

    return render_template(
        "reset_password.html",
        token=token
    )

# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    total_contacts = Contact.query.filter_by(
        created_by=user_id
    ).count()

    total_campaigns = Campaign.query.filter_by(
        created_by=user_id
    ).count()

    total_forms = Form.query.filter_by(
        created_by=user_id
    ).count()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        total_contacts=total_contacts,
        total_campaigns=total_campaigns,
        total_forms=total_forms
    )

# =========================================================
# CONTACTS
# =========================================================

@app.route("/contacts", methods=["GET", "POST"])
def contacts():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    # -----------------------------------------------------
    # ADD CONTACT FROM CONTACTS PAGE
    # -----------------------------------------------------

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not name or not email:

            flash(
                "Name and email are required.",
                "warning"
            )

            return redirect(url_for("contacts"))

        existing_contact = Contact.query.filter_by(
            email=email,
            created_by=user_id
        ).first()

        if existing_contact:

            flash(
                "This email already exists in your contacts.",
                "warning"
            )

            return redirect(url_for("contacts"))

        new_contact = Contact(
            name=name,
            email=email,
            created_by=user_id
        )

        try:

            db.session.add(new_contact)

            db.session.commit()

            flash(
                "Contact added successfully.",
                "success"
            )

        except IntegrityError:

            db.session.rollback()

            flash(
                "This email already exists in your contacts.",
                "warning"
            )

        return redirect(url_for("contacts"))

    # -----------------------------------------------------
    # DISPLAY CONTACTS
    # -----------------------------------------------------

    contact_list = Contact.query.filter_by(
        created_by=user_id
    ).order_by(
        Contact.id.desc()
    ).all()

    return render_template(
        "contacts.html",
        contacts=contact_list
    )


# =========================================================
# ADD CONTACT
# =========================================================

@app.route("/contacts/add", methods=["GET", "POST"])
def add_contact():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not name or not email:

            flash(
                "Name and email are required.",
                "warning"
            )

            return redirect(
                url_for("add_contact")
            )

        existing_contact = Contact.query.filter_by(
            email=email,
            created_by=user_id
        ).first()

        if existing_contact:

            flash(
                "This email already exists in your contacts.",
                "warning"
            )

            return redirect(
                url_for("add_contact")
            )

        contact = Contact(
            name=name,
            email=email,
            created_by=user_id
        )

        try:

            db.session.add(contact)

            db.session.commit()

            flash(
                "Contact added successfully.",
                "success"
            )

            return redirect(
                url_for("contacts")
            )

        except IntegrityError:

            db.session.rollback()

            flash(
                "This email already exists in your contacts.",
                "warning"
            )

            return redirect(
                url_for("add_contact")
            )

    return render_template(
        "add_contact.html"
    )


# =========================================================
# IMPORT CSV
# =========================================================

@app.route("/import_csv", methods=["POST"])
def import_csv():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    # -----------------------------------------------------
    # CHECK FILE
    # -----------------------------------------------------

    if "csv_file" not in request.files:

        flash(
            "No CSV file was selected.",
            "warning"
        )

        return redirect(url_for("contacts"))

    file = request.files["csv_file"]

    if file.filename == "":

        flash(
            "Please choose a CSV file.",
            "warning"
        )

        return redirect(url_for("contacts"))

    if not file.filename.lower().endswith(".csv"):

        flash(
            "Please upload a CSV file.",
            "warning"
        )

        return redirect(url_for("contacts"))

    # -----------------------------------------------------
    # CREATE UPLOAD FOLDER
    # -----------------------------------------------------

    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True
    )

    # -----------------------------------------------------
    # SAVE FILE
    # -----------------------------------------------------

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    # -----------------------------------------------------
    # READ CSV
    # -----------------------------------------------------

    try:

        df = pd.read_csv(
            filepath,
            dtype=str
        )

    except Exception as e:

        flash(
            f"Could not read the CSV file: {e}",
            "danger"
        )

        return redirect(url_for("contacts"))

    # -----------------------------------------------------
    # CLEAN COLUMN NAMES
    # -----------------------------------------------------

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # -----------------------------------------------------
    # FIND EMAIL COLUMN
    # -----------------------------------------------------

    email_column = None

    possible_email_columns = [
        "email",
        "email address",
        "email_address",
        "e-mail",
        "e-mail address"
    ]

    for column in possible_email_columns:

        if column in df.columns:

            email_column = column

            break

    if email_column is None:

        flash(
            "No email column was found. "
            "Your CSV must contain an Email column.",
            "danger"
        )

        try:
            os.remove(filepath)
        except OSError:
            pass

        return redirect(url_for("contacts"))

    # -----------------------------------------------------
    # FIND NAME COLUMNS
    # -----------------------------------------------------

    first_name_column = None

    last_name_column = None

    name_column = None

    possible_first_names = [
        "first name",
        "firstname",
        "first_name"
    ]

    possible_last_names = [
        "last name",
        "lastname",
        "last_name"
    ]

    possible_name_columns = [
        "name",
        "full name",
        "full_name"
    ]

    for column in possible_first_names:

        if column in df.columns:

            first_name_column = column

            break

    for column in possible_last_names:

        if column in df.columns:

            last_name_column = column

            break

    for column in possible_name_columns:

        if column in df.columns:

            name_column = column

            break

    # -----------------------------------------------------
    # COUNTERS
    # -----------------------------------------------------

    imported = 0

    duplicates = 0

    invalid = 0

    blank_rows = 0

    # -----------------------------------------------------
    # PROCESS CSV
    # -----------------------------------------------------

    for _, row in df.iterrows():

        raw_email = row.get(
            email_column,
            ""
        )

        if pd.isna(raw_email):

            email = ""

        else:

            email = str(
                raw_email
            ).strip().lower()

        # -------------------------------------------------
        # BLANK EMAIL
        # -------------------------------------------------

        if not email:

            blank_rows += 1

            continue

        # -------------------------------------------------
        # BASIC EMAIL VALIDATION
        # -------------------------------------------------

        if (
            "@" not in email
            or "." not in email.rsplit("@", 1)[-1]
        ):

            invalid += 1

            continue

        # -------------------------------------------------
        # GET NAME
        # -------------------------------------------------

        name = ""

        # FULL NAME

        if name_column:

            value = row.get(
                name_column,
                ""
            )

            if not pd.isna(value):

                name = str(
                    value
                ).strip()

        # FIRST + LAST NAME

        else:

            first_name = ""

            last_name = ""

            if first_name_column:

                value = row.get(
                    first_name_column,
                    ""
                )

                if not pd.isna(value):

                    first_name = str(
                        value
                    ).strip()

            if last_name_column:

                value = row.get(
                    last_name_column,
                    ""
                )

                if not pd.isna(value):

                    last_name = str(
                        value
                    ).strip()

            name = (
                f"{first_name} {last_name}"
                .strip()
            )

        # -------------------------------------------------
        # DEFAULT NAME
        # -------------------------------------------------

        if not name:

            name = email.split("@")[0]

        # -------------------------------------------------
        # CHECK DUPLICATE
        # -------------------------------------------------

        existing_contact = Contact.query.filter_by(
            email=email,
            created_by=user_id
        ).first()

        if existing_contact:

            duplicates += 1

            continue

        # -------------------------------------------------
        # CREATE CONTACT
        # -------------------------------------------------

        contact = Contact(
            name=name,
            email=email,
            created_by=user_id
        )

        db.session.add(contact)

        imported += 1

    # -----------------------------------------------------
    # COMMIT
    # -----------------------------------------------------

    try:

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        flash(
            f"An error occurred while importing contacts: {e}",
            "danger"
        )

        return redirect(url_for("contacts"))

    # -----------------------------------------------------
    # DELETE TEMP FILE
    # -----------------------------------------------------

    try:

        os.remove(filepath)

    except OSError:

        pass

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    flash(
        f"Import completed! "
        f"Imported: {imported} | "
        f"Duplicates: {duplicates} | "
        f"Invalid: {invalid} | "
        f"Blank: {blank_rows}",
        "success"
    )

    return redirect(
        url_for("contacts")
    )


# =========================================================
# DELETE CONTACT
# =========================================================

@app.route("/delete_contact/<int:contact_id>")
def delete_contact(contact_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    contact = Contact.query.filter_by(
        id=contact_id,
        created_by=user_id
    ).first()

    if contact:

        CampaignRecipient.query.filter_by(
            contact_id=contact.id
        ).delete()

        db.session.delete(contact)

        db.session.commit()

        flash(
            "Contact deleted successfully.",
            "success"
        )

    return redirect(
        url_for("contacts")
    )


# =========================================================
# BULK DELETE CONTACTS
# =========================================================

@app.route(
    "/bulk_delete_contacts",
    methods=["POST"]
)
def bulk_delete_contacts():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    contact_ids = request.form.getlist(
        "contact_ids"
    )

    if not contact_ids:

        flash(
            "No contacts selected.",
            "warning"
        )

        return redirect(
            url_for("contacts")
        )

    contacts_to_delete = Contact.query.filter(
        Contact.id.in_(contact_ids),
        Contact.created_by == user_id
    ).all()

    deleted = 0

    for contact in contacts_to_delete:

        CampaignRecipient.query.filter_by(
            contact_id=contact.id
        ).delete()

        db.session.delete(contact)

        deleted += 1

    db.session.commit()

    flash(
        f"{deleted} contact(s) deleted successfully.",
        "success"
    )

    return redirect(
        url_for("contacts")
    )


# =========================================================
# EDIT CONTACT
# =========================================================

@app.route(
    "/edit_contact/<int:contact_id>",
    methods=["GET", "POST"]
)
def edit_contact(contact_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    contact = Contact.query.filter_by(
        id=contact_id,
        created_by=user_id
    ).first()

    if not contact:

        flash(
            "Contact not found.",
            "danger"
        )

        return redirect(
            url_for("contacts")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        if not name or not email:

            flash(
                "Name and email are required.",
                "warning"
            )

            return redirect(
                url_for(
                    "edit_contact",
                    contact_id=contact.id
                )
            )

        # Check if another contact already uses email

        existing_contact = Contact.query.filter(
            Contact.email == email,
            Contact.created_by == user_id,
            Contact.id != contact.id
        ).first()

        if existing_contact:

            flash(
                "Another contact already uses this email.",
                "warning"
            )

            return redirect(
                url_for(
                    "edit_contact",
                    contact_id=contact.id
                )
            )

        contact.name = name

        contact.email = email

        try:

            db.session.commit()

            flash(
                "Contact updated successfully.",
                "success"
            )

            return redirect(
                url_for("contacts")
            )

        except IntegrityError:

            db.session.rollback()

            flash(
                "Email already exists.",
                "warning"
            )

            return redirect(
                url_for(
                    "edit_contact",
                    contact_id=contact.id
                )
            )

    return render_template(
        "edit_contact.html",
        contact=contact
    )


# =========================================================
# CAMPAIGNS
# =========================================================

# =========================================================
# CAMPAIGNS - STARTING POINTS
# =========================================================

@app.route("/campaigns")
def campaigns():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]


    # -----------------------------------------------------
    # GET AVAILABLE CAMPAIGN TEMPLATES
    # -----------------------------------------------------

    template_list = Template.query.filter(
        (Template.is_system_template.is_(True)) |
        (Template.created_by == user_id)
    ).order_by(
        Template.is_system_template.desc(),
        Template.created_at.desc()
    ).all()


    # -----------------------------------------------------
    # GET EXISTING CAMPAIGNS
    # -----------------------------------------------------

    campaign_list = Campaign.query.filter_by(
        created_by=user_id
    ).order_by(
        Campaign.created_at.desc()
    ).all()


    return render_template(
        "campaigns.html",
        templates=template_list,
        campaigns=campaign_list
    )


# =========================================================
# CREATE CAMPAIGN - EDITOR
# =========================================================

@app.route(
    "/campaigns/create",
    methods=["GET", "POST"]
)
def create_campaign():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]


    # =====================================================
    # POST - SAVE CAMPAIGN
    # =====================================================

    if request.method == "POST":

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()


        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not subject:

            flash(
                "Please enter a subject line.",
                "warning"
            )

            return redirect(
                url_for("create_campaign")
            )


        if not message:

            flash(
                "Please enter your email message.",
                "warning"
            )

            return redirect(
                url_for("create_campaign")
            )


        # -------------------------------------------------
        # CREATE CAMPAIGN
        # -------------------------------------------------

        new_campaign = Campaign(
            subject=subject,
            message=message,
            created_by=user_id
        )

        db.session.add(
            new_campaign
        )


        # Commit so campaign receives its ID

        db.session.commit()


        # -------------------------------------------------
        # CREATE CAMPAIGN RECIPIENTS
        # -------------------------------------------------

        contacts_for_campaign = Contact.query.filter_by(
            created_by=user_id
        ).all()


        for contact in contacts_for_campaign:

            recipient = CampaignRecipient(
                campaign_id=new_campaign.id,
                contact_id=contact.id,
                status="Pending"
            )

            db.session.add(
                recipient
            )


        db.session.commit()


        flash(
            "Campaign created successfully.",
            "success"
        )


        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=new_campaign.id
            )
        )


    # =====================================================
    # GET - OPEN CAMPAIGN EDITOR
    # =====================================================

    template_id = request.args.get(
        "template_id",
        type=int
    )


    selected_template = None


    if template_id:

        selected_template = Template.query.filter_by(
            id=template_id
        ).first()


        # Make sure a user cannot use
        # another user's private template

        if (
            selected_template
            and not selected_template.is_system_template
            and selected_template.created_by != user_id
        ):

            selected_template = None


    return render_template(
        "campaign_editor.html",
        template=selected_template
    )
# =========================================================
# PREVIEW CAMPAIGN
# =========================================================

@app.route(
    "/campaign/<int:campaign_id>"
)
def preview_campaign(campaign_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user = User.query.get_or_404(
        session["user_id"]
    )

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=session["user_id"]
    ).first_or_404()

    return render_template(
        "preview_campaign.html",
        campaign=campaign,
        user=user
    )

# =========================================================
# SEND TEST EMAIL
# =========================================================

@app.route(
    "/campaign/<int:campaign_id>/test",
    methods=["POST"]
)
def send_test_email(campaign_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]


    # =====================================================
    # GET CAMPAIGN
    # =====================================================

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=user_id
    ).first_or_404()


    # =====================================================
    # GET CURRENT USER
    # =====================================================

    user = User.query.get_or_404(
        user_id
    )


    # =====================================================
    # GET TEST EMAIL ADDRESS
    # =====================================================

    test_email = request.form.get(
        "test_email",
        ""
    ).strip().lower()


    # =====================================================
    # DEFAULT TO REGISTERED EMAIL
    # =====================================================

    if not test_email:

        test_email = user.email


    # =====================================================
    # BASIC EMAIL VALIDATION
    # =====================================================

    if "@" not in test_email:

        flash(
            "Please enter a valid email address.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    # =====================================================
    # GET EMAIL SETTINGS
    # =====================================================

    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()


    if not email_settings:

        flash(
            "Please configure your Email & Sending settings first.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    # =====================================================
    # CHECK SMTP SETTINGS
    # =====================================================

    if not email_settings.smtp_host:

        flash(
            "Please configure your SMTP host before sending a test email.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    if not email_settings.smtp_username:

        flash(
            "Please configure your SMTP username before sending a test email.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    if not email_settings.smtp_password:

        flash(
            "Please configure your SMTP password before sending a test email.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    if not email_settings.sender_email:

        flash(
            "Please configure your sender email before sending a test email.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    # =====================================================
    # SEND TEST EMAIL
    # =====================================================

    try:

        success, message = send_email(

            smtp_host=email_settings.smtp_host,

            smtp_port=email_settings.smtp_port,

            smtp_username=email_settings.smtp_username,

            smtp_password=email_settings.smtp_password,

            smtp_encryption=email_settings.smtp_encryption,

            sender_name=email_settings.sender_name,

            sender_email=email_settings.sender_email,

            recipient_email=test_email,

            subject=campaign.subject,

            body=campaign.message,

            reply_to_email=email_settings.reply_to_email
        )


        # =================================================
        # CHECK RESULT
        # =================================================

        if not success:

            raise Exception(message)


        flash(
            f"Test email sent successfully to {test_email}.",
            "success"
        )


    except Exception as e:

        flash(
            f"Test email failed: {e}",
            "danger"
        )


    return redirect(
        url_for(
            "preview_campaign",
            campaign_id=campaign.id
        )
    )

@app.route(
    "/campaign/<int:campaign_id>/schedule",
    methods=["POST"]
)
def schedule_campaign(campaign_id):

    if "user_id" not in session:
        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=user_id
    ).first_or_404()

    if campaign.status != "Draft":

        flash(
            "Only draft campaigns can be scheduled.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )

    scheduled_at_string = request.form.get(
        "scheduled_at",
        ""
    ).strip()

    if not scheduled_at_string:

        flash(
            "Please select a date and time.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )

    try:

        scheduled_at = datetime.strptime(
            scheduled_at_string,
            "%Y-%m-%dT%H:%M"
        )

    except ValueError:

        flash(
            "The selected date and time is invalid.",
            "danger"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )

    now = datetime.now()

    if scheduled_at <= now:

        flash(
            "Please select a future date and time.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )

    campaign.scheduled_at = scheduled_at
    campaign.status = "Scheduled"

    db.session.commit()

    flash(
        "Campaign scheduled successfully.",
        "success"
    )

    return redirect(
        url_for(
            "preview_campaign",
            campaign_id=campaign.id
        )
    )

# =========================================================
# SEND CAMPAIGN
# =========================================================

@app.route(
    "/campaign/<int:campaign_id>/send",
    methods=["POST"]
)
def send_campaign(campaign_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]


    # =====================================================
    # GET CAMPAIGN
    # =====================================================

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=user_id
    ).first_or_404()


    # =====================================================
    # GET EMAIL SETTINGS
    # =====================================================

    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()


    if not email_settings:

        flash(
            "Please configure your Email & Sending settings first.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    # =====================================================
    # CHECK SMTP SETTINGS
    # =====================================================

    if not email_settings.smtp_host:

        flash(
            "Please configure your SMTP host before sending.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    if not email_settings.smtp_username:

        flash(
            "Please configure your SMTP username before sending.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    if not email_settings.smtp_password:

        flash(
            "Please configure your SMTP password before sending.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    if not email_settings.sender_email:

        flash(
            "Please configure your sender email before sending.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    # =====================================================
    # PREVENT DUPLICATE CAMPAIGN RUNS
    # =====================================================

    updated = Campaign.query.filter(
        Campaign.id == campaign.id,
        Campaign.created_by == user_id,
        Campaign.status != "Sending"
    ).update(
        {
            "status": "Sending"
        },
        synchronize_session=False
    )

    db.session.commit()


    if updated == 0:

        flash(
            "This campaign is already being sent.",
            "warning"
        )

        return redirect(
            url_for("campaigns")
        )


    # =====================================================
    # GET PENDING RECIPIENTS
    # =====================================================

    recipients = CampaignRecipient.query.filter_by(
        campaign_id=campaign.id,
        status="Pending"
    ).all()


    if not recipients:

        campaign.status = "Sent"

        db.session.commit()

        flash(
            "This campaign has no pending recipients.",
            "warning"
        )

        return redirect(
            url_for(
                "preview_campaign",
                campaign_id=campaign.id
            )
        )


    sent = 0

    failed = 0


    print("")
    print("=" * 60)

    print(
        f"🚀 STARTING CAMPAIGN: {campaign.id}"
    )

    print(
        f"📧 Recipients: {len(recipients)}"
    )

    print("=" * 60)

    print("")


    # =====================================================
    # SEND TO EACH RECIPIENT
    # =====================================================

    for recipient in recipients:

        contact = db.session.get(
            Contact,
            recipient.contact_id
        )


        # -------------------------------------------------
        # CONTACT DOES NOT EXIST
        # -------------------------------------------------

        if not contact:

            recipient.status = "Failed"

            db.session.commit()

            failed += 1

            print(
                f"❌ Contact not found: "
                f"{recipient.contact_id}"
            )

            continue


        attempts = 0

        success = False


        # -------------------------------------------------
        # THREE ATTEMPTS
        # -------------------------------------------------

        while attempts < 3:

            attempts += 1


            try:

                print("")

                print(
                    f"📧 Attempt {attempts}/3 "
                    f"for {contact.email}"
                )


                # =========================================
                # SEND USING SAVED SMTP SETTINGS
                # =========================================

                success, message = send_email(

                    smtp_host=email_settings.smtp_host,

                    smtp_port=email_settings.smtp_port,

                    smtp_username=email_settings.smtp_username,

                    smtp_password=email_settings.smtp_password,

                    smtp_encryption=email_settings.smtp_encryption,

                    sender_name=email_settings.sender_name,

                    sender_email=email_settings.sender_email,

                    recipient_email=contact.email,

                    subject=campaign.subject,

                    body=campaign.message,

                    reply_to_email=email_settings.reply_to_email
                )


                # =========================================
                # CHECK RESULT
                # =========================================

                if not success:

                    raise Exception(message)


                recipient.status = "Sent"

                recipient.sent_at = datetime.now(
                    timezone.utc
                )

                db.session.commit()

                sent += 1

                print(
                    f"✅ Sent to: {contact.email}"
                )

                time.sleep(2)

                break


            except Exception as e:

                print(
                    f"❌ Attempt {attempts}/3 "
                    f"failed for {contact.email}"
                )

                print(
                    f"Error: {e}"
                )


                if attempts < 3:

                    print(
                        "⏳ Retrying in 5 seconds..."
                    )

                    time.sleep(5)


        # -------------------------------------------------
        # ALL ATTEMPTS FAILED
        # -------------------------------------------------

        if not success:

            recipient.status = "Pending"

            db.session.commit()

            failed += 1

            print("")

            print(
                f"⚠️ Could not send to "
                f"{contact.email} after 3 attempts."
            )


    # =====================================================
    # UPDATE CAMPAIGN TOTALS
    # =====================================================

    campaign.sent_count += sent

    campaign.failed_count += failed


    # =====================================================
    # CHECK REMAINING
    # =====================================================

    remaining = CampaignRecipient.query.filter_by(
        campaign_id=campaign.id,
        status="Pending"
    ).count()


    if remaining == 0:

        campaign.status = "Sent"

    else:

        campaign.status = "Draft"


    db.session.commit()


    # =====================================================
    # CAMPAIGN LOG
    # =====================================================

    print("")

    print("=" * 60)

    print(
        "🏁 CAMPAIGN RUN FINISHED"
    )

    print(
        f"✅ Sent this run: {sent}"
    )

    print(
        f"❌ Failed this run: {failed}"
    )

    print(
        f"⏳ Remaining: {remaining}"
    )

    print("=" * 60)

    print("")


    # =====================================================
    # USER MESSAGE
    # =====================================================

    if remaining == 0:

        flash(
            f"Campaign completed! "
            f"Sent: {sent} | "
            f"Failed: {failed}",
            "success"
        )

    else:

        flash(
            f"Campaign run completed! "
            f"Sent: {sent} | "
            f"Failed: {failed} | "
            f"Remaining: {remaining}",
            "warning"
        )


    return redirect(
        url_for("campaigns")
    )

def process_scheduled_campaigns():
    """
    Find scheduled campaigns whose scheduled time has arrived
    and send them automatically.
    """

    with app.app_context():

        now = datetime.now()

        scheduled_campaigns = Campaign.query.filter(
            Campaign.status == "Scheduled",
            Campaign.scheduled_at <= now
        ).all()

        if not scheduled_campaigns:
            return

        print("")
        print("=" * 60)
        print("🕐 CHECKING SCHEDULED CAMPAIGNS")
        print(
            f"📧 Campaigns ready to send: "
            f"{len(scheduled_campaigns)}"
        )
        print("=" * 60)

        for campaign in scheduled_campaigns:

            print("")
            print(
                f"🚀 Starting scheduled campaign "
                f"{campaign.id}: {campaign.subject}"
            )

            try:

                # Change the status first so the same campaign
                # cannot be picked up again by another scheduler run.
                campaign.status = "Sending"
                db.session.commit()

                user_id = campaign.created_by

                email_settings = EmailSettings.query.filter_by(
                    user_id=user_id
                ).first()

                if not email_settings:

                    print(
                        f"❌ No email settings found "
                        f"for campaign {campaign.id}"
                    )

                    campaign.status = "Draft"
                    campaign.scheduled_at = None

                    db.session.commit()

                    continue

                if not email_settings.smtp_host:
                    print(
                        f"❌ SMTP host missing "
                        f"for campaign {campaign.id}"
                    )

                    campaign.status = "Draft"
                    campaign.scheduled_at = None

                    db.session.commit()

                    continue

                if not email_settings.smtp_username:
                    print(
                        f"❌ SMTP username missing "
                        f"for campaign {campaign.id}"
                    )

                    campaign.status = "Draft"
                    campaign.scheduled_at = None

                    db.session.commit()

                    continue

                if not email_settings.smtp_password:
                    print(
                        f"❌ SMTP password missing "
                        f"for campaign {campaign.id}"
                    )

                    campaign.status = "Draft"
                    campaign.scheduled_at = None

                    db.session.commit()

                    continue

                if not email_settings.sender_email:
                    print(
                        f"❌ Sender email missing "
                        f"for campaign {campaign.id}"
                    )

                    campaign.status = "Draft"
                    campaign.scheduled_at = None

                    db.session.commit()

                    continue

                recipients = CampaignRecipient.query.filter_by(
                    campaign_id=campaign.id,
                    status="Pending"
                ).all()

                if not recipients:

                    campaign.status = "Sent"
                    campaign.scheduled_at = None

                    db.session.commit()

                    print(
                        f"⚠️ Campaign {campaign.id} "
                        f"has no pending recipients."
                    )

                    continue

                sent = 0
                failed = 0

                for recipient in recipients:

                    contact = db.session.get(
                        Contact,
                        recipient.contact_id
                    )

                    if not contact:

                        recipient.status = "Failed"

                        db.session.commit()

                        failed += 1

                        print(
                            f"❌ Contact not found: "
                            f"{recipient.contact_id}"
                        )

                        continue

                    attempts = 0
                    success = False

                    while attempts < 3:

                        attempts += 1

                        try:

                            print(
                                f"📧 Attempt "
                                f"{attempts}/3 "
                                f"for {contact.email}"
                            )

                            success, message = send_email(

                                smtp_host=email_settings.smtp_host,

                                smtp_port=email_settings.smtp_port,

                                smtp_username=email_settings.smtp_username,

                                smtp_password=email_settings.smtp_password,

                                smtp_encryption=email_settings.smtp_encryption,

                                sender_name=email_settings.sender_name,

                                sender_email=email_settings.sender_email,

                                recipient_email=contact.email,

                                subject=campaign.subject,

                                body=campaign.message,

                                reply_to_email=email_settings.reply_to_email
                            )

                            if not success:
                                raise Exception(message)

                            recipient.status = "Sent"

                            recipient.sent_at = datetime.now(
                                timezone.utc
                            )

                            db.session.commit()

                            sent += 1

                            print(
                                f"✅ Sent to: "
                                f"{contact.email}"
                            )

                            time.sleep(2)

                            break

                        except Exception as e:

                            print(
                                f"❌ Attempt "
                                f"{attempts}/3 failed "
                                f"for {contact.email}"
                            )

                            print(
                                f"Error: {e}"
                            )

                            if attempts < 3:

                                print(
                                    "⏳ Retrying in "
                                    "5 seconds..."
                                )

                                time.sleep(5)

                    if not success:

                        recipient.status = "Pending"

                        db.session.commit()

                        failed += 1

                campaign.sent_count += sent
                campaign.failed_count += failed

                remaining = CampaignRecipient.query.filter_by(
                    campaign_id=campaign.id,
                    status="Pending"
                ).count()

                if remaining == 0:

                    campaign.status = "Sent"
                    campaign.scheduled_at = None

                else:

                    campaign.status = "Draft"

                db.session.commit()

                print("")
                print(
                    f"🏁 Scheduled campaign "
                    f"{campaign.id} finished."
                )

                print(
                    f"✅ Sent: {sent}"
                )

                print(
                    f"❌ Failed: {failed}"
                )

                print(
                    f"⏳ Remaining: {remaining}"
                )

            except Exception as e:

                db.session.rollback()

                print("")
                print(
                    f"❌ Scheduled campaign "
                    f"{campaign.id} failed."
                )

                print(
                    f"Error: {e}"
                )

                campaign = db.session.get(
                    Campaign,
                    campaign.id
                )

                if campaign:

                    campaign.status = "Draft"
                    campaign.scheduled_at = None

                    db.session.commit()

# =========================================================
# FORMS

@app.route("/forms")
def forms():
    if "user_id" not in session:
        return redirect(url_for("login"))

    forms_list = Form.query.filter_by(
        created_by=session["user_id"]
    ).order_by(
        Form.created_at.desc()
    ).all()

    landing_pages_list = LandingPage.query.filter_by(
        created_by=session["user_id"]
    ).order_by(
        LandingPage.created_at.desc()
    ).all()

    return render_template(
        "forms.html",
        forms=forms_list,
        landing_pages=landing_pages_list
    )


# =========================================================
# CREATE FORM
# =========================================================

@app.route(
    "/forms/create",
    methods=["GET", "POST"]
)
def create_form():

    if "user_id" not in session:

        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        headline = request.form.get(
            "headline",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        button_text = request.form.get(
            "button_text",
            "Subscribe"
        ).strip()

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not name:

            flash(
                "Please enter a form name.",
                "warning"
            )

            return redirect(
                url_for("create_form")
            )

        if not headline:

            flash(
                "Please enter a headline.",
                "warning"
            )

            return redirect(
                url_for("create_form")
            )

        if not button_text:

            button_text = "Subscribe"

        # -------------------------------------------------
        # CREATE FORM

        new_form = Form(
            name=name,
            headline=headline,
            description=description,
            button_text=button_text,
            created_by=session["user_id"]
        )

        try:

            db.session.add(new_form)

            db.session.commit()

            flash(
                "Form created successfully!",
                "success"
            )

            return redirect(
                url_for("forms")
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f"Could not create form: {e}",
                "danger"
            )

            return redirect(
                url_for("create_form")
            )

    return render_template(
        "create_form.html"
    )


# =========================================================
# PREVIEW FORM
# =========================================================

@app.route(
    "/forms/<int:form_id>"
)

@app.route("/forms/<int:form_id>/edit", methods=["GET", "POST"])
def edit_form(form_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    form = Form.query.filter_by(
        id=form_id,
        created_by=session["user_id"]
    ).first_or_404()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        headline = request.form.get("headline", "").strip()
        description = request.form.get("description", "").strip()
        button_text = request.form.get(
            "button_text",
            "Subscribe"
        ).strip() or "Subscribe"

        if not name:
            flash("Please enter a form name.", "warning")

            return redirect(
                url_for(
                    "edit_form",
                    form_id=form.id
                )
            )

        if not headline:
            flash("Please enter a headline.", "warning")

            return redirect(
                url_for(
                    "edit_form",
                    form_id=form.id
                )
            )

        form.name = name
        form.headline = headline
        form.description = description
        form.button_text = button_text

        db.session.commit()

        flash(
            "Form updated successfully!",
            "success"
        )

        return redirect(
            url_for(
                "edit_form",
                form_id=form.id
            )
        )

    return render_template(
        "edit_form.html",
        form=form
    )

@app.route("/forms/<int:form_id>/preview")
def preview_form(form_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    form = Form.query.filter_by(
        id=form_id,
        created_by=session["user_id"]
    ).first_or_404()

    return render_template(
        "preview_form.html",
        form=form
    )

@app.route("/subscribe/<int:form_id>", methods=["GET", "POST"])
def subscribe_form(form_id):

    # Find the form
    form = Form.query.get_or_404(form_id)

    # Only process this section when the visitor submits the form
    if request.method == "POST":

        # Get the submitted values
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()

        # Check name
        if not name:
            flash("Please enter your name.", "warning")
            return redirect(
                url_for("subscribe_form", form_id=form.id)
            )

        # Check email
        if not email:
            flash("Please enter your email address.", "warning")
            return redirect(
                url_for("subscribe_form", form_id=form.id)
            )

        # Check if this email already belongs to this user's contacts
        existing_contact = Contact.query.filter_by(
            email=email,
            created_by=form.created_by
        ).first()

        if existing_contact:
            flash(
                "This email is already subscribed.",
                "warning"
            )
            return redirect(
                url_for("subscribe_form", form_id=form.id)
            )

        # Create the new contact
        new_contact = Contact(
            name=name,
            email=email,
            created_by=form.created_by
        )

        try:
            # Save the contact
            db.session.add(new_contact)
            db.session.commit()

            # Tell the subscriber it worked
            flash(
                "You have successfully subscribed!",
                "success"
            )

        except IntegrityError:
            # Undo the failed database transaction
            db.session.rollback()

            flash(
                "This email is already subscribed.",
                "warning"
            )

        # Return to the subscription form
        return redirect(
            url_for("subscribe_form", form_id=form.id)
        )

    # Display the form when the visitor first opens the page
    return render_template(
        "subscribe_form.html",
        form=form
    )
# =========================================================
# DELETE FORM
# =========================================================

@app.route(
    "/forms/<int:form_id>/delete",
    methods=["POST"]
)
def delete_form(form_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    form = Form.query.filter_by(
        id=form_id,
        created_by=session["user_id"]
    ).first_or_404()

    db.session.delete(form)

    db.session.commit()

    flash(
        "Form deleted successfully.",
        "success"
    )

    return redirect(
        url_for("forms")
    )

# =========================================================
# BUILT-IN EMAIL TEMPLATES
# =========================================================

SYSTEM_TEMPLATES = [

    {
        "name": "Clean Newsletter",
        "category": "Newsletter",
        "subject": "Your latest newsletter",
        "content": "A clean and professional newsletter email.",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>

<body style="margin:0; padding:0; background:#f3f4f6; font-family:Arial, sans-serif;">

    <div style="max-width:600px; margin:40px auto; background:white;">

        <div style="padding:35px; border-bottom:1px solid #e5e7eb;">
            <h1 style="margin:0; color:#111827;">
                Your Newsletter
            </h1>

            <p style="color:#6b7280; margin-top:10px;">
                The latest updates, ideas and news from us.
            </p>
        </div>

        <div style="padding:35px;">

            <h2 style="color:#111827;">
                What's new?
            </h2>

            <p style="color:#4b5563; line-height:1.7;">
                Share your latest news, useful information,
                company updates or helpful content with your audience.
            </p>

            <a href="#"
               style="display:inline-block;
                      margin-top:20px;
                      padding:12px 22px;
                      background:#111827;
                      color:white;
                      text-decoration:none;
                      border-radius:6px;">
                Read More
            </a>

        </div>

        <div style="padding:25px; background:#f9fafb; text-align:center;">
            <p style="font-size:12px; color:#9ca3af;">
                © Your Company
            </p>
        </div>

    </div>

</body>
</html>
"""
    },

    {
        "name": "Welcome Email",
        "category": "Welcome",
        "subject": "Welcome to our community!",
        "content": "A friendly welcome email for new subscribers.",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>

<body style="margin:0; background:#eef2ff; font-family:Arial, sans-serif;">

    <div style="max-width:600px; margin:40px auto; background:white; border-radius:12px; overflow:hidden;">

        <div style="padding:45px; text-align:center; background:#4f46e5; color:white;">

            <h1 style="margin:0;">
                Welcome! 👋
            </h1>

            <p style="margin-top:12px;">
                We're excited to have you here.
            </p>

        </div>

        <div style="padding:40px;">

            <h2 style="color:#111827;">
                Thanks for joining us
            </h2>

            <p style="color:#4b5563; line-height:1.7;">
                We're happy you're part of our community.
                You'll receive useful updates, resources and
                announcements from us.
            </p>

            <div style="text-align:center; margin-top:30px;">

                <a href="#"
                   style="display:inline-block;
                          padding:14px 25px;
                          background:#4f46e5;
                          color:white;
                          text-decoration:none;
                          border-radius:7px;">
                    Get Started
                </a>

            </div>

        </div>

    </div>

</body>
</html>
"""
    },

    {
        "name": "Product Launch",
        "category": "Promotion",
        "subject": "Something exciting is here 🚀",
        "content": "A bold product launch announcement.",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>

<body style="margin:0; background:#111827; font-family:Arial, sans-serif;">

    <div style="max-width:600px; margin:40px auto; background:white;">

        <div style="padding:55px 40px; text-align:center; background:#111827; color:white;">

            <p style="text-transform:uppercase; letter-spacing:2px; font-size:12px;">
                New Release
            </p>

            <h1 style="font-size:38px; margin:15px 0;">
                It's finally here.
            </h1>

            <p style="color:#d1d5db;">
                Meet our newest product.
            </p>

        </div>

        <div style="padding:40px; text-align:center;">

            <h2 style="color:#111827;">
                Built for better results
            </h2>

            <p style="color:#6b7280; line-height:1.7;">
                Introduce your product, explain what makes it
                different and give your audience a reason to try it.
            </p>

            <a href="#"
               style="display:inline-block;
                      margin-top:20px;
                      padding:14px 28px;
                      background:#111827;
                      color:white;
                      text-decoration:none;
                      border-radius:7px;">
                Explore Product
            </a>

        </div>

    </div>

</body>
</html>
"""
    },

    {
        "name": "Special Offer",
        "category": "Promotion",
        "subject": "A special offer just for you 🎁",
        "content": "A promotional email for discounts and offers.",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>

<body style="margin:0; background:#fff7ed; font-family:Arial, sans-serif;">

    <div style="max-width:600px; margin:40px auto; background:white;">

        <div style="padding:50px; text-align:center; background:#f97316; color:white;">

            <div style="font-size:45px;">
                🎁
            </div>

            <h1 style="margin:15px 0;">
                Special Offer
            </h1>

            <p>
                Don't miss this limited-time opportunity.
            </p>

        </div>

        <div style="padding:45px; text-align:center;">

            <h2 style="font-size:32px; color:#111827;">
                25% OFF
            </h2>

            <p style="color:#6b7280;">
                Give your subscribers an exclusive discount.
            </p>

            <a href="#"
               style="display:inline-block;
                      margin-top:20px;
                      padding:14px 30px;
                      background:#f97316;
                      color:white;
                      text-decoration:none;
                      border-radius:7px;">
                Claim Offer
            </a>

            <p style="margin-top:25px; font-size:12px; color:#9ca3af;">
                Offer available for a limited time.
            </p>

        </div>

    </div>

</body>
</html>
"""
    },

    {
        "name": "Announcement",
        "category": "Announcement",
        "subject": "Important announcement",
        "content": "A simple announcement email.",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>

<body style="margin:0; background:#f9fafb; font-family:Arial, sans-serif;">

    <div style="max-width:600px; margin:40px auto; background:white; border:1px solid #e5e7eb;">

        <div style="padding:30px; border-bottom:1px solid #e5e7eb;">

            <strong style="font-size:20px; color:#111827;">
                EmailFlow
            </strong>

        </div>

        <div style="padding:45px;">

            <p style="font-size:13px; color:#6b7280;">
                IMPORTANT UPDATE
            </p>

            <h1 style="color:#111827;">
                We have something to share.
            </h1>

            <p style="color:#4b5563; line-height:1.8;">
                Use this template when you need to communicate
                an important update, change or announcement
                to your subscribers.
            </p>

            <a href="#"
               style="display:inline-block;
                      margin-top:20px;
                      padding:12px 22px;
                      background:#111827;
                      color:white;
                      text-decoration:none;
                      border-radius:6px;">
                Learn More
            </a>

        </div>

    </div>

</body>
</html>
"""
    },

    {
        "name": "Event Invitation",
        "category": "Event",
        "subject": "You're invited! 🎉",
        "content": "An elegant event invitation email.",
        "html_content": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>

<body style="margin:0; background:#f5f3ff; font-family:Arial, sans-serif;">

    <div style="max-width:600px; margin:40px auto; background:white;">

        <div style="padding:50px; text-align:center; background:#7c3aed; color:white;">

            <p style="letter-spacing:2px; text-transform:uppercase;">
                You're Invited
            </p>

            <h1 style="font-size:36px;">
                Join Our Event
            </h1>

            <p>
                An experience you won't want to miss.
            </p>

        </div>

        <div style="padding:40px; text-align:center;">

            <h2 style="color:#111827;">
                Save the Date
            </h2>

            <p style="color:#6b7280;">
                Saturday, June 20
            </p>

            <p style="color:#6b7280;">
                2:00 PM · Online Event
            </p>

            <a href="#"
               style="display:inline-block;
                      margin-top:20px;
                      padding:14px 26px;
                      background:#7c3aed;
                      color:white;
                      text-decoration:none;
                      border-radius:7px;">
                Reserve My Spot
            </a>

        </div>

    </div>

</body>
</html>
"""
    }
]

# =========================================================
# CREATE BUILT-IN TEMPLATES FOR A USER
# =========================================================

def seed_system_templates_for_user(user_id):

    existing_templates = Template.query.filter_by(
        created_by=user_id,
        is_system_template=True
    ).all()

    existing_names = {
        template.name
        for template in existing_templates
    }

    templates_created = False

    for template_data in SYSTEM_TEMPLATES:

        if template_data["name"] in existing_names:
            continue

        new_template = Template(
            name=template_data["name"],
            subject=template_data["subject"],
            content=template_data["content"],
            category=template_data["category"],
            html_content=template_data["html_content"],
            is_system_template=True,
            created_by=user_id
        )

        db.session.add(new_template)

        templates_created = True

    if templates_created:
        db.session.commit()

# =========================================================
# TEMPLATES
# =========================================================

@app.route("/templates")
def templates():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Create the built-in templates if this user
    # does not already have them.
    seed_system_templates_for_user(user_id)

    template_list = Template.query.filter_by(
        created_by=user_id
    ).order_by(
        Template.is_system_template.desc(),
        Template.created_at.desc()
    ).all()

    return render_template(
        "templates.html",
        templates=template_list
    )
# =========================================================
# CREATE TEMPLATE
# =========================================================

@app.route(
    "/templates/create",
    methods=["GET", "POST"]
)
def create_template():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        content = request.form.get(
            "content",
            ""
        ).strip()

        # -----------------------------------------
        # VALIDATION
        # -----------------------------------------

        if not name:

            flash(
                "Please enter a template name.",
                "warning"
            )

            return redirect(
                url_for("create_template")
            )

        if not subject:

            flash(
                "Please enter an email subject.",
                "warning"
            )

            return redirect(
                url_for("create_template")
            )

        if not content:

            flash(
                "Please enter your email content.",
                "warning"
            )

            return redirect(
                url_for("create_template")
            )

        # -----------------------------------------
        # CREATE TEMPLATE
        # -----------------------------------------

        new_template = Template(
            name=name,
            subject=subject,
            content=content,
            created_by=session["user_id"]
        )

        try:

            db.session.add(new_template)

            db.session.commit()

            flash(
                "Template created successfully!",
                "success"
            )

            return redirect(
                url_for("templates")
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f"Could not create template: {e}",
                "danger"
            )

            return redirect(
                url_for("create_template")
            )

    return render_template(
        "create_template.html"
    )


# =========================================================
# EDIT TEMPLATE
# =========================================================

@app.route(
    "/templates/<int:template_id>/edit",
    methods=["GET", "POST"]
)
def edit_template(template_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    template = Template.query.filter_by(
        id=template_id,
        created_by=session["user_id"]
    ).first_or_404()

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        content = request.form.get(
            "content",
            ""
        ).strip()

        if not name:

            flash(
                "Please enter a template name.",
                "warning"
            )

            return redirect(
                url_for(
                    "edit_template",
                    template_id=template.id
                )
            )

        if not subject:

            flash(
                "Please enter an email subject.",
                "warning"
            )

            return redirect(
                url_for(
                    "edit_template",
                    template_id=template.id
                )
            )

        if not content:

            flash(
                "Please enter your email content.",
                "warning"
            )

            return redirect(
                url_for(
                    "edit_template",
                    template_id=template.id
                )
            )

        template.name = name
        template.subject = subject
        template.content = content

        try:

            db.session.commit()

            flash(
                "Template updated successfully!",
                "success"
            )

        except Exception as e:

            db.session.rollback()

            flash(
                f"Could not update template: {e}",
                "danger"
            )

        return redirect(
            url_for(
                "edit_template",
                template_id=template.id
            )
        )

    return render_template(
        "edit_template.html",
        template=template
    )

# =========================================================
# USE EMAIL TEMPLATE
# =========================================================

@app.route(
    "/templates/<int:template_id>/use",
    methods=["GET"]
)
def use_template(template_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    template = Template.query.filter_by(
        id=template_id,
        created_by=session["user_id"]
    ).first_or_404()

    return render_template(
        "use_template.html",
        template=template
    )

# =========================================================
# DELETE TEMPLATE
# =========================================================

@app.route(
    "/templates/<int:template_id>/delete",
    methods=["POST"]
)
def delete_template(template_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    template = Template.query.filter_by(
        id=template_id,
        created_by=session["user_id"]
    ).first_or_404()

    try:

        db.session.delete(template)

        db.session.commit()

        flash(
            "Template deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        flash(
            f"Could not delete template: {e}",
            "danger"
        )

    return redirect(
        url_for("templates")
    )

# =========================================================
# LANDING PAGES
# =========================================================

@app.route("/landing-pages")
def landing_pages():

    if "user_id" not in session:
        return redirect(url_for("login"))

    # Only show the five official EmailFlow landing-page templates.
    # This prevents old/legacy template rows in database.db from
    # appearing in the chooser.
    template_names = [
        "Creator",
        "Studio",
        "Newsletter",
        "Product",
        "From Scratch",
    ]

    found_templates = LandingPageTemplate.query.filter(
        LandingPageTemplate.is_system_template.is_(True),
        LandingPageTemplate.name.in_(template_names)
    ).all()

    template_order = {name: index for index, name in enumerate(template_names)}
    found_templates.sort(key=lambda item: template_order.get(item.name, 999))

    return render_template(
        "landing_pages.html",
        templates=found_templates
    )


@app.route("/landing-pages/templates/<int:template_id>/preview")
def preview_landing_template(template_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    template = LandingPageTemplate.query.filter_by(
        id=template_id,
        is_system_template=True
    ).first_or_404()

    return render_template(
        "preview_landing_template.html",
        template=template
    )


# =========================================================
# CREATE LANDING PAGE
# =========================================================

@app.route("/landing-pages/create", methods=["GET", "POST"])
def create_landing_page():

    if "user_id" not in session:
        return redirect(url_for("login"))

    template_id = request.args.get("template_id", type=int)
    selected_template = None

    if template_id:
        selected_template = LandingPageTemplate.query.filter_by(
            id=template_id,
            is_system_template=True
        ).first_or_404()

    if request.method == "POST":

        posted_template_id = request.form.get(
            "template_id",
            type=int
        )

        if posted_template_id:
            selected_template = LandingPageTemplate.query.filter_by(
                id=posted_template_id,
                is_system_template=True
            ).first()

        name = request.form.get("name", "").strip()
        headline = request.form.get("headline", "").strip()
        subheadline = request.form.get("subheadline", "").strip()
        description = request.form.get("description", "").strip()
        button_text = request.form.get(
            "button_text",
            "Get Started"
        ).strip() or "Get Started"
        button_url = request.form.get("button_url", "").strip()

        if not name:
            flash("Please enter a landing page name.", "warning")
            return redirect(url_for(
                "create_landing_page",
                template_id=posted_template_id
            ))

        if not headline:
            flash("Please enter a headline.", "warning")
            return redirect(url_for(
                "create_landing_page",
                template_id=posted_template_id
            ))

        # Default design for pages created from scratch.
        selected_style = "classic"
        background_color = "#f8fafc"
        headline_color = "#111827"
        button_color = "#4f46e5"
        button_text_color = "#ffffff"
        font_family = "Arial"
        border_radius = 14

        # Each starting template gets its own initial design.
        if selected_template:

            selected_style = selected_template.style

            if selected_style == "creator":
                background_color = "#f5f3ff"
                headline_color = "#312e81"
                button_color = "#7c3aed"
                button_text_color = "#ffffff"
                font_family = "Arial"
                border_radius = 20

            elif selected_style == "studio":
                background_color = "#111827"
                headline_color = "#ffffff"
                button_color = "#f59e0b"
                button_text_color = "#111827"
                font_family = "Arial"
                border_radius = 4

            elif selected_style == "newsletter":
                background_color = "#fffdf5"
                headline_color = "#78350f"
                button_color = "#b45309"
                button_text_color = "#ffffff"
                font_family = "Georgia"
                border_radius = 8

            elif selected_style == "product":
                background_color = "#eff6ff"
                headline_color = "#1e3a8a"
                button_color = "#2563eb"
                button_text_color = "#ffffff"
                font_family = "Arial"
                border_radius = 18

            elif selected_style == "scratch":
                background_color = "#ffffff"
                headline_color = "#111827"
                button_color = "#111827"
                button_text_color = "#ffffff"
                font_family = "Arial"
                border_radius = 0

            # If the template supplies text, use it unless the user
            # explicitly submitted different values.
            if not request.form.get("headline") and selected_template.headline:
                headline = selected_template.headline

        # Create the internal signup form.
        new_form = Form(
            name=f"{name} Signup Form",
            headline=headline,
            description=description,
            button_text=button_text,
            created_by=session["user_id"]
        )

        db.session.add(new_form)
        db.session.flush()

        new_landing_page = LandingPage(
            name=name,
            headline=headline,
            subheadline=subheadline,
            description=description,
            button_text=button_text,
            button_url=button_url,
            template_id=(
                selected_template.id
                if selected_template
                else None
            ),
            style=selected_style,
            form_id=new_form.id,
            created_by=session["user_id"],
            background_color=background_color,
            headline_color=headline_color,
            button_color=button_color,
            button_text_color=button_text_color,
            font_family=font_family,
            border_radius=border_radius
        )

        db.session.add(new_landing_page)
        db.session.commit()

        flash(
            "Landing page created successfully!",
            "success"
        )

        return redirect(url_for(
            "landing_page_created",
            landing_page_id=new_landing_page.id
        ))

    return render_template(
        "create_landing_page.html",
        template=selected_template
    )


# =========================================================
# LANDING PAGE CREATED / PUBLIC LINK
# =========================================================

@app.route("/landing-pages/<int:landing_page_id>/created")
def landing_page_created(landing_page_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    landing_page = LandingPage.query.filter_by(
        id=landing_page_id,
        created_by=session["user_id"]
    ).first_or_404()

    public_link = url_for(
        "public_landing_page",
        landing_page_id=landing_page.id,
        _external=True
    )

    return render_template(
        "landing_page_created.html",
        landing_page=landing_page,
        public_link=public_link
    )


# =========================================================
# EDIT LANDING PAGE CONTENT
# =========================================================

@app.route(
    "/landing-pages/<int:landing_page_id>/edit",
    methods=["GET", "POST"]
)
def edit_landing_page(landing_page_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    landing_page = LandingPage.query.filter_by(
        id=landing_page_id,
        created_by=session["user_id"]
    ).first_or_404()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        headline = request.form.get("headline", "").strip()
        subheadline = request.form.get("subheadline", "").strip()
        description = request.form.get("description", "").strip()
        button_text = request.form.get(
            "button_text",
            "Get Started"
        ).strip() or "Get Started"
        button_url = request.form.get("button_url", "").strip()

        background_color = request.form.get(
            "background_color",
            landing_page.background_color or "#f8fafc"
        ).strip()
        headline_color = request.form.get(
            "headline_color",
            landing_page.headline_color or "#111827"
        ).strip()
        button_color = request.form.get(
            "button_color",
            landing_page.button_color or "#4f46e5"
        ).strip()
        button_text_color = request.form.get(
            "button_text_color",
            landing_page.button_text_color or "#ffffff"
        ).strip()
        font_family = request.form.get(
            "font_family",
            landing_page.font_family or "Arial"
        ).strip()
        border_radius = request.form.get(
            "border_radius",
            landing_page.border_radius if landing_page.border_radius is not None else 14,
            type=int
        )
        border_radius = max(0, min(border_radius, 50))

        if not name:
            flash("Please enter a landing page name.", "warning")
            return redirect(url_for(
                "edit_landing_page",
                landing_page_id=landing_page.id
            ))

        if not headline:
            flash("Please enter a headline.", "warning")
            return redirect(url_for(
                "edit_landing_page",
                landing_page_id=landing_page.id
            ))

        landing_page.name = name
        landing_page.headline = headline
        landing_page.subheadline = subheadline
        landing_page.description = description
        landing_page.button_text = button_text
        landing_page.button_url = button_url
        landing_page.background_color = background_color
        landing_page.headline_color = headline_color
        landing_page.button_color = button_color
        landing_page.button_text_color = button_text_color
        landing_page.font_family = font_family
        landing_page.border_radius = border_radius

        db.session.commit()

        flash("Landing page updated successfully!", "success")

        return redirect(url_for(
            "edit_landing_page",
            landing_page_id=landing_page.id
        ))

    public_link = url_for(
        "public_landing_page",
        landing_page_id=landing_page.id,
        _external=True
    )

    return render_template(
        "edit_landing_page.html",
        landing_page=landing_page,
        public_link=public_link
    )


# =========================================================
# EDIT LANDING PAGE DESIGN
# =========================================================

@app.route(
    "/landing-pages/<int:landing_page_id>/design",
    methods=["GET", "POST"]
)
def edit_landing_page_design(landing_page_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    # The content and design editor are now one working editor.
    # Keep this route so old links/bookmarks continue to work.
    return redirect(url_for(
        "edit_landing_page",
        landing_page_id=landing_page_id
    ))


# =========================================================
# LANDING PAGE PREVIEW
# =========================================================

@app.route("/landing-pages/<int:landing_page_id>/preview")
def preview_landing_page(landing_page_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    landing_page = LandingPage.query.filter_by(
        id=landing_page_id,
        created_by=session["user_id"]
    ).first_or_404()

    return render_template(
        "preview_landing_page.html",
        landing_page=landing_page
    )


# =========================================================
# PUBLIC LANDING PAGE
# =========================================================

@app.route("/page/<int:landing_page_id>")
def public_landing_page(landing_page_id):

    landing_page = LandingPage.query.get_or_404(
        landing_page_id
    )

    return render_template(
        "public_landing_page.html",
        landing_page=landing_page
    )


# =========================================================
# SUBSCRIBE THROUGH LANDING PAGE
# =========================================================

@app.route(
    "/page/<int:landing_page_id>/subscribe",
    methods=["POST"]
)
def subscribe_landing_page(landing_page_id):

    landing_page = LandingPage.query.get_or_404(
        landing_page_id
    )

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()

    if not name:
        flash("Please enter your name.", "warning")
        return redirect(url_for(
            "public_landing_page",
            landing_page_id=landing_page.id
        ))

    if not email:
        flash("Please enter your email address.", "warning")
        return redirect(url_for(
            "public_landing_page",
            landing_page_id=landing_page.id
        ))

    existing_contact = Contact.query.filter_by(
        email=email,
        created_by=landing_page.created_by
    ).first()

    if existing_contact:
        flash(
            "This email is already subscribed.",
            "warning"
        )
        return redirect(url_for(
            "public_landing_page",
            landing_page_id=landing_page.id
        ))

    new_contact = Contact(
        name=name,
        email=email,
        created_by=landing_page.created_by
    )

    try:
        db.session.add(new_contact)
        db.session.commit()

        flash(
            "You have successfully subscribed!",
            "success"
        )

    except IntegrityError:
        db.session.rollback()
        flash(
            "This email is already subscribed.",
            "warning"
        )

    return redirect(url_for(
        "public_landing_page",
        landing_page_id=landing_page.id
    ))


# =========================================================
# DELETE LANDING PAGE
# =========================================================

@app.route(
    "/landing-pages/<int:landing_page_id>/delete",
    methods=["POST"]
)
def delete_landing_page(landing_page_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    landing_page = LandingPage.query.filter_by(
        id=landing_page_id,
        created_by=session["user_id"]
    ).first_or_404()

    try:
        db.session.delete(landing_page)
        db.session.commit()

        flash(
            "Landing page deleted successfully!",
            "success"
        )

    except Exception:
        db.session.rollback()
        flash(
            "Unable to delete the landing page.",
            "danger"
        )

    return redirect(url_for("forms"))

# =========================================================
# SETTINGS
# =========================================================

# =========================================================
# ANALYTICS
# =========================================================

@app.route("/analytics")
def analytics():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # -----------------------------------------------------
    # BASIC COUNTS
    # -----------------------------------------------------

    total_contacts = Contact.query.filter_by(
        created_by=user_id
    ).count()

    total_campaigns = Campaign.query.filter_by(
        created_by=user_id
    ).count()

    # -----------------------------------------------------
    # GET USER CAMPAIGNS
    # -----------------------------------------------------

    campaigns = Campaign.query.filter_by(
        created_by=user_id
    ).order_by(
        Campaign.created_at.desc()
    ).all()

    # -----------------------------------------------------
    # GET RECIPIENT RECORDS
    # -----------------------------------------------------

    campaign_ids = [
        campaign.id
        for campaign in campaigns
    ]

    if campaign_ids:

        recipient_records = CampaignRecipient.query.filter(
            CampaignRecipient.campaign_id.in_(campaign_ids)
        ).all()

    else:

        recipient_records = []


    # -----------------------------------------------------
    # OVERALL EMAIL STATISTICS
    # -----------------------------------------------------

    total_sent = sum(
        1
        for recipient in recipient_records
        if recipient.status == "Sent"
    )

    total_failed = sum(
        1
        for recipient in recipient_records
        if recipient.status == "Failed"
    )

    total_pending = sum(
        1
        for recipient in recipient_records
        if recipient.status == "Pending"
    )


    total_attempted = (
        total_sent +
        total_failed
    )


    if total_attempted > 0:

        delivery_rate = round(
            (total_sent / total_attempted) * 100,
            1
        )

    else:

        delivery_rate = 0


    # -----------------------------------------------------
    # CAMPAIGN PERFORMANCE
    # -----------------------------------------------------

    campaign_analytics = []


    for campaign in campaigns:

        campaign_recipients = [
            recipient
            for recipient in recipient_records
            if recipient.campaign_id == campaign.id
        ]


        recipient_count = len(
            campaign_recipients
        )


        sent_count = sum(
            1
            for recipient in campaign_recipients
            if recipient.status == "Sent"
        )


        failed_count = sum(
            1
            for recipient in campaign_recipients
            if recipient.status == "Failed"
        )


        pending_count = sum(
            1
            for recipient in campaign_recipients
            if recipient.status == "Pending"
        )


        attempted_count = (
            sent_count +
            failed_count
        )


        if attempted_count > 0:

            campaign_delivery_rate = round(
                (sent_count / attempted_count) * 100,
                1
            )

        else:

            campaign_delivery_rate = 0


        campaign_analytics.append({

            "campaign": campaign,

            "recipient_count": recipient_count,

            "sent_count": sent_count,

            "failed_count": failed_count,

            "pending_count": pending_count,

            "delivery_rate": campaign_delivery_rate

        })


    # -----------------------------------------------------
    # CAMPAIGN STATUS COUNTS
    # -----------------------------------------------------

    completed_campaigns = sum(
        1
        for campaign in campaigns
        if campaign.status == "Sent"
    )

    sending_campaigns = sum(
        1
        for campaign in campaigns
        if campaign.status == "Sending"
    )

    draft_campaigns = sum(
        1
        for campaign in campaigns
        if campaign.status == "Draft"
    )


    return render_template(
        "analytics.html",

        total_contacts=total_contacts,

        total_campaigns=total_campaigns,

        total_sent=total_sent,

        total_failed=total_failed,

        total_pending=total_pending,

        delivery_rate=delivery_rate,

        completed_campaigns=completed_campaigns,

        sending_campaigns=sending_campaigns,

        draft_campaigns=draft_campaigns,

        campaign_analytics=campaign_analytics

    )

@app.route("/settings")
def settings():
    """
    Main Settings page.

    For now, Account Settings is the first
    available settings section.
    """

    if "user_id" not in session:
        return redirect(url_for("login"))

    return redirect(
        url_for("account_settings")
    )


# =========================================================
# ACCOUNT SETTINGS
# =========================================================

@app.route(
    "/settings/account",
    methods=["GET", "POST"]
)
def account_settings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(
        id=session["user_id"]
    ).first_or_404()

    if request.method == "POST":

        action = request.form.get(
            "action",
            ""
        ).strip()

        # =================================================
        # UPDATE ACCOUNT INFORMATION
        # =================================================

        if action == "update_account":

            name = request.form.get(
                "name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip().lower()

            # ---------------------------------------------
            # VALIDATION
            # ---------------------------------------------

            if not name:

                flash(
                    "Please enter your name.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            if not email:

                flash(
                    "Please enter your email address.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            # ---------------------------------------------
            # CHECK WHETHER EMAIL IS ALREADY USED
            # ---------------------------------------------

            existing_user = User.query.filter(
                User.email == email,
                User.id != user.id
            ).first()

            if existing_user:

                flash(
                    "That email address is already being used.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            # ---------------------------------------------
            # UPDATE USER
            # ---------------------------------------------

            user.name = name
            user.email = email

            try:

                db.session.commit()

                # Keep the session name updated
                session["user_name"] = user.name

                flash(
                    "Account information updated successfully.",
                    "success"
                )

            except IntegrityError:

                db.session.rollback()

                flash(
                    "That email address is already being used.",
                    "warning"
                )

            except Exception as e:

                db.session.rollback()

                flash(
                    f"Could not update account: {e}",
                    "danger"
                )

            return redirect(
                url_for("account_settings")
            )

        # =================================================
        # CHANGE PASSWORD
        # =================================================

        if action == "change_password":

            current_password = request.form.get(
                "current_password",
                ""
            )

            new_password = request.form.get(
                "new_password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            # ---------------------------------------------
            # VALIDATION
            # ---------------------------------------------

            if not current_password:

                flash(
                    "Please enter your current password.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            if not new_password:

                flash(
                    "Please enter a new password.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            if len(new_password) < 8:

                flash(
                    "Your new password must be at least 8 characters long.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            if new_password != confirm_password:

                flash(
                    "The new passwords do not match.",
                    "warning"
                )

                return redirect(
                    url_for("account_settings")
                )

            # ---------------------------------------------
            # CHECK CURRENT PASSWORD
            # ---------------------------------------------

            if not bcrypt.check_password_hash(
                user.password,
                current_password
            ):

                flash(
                    "Your current password is incorrect.",
                    "danger"
                )

                return redirect(
                    url_for("account_settings")
                )

            # ---------------------------------------------
            # HASH NEW PASSWORD
            # ---------------------------------------------

            user.password = (
                bcrypt
                .generate_password_hash(new_password)
                .decode("utf-8")
            )

            try:

                db.session.commit()

                flash(
                    "Password changed successfully.",
                    "success"
                )

            except Exception as e:

                db.session.rollback()

                flash(
                    f"Could not change password: {e}",
                    "danger"
                )

            return redirect(
                url_for("account_settings")
            )

    return render_template(
        "settings_account.html",
        user=user
    )


# =========================================================
# SETTINGS PLACEHOLDER ROUTES
# =========================================================

@app.route("/settings/profile")
def settings_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get_or_404(session["user_id"])

    return render_template(
        "settings_profile.html",
        user=user
    )
@app.route("/settings/notifications")
def settings_notifications():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get_or_404(session["user_id"])

    return render_template(
        "settings_notifications.html",
        user=user
    )

@app.route("/settings/security")
def settings_security():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return redirect(
        url_for("account_settings")
    )

@app.route("/settings/account", methods=["GET", "POST"])
def settings_account():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":

        action = request.form.get("action")

        # ==========================
        # UPDATE ACCOUNT
        # ==========================

        if action == "update_account":

            name = request.form.get(
                "name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip().lower()

            if not name:

                flash(
                    "Please enter your name.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            if not email:

                flash(
                    "Please enter your email address.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            existing_user = User.query.filter(
                User.email == email,
                User.id != user.id
            ).first()

            if existing_user:

                flash(
                    "That email address is already in use.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            user.name = name
            user.email = email

            try:

                db.session.commit()

                session["user_name"] = user.name

                flash(
                    "Account information updated successfully.",
                    "success"
                )

            except IntegrityError:

                db.session.rollback()

                flash(
                    "That email address is already in use.",
                    "warning"
                )

            except Exception:

                db.session.rollback()

                flash(
                    "Unable to update your account.",
                    "danger"
                )

            return redirect(
                url_for("settings_account")
            )


        # ==========================
        # CHANGE PASSWORD
        # ==========================

        if action == "change_password":

            current_password = request.form.get(
                "current_password",
                ""
            )

            new_password = request.form.get(
                "new_password",
                ""
            )

            confirm_password = request.form.get(
                "confirm_password",
                ""
            )

            if not current_password:

                flash(
                    "Please enter your current password.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            if not new_password:

                flash(
                    "Please enter a new password.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            if len(new_password) < 8:

                flash(
                    "Your new password must be at least 8 characters.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            if new_password != confirm_password:

                flash(
                    "The new passwords do not match.",
                    "warning"
                )

                return redirect(
                    url_for("settings_account")
                )

            if not bcrypt.check_password_hash(
                user.password,
                current_password
            ):

                flash(
                    "Your current password is incorrect.",
                    "danger"
                )

                return redirect(
                    url_for("settings_account")
                )

            user.password = bcrypt.generate_password_hash(
                new_password
            ).decode("utf-8")

            try:

                db.session.commit()

                flash(
                    "Password changed successfully.",
                    "success"
                )

            except Exception:

                db.session.rollback()

                flash(
                    "Unable to change your password.",
                    "danger"
                )

            return redirect(
                url_for("settings_account")
            )


    return render_template(
        "settings_account.html",
        user=user
    )

# =========================================================
# SETTINGS - EMAIL & SENDING
# =========================================================

@app.route("/settings/email")
def settings_email():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    user = User.query.get_or_404(user_id)

    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()

    if not email_settings:

        email_settings = EmailSettings(
            user_id=user_id,
            provider="SMTP",
            sender_name=user.name,
            sender_email=user.email,
            reply_to_email=user.email,
            smtp_host="",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_security="TLS",
            smtp_encryption="TLS"
        )

        db.session.add(email_settings)
        db.session.commit()

    return render_template(
        "settings_email.html",
        email_settings=email_settings,
        user=user
    )

def save_sender_settings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()

    if not email_settings:

        flash(
            "Email settings could not be found.",
            "danger"
        )

        return redirect(
            url_for("settings_email")
        )

    sender_name = request.form.get(
        "sender_name",
        ""
    ).strip()

    sender_email = request.form.get(
        "sender_email",
        ""
    ).strip().lower()

    reply_to_email = request.form.get(
        "reply_to_email",
        ""
    ).strip().lower()

    print("================================")
    print("SENDER FORM RECEIVED")
    print("sender_name:", repr(sender_name))
    print("sender_email:", repr(sender_email))
    print("reply_to_email:", repr(reply_to_email))
    print("================================")

    if not sender_name:

        flash(
            "Please enter a sender name.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not sender_email:

        flash(
            "Please enter a sender email address.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    email_settings.sender_name = sender_name

    email_settings.sender_email = sender_email

    email_settings.reply_to_email = reply_to_email

    db.session.commit()

    flash(
        "Sender details saved successfully.",
        "success"
    )

    return redirect(
        url_for("settings_email")
    )

@app.route(
    "/settings/email/smtp",
    methods=["POST"]
)
def save_smtp_settings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()

    if not email_settings:

        flash(
            "Email settings could not be found.",
            "danger"
        )

        return redirect(
            url_for("settings_email")
        )

    smtp_host = request.form.get(
        "smtp_host",
        ""
    ).strip()

    smtp_port = request.form.get(
        "smtp_port",
        "587"
    ).strip()

    smtp_username = request.form.get(
        "smtp_username",
        ""
    ).strip()

    smtp_password = request.form.get(
        "smtp_password",
        ""
    )

    smtp_encryption = request.form.get(
        "smtp_encryption",
        "TLS"
    ).strip()

    print("================================")
    print("SMTP FORM RECEIVED")
    print("smtp_host:", repr(smtp_host))
    print("smtp_port:", repr(smtp_port))
    print("smtp_username:", repr(smtp_username))
    print("smtp_password received:", bool(smtp_password))
    print("smtp_encryption:", repr(smtp_encryption))
    print("================================")

    if not smtp_host:

        flash(
            "Please enter an SMTP host.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not smtp_username:

        flash(
            "Please enter an SMTP username.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    try:

        smtp_port = int(smtp_port)

    except ValueError:

        flash(
            "SMTP port must be a number.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    email_settings.smtp_host = smtp_host

    email_settings.smtp_port = smtp_port

    email_settings.smtp_username = smtp_username

    if smtp_password:

        email_settings.smtp_password = smtp_password

    email_settings.smtp_encryption = smtp_encryption

    db.session.commit()

    print("================================")
    print("SMTP SETTINGS SAVED")
    print("saved host:", repr(email_settings.smtp_host))
    print("saved port:", email_settings.smtp_port)
    print("saved username:", repr(email_settings.smtp_username))
    print(
        "password saved:",
        bool(email_settings.smtp_password)
    )
    print("================================")

    flash(
        "SMTP settings saved successfully.",
        "success"
    )

    return redirect(
        url_for("settings_email")
    )

# =========================================================
# SETTINGS - TEST SMTP CONNECTION
# =========================================================

@app.route(
    "/settings/email/test-connection",
    methods=["POST"]
)
def test_email_smtp():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()

    if not email_settings:

        flash(
            "Please save your email settings first.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not email_settings.smtp_host:

        flash(
            "Please enter your SMTP host.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not email_settings.smtp_username:

        flash(
            "Please enter your SMTP username.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not email_settings.smtp_password:

        flash(
            "Please enter your SMTP password.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    success, message = test_smtp_connection(
        smtp_host=email_settings.smtp_host,
        smtp_port=email_settings.smtp_port,
        smtp_username=email_settings.smtp_username,
        smtp_password=email_settings.smtp_password,
        smtp_encryption=email_settings.smtp_encryption
    )

    if success:

        flash(
            message,
            "success"
        )

    else:

        flash(
            message,
            "danger"
        )

    return redirect(
        url_for("settings_email")
    )

@app.route(
    "/settings/email/send-test",
    methods=["POST"]
)
def send_settings_test_email():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Get the saved email settings
    email_settings = EmailSettings.query.filter_by(
        user_id=user_id
    ).first()

    if not email_settings:

        flash(
            "Please save your email settings first.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    # Make sure SMTP settings exist
    if not email_settings.smtp_host:

        flash(
            "Please enter your SMTP host first.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not email_settings.smtp_username:

        flash(
            "Please enter your SMTP username first.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    if not email_settings.smtp_password:

        flash(
            "Please enter your SMTP password first.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    # The test email will be sent to the
    # logged-in user's email address.
    recipient_email = email_settings.sender_email

    if not recipient_email:

        flash(
            "Please enter a sender email address first.",
            "warning"
        )

        return redirect(
            url_for("settings_email")
        )

    # Send the email
    success, message = send_email(

        smtp_host=email_settings.smtp_host,

        smtp_port=email_settings.smtp_port,

        smtp_username=email_settings.smtp_username,

        smtp_password=email_settings.smtp_password,

        smtp_encryption=email_settings.smtp_encryption,

        sender_name=email_settings.sender_name,

        sender_email=email_settings.sender_email,

        recipient_email=recipient_email,

        subject="EmailFlow Test Email",

        body=(
            "Hello!\n\n"
            "This is a test email from EmailFlow.\n\n"
            "Your SMTP connection is working correctly "
            "and EmailFlow can now send emails through "
            "your configured email provider.\n\n"
            "EmailFlow"
        ),

        reply_to_email=email_settings.reply_to_email
    )

    if success:

        flash(
            "Test email sent successfully! "
            "Check your inbox.",
            "success"
        )

    else:

        flash(
            message,
            "danger"
        )

    return redirect(
        url_for("settings_email")
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


with app.app_context():
    db.create_all()

    # Update existing database tables
    inspector = inspect(db.engine)

    # =====================================================
    # USER EMAIL VERIFICATION MIGRATION
    # =====================================================

    if "users" in inspector.get_table_names():

        existing_user_columns = {
            column["name"]
            for column in inspector.get_columns("users")
        }

        with db.engine.connect() as connection:

            # Add email_verified column
            if "email_verified" not in existing_user_columns:

                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN email_verified "
                        "BOOLEAN DEFAULT 1 NOT NULL"
                    )
                )

            # Add email_verified_at column
            if "email_verified_at" not in existing_user_columns:

                connection.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN email_verified_at "
                        "DATETIME"
                    )
                )

            connection.commit()


    # =====================================================
    # LANDING PAGE TABLE MIGRATION
    # =====================================================

    if "landing_pages" in inspector.get_table_names():

        existing_columns = {
            column["name"]
            for column in inspector.get_columns("landing_pages")
        }

        landing_page_columns = {
            "subheadline": "VARCHAR(500)",
            "description": "TEXT",
            "button_text": "VARCHAR(100)",
            "button_url": "VARCHAR(500)",
            "template_id": "INTEGER",
            "style": "VARCHAR(50) DEFAULT 'classic'",
            "background_color": "VARCHAR(20) DEFAULT '#f8fafc'",
            "headline_color": "VARCHAR(20) DEFAULT '#111827'",
            "button_color": "VARCHAR(20) DEFAULT '#4f46e5'",
            "button_text_color": "VARCHAR(20) DEFAULT '#ffffff'",
            "font_family": "VARCHAR(100) DEFAULT 'Arial'",
            "border_radius": "INTEGER DEFAULT 14",
        }

        with db.engine.connect() as connection:

            for column_name, column_type in landing_page_columns.items():

                if column_name not in existing_columns:

                    connection.execute(
                        text(
                            f"ALTER TABLE landing_pages "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )

            connection.commit()


    # =====================================================
    # TEMPLATE TABLE MIGRATION
    # =====================================================

    if "templates" in inspector.get_table_names():

        existing_template_columns = {
            column["name"]
            for column in inspector.get_columns("templates")
        }

        template_columns = {
            "category": "VARCHAR(100)",
            "html_content": "TEXT",
            "is_system_template": "BOOLEAN",
        }

        with db.engine.connect() as connection:

            for column_name, column_type in template_columns.items():

                if column_name not in existing_template_columns:

                    connection.execute(
                        text(
                            f"ALTER TABLE templates "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )

            connection.commit()


    # =====================================================
    # CONTACT UNSUBSCRIBE TABLE MIGRATION
    # =====================================================

    if "contacts" in inspector.get_table_names():

        existing_contact_columns = {
            column["name"]
            for column in inspector.get_columns("contacts")
        }

        contact_columns = {
            "unsubscribed": "BOOLEAN DEFAULT 0 NOT NULL",
            "unsubscribed_at": "DATETIME",
        }

        with db.engine.connect() as connection:

            for column_name, column_type in contact_columns.items():

                if column_name not in existing_contact_columns:

                    connection.execute(
                        text(
                            f"ALTER TABLE contacts "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )

            connection.commit()

    # =====================================================
    # SEED LANDING PAGE STARTING TEMPLATES
    # =====================================================

    if "landing_page_templates" in inspector.get_table_names():

        system_templates = [
            {
                "name": "Creator",
                "category": "Email Capture",
                "description": "A bold creator-focused signup page.",
                "style": "creator",
                "headline": "Be known for what you actually do.",
                "subheadline": "Build your audience and turn your ideas into something people remember.",
                "description_text": "Join the community and get useful ideas, updates and resources delivered to your inbox.",
                "button_text": "Subscribe",
            },
            {
                "name": "Studio",
                "category": "Business",
                "description": "A polished business-style landing page.",
                "style": "studio",
                "headline": "Build something people remember.",
                "subheadline": "A simple place to share your work, ideas and expertise.",
                "description_text": "Get practical insights, resources and updates from our studio.",
                "button_text": "Get Started",
            },
            {
                "name": "Newsletter",
                "category": "Email Capture",
                "description": "A clean newsletter signup page.",
                "style": "newsletter",
                "headline": "Get the ideas worth reading.",
                "subheadline": "A short, useful newsletter delivered straight to your inbox.",
                "description_text": "No spam. Just useful ideas, stories and resources.",
                "button_text": "Join the Newsletter",
            },
            {
                "name": "Product",
                "category": "Product Sales",
                "description": "A product-focused conversion page.",
                "style": "product",
                "headline": "Something worth sharing.",
                "subheadline": "Show people what you have built and give them a reason to take action.",
                "description_text": "Enter your details below to get access and receive updates.",
                "button_text": "Get Access",
            },
            {
                "name": "From Scratch",
                "category": "Blank",
                "description": "Start with a clean blank layout.",
                "style": "scratch",
                "headline": "Your headline goes here.",
                "subheadline": "Add a short description of your offer.",
                "description_text": "Tell your visitors why they should subscribe.",
                "button_text": "Subscribe",
            },
        ]

        for item in system_templates:

            existing = LandingPageTemplate.query.filter_by(
                name=item["name"],
                is_system_template=True
            ).first()

            if existing:
                # Refresh the official system template so old template
                # text from earlier versions cannot break the chooser.
                existing.category = item["category"]
                existing.description = item["description"]
                existing.style = item["style"]
                existing.headline = item["headline"]
                existing.subheadline = item["subheadline"]
                existing.description_text = item["description_text"]
                existing.button_text = item["button_text"]
            else:
                db.session.add(
                    LandingPageTemplate(
                        name=item["name"],
                        category=item["category"],
                        description=item["description"],
                        style=item["style"],
                        headline=item["headline"],
                        subheadline=item["subheadline"],
                        description_text=item["description_text"],
                        button_text=item["button_text"],
                        is_system_template=True,
                    )
                )

            # Add scheduled_at column to campaigns table
            if "campaigns" in inspector.get_table_names():

                campaign_columns = {
                    column["name"]
                    for column in inspector.get_columns("campaigns")
                }

                if "scheduled_at" not in campaign_columns:
                    with db.engine.connect() as connection:
                        connection.execute(
                            text(
                                "ALTER TABLE campaigns "
                                "ADD COLUMN scheduled_at DATETIME"
                            )
                        )

                        connection.commit()

        db.session.commit()

@app.route(
    "/unsubscribe/<token>",
    methods=["GET", "POST"]
)
def unsubscribe(token):

    serializer = URLSafeSerializer(
        app.secret_key,
        salt="emailflow-unsubscribe"
    )

    try:

        data = serializer.loads(token)

    except Exception:

        return render_template(
            "unsubscribe.html",
            error="This unsubscribe link is invalid or has expired."
        )

    contact_id = data.get("contact_id")

    if not contact_id:

        return render_template(
            "unsubscribe.html",
            error="This unsubscribe link is invalid."
        )

    contact = Contact.query.get(contact_id)

    if not contact:

        return render_template(
            "unsubscribe.html",
            error="We could not find this contact."
        )

    if request.method == "POST":

        if not contact.unsubscribed:

            contact.unsubscribed = True

            contact.unsubscribed_at = datetime.now(timezone.utc)

            db.session.commit()

        return render_template(
            "unsubscribe.html",
            success=True,
            contact=contact
        )

    return render_template(
        "unsubscribe.html",
        contact=contact,
        token=token
    )


@app.route(
    "/test-unsubscribe/<int:contact_id>"
)
def test_unsubscribe(contact_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    contact = Contact.query.filter_by(
        id=contact_id,
        created_by=session["user_id"]
    ).first_or_404()

    token = create_unsubscribe_token(
        contact.id
    )

    return redirect(
        url_for(
            "unsubscribe",
            token=token
        )
    )

scheduler = BackgroundScheduler()

scheduler.add_job(
    process_scheduled_campaigns,
    "interval",
    minutes=1,
    id="emailflow_scheduled_campaigns",
    replace_existing=True
)

scheduler.start()

if __name__ == "__main__":
    app.run(debug=True)
