# Housing Alert System

A web application that monitors housing offers and sends email alerts when new listings are found based on your criteria.

## Table of Contents

- [Description](#description)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Configuration](#configuration)
- [For Developers](#for-developers)
  - [Key Code Components](#key-code-components)
  - [How to Extend or Improve](#how-to-extend-or-improve)

## Description

This application allows users to set up alerts for housing offers based on city, price, and geographical bounds. It periodically checks a housing website for new listings and sends email notifications when matches are found.

## Prerequisites

- Python 3.7 or higher installed on your system.
- An SMTP email account (e.g., Gmail) for sending email notifications.
- Basic knowledge of command-line operations.

## Installation

Follow these simple steps to set up and run the project:

1. **Clone the Repository**

   ```bash
   git clone https://github.com/ayoubachak/find-logement-crous.git
   cd find-logement-crous
   ```

2. **Create a Virtual Environment**

   ```bash
   python -m venv venv
   ```

3. **Activate the Virtual Environment**

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

   - On macOS/Linux:

     ```bash
     source venv/bin/activate
     ```

4. **Install the Required Packages**

   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. **Set Up Environment Variables**

   Create a `.env` file in the project root directory and add the following:

   ```env
   SECRET_KEY=your_secret_key
   EMAIL_PASSWORD=your_email_password
   DATABASE_URL=sqlite:///alerts.db
   ```

   - Replace `your_secret_key` with a random string (you can use an online generator).
   - Replace `your_email_password` with the password of your email account.
   - The `DATABASE_URL` is set to use a local SQLite database by default.

2. **Configure Email Settings**

   Open `config.py` and ensure the email settings match your email provider:

   ```python
   EMAIL_HOST = 'smtp.gmail.com'  # For Gmail
   EMAIL_PORT = 587  # Port for TLS
   EMAIL_HOST_USER = 'your_email@gmail.com'
   EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
   ```

   - Replace `'your_email@gmail.com'` with your email address.

3. **Run the Application**

   ```bash
   python app.py
   ```

4. **Access the Application**

   Open your web browser and navigate to `http://localhost:5000` to use the application.

## Configuration

- **Creating Alerts**: Click on "Create Alert" and fill in the form with your criteria.
- **Email Notifications**: The application will send emails to the addresses you specify when new housing offers are found.
- **Managing Alerts**: You can edit or delete alerts from the main dashboard.

## For Developers

### Key Code Components

- **`app.py`**: The main Flask application that handles routing, background tasks, and WebSocket communication.
  - **Background Tasks**: Uses threading to manage alert checking without blocking the main application.
  - **SocketIO**: Implements real-time logging updates to the frontend.

- **`models.py`**: Contains the SQLAlchemy models for the database.
  - **`Alert` Model**: Stores alert criteria and status.
  - **`AlertLog` Model**: Logs activity related to alerts.

- **`scraper.py`**: Handles web scraping and email notifications.
  - **`check_for_results` Function**: Scrapes the housing website based on alert criteria.
  - **`send_email` Function**: Sends email notifications with the results.

### How to Extend or Improve

- **Enhance Scraping Logic**: Improve the `check_for_results` function to handle more websites or to be more efficient.
- **UI Improvements**: Update the templates to provide a better user experience.
- **Error Handling**: Add more robust error handling and logging throughout the application.
- **Authentication**: Implement user accounts to manage alerts individually.
- **Dockerization**: Create a Dockerfile for containerization and easier deployment.
- **Tests**: Write unit and integration tests to ensure code reliability.
