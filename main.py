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
FROM_EMAIL = os.environ.get("FROM_EMAIL", "astelpauly2002@gmail.com")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "ewpfefvucsamzqvp")

EMAILS_PER_DAY = 20
INTERVAL_MINUTES = 1
START_HOUR = 9
END_HOUR = 19   # 7 PM

# ==========================
# FLASK SERVER
# ==========================
app = Flask(__name__)

@app.route("/")
def home():
    return "Email Scheduler is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==========================
# SCHEDULER HELPERS
# ==========================
def is_valid_time():
    now = datetime.now()
    print(f"[TIME CHECK] Now: {now}")
    if now.weekday() > 4:
        print("[TIME CHECK] Weekend detected. Scheduler paused.")
        return False
    if not (START_HOUR <= now.hour < END_HOUR):
        print(f"[TIME CHECK] Outside working hours ({START_HOUR}-{END_HOUR}). Scheduler paused.")
        return False
    return True

def get_today_sent_count():
    today = datetime.now().date()
    print(f"[COUNT CHECK] Counting emails sent today: {today}")
    try:
        result = supabase.table("email_events") \
            .select("id,event_type,flag_sent,modified_at") \
            .eq("flag_sent", True) \
            .gte("modified_at", str(today)) \
            .execute()
        count = len(result.data) if result.data else 0
        print(f"[COUNT CHECK] Emails sent today: {count}")
        return count
    except Exception as e:
        print(f"[COUNT CHECK] Error fetching sent emails: {e}")
        return 0

# ==========================
# GET NEXT UNSENT EVENT + LOGS
# ==========================
def get_next_unsent_event():
    print("[EVENT FETCH] Fetching next unsent email event...")
    try:
        event_result = supabase.table("email_events") \
            .select("*") \
            .eq("flag_sent", False) \
            .limit(1) \
            .execute()
        print(f"[EVENT FETCH] Raw event data: {event_result.data}")

        if not event_result.data:
            print("[EVENT FETCH] No pending email events found.")
            return None

        event = event_result.data[0]
        campaign_id = event.get("campaign_id")
        lead_id = event.get("lead_id")
        print(f"[EVENT FETCH] Event ID: {event.get('id')}, Campaign ID: {campaign_id}, Lead ID: {lead_id}")

        # Fetch email content
        content_result = supabase.table("email_contents") \
            .select("*") \
            .eq("campaign_id", campaign_id) \
            .limit(1) \
            .execute()
        print(f"[CONTENT FETCH] Raw content data: {content_result.data}")
        if not content_result.data:
            print(f"[CONTENT FETCH] No email content for campaign {campaign_id}")
            return None
        email_content = content_result.data[0]

        # Fetch lead info
        lead_result = supabase.table("leads") \
            .select("*") \
            .eq("id", lead_id) \
            .eq("campaign_id", campaign_id) \
            .limit(1) \
            .execute()
        print(f"[LEAD FETCH] Raw lead data: {lead_result.data}")
        if not lead_result.data:
            print(f"[LEAD FETCH] No lead found with ID {lead_id} for campaign {campaign_id}")
            return None
        lead = lead_result.data[0]

        return {
            "event_id": event["id"],
            "campaign_id": campaign_id,
            "lead_id": lead_id,
            "user_id": lead.get("user_id"),
            "lead_name": lead.get("name"),
            "lead_email": lead.get("email"),
            "subject": email_content.get("subject"),
            "content": email_content.get("content"),
            "redirect_url": email_content.get("redirect_url", ""),
        }

    except Exception as e:
        print(f"[EVENT FETCH] Error: {e}")
        return None

# ==========================
# SEND EMAIL WITH LOGS
# ==========================
def send_email(data):
    try:
        print(f"[SEND EMAIL] Preparing email for {data['lead_email']}")
        pixel_url = f"{BACKEND_URL}/track?u={data['user_id']}&c={data['campaign_id']}&l={data['lead_id']}"
        click_url = f"{BACKEND_URL}/click?u={data['user_id']}&c={data['campaign_id']}&l={data['lead_id']}&redirect={data['redirect_url']}"

        html_content = f"""
        <html>
            <body>
                <p>Dear {data['lead_name']},</p>
                <p>{data['content']}</p>
                <p><a href="{click_url}">Click here for more details</a></p>
                <img src="{pixel_url}" width="1" height="1" />
            </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = data['subject']
        msg["From"] = FROM_EMAIL
        msg["To"] = data['lead_email']
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(FROM_EMAIL, APP_PASSWORD)
            server.sendmail(FROM_EMAIL, data['lead_email'], msg.as_string())

        print(f"[SEND EMAIL] Email sent to {data['lead_email']}")

        # Mark event as sent
        supabase.table("email_events") \
            .update({"flag_sent": True}) \
            .eq("id", data["event_id"]) \
            .execute()
        print(f"[SEND EMAIL] Event {data['event_id']} marked as sent.")

    except Exception as e:
        print(f"[SEND EMAIL] Error sending email: {e}")

# ==========================
# RUN SCHEDULER
# ==========================
def run_scheduler():
    while True:
        try:
            print("\n[SCHEDULER] Checking for emails at", datetime.now())
            if not is_valid_time():
                time.sleep(60)
                continue

            sent_today = get_today_sent_count()
            if sent_today >= EMAILS_PER_DAY:
                print(f"[SCHEDULER] Daily limit ({EMAILS_PER_DAY}) reached")
                time.sleep(600)
                continue

            data = get_next_unsent_event()
            if data:
                send_email(data)
            else:
                print("[SCHEDULER] No pending emails to send.")

            time.sleep(INTERVAL_MINUTES * 60)

        except Exception as e:
            print(f"[SCHEDULER] Unexpected error: {e}")
            time.sleep(60)

# ==========================
# MAIN
# ==========================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_scheduler()