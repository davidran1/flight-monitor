import time
import random
from datetime import date, timedelta, datetime
from typing import List, Tuple, Dict, Any

import config
from database import FlightDatabase
from google_flights_client import GoogleFlightsLiveClient
from notifier import EmailNotifier

def generate_date_pairs(
    target_year: int,
    target_months: List[int],
    min_stay: int,
    max_stay: int,
    dep_step: int = 1,
    stay_step: int = 1,
    exclude_weekdays: List[int] = None,
    latest_departure_date: str = None
) -> List[Tuple[str, str, int]]:
    """
    Generates all valid (departure_date_str, return_date_str, stay_days) pairs
    strictly excluding Friday (4) and Saturday (5) for both departure and return,
    and limiting departures up to latest_departure_date (e.g. 2027-02-07).
    """
    if exclude_weekdays is None:
        exclude_weekdays = [4, 5]

    pairs = []
    current_date = date(target_year, target_months[0], 1)
    
    if latest_departure_date:
        end_date = datetime.strptime(latest_departure_date, "%Y-%m-%d").date()
    else:
        last_month = target_months[-1]
        if last_month == 2:
            is_leap = (target_year % 4 == 0 and target_year % 100 != 0) or (target_year % 400 == 0)
            end_date = date(target_year, 2, 29 if is_leap else 28)
        else:
            end_date = date(target_year, last_month, 31)

    while current_date <= end_date:
        if current_date.weekday() not in exclude_weekdays:
            for stay in range(min_stay, max_stay + 1, stay_step):
                ret_date = current_date + timedelta(days=stay)
                if ret_date.weekday() not in exclude_weekdays:
                    pairs.append((
                        current_date.strftime("%Y-%m-%d"),
                        ret_date.strftime("%Y-%m-%d"),
                        stay
                    ))
        current_date += timedelta(days=dep_step)

    return pairs

class FlightScanner:
    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.db = FlightDatabase(config.DB_PATH)
        self.notifier = EmailNotifier(
            smtp_host=config.SMTP_HOST,
            smtp_port=config.SMTP_PORT,
            smtp_user=config.SMTP_USER,
            smtp_password=config.SMTP_PASSWORD,
            email_to=config.EMAIL_TO,
            enabled=config.EMAIL_ENABLED
        )
        self.live_client = GoogleFlightsLiveClient() if not use_mock else None

    def run_scan(self, max_pairs: int = None) -> Dict[str, Any]:
        """
        Executes a scan cycle over the 151 refined combinations.
        Collects all new flights and price drops under MAX_PRICE_USD ($1,100).
        Sends ONE single consolidated email if matching deals are found,
        including a summary table of the Top 10 existing flights in the database sorted by price.
        """
        date_pairs = generate_date_pairs(
            target_year=config.TARGET_YEAR,
            target_months=config.TARGET_MONTHS,
            min_stay=config.MIN_STAY_DAYS,
            max_stay=config.MAX_STAY_DAYS,
            dep_step=config.DEPARTURE_STEP_DAYS,
            stay_step=config.STAY_STEP_DAYS,
            exclude_weekdays=config.EXCLUDE_WEEKDAYS,
            latest_departure_date=config.LATEST_DEPARTURE_DATE
        )

        if max_pairs:
            date_pairs = date_pairs[:max_pairs]

        print(f"\n==================================================")
        print(f"🚀 סריקת טיסות איתיחאד: TLV ➔ HKT (ממוקד ויעיל)")
        print(f"📅 חלון יציאות: מ-1 בינואר עד {config.LATEST_DEPARTURE_DATE}")
        print(f"🚫 מגבלה: ללא טיסות בשישי ושבת (בהלוך ובחזור)")
        print(f"⏳ משך שהות בפוקט: {config.MIN_STAY_DAYS}-{config.MAX_STAY_DAYS} ימים")
        print(f"⏱️ מקסימום זמן טיסה: עד {config.MAX_DURATION_HOURS} שעות לכל כיוון")
        print(f"💰 סינון מחיר מרבי: עד {config.MAX_PRICE_USD:.0f}$ בלבד")
        print(f"📧 התראות: מייל מרוכז הכולל דילים חדשים + קישורים למאגר הקיים")
        print(f"🔢 סה\"כ קומבינציות תאריכים לסריקה: {len(date_pairs)}")
        print(f"==================================================\n")

        total_checked = 0
        new_deals = []

        for i, (dep_date, ret_date, stay) in enumerate(date_pairs, 1):
            print(f"[{i}/{len(date_pairs)}] בודק {dep_date} ➔ {ret_date} ({stay} ימים)...", end=" ", flush=True)

            flights = self._get_flights_for_dates(dep_date, ret_date, stay)
            print(f"נמצאו {len(flights)} טיסות.")

            for flight in flights:
                total_checked += 1
                is_new, alert_type, old_price = self.db.save_or_update_flight(flight)

                price = flight["price"]
                if price <= config.MAX_PRICE_USD:
                    if alert_type == "NEW_FLIGHT":
                        print(f"  ✨ [טיסה חדשה מתחת לרף!] מחיר: ${price:.0f} | הלוך: {flight['outbound_duration_hours']}h | חזור: {flight['inbound_duration_hours']}h")
                        new_deals.append({
                            "flight": flight,
                            "alert_type": "NEW_FLIGHT",
                            "price": price,
                            "old_price": None
                        })
                        self.db.log_alert(flight["flight_key"], "NEW_FLIGHT", None, price)

                    elif alert_type == "PRICE_DROP":
                        print(f"  📉 [צניחת מחיר מתחת לרף!] ירד מ-${old_price:.0f} ל-${price:.0f}!")
                        new_deals.append({
                            "flight": flight,
                            "alert_type": "PRICE_DROP",
                            "price": price,
                            "old_price": old_price
                        })
                        self.db.log_alert(flight["flight_key"], "PRICE_DROP", old_price, price)

            if not self.use_mock:
                time.sleep(0.8)

        stats = self.db.get_summary_stats()

        if new_deals:
            # Retrieve the Top 10 existing cheapest flights from the DB to include in the email
            existing_cheapest = self.db.get_top_cheapest_flights(limit=10)
            print(f"\n📨 שולח מייל מרוכז אחד עם {len(new_deals)} טיסות חדשות + טבלת 10 הטיסות הזולות הקיימות במאגר...")
            self.notifier.send_consolidated_alert(
                deals=new_deals,
                max_price_usd=config.MAX_PRICE_USD,
                existing_cheapest=existing_cheapest
            )
        else:
            print(f"\nℹ️ לא נמצאו טיסות חדשות או ירידות מחיר מתחת ל-${config.MAX_PRICE_USD:.0f} בסבב זה. (לא נשלח מייל למניעת ספאם)")

        summary = {
            "total_pairs_checked": len(date_pairs),
            "total_flights_found": total_checked,
            "matching_deals": len(new_deals),
            "db_stats": stats
        }

        print(f"\n✅ סריקה הסתיימה בהצלחה!")
        print(f"  - טיסות רלוונטיות מתחת ל-${config.MAX_PRICE_USD:.0f} שנמצאו בסבב זה: {len(new_deals)}")
        print(f"  - סה\"כ טיסות במאגר: {stats['total_flights']}")
        if stats['min_price']:
            print(f"  - המחיר הנמוך ביותר במאגר: ${stats['min_price']:.0f}")

        return summary

    def _get_flights_for_dates(self, dep_date: str, ret_date: str, stay_days: int) -> List[Dict[str, Any]]:
        if self.use_mock:
            return self._generate_mock_flights(dep_date, ret_date, stay_days)

        try:
            return self.live_client.search_roundtrip_flights(
                origin=config.ORIGIN,
                destination=config.DESTINATION,
                departure_date=dep_date,
                return_date=ret_date,
                airline_code=config.AIRLINE_CODE,
                max_duration_hours=config.MAX_DURATION_HOURS
            )
        except Exception as e:
            print(f"  [Live Engine Error: {e}]")
            return []

    def _generate_mock_flights(self, dep_date: str, ret_date: str, stay_days: int) -> List[Dict[str, Any]]:
        outbound_options = [
            ("EY598 + EY430", 12.0, "TLV ➔ AUH (3h) | AUH ➔ HKT (6.2h)"),
            ("EY594 + EY432", 13.5, "TLV ➔ AUH (3.2h) | AUH ➔ HKT (6.5h)")
        ]
        inbound_options = [
            ("EY431 + EY595", 13.0, "HKT ➔ AUH (6.5h) | AUH ➔ TLV (3.5h)"),
            ("EY433 + EY599", 14.2, "HKT ➔ AUH (6.8h) | AUH ➔ TLV (3.8h)")
        ]

        flights = []
        out_flight, out_dur, out_sum = random.choice(outbound_options)
        in_flight, in_dur, in_sum = random.choice(inbound_options)
        base_price = round(random.uniform(920, 1180), 0)

        flight_key = f"TLV-HKT_{dep_date}_{ret_date}_{out_flight}_{in_flight}"
        etihad_link = f"https://www.etihad.com/en-il/book?origin=TLV&destination=HKT&departureDate={dep_date}&returnDate={ret_date}&cabin=ECONOMY&adults=1"

        flights.append({
            "flight_key": flight_key,
            "origin": "TLV",
            "destination": "HKT",
            "airline": "Etihad Airways",
            "departure_date": dep_date,
            "return_date": ret_date,
            "stay_days": stay_days,
            "outbound_flight_nums": out_flight,
            "inbound_flight_nums": in_flight,
            "outbound_duration_hours": out_dur,
            "inbound_duration_hours": in_dur,
            "outbound_summary": f"{out_sum} [סה\"כ {out_dur} שעות]",
            "inbound_summary": f"{in_sum} [סה\"כ {in_dur} שעות]",
            "price": base_price,
            "currency": "USD",
            "booking_link": etihad_link
        })
        return flights
