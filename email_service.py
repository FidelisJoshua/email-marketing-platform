import smtplib
from email.mime.text import MIMEText


import smtplib
from email.mime.text import MIMEText


def send_email(subject, body, recipient):

    sender = "joshuafidelisk@gmail.com"
    password = "ilfxdtpvoyknoufo"

    message = MIMEText(body, "plain")
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    print("1. Connecting to Gmail...")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:

        print("2. Connected")

        server.ehlo()

        print("3. Starting TLS...")

        server.starttls()

        server.ehlo()

        print("4. Logging in...")

        server.login(sender, password)

        print("5. Sending email...")

        server.send_message(message)

        print("6. Email sent!")

    return True