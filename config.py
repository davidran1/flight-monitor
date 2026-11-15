import os
from dotenv import load_dotenv

load_dotenv()

# Flight Search Parameters
ORIGIN = os.getenv("ORIGIN", "TLV")
DESTINATION = os.getenv("DESTINATION", "HKT")
AIRLINE_CODE = os.getenv("AIRLINE_CODE", "EY")  # EY = Etihad Airways
MAX_DURATION_HOURS = float(os.getenv("MAX_DURATION_HOURS", "15.0"))

# Price Ceiling Filter (Alert only for flights <= this price)
MAX_PRICE_USD = float(os.getenv("MAX_PRICE_USD", "1100.0"))

# Stay Duration: 15 to 22 days
MIN_STAY_DAYS = int(os.getenv("MIN_STAY_DAYS", "15"))
MAX_STAY_DAYS = int(os.getenv("MAX_STAY_DAYS", "22"))

# Departure window: January 1 up to February 7
TARGET_YEAR = int(os.getenv("TARGET_YEAR", "2027"))
TARGET_MONTHS = [1, 2]
LATEST_DEPARTURE_DATE = os.getenv("LATEST_DEPARTURE_DATE", f"{TARGET_YEAR}-02-07")

# Step 1 = Every possible day
DEPARTURE_STEP_DAYS = int(os.getenv("DEPARTURE_STEP_DAYS", "1"))
STAY_STEP_DAYS = int(os.getenv("STAY_STEP_DAYS", "1"))

# Exclude Friday (4) and Saturday (5) - No flights on Fri/Sat!
EXCLUDE_WEEKDAYS = [4, 5]

# Email Notification Settings (Gmail SMTP)
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() in ("true", "1", "yes")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

# Scheduler Interval (minutes) for continuous mode
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))

# Database Path
DB_PATH = os.getenv("DB_PATH", "flights.db")
