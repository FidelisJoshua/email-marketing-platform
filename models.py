from datetime import datetime, UTC

from extension import db


# =========================================================
# USER
# =========================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )

    def __repr__(self):
        return f"<User {self.email}>"


# =========================================================
# CONTACT
# =========================================================

class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        nullable=False
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # A user cannot have the same email twice.
    # Different users can have the same email.
    __table_args__ = (
        db.UniqueConstraint(
            "email",
            "created_by",
            name="unique_contact_per_user"
        ),
    )

    def __repr__(self):
        return f"<Contact {self.email}>"


# =========================================================
# CAMPAIGN
# =========================================================

class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    subject = db.Column(
        db.String(255),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="Draft",
        nullable=False
    )

    sent_count = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    failed_count = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.now(UTC),
        nullable=False
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    def __repr__(self):
        return f"<Campaign {self.subject}>"


# =========================================================
# CAMPAIGN RECIPIENT
# =========================================================

class CampaignRecipient(db.Model):
    __tablename__ = "campaign_recipients"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    campaign_id = db.Column(
        db.Integer,
        db.ForeignKey("campaigns.id"),
        nullable=False
    )

    contact_id = db.Column(
        db.Integer,
        db.ForeignKey("contacts.id"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    sent_at = db.Column(
        db.DateTime,
        nullable=True
    )

    def __repr__(self):
        return (
            f"<CampaignRecipient "
            f"{self.campaign_id}-{self.contact_id}>"
        )


# =========================================================
# FORM
# =========================================================

class Form(db.Model):
    __tablename__ = "forms"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    headline = db.Column(
        db.String(255),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    button_text = db.Column(
        db.String(100),
        default="Subscribe",
        nullable=False
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.now(UTC),
        nullable=False
    )

    def __repr__(self):
        return f"<Form {self.name}>"


# =========================================================
# LANDING PAGE

class LandingPage(db.Model):
    __tablename__ = "landing_pages"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    headline = db.Column(
        db.String(255),
        nullable=False
    )

    subheadline = db.Column(
        db.String(500),
        nullable=True
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    button_text = db.Column(
        db.String(100),
        default="Get Started",
        nullable=False
    )

    button_url = db.Column(
        db.String(500),
        nullable=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<LandingPage {self.name}>"