import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, Any, Optional, List

HEBREW_WEEKDAYS = {
    0: "שני",
    1: "שלישי",
    2: "רביעי",
    3: "חמישי",
    4: "שישי",
    5: "שבת",
    6: "ראשון"
}

class EmailNotifier:
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        email_to: str = "",
        enabled: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.email_to = email_to or smtp_user
        self.enabled = enabled

    def is_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.email_to)

    def _send_mime(self, subject: str, plain_text: str, html_content: str) -> bool:
        with open("latest_email_preview.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        if not self.enabled or not self.is_configured():
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Etihad Flight Bot <{self.smtp_user}>"
            msg["To"] = self.email_to

            msg.attach(MIMEText(plain_text, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, [self.email_to], msg.as_string())

            print(f"  [Email Sent] '{subject}' נשלח ל-{self.email_to}")
            return True
        except Exception as e:
            print(f"  [Email Error] שגיאה בשליחת מייל: {e}")
            return False

    def send_alert(self, flight: Dict[str, Any], alert_type: str, old_price: Optional[float] = None) -> bool:
        subject, html_content = self._generate_alert_content(flight, alert_type, old_price)
        plain_text = (
            f"{subject}\n\n"
            f"מסלול: {flight['origin']} ➔ {flight['destination']}\n"
            f"תאריכים: {flight['departure_date']} עד {flight['return_date']} ({flight['stay_days']} ימים)\n"
            f"מחיר: {flight['price']} {flight['currency']}\n"
            f"הלוך: {flight['outbound_duration_hours']} שעות | חזור: {flight['inbound_duration_hours']} שעות\n"
            f"קישור: {flight.get('booking_link', '')}\n"
        )
        return self._send_mime(subject, plain_text, html_content)

    def send_digest_email(self, top_flights: List[Dict[str, Any]], total_scanned: int, min_price: float) -> bool:
        """
        Sends a single consolidated digest email containing the top cheapest flights found across the full scan.
        """
        subject = f"📊 דוח טיסות איתיחאד מרוכז: נמצאו טיסות לפוקט החל מ-${min_price:,.0f}!"

        flight_rows_html = ""
        for i, f in enumerate(top_flights, 1):
            dep_dt = datetime.strptime(f['departure_date'], "%Y-%m-%d")
            ret_dt = datetime.strptime(f['return_date'], "%Y-%m-%d")
            dep_day = HEBREW_WEEKDAYS.get(dep_dt.weekday(), "")
            ret_day = HEBREW_WEEKDAYS.get(ret_dt.weekday(), "")

            flight_rows_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; background: {'#ffffff' if i%2!=0 else '#f8fafc'};">
              <td style="padding: 12px; font-weight: bold; text-align: center;">#{i}</td>
              <td style="padding: 12px;">
                <strong>יציאה:</strong> יום {dep_day}, {f['departure_date']}<br>
                <strong>חזרה:</strong> יום {ret_day}, {f['return_date']}<br>
                <span style="color:#64748b; font-size:13px;">({f['stay_days']} ימי שהות בפוקט)</span>
              </td>
              <td style="padding: 12px; font-size:13px;">
                🛫 <strong>הלוך:</strong> {f['outbound_duration_hours']:.1f} שעות<br>
                🛬 <strong>חזור:</strong> {f['inbound_duration_hours']:.1f} שעות
              </td>
              <td style="padding: 12px; font-size: 18px; font-weight: bold; color: #047857; text-align: center;">
                ${f['lowest_price']:,.0f}
              </td>
              <td style="padding: 12px; text-align: center;">
                <a href="{f.get('booking_link', 'https://www.etihad.com')}" target="_blank"
                   style="display: inline-block; background-color: #d97706; color: #ffffff !important; padding: 8px 14px; border-radius: 6px; font-weight: bold; font-size: 13px; text-decoration: none;">
                  הזמן באתר איתיחאד ➔
                </a>
              </td>
            </tr>
            """

        html_content = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }}
  .container {{ max-width: 720px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0; }}
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff; padding: 28px 24px; text-align: center; }}
  .header h1 {{ margin: 0 0 8px 0; font-size: 22px; font-weight: 700; }}
  .badge {{ display: inline-block; background-color: #059669; color: #ffffff; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600; }}
  .content {{ padding: 24px; color: #1e293b; text-align: right; }}
  .info-bar {{ background-color: #f8fafc; border-right: 4px solid #3b82f6; padding: 12px 16px; margin-bottom: 20px; border-radius: 4px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
  th {{ background-color: #f8fafc; padding: 12px; border-bottom: 2px solid #cbd5e1; color: #475569; font-weight: bold; text-align: right; }}
  .footer {{ background-color: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">דוח סריקה מרוכז</span>
      <h1 style="margin-top:12px;">טיסות איתיחאד לתאילנד: TLV ⇄ HKT</h1>
      <p style="margin:0; opacity:0.85; font-size:14px;">ינואר - פברואר • ללא שישי ושבת • עד 15 שעות טיסה</p>
    </div>

    <div class="content">
      <div class="info-bar">
        📌 <strong>תוצאות הסריקה המלאה:</strong><br>
        • נסרקו כל קומבינציות התאריכים (שהות 15-25 ימים).<br>
        • <strong>הוחרגו טיסות בימי שישי ושבת</strong> (גם בהלוך וגם בחזור).<br>
        • סה"כ טיסות שנשמרו במאגר: <strong>{total_scanned}</strong><br>
        • המחיר הזול ביותר שהתגלה: <strong style="color:#047857; font-size:16px;">${min_price:,.0f}</strong><br>
        • מעכשיו המערכת עוקבת ברקע ותתריע רק על <strong>טיסות חדשות שנוספות או ירידות מחיר</strong>!
      </div>

      <h3 style="margin: 20px 0 10px 0; color: #0f172a;">🏆 הטיסות המשתלמות ביותר (ממוינות לפי המחיר הנמוך ביותר):</h3>
      <table>
        <thead>
          <tr>
            <th style="text-align: center;">#</th>
            <th>תאריכים ושהות</th>
            <th>זמני טיסה</th>
            <th style="text-align: center;">מחיר הלוך-חזור</th>
            <th style="text-align: center;">הזמנה</th>
          </tr>
        </thead>
        <tbody>
          {flight_rows_html}
        </tbody>
      </table>
    </div>

    <div class="footer">
      מערכת ניטור טיסות איתיחאד • עודכן בתאריך {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    </div>
  </div>
</body>
</html>"""

        plain_text = f"דוח סריקה מרוכז: נמצאו {total_scanned} טיסות החל מ-${min_price:.0f}. פתח את המייל לצפייה בטבלה המלאה."
        return self._send_mime(subject, plain_text, html_content)

    def send_test_email(self) -> bool:
        sample_flight = {
            "origin": "TLV",
            "destination": "HKT",
            "departure_date": "2027-01-18",
            "return_date": "2027-02-05",
            "stay_days": 18,
            "outbound_flight_nums": "EY (TLV ➔ AUH ➔ HKT)",
            "inbound_flight_nums": "EY (HKT ➔ AUH ➔ TLV)",
            "outbound_duration_hours": 12.0,
            "inbound_duration_hours": 13.0,
            "outbound_summary": "TLV ➔ AUH (3h) | AUH ➔ HKT (6.2h) [סה\"כ 12.0 שעות]",
            "inbound_summary": "HKT ➔ AUH (6.5h) | AUH ➔ TLV (3.5h) [סה\"כ 13.0 שעות]",
            "price": 1700.0,
            "currency": "USD",
            "booking_link": "https://www.etihad.com"
        }
        return self.send_alert(sample_flight, "TEST_ALERT")

    def _generate_alert_content(self, f: Dict[str, Any], alert_type: str, old_price: Optional[float] = None) -> tuple[str, str]:
        currency = f.get("currency", "USD")
        curr_symbol = "$" if currency == "USD" else ("₪" if currency == "ILS" else currency)
        price = f['price']

        if alert_type == "NEW_FLIGHT":
            badge_title = "טיסה חדשה נוספה למערכת!"
            badge_color = "#10b981"
            subject = f"✈️ טיסת איתיחאד חדשה לפוקט! {curr_symbol}{price:,.0f} ({f['departure_date']} - {f['return_date']})"
            price_subtext = f"מחיר פתיחה מעולה: {curr_symbol}{price:,.0f}"
        elif alert_type == "PRICE_DROP":
            badge_title = "ירידת מחיר זוהתה!"
            badge_color = "#f59e0b"
            diff = (old_price - price) if old_price else 0
            subject = f"📉 צניחת מחיר בטיסת איתיחאד! כעת {curr_symbol}{price:,.0f} (ירד ב-{curr_symbol}{diff:,.0f})"
            price_subtext = f"<del style='color:#9ca3af;'>{curr_symbol}{old_price:,.0f}</del> <strong style='color:#10b981;'>{curr_symbol}{price:,.0f}</strong> (חיסכון של {curr_symbol}{diff:,.0f}!)"
        else:
            badge_title = "בדיקת מערכת התראות"
            badge_color = "#3b82f6"
            subject = f"🧪 בדיקת חיבור מערכת ההתראות - איתיחאד לפוקט"
            price_subtext = f"מחיר לדוגמה: {curr_symbol}{price:,.0f}"

        html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e5e7eb; }}
  .header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff; padding: 28px 24px; text-align: center; }}
  .header h1 {{ margin: 0 0 8px 0; font-size: 22px; font-weight: 700; }}
  .badge {{ display: inline-block; background-color: {badge_color}; color: #ffffff; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600; }}
  .content {{ padding: 24px; color: #1f2937; line-height: 1.6; text-align: right; }}
  .price-box {{ background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 8px; padding: 16px; text-align: center; margin: 20px 0; }}
  .price-main {{ font-size: 32px; font-weight: 800; color: #0f172a; margin: 0; }}
  .flight-card {{ background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .flight-title {{ font-weight: 700; color: #334155; margin-bottom: 8px; display: flex; justify-content: space-between; }}
  .route-info {{ font-size: 14px; color: #475569; margin: 4px 0; }}
  .duration-pill {{ background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  .btn-wrapper {{ text-align: center; margin-top: 28px; }}
  .btn {{ display: inline-block; background-color: #d97706; color: #ffffff !important; padding: 14px 28px; border-radius: 8px; font-weight: 700; text-decoration: none; font-size: 16px; }}
  .footer {{ background-color: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">{badge_title}</span>
      <h1 style="margin-top:12px;">תל אביב (TLV) ⇄ פוקט (HKT)</h1>
      <p style="margin:0; opacity:0.85; font-size:14px;">איתיחאד איירווייז • עצירה קצרה באבו דאבי</p>
    </div>

    <div class="content">
      <div class="price-box">
        <p class="price-main">{curr_symbol}{price:,.0f}</p>
        <p style="margin:4px 0 0 0; font-size:14px;">{price_subtext}</p>
      </div>

      <div class="flight-card">
        <div class="flight-title">
          <span>🛫 טיסת הלוך: {f['departure_date']}</span>
          <span class="duration-pill">{f['outbound_duration_hours']:.1f} שעות</span>
        </div>
        <p class="route-info"><strong>טיסות:</strong> {f['outbound_flight_nums']}</p>
        <p class="route-info" style="font-size:13px; color:#64748b;">{f['outbound_summary']}</p>
      </div>

      <div class="flight-card">
        <div class="flight-title">
          <span>🛬 טיסת חזור: {f['return_date']}</span>
          <span class="duration-pill">{f['inbound_duration_hours']:.1f} שעות</span>
        </div>
        <p class="route-info"><strong>משך שהות בפוקט:</strong> {f['stay_days']} ימים</p>
        <p class="route-info"><strong>טיסות:</strong> {f['inbound_flight_nums']}</p>
        <p class="route-info" style="font-size:13px; color:#64748b;">{f['inbound_summary']}</p>
      </div>

      <div class="btn-wrapper">
        <a href="{f.get('booking_link', 'https://www.etihad.com')}" target="_blank" class="btn">
          צפייה והזמנה ישירה באתר Etihad Airways ➔
        </a>
      </div>
    </div>

    <div class="footer">
      התראה זו נשלחה אוטומטית על ידי סורק הטיסות האישי שלך.<br>
      זמן סריקה: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    </div>
  </div>
</body>
</html>"""
        return subject, html
