from datetime import datetime, UTC

from extension import db


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

    email_verified = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    email_verified_at = db.Column(
        db.DateTime,
        nullable=True
    )

    def __repr__(self):
        return f"<User {self.email}>"

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

    unsubscribed = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    unsubscribed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    __table_args__ = (
        db.UniqueConstraint(
            "email",
            "created_by",
            name="unique_contact_per_user"
        ),
    )

    def __repr__(self):
        return f"<Contact {self.email}>"

class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
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


class CampaignRecipient(db.Model):
    __tablename__ = "campaign_recipients"

    id = db.Column(db.Integer, primary_key=True)
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
    sent_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<CampaignRecipient {self.campaign_id}-{self.contact_id}>"


class Form(db.Model):
    __tablename__ = "forms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    headline = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
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


class LandingPageTemplate(db.Model):
    __tablename__ = "landing_page_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(
        db.String(100),
        nullable=False,
        default="General"
    )
    description = db.Column(db.Text, nullable=True)
    style = db.Column(
        db.String(50),
        nullable=False,
        default="classic"
    )
    headline = db.Column(db.String(255), nullable=False)
    subheadline = db.Column(db.String(500), nullable=True)
    description_text = db.Column(db.Text, nullable=True)
    button_text = db.Column(
        db.String(100),
        nullable=False,
        default="Get Started"
    )
    is_system_template = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.now(UTC),
        nullable=False
    )

    def __repr__(self):
        return f"<LandingPageTemplate {self.name}>"


class LandingPage(db.Model):
    __tablename__ = "landing_pages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    headline = db.Column(db.String(255), nullable=False)
    subheadline = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    button_text = db.Column(
        db.String(100),
        default="Get Started",
        nullable=False
    )
    button_url = db.Column(db.String(500), nullable=True)

    form_id = db.Column(
        db.Integer,
        db.ForeignKey("forms.id"),
        nullable=False
    )

    template_id = db.Column(
        db.Integer,
        db.ForeignKey("landing_page_templates.id"),
        nullable=True
    )

    style = db.Column(
        db.String(50),
        nullable=False,
        default="classic"
    )

    background_color = db.Column(
        db.String(20),
        nullable=False,
        default="#f8fafc"
    )

    headline_color = db.Column(
        db.String(20),
        nullable=False,
        default="#111827"
    )

    button_color = db.Column(
        db.String(20),
        nullable=False,
        default="#4f46e5"
    )

    button_text_color = db.Column(
        db.String(20),
        nullable=False,
        default="#ffffff"
    )

    font_family = db.Column(
        db.String(100),
        nullable=False,
        default="Arial"
    )

    border_radius = db.Column(
        db.Integer,
        nullable=False,
        default=14
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
        return f"<LandingPage {self.name}>"


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(
        db.String(100),
        nullable=False,
        default="General"
    )
    html_content = db.Column(db.Text, nullable=True)
    is_system_template = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )
    created_at = db.Column(
        db.DateTime,
        default=datetime.now(UTC),
        nullable=False
    )

    def __repr__(self):
        return f"<Template {self.name}>"


class EmailSettings(db.Model):
    __tablename__ = "email_settings"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True
    )

    sender_name = db.Column(
        db.String(150),
        nullable=True
    )

    sender_email = db.Column(
        db.String(255),
        nullable=True
    )

    reply_to_email = db.Column(
        db.String(255),
        nullable=True
    )

    smtp_host = db.Column(
        db.String(255),
        nullable=True
    )

    smtp_port = db.Column(
        db.Integer,
        nullable=True
    )

    smtp_username = db.Column(
        db.String(255),
        nullable=True
    )

    smtp_password = db.Column(
        db.String(255),
        nullable=True
    )

    smtp_encryption = db.Column(
        db.String(20),
        nullable=True,
        default="TLS"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.now(UTC),
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(UTC),
        onupdate=datetime.now(UTC),
        nullable=False
    )

    def __repr__(self):
        return f"<EmailSettings {self.sender_email}>"