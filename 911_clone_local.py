import mysql.connector
from mysql.connector import Error
from tkinter import Tk, Label, Button, Entry, OptionMenu, StringVar
from tkcalendar import Calendar
import webbrowser
import re
import pytz
from datetime import datetime

# Database connection parameters (update if needed)
host = 'localhost'   # Database host
user = 'root'               # Database username
password = ''               # Database password (adjust if needed)
database = 'comcenter'      # Database name
port = 3306                 # Database port (adjust if needed)

# Set the local timezone to match the PC's timezone (Asia/Manila for example)
local_timezone = pytz.timezone("Asia/Manila")  # Adjust the timezone accordingly

# Function to fetch Barangays based on filtered letters
def fetch_barangays(filtered_letters):
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            # SQL query to fetch Barangay names starting with the filtered letters
            query = """
            SELECT Barangay 
            FROM barangay 
            WHERE Barangay LIKE %s
            """
            cursor.execute(query, (filtered_letters + '%',))
            barangays = cursor.fetchall()

            return [barangay[0] for barangay in barangays]  # Return only the Barangay names
    except Error as e:
        print(f"Error fetching Barangay data: {e}")
        return []
    finally:
        if connection and connection.is_connected():
            connection.close()

# Function to get the Barangay_ID based on the Barangay name
def get_barangay_id(barangay_name):
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
        )
        if connection.is_connected():
            cursor = connection.cursor()

            # SQL query to fetch Barangay_ID for the selected Barangay
            query = """
            SELECT Barangay_ID
            FROM barangay
            WHERE Barangay = %s
            """
            cursor.execute(query, (barangay_name,))
            result = cursor.fetchone()

            if result:
                return result[0]  # Return the Barangay_ID
            else:
                print(f"Barangay '{barangay_name}' not found.")
                return None
    except Error as e:
        print(f"Error fetching Barangay_ID: {e}")
        return None
    finally:
        if connection and connection.is_connected():
            connection.close()

# Function to get user input using a GUI
def get_user_input():
    # Create main window
    window = Tk()
    window.title("Enter Data")

    # Display labels and entry fields
    Label(window, text="Enter CallLog_ID:").grid(row=0, column=0)
    CallLog_ID = Entry(window)
    CallLog_ID.grid(row=0, column=1)

    Label(window, text="Enter Type_Emergency_ID:").grid(row=1, column=0)
    Type_Emergency_ID = Entry(window)
    Type_Emergency_ID.grid(row=1, column=1)

    Label(window, text="Enter NameCaller:").grid(row=2, column=0)
    NameCaller = Entry(window)
    NameCaller.grid(row=2, column=1)

    Label(window, text="Enter Address:").grid(row=3, column=0)
    Address = Entry(window)
    Address.grid(row=3, column=1)

    Label(window, text="Enter LandMark:").grid(row=4, column=0)
    LandMark = Entry(window)
    LandMark.grid(row=4, column=1)

    Label(window, text="Enter Remarks:").grid(row=5, column=0)
    Remarks = Entry(window)
    Remarks.grid(row=5, column=1)

    # Barangay filter entry field
    Label(window, text="Filter Barangay (first two letters):").grid(row=6, column=0)
    Barangay_filter = Entry(window)
    Barangay_filter.grid(row=6, column=1)

    # Fetch Barangay names based on filter
    barangay_options = StringVar(window)
    barangay_options.set("Select Barangay")

    def update_barangay_list():
        filtered_letters = Barangay_filter.get().lower()
        barangays = fetch_barangays(filtered_letters)
        if barangays:
            barangay_options.set(barangays[0])  # Set first barangay as default
            barangay_menu['menu'].delete(0, 'end')
            for barangay in barangays:
                barangay_menu['menu'].add_command(label=barangay, command=lambda value=barangay: barangay_options.set(value))
        else:
            barangay_options.set("No matching Barangay")

    # Button to update Barangay list based on filter
    Button(window, text="Filter Barangay", command=update_barangay_list).grid(row=7, column=1)

    # Barangay dropdown menu
    barangay_menu = OptionMenu(window, barangay_options, "Select Barangay")
    barangay_menu.grid(row=8, column=1)

    # Date Picker
    Label(window, text="Select Date (YYYY-MM-DD):").grid(row=9, column=0)
    cal = Calendar(window, selectmode='day', date_pattern='yyyy-mm-dd')
    cal.grid(row=9, column=1)

    # Time Picker (using a button)
    time_selected = None
    def select_time():
        nonlocal time_selected
        # Get the current time in local timezone
        local_time = datetime.now(local_timezone).strftime("%H:%M:%S")
        time_selected = local_time
        print(f"Selected time: {time_selected}")

    time_button = Button(window, text="Select Time", command=select_time)
    time_button.grid(row=10, column=1)

    # Longitude and Latitude placeholders
    longitude = None
    latitude = None

    # Function to extract coordinates from the Google Maps URL
    def validate_and_extract_coordinates(url):
        # Updated regular expression to capture the @lat,long section
        match = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", url)
        if match:
            latitude = float(match.group(1))
            longitude = float(match.group(2))
            return latitude, longitude
        else:
            print("Invalid Google Maps URL format. Coordinates not found.")
            return None, None

    # Display instructions for the user
    Label(window, text="Please manually select a point on the map and copy the URL with coordinates.").grid(row=11, column=0, columnspan=2)
    Label(window, text="Paste the updated Google Maps URL here (with new coordinates):").grid(row=12, column=0, columnspan=2)

    # Entry field for the user to paste the updated URL with coordinates
    updated_url = Entry(window)
    updated_url.grid(row=13, column=0, columnspan=2)

    # Function to browse the map (Google Maps)
    def browse_map():
        # Open Google Maps for the user to select the location
        google_maps_url = "https://www.google.com/maps"
        webbrowser.open(google_maps_url)
        print("Please select your location on Google Maps and copy the URL with coordinates.")

    Button(window, text="Browse Map", command=browse_map).grid(row=14, column=0)

    # Function to capture coordinates
    def capture_coordinates():
        new_url = updated_url.get()
        latitude, longitude = validate_and_extract_coordinates(new_url)
        if latitude is not None and longitude is not None:
            print(f"Updated Coordinates - Latitude: {latitude}, Longitude: {longitude}")
            return latitude, longitude
        else:
            print("No valid coordinates found in the URL.")
            return None, None

    # Function to submit the user input and send it to the database
    def submit():
        nonlocal CallLog_ID, Type_Emergency_ID, NameCaller, Address, LandMark, Remarks, cal, updated_url, time_selected
        selected_date = cal.get_date()

        # Ensure time_selected is not None and default it to current time if not set
        if time_selected is None:
            time_selected = datetime.now(local_timezone).strftime("%H:%M:%S")  # Default to current time in local timezone
        print(f"Date: {selected_date} Time: {time_selected}")

        # Get the Barangay name from the selected option
        selected_barangay = barangay_options.get()

        # Fetch Barangay_ID based on the selected Barangay
        Brgy_ID = get_barangay_id(selected_barangay)
        if Brgy_ID is None:
            print("Invalid Barangay selection, cannot proceed.")
            return

        # Extract the latitude and longitude from the URL
        latitude, longitude = capture_coordinates()
        if latitude is None or longitude is None:
            print("Invalid coordinates, cannot proceed.")
            return

        # Collect all user inputs
        data = (
            CallLog_ID.get(),
            Type_Emergency_ID.get(),
            NameCaller.get(),
            Address.get(),
            LandMark.get(),
            Remarks.get(),
            f"{selected_date} {time_selected}",
            longitude,
            latitude,
            Brgy_ID  # Use the Barangay_ID
        )
        window.quit()
        window.destroy()

        # Call insert function after collecting input
        insert_data(data)

    Button(window, text="Submit", command=submit).grid(row=15, column=1)

    window.mainloop()

# Function to insert data into the database
def insert_data(data):
    connection = None
    try:
        # Establish the database connection
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
        )

        if connection.is_connected():
            print("Connected to the database.")

            # Create an insert query
            query = """
            INSERT INTO fed_call_log 
            (CallLog_ID, Type_Emergency_ID, NameCaller, Address, LandMark, Remarks, Date_Log, Longitude, Latitude, Brgy_ID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Create a cursor and execute the query
            cursor = connection.cursor()
            cursor.execute(query, data)

            # Commit the transaction
            connection.commit()
            print("Data inserted successfully!")

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("Connection closed.")

# Call the insert function after getting user input
get_user_input()