import sqlite3
import os

DATABASE = "instance/database.db"

if not os.path.exists(DATABASE):
    print("❌ Database not found.")
    print(f"Expected location: {DATABASE}")
    exit()

connection = sqlite3.connect(DATABASE)
cursor = connection.cursor()

print("🔧 Updating contacts table...")

# Create a new contacts table without the global UNIQUE constraint
cursor.execute("""
    CREATE TABLE contacts_new (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(120) NOT NULL,
        created_by INTEGER NOT NULL,
        FOREIGN KEY (created_by) REFERENCES users(id),
        UNIQUE(email, created_by)
    )
""")

# Copy existing contacts
cursor.execute("""
    INSERT INTO contacts_new (
        id,
        name,
        email,
        created_by
    )
    SELECT
        id,
        name,
        email,
        created_by
    FROM contacts
""")

# Remove old table
cursor.execute("""
    DROP TABLE contacts
""")

# Rename new table
cursor.execute("""
    ALTER TABLE contacts_new
    RENAME TO contacts
""")

connection.commit()
connection.close()

print("✅ Database updated successfully!")
print("✅ Global email uniqueness removed.")
print("✅ Email uniqueness is now per user.")