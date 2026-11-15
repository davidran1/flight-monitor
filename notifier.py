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

    def send_consolidated_alert(
        self,
        deals: List[Dict[str, Any]],
        max_price_usd: float,
        existing_cheapest: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Sends ONE consolidated email containing:
        1. All newly discovered flights / price drops under max_price_usd.
        2. The Top cheapest existing flights currently recorded in the database, sorted by price.
        3. Direct booking links for each flight.
        """
        if not deals:
            return False

        deals = sorted(deals, key=lambda d: d["price"])
        lowest_price = deals[0]["price"]
        count = len(deals)

        subject = f"✈️ התראת טיסות איתיחאד: נמצאו {count} טיסות חדשות מתחת ל-$1,100! (החל מ-${lowest_price:,.0f})"

        # 1. Build New Deals Rows
        new_deals_rows_html = ""
        for i, d in enumerate(deals, 1):
            f = d["flight"]
            alert_type = d["alert_type"]
            old_price = d.get("old_price")

            dep_dt = datetime.strptime(f['departure_date'], "%Y-%m-%d")
            ret_dt = datetime.strptime(f['return_date'], "%Y-%m-%d")
            dep_day = HEBREW_WEEKDAYS.get(dep_dt.weekday(), "")
            ret_day = HEBREW_WEEKDAYS.get(ret_dt.weekday(), "")

            if alert_type == "PRICE_DROP" and old_price:
                diff = old_price - f['price']
                price_badge = f"""
                <span style="font-size: 18px; font-weight: 800; color: #047857;">${f['price']:,.0f}</span><br>
                <del style="color:#94a3b8; font-size:12px;">${old_price:,.0f}</del>
                <span style="color:#d97706; font-size:12px; font-weight:bold;">(ירד ב-${diff:,.0f}!)</span>
                """
                tag = '<span style="background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">ירידת מחיר</span>'
            else:
                price_badge = f'<span style="font-size: 18px; font-weight: 800; color: #047857;">${f["price"]:,.0f}</span>'
                tag = '<span style="background:#d1fae5; color:#047857; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:bold;">טיסה חדשה</span>'

            new_deals_rows_html += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; background: {'#ffffff' if i%2!=0 else '#f8fafc'};">
              <td style="padding: 12px; font-weight: bold; text-align: center;">#{i}</td>
              <td style="padding: 12px;">
                {tag}<br>
                <strong>יציאה:</strong> יום {dep_day}, {f['departure_date']}<br>
                <strong>חזרה:</strong> יום {ret_day}, {f['return_date']}<br>
                <span style="color:#64748b; font-size:13px;">({f['stay_days']} ימי שהות בפוקט)</span>
              </td>
              <td style="padding: 12px; font-size:13px;">
                🛫 <strong>הלוך:</strong> {f['outbound_duration_hours']:.1f} שעות<br>
                🛬 <strong>חזור:</strong> {f['inbound_duration_hours']:.1f} שעות
              </td>
              <td style="padding: 12px; text-align: center;">
                {price_badge}
              </td>
              <td style="padding: 12px; text-align: center;">
                <a href="{f.get('booking_link', 'https://www.etihad.com')}" target="_blank"
                   style="display: inline-block; background-color: #d97706; color: #ffffff !important; padding: 8px 14px; border-radius: 6px; font-weight: bold; font-size: 13px; text-decoration: none;">
                  הזמן באתר איתיחאד ➔
                </a>
              </td>
            </tr>
            """

        # 2. Build Existing Top Database Flights Section
        existing_section_html = ""
        if existing_cheapest:
            existing_rows_html = ""
            for j, ef in enumerate(existing_cheapest, 1):
                edep_dt = datetime.strptime(ef['departure_date'], "%Y-%m-%d")
                eret_dt = datetime.strptime(ef['return_date'], "%Y-%m-%d")
                edep_day = HEBREW_WEEKDAYS.get(edep_dt.weekday(), "")
                eret_day = HEBREW_WEEKDAYS.get(eret_dt.weekday(), "")

                existing_rows_html += f"""
                <tr style="border-bottom: 1px solid #e2e8f0; background: {'#ffffff' if j%2!=0 else '#f8fafc'};">
                  <td style="padding: 10px; font-weight: bold; text-align: center;">{j}</td>
                  <td style="padding: 10px; font-size: 13px;">
                    יום {edep_day}, {ef['departure_date']} ➔ יום {eret_day}, {ef['return_date']}
                    <span style="color:#64748b;">({ef['stay_days']} ימים)</span>
                  </td>
                  <td style="padding: 10px; font-size: 12px; color:#475569;">
                    הלוך: {ef['outbound_duration_hours']:.1f}h | חזור: {ef['inbound_duration_hours']:.1f}h
                  </td>
                  <td style="padding: 10px; font-size: 16px; font-weight: bold; color: #047857; text-align: center;">
                    ${ef['lowest_price']:,.0f}
                  </td>
                  <td style="padding: 10px; text-align: center;">
                    <a href="{ef.get('booking_link', 'https://www.etihad.com')}" target="_blank"
                       style="display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 6px 12px; border-radius: 4px; font-size: 12px; text-decoration: none; font-weight: bold;">
                      הזמנה ➔
                    </a>
                  </td>
                </tr>
                """

            existing_section_html = f"""
            <div style="margin-top: 36px; padding-top: 24px; border-top: 2px dashed #cbd5e1;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0; font-size: 18px; color: #0f172a;">📊 10 הטיסות הזולות ביותר הקיימות כרגע במאגר:</h3>
              </div>
              <p style="margin: 0 0 12px 0; color: #64748b; font-size: 13px;">
                כל הטיסות ממוינות לפי המחיר הנמוך ביותר שנרשם במסד הנתונים:
              </p>
              <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                  <tr style="background: #f1f5f9;">
                    <th style="padding: 8px; text-align: center;">#</th>
                    <th style="padding: 8px;">תאריכים ושהות</th>
                    <th style="padding: 8px;">זמני טיסה</th>
                    <th style="padding: 8px; text-align: center;">מחיר שנשמר</th>
                    <th style="padding: 8px; text-align: center;">קישור</th>
                  </tr>
                </thead>
                <tbody>
                  {existing_rows_html}
                </tbody>
              </table>
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; }}
  .container {{ max-width: 720px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0; }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 28px 24px; text-align: center; }}
  .badge {{ display: inline-block; background-color: #10b981; color: #ffffff; padding: 4px 12px; border-radius: 9999px; font-size: 13px; font-weight: 600; }}
  .content {{ padding: 24px; color: #1e293b; text-align: right; }}
  .info-bar {{ background-color: #f8fafc; border-right: 4px solid #10b981; padding: 12px 16px; margin-bottom: 20px; border-radius: 4px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 14px; }}
  th {{ background-color: #f8fafc; padding: 12px; border-bottom: 2px solid #cbd5e1; color: #475569; font-weight: bold; text-align: right; }}
  .footer {{ background-color: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">התראת טיסות חדשות ומוזלות</span>
      <h1 style="margin: 12px 0 6px 0; font-size: 22px;">איתיחאד: תל אביב ⇄ פוקט מתחת ל-${max_price_usd:,.0f}</h1>
      <p style="margin:0; opacity:0.85; font-size:14px;">ינואר - 7 בפברואר • שהות 15-22 יום • ללא שישי ושבת • עד 15 שעות טיסה</p>
    </div>

    <div class="content">
      <div class="info-bar">
        ⚡ <strong>תוצאות סבב הסריקה האחרון:</strong><br>
        • זוהו <strong>{count} טיסות חדשות / צניחות מחיר</strong> מתחת ל-${max_price_usd:,.0f} (החל מ-<strong style="color:#047857;">${lowest_price:,.0f}</strong>).<br>
        • ממוינות למטה מהמחיר הנמוך ביותר לגבוה ביותר.
      </div>

      <h3 style="margin: 0 0 10px 0; font-size: 18px; color: #0f172a;">🔥 הטיסות החדשות שהתגלו בסבב זה:</h3>
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
          {new_deals_rows_html}
        </tbody>
      </table>

      {existing_section_html}
    </div>

    <div class="footer">
      מערכת ניטור טיסות איתיחאד • נסרק בענן בתאריך {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}<br>
      <a href="https://github.com/davidran1/flight-monitor" target="_blank" style="color: #2563eb; text-decoration: none; margin-top: 4px; display: inline-block;">
        🔗 צפייה במאגר הפרויקט ב-GitHub
      </a>
    </div>
  </div>
</body>
</html>"""

        plain_text = f"נמצאו {count} טיסות איתיחאד מתחת ל-${max_price_usd:,.0f} (החל מ-${lowest_price:,.0f}). פתח את המייל לצפייה בפרטים ובמאגר המלא."
        return self._send_mime(subject, plain_text, html_content)

    def send_test_email(self) -> bool:
        sample_deal = {
            "flight": {
                "origin": "TLV",
                "destination": "HKT",
                "departure_date": "2027-01-18",
                "return_date": "2027-02-05",
                "stay_days": 18,
                "outbound_flight_nums": "EY (TLV ➔ AUH ➔ HKT)",
                "inbound_flight_nums": "EY (HKT ➔ AUH ➔ TLV)",
                "outbound_duration_hours": 12.0,
                "inbound_duration_hours": 13.0,
                "price": 1050.0,
                "currency": "USD",
                "booking_link": "https://www.etihad.com"
            },
            "alert_type": "NEW_FLIGHT",
            "price": 1050.0
        }
        sample_existing = [
            {
                "departure_date": "2027-01-17",
                "return_date": "2027-02-02",
                "stay_days": 16,
                "outbound_duration_hours": 12.5,
                "inbound_duration_hours": 12.7,
                "lowest_price": 1400.0,
                "booking_link": "https://www.etihad.com"
            },
            {
                "departure_date": "2027-01-18",
                "return_date": "2027-02-03",
                "stay_days": 16,
                "outbound_duration_hours": 12.5,
                "inbound_duration_hours": 12.7,
                "lowest_price": 1400.0,
                "booking_link": "https://www.etihad.com"
            }
        ]
        return self.send_consolidated_alert([sample_deal], max_price_usd=1100.0, existing_cheapest=sample_existing)
