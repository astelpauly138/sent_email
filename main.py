# main.py
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from supabase_client import supabase
import os
import threading
from flask import Flask

# ==========================
# CONFIG
# ==========================
BACKEND_URL = "https://email-tracking-0au6.onrender.com"
FROM_EMAIL = os.environ.get("FROM_EMAIL", "your-email@gmail.com")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "your-app-password")

EMAILS_PER_DAY = 20
INTERVAL_MINUTES = 1
START_HOUR = 9
END_HOUR = 19   # 7 PM

# ==========================
# FLASK SERVER TO KEEP RENDER HAPPY
# ==========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Email Scheduler is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))  # Render sets $PORT automatically
    app.run(host="0.0.0.0", port=port)

# ==========================
# SCHEDULER FUNCTIONS
# ==========================
def is_valid_time():
    now = datetime.now()
    if now.weekday() > 4:  # Mon-Fri only
        return False
    if not (START_HOUR <= now.hour < END_HOUR):
        return False
    return True

def get_today_sent_count():
    today = datetime.now().date()
    result = supabase.table("email_events") \
        .select("id") \
        .eq("flag_sent", True) \
        .eq("event_type", "sent") \
        .gte("modified_at", str(today)) \
        .execute()
    return len(result.data) if result.data else 0

def get_next_unsent_event():
    result = supabase.table("email_events") \
        .select("*") \
        .eq("event_type", "sent") \
        .eq("flag_sent", False) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None

def send_email(event):
    campaign_id = event["campaign_id"]
    lead_id = event["lead_id"]
    user_id = event["user_id"]

    lead = supabase.table("leads") \
        .select("*") \
        .eq("id", lead_id) \
        .single() \
        .execute().data

    email_content = supabase.table("email_contents") \
        .select("*") \
        .eq("campaign_id", campaign_id) \
        .limit(1) \
        .execute().data[0]

    name = lead["name"]
    to_email = lead["email"]
    subject = email_content["subject"]
    content = email_content["content"]
    redirect_url = email_content["redirect_url"]

    pixel_url = f"{BACKEND_URL}/track?u={user_id}&c={campaign_id}&l={lead_id}"
    click_url = f"{BACKEND_URL}/click?u={user_id}&c={campaign_id}&l={lead_id}&redirect={redirect_url}"

    html_content = f"""
    <html>
        <body>
            <p>Dear {name},</p>
            <p>{content}</p>
            <p><a href="{click_url}">Click here for more details</a></p>
            <img src="{pixel_url}" width="1" height="1" />
        </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(FROM_EMAIL, APP_PASSWORD)
        server.sendmail(FROM_EMAIL, to_email, msg.as_string())

    print(f"Email sent to {to_email}")

    supabase.table("email_events") \
        .update({"flag_sent": True}) \
        .eq("id", event["id"]) \
        .execute()

def run_scheduler():
    while True:
        try:
            if not is_valid_time():
                time.sleep(60)
                continue

            sent_today = get_today_sent_count()
            if sent_today >= EMAILS_PER_DAY:
                print("Daily limit reached")
                time.sleep(600)
                continue

            event = get_next_unsent_event()
            if event:
                send_email(event)
            else:
                print("No pending emails")

            time.sleep(INTERVAL_MINUTES * 60)

        except Exception as e:
            print("Error:", e)
            time.sleep(60)

# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    # Start Flask server in a separate thread (port required for Render)
    threading.Thread(target=run_flask).start()
    # Start your email scheduler
    run_scheduler()