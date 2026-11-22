import sys
import time
import argparse
from datetime import datetime

import config
from scanner import FlightScanner
from database import FlightDatabase
from notifier import EmailNotifier

def print_banner():
    banner = f"""
  ==============================================================
  ✈️  ETIHAD AIRWAYS FLIGHT MONITOR: TLV ➔ HKT (פוקט)
  ==============================================================
  חברה: Etihad Airways (EY) | מסלול: תל אביב ⇄ פוקט
  משך טיסה: מקסימום 15 שעות לכל כיוון (קונקשן באבו דאבי)
  סינון מחיר מרבי להתראה: עד {config.MAX_PRICE_USD:.0f}$ בלבד!
  חלון יציאות: ינואר ופברואר (חזרה עד 7 במרץ 2027)
  משך שהות: 15 עד 22 ימים בפוקט
  הגבלה: ללא טיסות בשישי ושבת (בהלוך ובחזור)
  התראות: מייל מרוכז לדילים חדשים + דוח מצב תקופתי כל 3 ימים
  ==============================================================
    """
    print(banner)

def show_summary():
    db = FlightDatabase(config.DB_PATH)
    stats = db.get_summary_stats()
    
    print("\n📊 --- סיכום מאגר הטיסות שנשמרו ---")
    print(f"סה\"כ טיסות במאגר: {stats['total_flights']}")
    print(f"סה\"כ התראות שנשלחו עד כה: {stats['total_alerts']}")
    if stats['total_flights'] > 0:
        print(f"טווח מחירים נוכחי: {stats['min_price']:.0f}$ - {stats['max_price']:.0f}$")
        print(f"\n🏆 הטיסות המשתלמות ביותר (זמן ≤ 15 שעות | ללא שישי-שבת):")
        top_list = db.get_top_cheapest_flights(limit=15)
        for i, f in enumerate(top_list, 1):
            star = "🔥" if f['lowest_price'] <= config.MAX_PRICE_USD else "  "
            print(f" {star} {i}. {f['departure_date']} ➔ {f['return_date']} ({f['stay_days']} ימים) | מחיר: {f['lowest_price']:.0f}$ | הלוך: {f['outbound_duration_hours']:.1f}h | חזור: {f['inbound_duration_hours']:.1f}h")
    else:
        print("טרם נסרקו טיסות. הרץ: python main.py --scan")
    print("------------------------------------\n")

def send_digest_now():
    """
    Sends the periodic status report of the top cheapest flights currently in the database.
    """
    db = FlightDatabase(config.DB_PATH)
    stats = db.get_summary_stats()
    top_flights = db.get_top_cheapest_flights(limit=15)
    
    if not top_flights:
        print("⚠️ מאגר הנתונים ריק. בצע סריקה תחילה.")
        return False

    notifier = EmailNotifier(
        smtp_host=config.SMTP_HOST,
        smtp_port=config.SMTP_PORT,
        smtp_user=config.SMTP_USER,
        smtp_password=config.SMTP_PASSWORD,
        email_to=config.EMAIL_TO,
        enabled=True
    )
    print(f"\n📨 שולח דוח מצב תקופתי עם {len(top_flights)} הטיסות הזולות ביותר ל-{notifier.email_to}...")
    success = notifier.send_periodic_status_digest(
        top_flights=top_flights,
        total_scanned=stats["total_flights"],
        min_price=stats["min_price"]
    )
    if success:
        print("✅ דוח המצב התקופתי נשלח בהצלחה למייל!")
    return success

def test_email():
    print("\n📧 בודק חיבור לשליחת מייל...")
    notifier = EmailNotifier(
        smtp_host=config.SMTP_HOST,
        smtp_port=config.SMTP_PORT,
        smtp_user=config.SMTP_USER,
        smtp_password=config.SMTP_PASSWORD,
        email_to=config.EMAIL_TO,
        enabled=True
    )
    if not notifier.is_configured():
        print("⚠️ פרטי ה-SMTP חסרים בקובץ .env!")
        return

    sample_deal = {
        "flight": {
            "origin": "TLV",
            "destination": "HKT",
            "departure_date": "2027-01-25",
            "return_date": "2027-02-09",
            "stay_days": 15,
            "outbound_flight_nums": "EY-TLV➔AUH + EY-AUH➔HKT",
            "inbound_flight_nums": "EY-HKT➔AUH + EY-AUH➔TLV",
            "outbound_duration_hours": 12.5,
            "inbound_duration_hours": 13.0,
            "price": 1139.0,
            "currency": "USD",
            "booking_link": "https://www.etihad.com"
        },
        "alert_type": "NEW_FLIGHT",
        "price": 1139.0
    }
    success = notifier.send_consolidated_alert([sample_deal], max_price_usd=config.MAX_PRICE_USD)
    if success:
        print(f"✅ מייל בדיקה נשלח בהצלחה לכתובת: {notifier.email_to}")
    else:
        print("❌ שליחת המייל נכשלה. בדוק את ההגדרות והסיסמה.")

def watch_mode(interval_minutes: int, use_mock: bool):
    print(f"\n🔄 מפעיל מצב ניטור רציף (סריקה כל {interval_minutes} דקות)...")
    print("המערכת רצה ברקע, בודקת טיסות, ושולחת מייל מרוכז יחיד אם התגלו טיסות מתחת ל-1,100$.")
    print("לעצירה לחץ Ctrl + C\n")
    scanner = FlightScanner(use_mock=use_mock)

    round_count = 1
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] סבב ניטור #{round_count} החל...")
            scanner.run_scan()
            round_count += 1
            print(f"\n💤 ממתין {interval_minutes} דקות עד לסבב הניטור הבא...")
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            print("\n🛑 ניטור הופסק על ידי המשתמש.")
            break
        except Exception as e:
            print(f"\n⚠️ שגיאה במהלך הסריקה: {e}")
            print(f"ממתין 60 שניות ומנסה שוב...")
            time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description="Etihad Airways Flight Monitor TLV <-> HKT")
    parser.add_argument("--scan", action="store_true", help="בצע סריקה מלאה של כל 189 הקומבינציות (מייל מרוכז אם נמצאו טיסות <= 1,100$)")
    parser.add_argument("--digest", action="store_true", help="שלח מיידית את דוח המצב התקופתי עם הטיסות הזולות ביותר במאגר")
    parser.add_argument("--watch", action="store_true", help="הפעל ניטור רציף תמידי ברקע לזיהוי טיסות חדשות וירידות מחיר")
    parser.add_argument("--interval", type=int, default=config.SCAN_INTERVAL_MINUTES, help="מרווח זמן בין סריקות במצב watch בדקות")
    parser.add_argument("--test-mock", action="store_true", help="הרץ סריקת הדמיה לבדיקת המערכת")
    parser.add_argument("--test-email", action="store_true", help="שלח מייל בדיקה לווידוא הגדרות ה-SMTP")
    parser.add_argument("--summary", action="store_true", help="הצג את הטיסות הזולות ביותר שנשמרו במאגר")

    args = parser.parse_args()
    print_banner()

    if args.digest:
        send_digest_now()
    elif args.summary:
        show_summary()
    elif args.test_email:
        test_email()
    elif args.test_mock:
        print("🧪 הרצת סימולציה (Mock Mode)...")
        scanner = FlightScanner(use_mock=True)
        scanner.run_scan()
        show_summary()
    elif args.watch:
        watch_mode(args.interval, use_mock=False)
    elif args.scan:
        scanner = FlightScanner(use_mock=False)
        scanner.run_scan()
        show_summary()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
