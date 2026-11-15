import sqlite3
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

class FlightDatabase:
    def __init__(self, db_path: str = "flights.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Flights table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flights (
                    flight_key TEXT PRIMARY KEY,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    airline TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    stay_days INTEGER NOT NULL,
                    outbound_flight_nums TEXT NOT NULL,
                    inbound_flight_nums TEXT NOT NULL,
                    outbound_duration_hours REAL NOT NULL,
                    inbound_duration_hours REAL NOT NULL,
                    outbound_summary TEXT NOT NULL,
                    inbound_summary TEXT NOT NULL,
                    first_price REAL NOT NULL,
                    lowest_price REAL NOT NULL,
                    latest_price REAL NOT NULL,
                    currency TEXT NOT NULL,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    booking_link TEXT
                )
            """)

            # Price history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_key TEXT NOT NULL,
                    price REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (flight_key) REFERENCES flights(flight_key)
                )
            """)

            # Alerts log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_key TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    old_price REAL,
                    new_price REAL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_or_update_flight(self, flight: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Saves or updates a flight record.
        Returns:
            (is_new, alert_type, old_price)
        """
        flight_key = flight["flight_key"]
        current_price = float(flight["price"])
        currency = flight.get("currency", "USD")
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT flight_key, lowest_price, latest_price FROM flights WHERE flight_key = ?", (flight_key,))
            row = cursor.fetchone()

            if not row:
                cursor.execute("""
                    INSERT INTO flights (
                        flight_key, origin, destination, airline, departure_date, return_date,
                        stay_days, outbound_flight_nums, inbound_flight_nums,
                        outbound_duration_hours, inbound_duration_hours,
                        outbound_summary, inbound_summary,
                        first_price, lowest_price, latest_price, currency,
                        first_seen_at, last_seen_at, booking_link
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    flight_key,
                    flight["origin"],
                    flight["destination"],
                    flight["airline"],
                    flight["departure_date"],
                    flight["return_date"],
                    flight["stay_days"],
                    flight["outbound_flight_nums"],
                    flight["inbound_flight_nums"],
                    flight["outbound_duration_hours"],
                    flight["inbound_duration_hours"],
                    flight["outbound_summary"],
                    flight["inbound_summary"],
                    current_price,
                    current_price,
                    current_price,
                    currency,
                    now,
                    now,
                    flight.get("booking_link", "")
                ))

                cursor.execute("""
                    INSERT INTO price_history (flight_key, price, recorded_at)
                    VALUES (?, ?, ?)
                """, (flight_key, current_price, now))
                conn.commit()

                return True, "NEW_FLIGHT", None

            lowest_price = float(row["lowest_price"])
            latest_price = float(row["latest_price"])
            alert_type = None
            old_price = None

            if current_price < lowest_price:
                alert_type = "PRICE_DROP"
                old_price = lowest_price
                new_lowest = current_price
            else:
                new_lowest = lowest_price

            cursor.execute("""
                UPDATE flights SET
                    lowest_price = ?,
                    latest_price = ?,
                    last_seen_at = ?
                WHERE flight_key = ?
            """, (new_lowest, current_price, now, flight_key))

            if current_price != latest_price:
                cursor.execute("""
                    INSERT INTO price_history (flight_key, price, recorded_at)
                    VALUES (?, ?, ?)
                """, (flight_key, current_price, now))

            conn.commit()
            return False, alert_type, old_price

    def log_alert(self, flight_key: str, alert_type: str, old_price: Optional[float], new_price: float):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts_log (flight_key, alert_type, old_price, new_price)
                VALUES (?, ?, ?, ?)
            """, (flight_key, alert_type, old_price, new_price))
            conn.commit()

    def get_top_cheapest_flights(self, limit: int = 15) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT flight_key, origin, destination, airline, departure_date, return_date,
                       stay_days, outbound_flight_nums, inbound_flight_nums,
                       outbound_duration_hours, inbound_duration_hours,
                       outbound_summary, inbound_summary, lowest_price, latest_price, currency, booking_link
                FROM flights
                ORDER BY lowest_price ASC, (outbound_duration_hours + inbound_duration_hours) ASC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def get_summary_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_flights, MIN(lowest_price) as min_price, MAX(lowest_price) as max_price FROM flights")
            row = cursor.fetchone()
            
            cursor.execute("SELECT COUNT(*) as total_alerts FROM alerts_log")
            alerts_row = cursor.fetchone()

            cheapest = self.get_top_cheapest_flights(limit=5)

            return {
                "total_flights": row["total_flights"] if row else 0,
                "min_price": row["min_price"] if row else 0,
                "max_price": row["max_price"] if row else 0,
                "total_alerts": alerts_row["total_alerts"] if alerts_row else 0,
                "cheapest_5": cheapest
            }
