import mysql.connector
import time
from datetime import datetime, timedelta

# Database Configuration for comcenter (Correct IP)
DB_CONFIG_COMCENTER = {
    "host": "192.168.0.200",  # Correct IP address
    "user": "root",
    "password": "",
    "database": "comcenter",
    "port": 3306,
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci"
}

# Database Configuration for sms_db
DB_CONFIG_SMS = {
    "host": "192.168.0.200",  # Correct IP address
    "user": "root",
    "password": "",
    "database": "sms_db",
    "port": 3306,
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci"
}


# Function to fetch and insert data
def fetch_and_insert_data():
    try:
        # Connect to comcenter database
        db_comcenter = mysql.connector.connect(**DB_CONFIG_COMCENTER)
        cursor_comcenter = db_comcenter.cursor()

        # Get the current time and time 1 hour ago
        current_time = datetime.now()
        one_hour_ago = current_time - timedelta(hours=1)

        # Convert the times to the correct format for MySQL
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
        one_hour_ago_str = one_hour_ago.strftime('%Y-%m-%d %H:%M:%S')

        # Fetch records from comcenter.fed_call_log within the last hour
        cursor_comcenter.execute("""
            SELECT CallLog_ID, Type_Emergency_ID, Brgy_ID, Remarks, Date_Log 
            FROM comcenter.fed_call_log
            WHERE Date_Log >= %s AND Date_Log <= %s
            AND Type_Emergency_ID IN (68, 44, 62, 46, 57, 86, 159, 9, 161)
            ORDER BY Date_Log DESC
            LIMIT 10;
        """, (one_hour_ago_str, current_time_str))
        records = cursor_comcenter.fetchall()

        if records:
            print(f"Fetched {len(records)} records from comcenter.fed_call_log.")
        else:
            print("No new records found to fetch.")
            db_comcenter.close()
            return

        # Insert records into sms_db.fed_call_log
        db_sms = mysql.connector.connect(**DB_CONFIG_SMS)
        cursor_sms = db_sms.cursor()

        for record in records:
            # Check if the record already exists in the sms_db.fed_call_log based on CallLog_ID
            cursor_sms.execute("SELECT COUNT(*) FROM sms_db.fed_call_log WHERE CallLog_ID = %s", (record[0],))
            if cursor_sms.fetchone()[0] == 0:
                # Insert the new record if it doesn't exist
                cursor_sms.execute("""
                    INSERT INTO sms_db.fed_call_log (CallLog_ID, Type_Emergency_ID, Barangay, Remarks, Date_Log, Status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (record[0], record[1], record[2], record[3], record[4], 'pending'))
                print(f"Inserted CallLog_ID={record[0]} into sms_db.fed_call_log.")
            else:
                print(f"CallLog_ID={record[0]} already exists, skipping insertion.")

        db_sms.commit()  # Commit changes to sms_db
        db_comcenter.close()
        db_sms.close()

    except mysql.connector.Error as e:
        print(f"Database Error: {e}")


# Main loop to periodically fetch and insert data
def main():
    for _ in range(10):  # Adjust the range for the number of times you want to run the check
        fetch_and_insert_data()
        time.sleep(10)  # Check every 10 seconds


if __name__ == "__main__":
    main()
