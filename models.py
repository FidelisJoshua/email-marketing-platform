from datetime import datetime
from extension import db

class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    def __repr__(self):
        return f"<Contact {self.email}>"

class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)

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
        default=datetime.utcnow,
        nullable=False
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    def __repr__(self):
        return f"<Campaign {self.subject}>"
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<User {self.email}>"

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

    sent_at = db.Column(
        db.DateTime,
        nullable=True
    )

    def __repr__(self):
        return f"<CampaignRecipient {self.campaign_id}-{self.contact_id}>"