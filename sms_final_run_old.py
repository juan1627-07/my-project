import requests
import mysql.connector
import time
import re

from datetime import datetime

# PhilSMS API Configuration
API_URL = "https://app.philsms.com/api/v3/sms/send"
API_TOKEN = "1472|Byhr6qlWfESA1okRrL3iTsnKiWFQ37AQpSdi3xAn"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Database Configuration for comcenter
DB_CONFIG_COMCENTER = {
    "host": "192.168.0.200",
    "user": "root",
    "password": "",
    "database": "comcenter",
    "port": 3306,
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
    "connect_timeout": 10  # Prevents freezing
}

# Database Configuration for sms_db
DB_CONFIG_SMS = {
    "host": "192.168.0.200",
    "user": "root",
    "password": "",
    "database": "sms_db",
    "port": 3306,
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
    "connect_timeout": 10  # Prevents freezing
}

# Fixed recipient numbers (Only these numbers will receive the SMS)
RECIPIENT_NUMBER = ["+639353767468", "+639208732901"]

# 🕒 Mark messages as inactive if still pending after 30 minutes
def mark_old_messages_inactive():
    try:
        db = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor = db.cursor()
        cursor.execute("""
            UPDATE sms_queue 
            SET status = 'inactive' 
            WHERE status = 'pending' 
            AND created_at < NOW() - INTERVAL 1 HOUR;
        """)
        db.commit()
        db.close()
        print("Old messages marked as inactive. \n ", flush=True)
    except mysql.connector.Error as e:
        print(f"Database Error: {e}", flush=True)


# 📩 Fetch a pending SMS with lock to prevent duplication
def fetch_pending_sms():
    try:
        db = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor = db.cursor()

        # Lock the record to ensure only one process can fetch and send this message
        cursor.execute("""
            UPDATE sms_queue
            SET status = 'in_progress'
            WHERE status = 'pending' 
            AND created_at >= NOW() - INTERVAL 30 MINUTE
            ORDER BY created_at DESC 
            LIMIT 1;
        """)
        db.commit()  # Commit the update (locking the record)

        cursor.execute("""
            SELECT id, message FROM sms_queue 
            WHERE status = 'in_progress'
            ORDER BY created_at DESC 
            LIMIT 1;
        """)
        sms_record = cursor.fetchone()
        db.close()

        return {"id": sms_record[0], "message": sms_record[1]} if sms_record else None
    except mysql.connector.Error as e:
        print(f"❌ Database Error: {e}", flush=True)
        return None


# ✅ Update SMS status after sending
def update_sms_status(sms_id):
    try:
        db = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor = db.cursor()
        cursor.execute("UPDATE sms_queue SET status = 'sent' WHERE id = %s", (sms_id,))
        db.commit()
        db.close()
        print(f"SMS ID {sms_id} marked as sent.", flush=True)
    except mysql.connector.Error as e:
        print(f"Database Update Error: {e}", flush=True)


# 📤 Send SMS
# 📤 Send SMS with status check to avoid duplicate sending
EXCLUDED_NUMBERS = ["+639177705044"]  # Add more if needed

def send_sms(sms_id, message):
    db = mysql.connector.connect(**DB_CONFIG_SMS)
    cursor = db.cursor()

    # Step 1: Check the current status of the message before sending
    cursor.execute("SELECT status FROM sms_queue WHERE id = %s", (sms_id,))
    status = cursor.fetchone()

    if status and status[0] == 'in_progress':
        # Step 2: Filter recipients and exclude specified numbers
        filtered_recipients = [num for num in RECIPIENT_NUMBER if num not in EXCLUDED_NUMBERS]

        if not filtered_recipients:
            print("No recipients to send to after exclusions. Skipping SMS.")
            db.close()
            return

        recipients = ",".join(filtered_recipients)
        print(f"Debug: Sending SMS to recipients: {recipients}")  # Log the recipients

        payload = {
            "sender_id": "PhilSMS",
            "recipient": recipients,
            "message": message
        }

        try:
            print(f"Sending SMS ID {sms_id}...", flush=True)
            response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=10)

            if response.status_code == 200:
                update_sms_status(sms_id)
            else:
                print(f"Failed to send SMS: {response.text}", flush=True)
        except requests.Timeout:
            print("Timeout Error: PhilSMS API did not respond within 10 seconds.", flush=True)
        except requests.RequestException as e:
            print(f"Network Error: {e}", flush=True)

    db.close()



# 📝 Fetch and Insert Data from comcenter to sms_db
def fetch_and_insert_data():
    try:
        db_comcenter = mysql.connector.connect(**DB_CONFIG_COMCENTER)
        cursor_comcenter = db_comcenter.cursor()

        cursor_comcenter.execute("""
            SELECT CallLog_ID, Type_Emergency_ID, Brgy_ID, Remarks, Date_Log 
            FROM comcenter.fed_call_log
            WHERE Type_Emergency_ID IN (68, 44, 62, 46, 57, 86, 159, 9, 160, 161)
            ORDER BY Date_Log DESC
            LIMIT 10;
        """)
        records = cursor_comcenter.fetchall()
        db_comcenter.close()

        db_sms = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor_sms = db_sms.cursor()

        for record in records:
            calllog_id, type_emergency_id, brgy_id, remarks, date_log = record

            cursor_sms.execute("SELECT COUNT(*) FROM fed_call_log WHERE CallLog_ID = %s", (calllog_id,))
            if cursor_sms.fetchone()[0] == 0:
                cursor_sms.execute("""
                    INSERT INTO fed_call_log (CallLog_ID, Type_Emergency_ID, Barangay, Remarks, Date_Log, Status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """, (calllog_id, type_emergency_id, brgy_id, remarks, date_log))

        db_sms.commit()
        db_sms.close()

        # ✅ Update remarks if changed
        update_remarks_if_changed()

    except mysql.connector.Error as e:
        print(f"Database Error: {e}", flush=True)


# 🔄 Update remarks if changed
def update_remarks_if_changed():
    try:
        db_comcenter = mysql.connector.connect(**DB_CONFIG_COMCENTER)
        cursor_comcenter = db_comcenter.cursor()

        db_sms = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor_sms = db_sms.cursor()

        cursor_comcenter.execute("""
            SELECT CallLog_ID, Remarks FROM comcenter.fed_call_log
            WHERE Type_Emergency_ID IN (68, 44, 62, 46, 57, 86, 159, 9, 160, 161)
        """)
        comcenter_data = cursor_comcenter.fetchall()

        for calllog_id, comcenter_remarks in comcenter_data:
            cursor_sms.execute("SELECT Remarks FROM fed_call_log WHERE CallLog_ID = %s", (calllog_id,))
            result = cursor_sms.fetchone()

            if result:
                sms_remarks = result[0]

                if sms_remarks.strip() != comcenter_remarks.strip():
                    cursor_sms.execute("""
                        UPDATE fed_call_log 
                        SET Remarks = %s, Status = 'pending'
                        WHERE CallLog_ID = %s
                    """, (comcenter_remarks, calllog_id))

        db_sms.commit()
        db_sms.close()
        db_comcenter.close()
        print("Remarks updated & status reset to pending for updated entries.", flush=True)

    except mysql.connector.Error as e:
        print(f"Database Error: {e}", flush=True)


# 🔁 Main Loop
def main():
    try:
        while True:
            print("Running SMS Processing Loop...", flush=True)
            fetch_and_insert_data()
            mark_old_messages_inactive()
            sms_data = fetch_pending_sms()

            if sms_data:
                send_sms(sms_data["id"], sms_data["message"])

            time.sleep(10)
    except KeyboardInterrupt:
        print("\n Script stopped by user. Exiting gracefully...", flush=True)


if __name__ == "__main__":
    main()
