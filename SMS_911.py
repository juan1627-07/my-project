import requests
import mysql.connector
import time
import re

from datetime import datetime

# PhilSMS API Configuration
API_URL = "https://app.philsms.com/api/v3/sms/send"
API_TOKEN = "1597|lOvd3aIwr1XJtC0KI5EzdKW4HcHuL6G9GpEBENf9"
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
    "connect_timeout": 10
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
    "connect_timeout": 10
}

# 🔄 Get recipient numbers from sms_db.recipient_list
def get_recipient_numbers():
    try:
        db = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor = db.cursor()
        cursor.execute("SELECT phone_number FROM recipient_list")
        recipients = [row[0] for row in cursor.fetchall()]
        db.close()
        return recipients
    except mysql.connector.Error as e:
        print(f"Error fetching recipients: {e}", flush=True)
        return []

# 🕒 Mark messages as inactive if still pending after 1 hour
def mark_old_messages_inactive():
    try:
        db = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor = db.cursor()
        cursor.execute("""
            UPDATE sms_queue 
            SET status = 'inactive' 
            WHERE (status = 'pending' OR status = 'in_progress')
            AND created_at < NOW() - INTERVAL 1 HOUR;
        """)
        db.commit()
        db.close()
        print("Old messages marked as inactive.\n", flush=True)
    except mysql.connector.Error as e:
        print(f"Database Error: {e}", flush=True)

# 📩 Fetch a pending SMS with lock to prevent duplication
def fetch_pending_sms():
    try:
        db = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor = db.cursor()
        cursor.execute("""
            UPDATE sms_queue
            SET status = 'in_progress'
            WHERE status = 'pending' 
            AND created_at >= NOW() - INTERVAL 30 MINUTE
            ORDER BY created_at DESC 
            LIMIT 1;
        """)
        db.commit()
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

def send_sms(sms_id, message, recipients):
    db = mysql.connector.connect(**DB_CONFIG_SMS)
    cursor = db.cursor()

    # Step 1: Check the current status of the message before sending
    cursor.execute("SELECT status FROM sms_queue WHERE id = %s", (sms_id,))
    status = cursor.fetchone()

    if status and status[0] == 'in_progress':
        # Step 2: Send SMS to all valid recipients
        recipients_str = ",".join(recipients)  # Create comma-separated string of recipients
        print(f"Debug: Sending SMS to recipients: {recipients_str}")  # Log the recipients

        payload = {
            "sender_id": "PhilSMS",
            "recipient": recipients_str,
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
# Function to fetch data from comcenter and insert into sms_db, also update Barangay if changed
def fetch_and_insert_data():
    try:
        # Connect to the comcenter database
        db_comcenter = mysql.connector.connect(**DB_CONFIG_COMCENTER)
        cursor_comcenter = db_comcenter.cursor()

        # Query to get the last 10 records based on Type_Emergency_IDs
        cursor_comcenter.execute("""
            SELECT CallLog_ID, Type_Emergency_ID, Brgy_ID, Remarks, Date_Log 
            FROM comcenter.fed_call_log
            WHERE Type_Emergency_ID IN (68, 44, 62, 46, 57, 86, 159, 9, 160, 161)
            ORDER BY Date_Log DESC
            LIMIT 10;
        """)

        # Fetch the records
        records = cursor_comcenter.fetchall()
        db_comcenter.close()

        # Connect to the sms_db database
        db_sms = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor_sms = db_sms.cursor()

        for record in records:
            calllog_id, type_emergency_id, brgy_id, remarks, date_log = record

            # Check if the CallLog_ID already exists in sms_db.fed_call_log
            cursor_sms.execute("SELECT COUNT(*) FROM fed_call_log WHERE CallLog_ID = %s", (calllog_id,))
            if cursor_sms.fetchone()[0] == 0:
                # If not found, insert the new record into sms_db.fed_call_log
                cursor_sms.execute("""
                    INSERT INTO fed_call_log (CallLog_ID, Type_Emergency_ID, Barangay, Remarks, Date_Log, Status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                """, (calllog_id, type_emergency_id, brgy_id, remarks, date_log))
            else:
                # If found, check if the Barangay has changed
                cursor_sms.execute("SELECT Barangay FROM fed_call_log WHERE CallLog_ID = %s", (calllog_id,))
                current_barangay = cursor_sms.fetchone()[0]

                # Only update if Barangay has changed
                if current_barangay != brgy_id:  # If Barangay has changed
                    cursor_sms.execute("""
                        UPDATE fed_call_log
                        SET Barangay = %s
                        WHERE CallLog_ID = %s
                    """, (brgy_id, calllog_id))

        # Commit the changes to the sms_db
        db_sms.commit()
        db_sms.close()

        # Optional: Update the remarks if changed
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

            # Fetch recipient numbers at the start or when needed
            recipients = get_recipient_numbers()

            if not recipients:
                print("No valid recipients found. Skipping SMS processing.", flush=True)
                time.sleep(10)
                continue  # Skip the loop iteration if no recipients are available

            # Fetch data from the sms_queue table and insert new data if needed
            fetch_and_insert_data()
            mark_old_messages_inactive()
            sms_data = fetch_pending_sms()

            if sms_data:
                # Send the SMS only if there are valid recipients
                send_sms(sms_data["id"], sms_data["message"], recipients)

            time.sleep(10)  # Wait for 10 seconds before running the loop again

    except KeyboardInterrupt:
        print("\n Script stopped by user. Exiting gracefully...", flush=True)


if __name__ == "__main__":
    main()

