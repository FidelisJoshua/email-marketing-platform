import smtplib

from email.message import EmailMessage


# =========================================================
# SMTP CONNECTION TEST
# =========================================================

def test_smtp_connection(
    smtp_host,
    smtp_port,
    smtp_username,
    smtp_password,
    smtp_encryption="TLS"
):
    """
    Test an SMTP server connection and authentication.

    Returns:
        (True, success_message)
        or
        (False, error_message)
    """

    if not smtp_host:
        return False, "SMTP host is required."

    if not smtp_username:
        return False, "SMTP username is required."

    if not smtp_password:
        return False, "SMTP password is required."

    try:

        smtp_port = int(smtp_port)

    except (TypeError, ValueError):

        return False, "SMTP port must be a valid number."


    try:

        encryption = (
            smtp_encryption or "TLS"
        ).upper().strip()


        # =================================================
        # SSL
        # =================================================

        if encryption == "SSL":

            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                timeout=20
            ) as server:

                server.login(
                    smtp_username,
                    smtp_password
                )


        # =================================================
        # NO ENCRYPTION
        # =================================================

        elif encryption in (
            "NONE",
            "PLAIN",
            "NO ENCRYPTION"
        ):

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=20
            ) as server:

                server.ehlo()

                server.login(
                    smtp_username,
                    smtp_password
                )


        # =================================================
        # TLS / STARTTLS
        # =================================================

        else:

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=20
            ) as server:

                server.ehlo()

                server.starttls()

                server.ehlo()

                server.login(
                    smtp_username,
                    smtp_password
                )


        return (
            True,
            "SMTP connection successful."
        )


    except smtplib.SMTPAuthenticationError:

        return (
            False,
            "SMTP authentication failed. "
            "Check your username and password."
        )


    except smtplib.SMTPConnectError:

        return (
            False,
            "Could not connect to the SMTP server."
        )


    except smtplib.SMTPServerDisconnected:

        return (
            False,
            "The SMTP server disconnected the connection."
        )


    except TimeoutError:

        return (
            False,
            "Connection to the SMTP server timed out."
        )


    except OSError as error:

        return (
            False,
            f"Network error: {error}"
        )


    except Exception as error:

        return (
            False,
            f"SMTP connection failed: {error}"
        )


# =========================================================
# SEND EMAIL
# =========================================================

def send_email(
    smtp_host,
    smtp_port,
    smtp_username,
    smtp_password,
    smtp_encryption,
    sender_name,
    sender_email,
    recipient_email,
    subject,
    body,
    reply_to_email=None
):
    """
    Send one email through the configured SMTP server.

    Returns:
        (True, success_message)
        or
        (False, error_message)
    """

    if not smtp_host:
        return False, "SMTP host is required."

    if not smtp_username:
        return False, "SMTP username is required."

    if not smtp_password:
        return False, "SMTP password is required."

    if not sender_email:
        return False, "Sender email is required."

    if not recipient_email:
        return False, "Recipient email is required."

    try:
        smtp_port = int(smtp_port)

    except (TypeError, ValueError):
        return False, "SMTP port must be a valid number."

    # =====================================================
    # BUILD EMAIL
    # =====================================================

    message = EmailMessage()

    message["Subject"] = subject

    message["From"] = (
        f"{sender_name} <{sender_email}>"
        if sender_name
        else sender_email
    )

    message["To"] = recipient_email

    if reply_to_email:
        message["Reply-To"] = reply_to_email

    message.set_content(
        "This email contains HTML content. "
        "Please view it in an HTML-compatible email client."
    )

    message.add_alternative(
        body,
        subtype="html"
    )

    # =====================================================
    # CONNECT AND SEND
    # =====================================================

    try:

        encryption = (
            smtp_encryption or "TLS"
        ).upper().strip()

        print("================================")
        print("EMAIL SEND STARTED")
        print("SMTP host:", smtp_host)
        print("SMTP port:", smtp_port)
        print("SMTP username:", smtp_username)
        print("Sender:", sender_email)
        print("Recipient:", recipient_email)
        print("Encryption:", encryption)
        print("================================")

        # =================================================
        # SSL
        # =================================================

        if encryption == "SSL":

            print("Connecting using SSL...")

            with smtplib.SMTP_SSL(
                smtp_host,
                smtp_port,
                timeout=60
            ) as server:

                print("SSL connection established.")

                print("Logging into SMTP server...")

                server.login(
                    smtp_username,
                    smtp_password
                )

                print("SMTP login successful.")

                print("Sending email...")

                server.send_message(message)

                print("Email sent successfully.")

        # =================================================
        # NO ENCRYPTION
        # =================================================

        elif encryption in (
            "NONE",
            "PLAIN",
            "NO ENCRYPTION"
        ):

            print("Connecting without encryption...")

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=60
            ) as server:

                print("SMTP connection established.")

                server.ehlo()

                print("Logging into SMTP server...")

                server.login(
                    smtp_username,
                    smtp_password
                )

                print("SMTP login successful.")

                print("Sending email...")

                server.send_message(message)

                print("Email sent successfully.")

        # =================================================
        # TLS / STARTTLS
        # =================================================

        else:

            print("Connecting using TLS / STARTTLS...")

            with smtplib.SMTP(
                smtp_host,
                smtp_port,
                timeout=60
            ) as server:

                print("SMTP connection established.")

                server.ehlo()

                print("Starting TLS...")

                server.starttls()

                server.ehlo()

                print("TLS connection established.")

                print("Logging into SMTP server...")

                server.login(
                    smtp_username,
                    smtp_password
                )

                print("SMTP login successful.")

                print("Sending email...")

                server.send_message(message)

                print("Email sent successfully.")

        print("================================")
        print("EMAIL SEND COMPLETE")
        print("================================")

        return (
            True,
            "Email sent successfully."
        )

    except smtplib.SMTPAuthenticationError:

        return (
            False,
            "SMTP authentication failed. "
            "Check your username and password."
        )

    except smtplib.SMTPRecipientsRefused:

        return (
            False,
            "The SMTP server rejected the recipient address."
        )

    except smtplib.SMTPSenderRefused:

        return (
            False,
            "The SMTP server rejected the sender address."
        )

    except smtplib.SMTPDataError as error:

        return (
            False,
            f"SMTP server rejected the email data: {error}"
        )

    except smtplib.SMTPConnectError:

        return (
            False,
            "Could not connect to the SMTP server."
        )

    except smtplib.SMTPServerDisconnected:

        return (
            False,
            "The SMTP server disconnected the connection."
        )

    except TimeoutError:

        return (
            False,
            "The SMTP server timed out while sending the email."
        )

    except OSError as error:

        return (
            False,
            f"Network error while sending email: {error}"
        )

    except Exception as error:

        return (
            False,
            f"Email sending failed: {error}"
        )