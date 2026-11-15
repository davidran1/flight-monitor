import time
import random
from datetime import date, timedelta
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
    exclude_weekdays: List[int] = None
) -> List[Tuple[str, str, int]]:
    """
    Generates all valid (departure_date_str, return_date_str, stay_days) pairs
    strictly excluding Friday (4) and Saturday (5) for both departure and return.
    """
    if exclude_weekdays is None:
        exclude_weekdays = [4, 5]

    pairs = []
    current_date = date(target_year, target_months[0], 1)
    
    last_month = target_months[-1]
    if last_month == 2:
        is_leap = (target_year % 4 == 0 and target_year % 100 != 0) or (target_year % 400 == 0)
        end_date = date(target_year, 2, 29 if is_leap else 28)
    else:
        end_date = date(target_year, last_month, 31)

    while current_date <= end_date:
        if current_date.month in target_months and current_date.weekday() not in exclude_weekdays:
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

    def run_scan(self, silent_baseline: bool = True, max_pairs: int = None) -> Dict[str, Any]:
        """
        Executes scan cycle.
        If silent_baseline=True: Saves all flights quietly into SQLite DB,
        and at the end sends ONE single consolidated digest email with the cheapest flights.
        If silent_baseline=False (watch mode): Sends immediate alert for any newly added flight or price drop.
        """
        date_pairs = generate_date_pairs(
            target_year=config.TARGET_YEAR,
            target_months=config.TARGET_MONTHS,
            min_stay=config.MIN_STAY_DAYS,
            max_stay=config.MAX_STAY_DAYS,
            dep_step=config.DEPARTURE_STEP_DAYS,
            stay_step=config.STAY_STEP_DAYS,
            exclude_weekdays=config.EXCLUDE_WEEKDAYS
        )

        if max_pairs:
            date_pairs = date_pairs[:max_pairs]

        print(f"\n==================================================")
        print(f"🚀 סריקת טיסות איתיחאד: TLV ➔ HKT")
        print(f"📅 חודשים: ינואר-פברואר {config.TARGET_YEAR}")
        print(f"🚫 מגבלה: ללא טיסות בשישי ושבת (בהלוך ובחזור)")
        print(f"⏳ משך שהות בפוקט: {config.MIN_STAY_DAYS}-{config.MAX_STAY_DAYS} ימים")
        print(f"⏱️ מקסימום זמן טיסה: עד {config.MAX_DURATION_HOURS} שעות לכל כיוון")
        print(f"📧 מצב התראות: {'דוח מרוכז בסיום הסריקה' if silent_baseline else 'התראה מיידית על כל שינוי/טיסה חדשה'}")
        print(f"🔢 סה\"כ קומבינציות תאריכים לסריקה: {len(date_pairs)}")
        print(f"==================================================\n")

        total_checked = 0
        new_flights_count = 0
        price_drops_count = 0

        for i, (dep_date, ret_date, stay) in enumerate(date_pairs, 1):
            print(f"[{i}/{len(date_pairs)}] בודק {dep_date} ➔ {ret_date} ({stay} ימים)...", end=" ", flush=True)

            flights = self._get_flights_for_dates(dep_date, ret_date, stay)
            print(f"נמצאו {len(flights)} טיסות.")

            for flight in flights:
                total_checked += 1
                is_new, alert_type, old_price = self.db.save_or_update_flight(flight)

                if alert_type == "NEW_FLIGHT":
                    new_flights_count += 1
                    if not silent_baseline:
                        print(f"  ✨ [טיסה חדשה!] מחיר: {flight['currency']}{flight['price']:.0f} | הלוך: {flight['outbound_duration_hours']}h | חזור: {flight['inbound_duration_hours']}h")
                        self.notifier.send_alert(flight, "NEW_FLIGHT")
                        self.db.log_alert(flight["flight_key"], "NEW_FLIGHT", None, flight["price"])

                elif alert_type == "PRICE_DROP":
                    price_drops_count += 1
                    print(f"  📉 [צניחת מחיר!] ירד מ-{old_price:.0f} ל-{flight['price']:.0f} {flight['currency']}!")
                    self.notifier.send_alert(flight, "PRICE_DROP", old_price)
                    self.db.log_alert(flight["flight_key"], "PRICE_DROP", old_price, flight["price"])

            if not self.use_mock:
                time.sleep(0.8)

        stats = self.db.get_summary_stats()

        # If silent baseline was requested, send the consolidated digest email now
        if silent_baseline:
            top_cheapest = self.db.get_top_cheapest_flights(limit=15)
            if top_cheapest:
                print("\n📨 שולח דוח מרוכז של הטיסות הזולות ביותר למייל...")
                self.notifier.send_digest_email(
                    top_flights=top_cheapest,
                    total_scanned=stats["total_flights"],
                    min_price=stats["min_price"]
                )

        summary = {
            "total_pairs_checked": len(date_pairs),
            "total_flights_found": total_checked,
            "new_flights": new_flights_count,
            "price_drops": price_drops_count,
            "db_stats": stats
        }

        print(f"\n✅ סריקה הסתיימה בהצלחה!")
        print(f"  - טיסות חדשות שנוספו למאגר: {new_flights_count}")
        print(f"  - ירידות מחיר שזוהו: {price_drops_count}")
        print(f"  - סה\"כ טיסות במאגר: {stats['total_flights']}")
        if stats['min_price']:
            print(f"  - המחיר הנמוך ביותר במאגר: {stats['min_price']:.0f} USD")

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
        base_price = round(random.uniform(720, 1150), 0)

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
