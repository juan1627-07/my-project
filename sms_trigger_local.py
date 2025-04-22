import requests
import mysql.connector
import time

# PhilSMS API Configuration
API_URL = "https://app.philsms.com/api/v3/sms/send"
API_TOKEN = "1472|Byhr6qlWfESA1okRrL3iTsnKiWFQ37AQpSdi3xAn"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "sms_db",
    "port": 3306,
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci"
}

# Fixed recipient number
RECIPIENT_NUMBER = "+639353767468"


# Mark messages older than 1 hour as "inactive"
def mark_old_messages_inactive():
    try:
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor()
        query = """
        UPDATE sms_queue 
        SET status = 'inactive' 
        WHERE status = 'pending' 
        AND created_at < NOW() - INTERVAL 1 HOUR;
        """
        cursor.execute(query)
        db.commit()
        db.close()
    except mysql.connector.Error as e:
        print(f"Database Error: {e}")


# Fetch the latest "pending" SMS (created within the last hour)
def get_latest_pending_sms():
    try:
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor()
        query = """
        SELECT id, message FROM sms_queue 
        WHERE status = 'pending' 
        AND created_at >= NOW() - INTERVAL 1 HOUR
        ORDER BY created_at DESC 
        LIMIT 1;
        """
        cursor.execute(query)
        sms_record = cursor.fetchone()
        db.close()
        return {"id": sms_record[0], "message": sms_record[1]} if sms_record else None
    except mysql.connector.Error as e:
        print(f"Database Error: {e}")
        return None


# Update the SMS status
def update_sms_status(sms_id, status):
    try:
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor()
        query = "UPDATE sms_queue SET status = %s WHERE id = %s"
        cursor.execute(query, (status, sms_id))
        db.commit()
        db.close()
        print(f"SMS ID {sms_id} marked as '{status}'.")
    except mysql.connector.Error as e:
        print(f"Database Update Error: {e}")


# Send SMS function
def send_sms(sms_id, message):
    payload = {
        "sender_id": "PhilSMS",
        "recipient": RECIPIENT_NUMBER,
        "message": message
    }
    response = requests.post(API_URL, headers=HEADERS, json=payload)

    if response.status_code == 200:
        print(f"SMS sent successfully: {response.json()}")
        update_sms_status(sms_id, "sent")
    else:
        print(f"Failed to send SMS: {response.text}")


# Main loop to automate the process
def main():
    try:
        while True:
            mark_old_messages_inactive()  # Mark outdated messages inactive
            sms_data = get_latest_pending_sms()
            if sms_data:
                send_sms(sms_data["id"], sms_data["message"])
            else:
                print("No pending SMS found.")
            time.sleep(10)  # Wait 10 seconds before checking again
    except KeyboardInterrupt:
        print("\nScript stopped by user. Exiting gracefully...")



if __name__ == "__main__":
    main()
