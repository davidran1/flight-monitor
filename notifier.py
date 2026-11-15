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

    def send_consolidated_alert(self, deals: List[Dict[str, Any]], max_price_usd: float) -> bool:
        """
        Sends ONE consolidated email containing all newly discovered flights and price drops
        under the price ceiling found in this specific scan run.
        """
        if not deals:
            return False

        # Sort deals by price ascending
        deals = sorted(deals, key=lambda d: d["price"])
        lowest_price = deals[0]["price"]
        count = len(deals)

        subject = f"✈️ התראת טיסות איתיחאד: נמצאו {count} טיסות חדשות מתחת ל-$1,100! (החל מ-${lowest_price:,.0f})"

        rows_html = ""
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

            rows_html += f"""
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
      <p style="margin:0; opacity:0.85; font-size:14px;">ינואר - פברואר • ללא שישי ושבת • עד 15 שעות טיסה</p>
    </div>

    <div class="content">
      <div class="info-bar">
        ⚡ <strong>תוצאות סבב הסריקה האחרון:</strong><br>
        • זוהו <strong>{count} טיסות חדשות / צניחות מחיר</strong> שעומדות בקריטריונים שלך.<br>
        • מחיר כולל: <strong>לא יותר מ-${max_price_usd:,.0f}</strong> (החל מ-<strong style="color:#047857;">${lowest_price:,.0f}</strong>).<br>
        • ללא ימי שישי ושבת, זמן טיסה עד 15 שעות בלבד.<br>
        • כל האפשרויות מסודרות למטה מהמחיר הנמוך ביותר לגבוה ביותר.
      </div>

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
          {rows_html}
        </tbody>
      </table>
    </div>

    <div class="footer">
      מערכת ניטור טיסות איתיחאד • נסרק בענן בתאריך {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    </div>
  </div>
</body>
</html>"""

        plain_text = f"נמצאו {count} טיסות איתיחאד מתחת ל-${max_price_usd:,.0f} (החל מ-${lowest_price:,.0f}). פתח את המייל לצפייה בפרטים."
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
        return self.send_consolidated_alert([sample_deal], max_price_usd=1100.0)
