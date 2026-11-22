import os
import webbrowser
import sqlite3
from datetime import datetime

HEBREW_WEEKDAYS = {
    0: "שני",
    1: "שלישי",
    2: "רביעי",
    3: "חמישי",
    4: "שישי",
    5: "שבת",
    6: "ראשון"
}

def generate_html_report(db_path: str = "flights.db", output_file: str = "flights_report.html", auto_open: bool = True):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT origin, destination, airline, departure_date, return_date, stay_days,
               outbound_flight_nums, inbound_flight_nums,
               outbound_duration_hours, inbound_duration_hours,
               outbound_summary, inbound_summary, lowest_price, latest_price, currency, booking_link
        FROM flights
        ORDER BY lowest_price ASC, (outbound_duration_hours + inbound_duration_hours) ASC
    """)
    flights = [dict(r) for r in c.fetchall()]
    conn.close()

    total_count = len(flights)
    min_price = flights[0]["lowest_price"] if flights else 0
    max_price = flights[-1]["lowest_price"] if flights else 0

    rows_html = ""
    for i, f in enumerate(flights, 1):
        dep_dt = datetime.strptime(f['departure_date'], "%Y-%m-%d")
        ret_dt = datetime.strptime(f['return_date'], "%Y-%m-%d")
        dep_day = HEBREW_WEEKDAYS.get(dep_dt.weekday(), "")
        ret_day = HEBREW_WEEKDAYS.get(ret_dt.weekday(), "")

        deal_class = "deal-cheap" if f['lowest_price'] <= 1100 else ""
        deal_badge = '<span class="badge-cheap">🔥 דיל מעולה</span>' if f['lowest_price'] <= 1100 else ''

        rows_html += f"""
        <tr class="{deal_class}">
          <td style="text-align: center; font-weight: bold;">{i}</td>
          <td>
            {deal_badge}
            <strong>יציאה:</strong> יום {dep_day}, {f['departure_date']}<br>
            <strong>חזרה:</strong> יום {ret_day}, {f['return_date']}<br>
            <span style="color: #64748b; font-size: 13px;">({f['stay_days']} ימי שהות בפוקט)</span>
          </td>
          <td>
            🛫 <strong>הלוך:</strong> {f['outbound_duration_hours']:.1f} שעות<br>
            🛬 <strong>חזור:</strong> {f['inbound_duration_hours']:.1f} שעות<br>
            <span style="color: #64748b; font-size: 12px;">{f['outbound_flight_nums']}</span>
          </td>
          <td style="text-align: center;">
            <span class="price-tag">${f['lowest_price']:,.0f}</span>
          </td>
          <td style="text-align: center;">
            <a href="{f.get('booking_link', 'https://www.etihad.com')}" target="_blank" class="btn-book">
              הזמן באתר Etihad ➔
            </a>
          </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<title>מאגר טיסות איתיחאד לפוקט - TLV ⇄ HKT</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #0f172a; }}
  .container {{ max-width: 1000px; margin: 0 auto; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0; overflow: hidden; }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 32px 24px; text-align: center; }}
  .stats-bar {{ display: flex; justify-content: space-around; background: #f1f5f9; padding: 16px; border-bottom: 1px solid #cbd5e1; }}
  .stat-card {{ text-align: center; }}
  .stat-val {{ font-size: 24px; font-weight: 800; color: #047857; margin: 0; }}
  .stat-lbl {{ font-size: 12px; color: #64748b; text-transform: uppercase; margin: 0; }}
  .search-box {{ padding: 16px 24px; background: #ffffff; border-bottom: 1px solid #e2e8f0; display: flex; gap: 12px; }}
  .search-input {{ flex: 1; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ background: #f8fafc; padding: 14px; border-bottom: 2px solid #cbd5e1; text-align: right; color: #475569; }}
  td {{ padding: 14px; border-bottom: 1px solid #e2e8f0; vertical-align: middle; }}
  tr:hover {{ background-color: #f8fafc; }}
  .price-tag {{ font-size: 20px; font-weight: 800; color: #047857; }}
  .badge-cheap {{ background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; margin-bottom: 4px; }}
  .btn-book {{ background: #d97706; color: #ffffff !important; padding: 8px 16px; border-radius: 6px; font-weight: 700; text-decoration: none; font-size: 13px; display: inline-block; transition: background 0.2s; }}
  .btn-book:hover {{ background: #b45309; }}
  .footer {{ padding: 16px; text-align: center; font-size: 12px; color: #64748b; background: #f8fafc; border-top: 1px solid #e2e8f0; }}
</style>
<script>
  function filterTable() {{
    const query = document.getElementById('search').value.toLowerCase();
    const rows = document.querySelectorAll('tbody tr');
    rows.forEach(r => {{
      const text = r.innerText.toLowerCase();
      r.style.display = text.includes(query) ? '' : 'none';
    }});
  }}
</script>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1 style="margin: 0 0 8px 0; font-size: 24px;">📊 מאגר כל טיסות איתיחאד שנשמרו: TLV ⇄ HKT</h1>
      <p style="margin: 0; opacity: 0.85;">ינואר - פברואר 2027 • ללא שישי ושבת • משך טיסה עד 15 שעות בלבד</p>
    </div>

    <div class="stats-bar">
      <div class="stat-card">
        <p class="stat-val">{total_count}</p>
        <p class="stat-lbl">סה"כ טיסות במאגר</p>
      </div>
      <div class="stat-card">
        <p class="stat-val">${min_price:,.0f}</p>
        <p class="stat-lbl">מחיר נמוך ביותר</p>
      </div>
      <div class="stat-card">
        <p class="stat-val" style="color: #64748b;">${max_price:,.0f}</p>
        <p class="stat-lbl">מחיר מרבי במאגר</p>
      </div>
    </div>

    <div class="search-box">
      <input type="text" id="search" class="search-input" onkeyup="filterTable()" placeholder="🔍 חפש לפי תאריך יציאה, חזרה, משך שהות או יום בשבוע...">
    </div>

    <table>
      <thead>
        <tr>
          <th style="width: 50px; text-align: center;">#</th>
          <th>תאריכים ושהות</th>
          <th>זמני טיסה ומקטעים</th>
          <th style="text-align: center; width: 120px;">מחיר הלוך-חזור</th>
          <th style="text-align: center; width: 160px;">הזמנה ישירה</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <div class="footer">
      דוח מאגר טיסות מקומי • הופק בתאריך {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    </div>
  </div>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ דוח מלא של כל {total_count} הטיסות הופק בהצלחה לקובץ: {output_file}")
    if auto_open:
        abs_path = os.path.abspath(output_file)
        webbrowser.open(f"file://{abs_path}")

if __name__ == "__main__":
    generate_html_report()

