import os
import time
from datetime import datetime, timezone

import pandas as pd
from flask import Flask, render_template, request, session, redirect, url_for, flash
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
    LandingPage
)
from email_service import send_email


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = "my_super_secret_key"

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# =========================================================
# INITIALIZE EXTENSIONS
# =========================================================

bcrypt = Bcrypt(app)

db.init_app(app)


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

            return redirect(url_for("register"))

        hashed_password = (
            bcrypt
            .generate_password_hash(password)
            .decode("utf-8")
        )

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

            flash(
                "Registration successful. Please log in.",
                "success"
            )

            return redirect(url_for("login"))

        except IntegrityError:

            db.session.rollback()

            flash(
                "An account with this email already exists.",
                "warning"
            )

            return redirect(url_for("register"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

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

        session["user_id"] = user.id

        session["user_name"] = user.name

        return redirect(url_for("dashboard"))

    return render_template("login.html")


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

@app.route(
    "/campaigns",
    methods=["GET", "POST"]
)
def campaigns():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]

    if request.method == "POST":

        subject = request.form.get(
            "subject",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        if not subject or not message:

            flash(
                "Subject and message are required.",
                "warning"
            )

            return redirect(
                url_for("campaigns")
            )

        new_campaign = Campaign(
            subject=subject,
            message=message,
            created_by=user_id
        )

        db.session.add(new_campaign)

        db.session.commit()

        # -------------------------------------------------
        # CREATE RECIPIENT RECORDS
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

            db.session.add(recipient)

        db.session.commit()

        flash(
            "Campaign created successfully.",
            "success"
        )

        return redirect(
            url_for("campaigns")
        )

    campaign_list = Campaign.query.filter_by(
        created_by=user_id
    ).order_by(
        Campaign.created_at.desc()
    ).all()

    return render_template(
        "campaigns.html",
        campaigns=campaign_list
    )


# =========================================================
# PREVIEW CAMPAIGN
# =========================================================

@app.route(
    "/campaign/<int:campaign_id>"
)
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


# =========================================================
# SEND TEST EMAIL
# =========================================================

@app.route(
    "/campaign/<int:campaign_id>/test"
)
def send_test_email(campaign_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=session["user_id"]
    ).first_or_404()

    try:

        send_email(
            subject=campaign.subject,
            body=campaign.message,
            recipient="officialfizzlefit@gmail.com"
        )

        flash(
            "Test email sent successfully!",
            "success"
        )

    except Exception as e:

        flash(
            f"Test email failed: {e}",
            "danger"
        )

    return redirect(
        url_for("preview_campaign", campaign_id=campaign.id)
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

        return redirect(url_for("login"))

    user_id = session["user_id"]

    campaign = Campaign.query.filter_by(
        id=campaign_id,
        created_by=user_id
    ).first_or_404()

    # -----------------------------------------------------
    # PREVENT DUPLICATE CAMPAIGN RUNS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # GET PENDING RECIPIENTS
    # -----------------------------------------------------

    recipients = CampaignRecipient.query.filter_by(
        campaign_id=campaign.id,
        status="Pending"
    ).all()

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

    # -----------------------------------------------------
    # SEND TO EACH RECIPIENT
    # -----------------------------------------------------

    for recipient in recipients:

        contact = db.session.get(
            Contact,
            recipient.contact_id
        )

        # -------------------------------------------------
        # CONTACT NO LONGER EXISTS
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

                send_email(
                    subject=campaign.subject,
                    body=campaign.message,
                    recipient=contact.email
                )

                recipient.status = "Sent"

                recipient.sent_at = datetime.now(
                    timezone.utc
                )

                db.session.commit()

                sent += 1

                success = True

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

    # -----------------------------------------------------
    # UPDATE CAMPAIGN TOTALS
    # -----------------------------------------------------

    campaign.sent_count += sent

    campaign.failed_count += failed

    # -----------------------------------------------------
    # CHECK REMAINING
    # -----------------------------------------------------

    remaining = CampaignRecipient.query.filter_by(
        campaign_id=campaign.id,
        status="Pending"
    ).count()

    if remaining == 0:

        campaign.status = "Sent"

    else:

        campaign.status = "Draft"

    db.session.commit()

    print("")

    print("=" * 60)

    print("🏁 CAMPAIGN RUN FINISHED")

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

    # -----------------------------------------------------
    # USER MESSAGE
    # -----------------------------------------------------

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


# =========================================================
# FORMS
# =========================================================

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
        # -------------------------------------------------

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
def preview_form(form_id):

    if "user_id" not in session:

        return redirect(url_for("login"))

    form = Form.query.filter_by(
        id=form_id,
        created_by=session["user_id"]
    ).first_or_404()

    return render_template(
        "form_preview.html",
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
# LOGOUT
# =========================================================

# =========================================================
# LANDING PAGES
# =========================================================

@app.route("/landing-pages")
def landing_pages():

    # User must be logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Get only landing pages belonging to this user
    landing_pages_list = LandingPage.query.filter_by(
        created_by=session["user_id"]
    ).order_by(
        LandingPage.created_at.desc()
    ).all()

    return render_template(
        "landing_pages.html",
        landing_pages=landing_pages_list
    )


# =========================================================
# CREATE LANDING PAGE
# =========================================================

@app.route("/landing-pages/create", methods=["GET", "POST"])
def create_landing_page():

    # User must be logged in
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

        subheadline = request.form.get(
            "subheadline",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        button_text = request.form.get(
            "button_text",
            "Get Started"
        ).strip()

        button_url = request.form.get(
            "button_url",
            ""
        ).strip()

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not name:

            flash(
                "Please enter a landing page name.",
                "warning"
            )

            return redirect(
                url_for("create_landing_page")
            )

        if not headline:

            flash(
                "Please enter a headline.",
                "warning"
            )

            return redirect(
                url_for("create_landing_page")
            )

        if not button_text:

            button_text = "Get Started"

        # -------------------------------------------------
        # CREATE LANDING PAGE
        # -------------------------------------------------

        new_landing_page = LandingPage(
            name=name,
            headline=headline,
            subheadline=subheadline,
            description=description,
            button_text=button_text,
            button_url=button_url,
            created_by=session["user_id"]
        )

        db.session.add(new_landing_page)
        db.session.commit()

        flash(
            "Landing page created successfully!",
            "success"
        )

        return redirect(
            url_for("landing_pages")
        )

    return render_template(
        "create_landing_page.html"
    )

@app.route("/landing-pages/<int:landing_page_id>/edit", methods=["GET", "POST"])
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
        button_text = request.form.get("button_text", "Get Started").strip() or "Get Started"
        button_url = request.form.get("button_url", "").strip()

        if not name:
            flash("Please enter a landing page name.", "warning")
            return redirect(url_for("edit_landing_page", landing_page_id=landing_page.id))

        if not headline:
            flash("Please enter a headline.", "warning")
            return redirect(url_for("edit_landing_page", landing_page_id=landing_page.id))

        landing_page.name = name
        landing_page.headline = headline
        landing_page.subheadline = subheadline
        landing_page.description = description
        landing_page.button_text = button_text
        landing_page.button_url = button_url

        db.session.commit()

        flash("Landing page updated successfully!", "success")

        return redirect(
            url_for(
                "edit_landing_page",
                landing_page_id=landing_page.id
            )
        )

    return render_template(
        "edit_landing_page.html",
        landing_page=landing_page
    )


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

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


with app.app_context():
    db.create_all()

    # Update existing LandingPage table
    inspector = inspect(db.engine)

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

if __name__ == "__main__":
    app.run(debug=True)