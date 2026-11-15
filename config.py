import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv(override=True)

EMAIL_HOST = 'smtp.gmail.com'  # Gmail SMTP server
EMAIL_PORT = 587  # Port for TLS
EMAIL_HOST_USER = os.getenv('EMAIL_USER')  # Load the email user from .env
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')  # Load the password from .env
assert EMAIL_HOST_PASSWORD, 'EMAIL_PASSWORD environment variable not set'
