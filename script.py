# send_sms_telesign.py
from telesign.messaging import MessagingClient

# Replace the defaults below with your Telesign authentication credentials or pull them from environment variables.
customer_id = '912B9041-427F-46BC-A0F8-BB97B9926055'
api_key = '7gqJIZpVz+3CAoyYOh6JR3hJ/yk+Q+DI+h/1aH3br27n1m/POjPcTfmIGt0LYyXZ5vu6HrwVUyB0SIVhdVIWKQ=='

# Set the phone number to send the SMS to
phone_number = '639353767468'

# Set the message text
message = "Get 50% off your next order with our holiday offer. See details here: https://vero-finto.com/holiday-offer42 Reply STOP to opt out"
message_type = "ARN"  # Example message type

# Instantiate a messaging client object
messaging = MessagingClient(customer_id, api_key)

# Send the message
response = messaging.message(phone_number, message, message_type)

# Print the response for debugging
print(f"Response:\n{response.body}\n")
