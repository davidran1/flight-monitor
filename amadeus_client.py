import re
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def parse_iso_duration(duration_str: str) -> float:
    """
    Parses ISO 8601 duration string (e.g. 'PT13H45M', 'PT14H') into hours as a float.
    """
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration_str)
    if not match:
        return 0.0
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    return round(hours + (minutes / 60.0), 2)

class AmadeusFlightClient:
    def __init__(self, client_id: str, client_secret: str, environment: str = "production"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment
        self.base_url = "https://api.amadeus.com" if environment == "production" else "https://test.api.amadeus.com"
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _ensure_token(self):
        if self._access_token and time.time() < self._token_expires_at:
            return

        token_url = f"{self.base_url}/v1/security/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(token_url, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 1799)
        self._token_expires_at = time.time() + expires_in - 60  # Renew 1 minute early

    def search_roundtrip_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        airline_code: str = "EY",
        max_duration_hours: float = 15.0,
        currency: str = "USD"
    ) -> List[Dict[str, Any]]:
        """
        Searches for roundtrip flights with max duration constraint and specific airline.
        """
        self._ensure_token()

        search_url = f"{self.base_url}/v2/shopping/flight-offers"
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": 1,
            "includedAirlineCodes": airline_code,
            "currencyCode": currency,
            "max": 50
        }
        headers = {
            "Authorization": f"Bearer {self._access_token}"
        }

        # Handle rate-limiting gracefully
        for attempt in range(3):
            res = requests.get(search_url, params=params, headers=headers, timeout=20)
            if res.status_code == 429:
                wait_sec = 2 ** (attempt + 1)
                time.sleep(wait_sec)
                continue
            res.raise_for_status()
            break
        else:
            return []

        raw_data = res.json()
        return self._filter_and_parse_offers(raw_data, origin, destination, airline_code, max_duration_hours, departure_date, return_date)

    def _filter_and_parse_offers(
        self,
        raw_data: Dict[str, Any],
        origin: str,
        destination: str,
        airline_code: str,
        max_duration_hours: float,
        dep_date: str,
        ret_date: str
    ) -> List[Dict[str, Any]]:
        offers = raw_data.get("data", [])
        valid_flights = []

        dep_dt = datetime.strptime(dep_date, "%Y-%m-%d")
        ret_dt = datetime.strptime(ret_date, "%Y-%m-%d")
        stay_days = (ret_dt - dep_dt).days

        for offer in offers:
            itineraries = offer.get("itineraries", [])
            if len(itineraries) < 2:
                continue

            outbound = itineraries[0]
            inbound = itineraries[1]

            outbound_dur = parse_iso_duration(outbound.get("duration", "PT99H"))
            inbound_dur = parse_iso_duration(inbound.get("duration", "PT99H"))

            # Filter: Duration MUST be <= max_duration_hours in BOTH directions
            if outbound_dur > max_duration_hours or inbound_dur > max_duration_hours:
                continue

            # Ensure segments are operated/marketed by target airline
            out_segments = outbound.get("segments", [])
            in_segments = inbound.get("segments", [])

            out_airline_ok = all(s.get("carrierCode") == airline_code for s in out_segments)
            in_airline_ok = all(s.get("carrierCode") == airline_code for s in in_segments)

            if not (out_airline_ok and in_airline_ok):
                continue

            out_flight_nums = " + ".join(f"{s.get('carrierCode')}{s.get('number')}" for s in out_segments)
            in_flight_nums = " + ".join(f"{s.get('carrierCode')}{s.get('number')}" for s in in_segments)

            # Build readable summary of layover in Abu Dhabi (AUH)
            out_summary = self._build_itinerary_summary(out_segments, outbound_dur)
            in_summary = self._build_itinerary_summary(in_segments, inbound_dur)

            price = float(offer.get("price", {}).get("total", 0.0))
            currency = offer.get("price", {}).get("currency", "USD")

            flight_key = f"{origin}-{destination}_{dep_date}_{ret_date}_{out_flight_nums}_{in_flight_nums}"

            # Direct booking link
            etihad_link = (
                f"https://www.etihad.com/en-il/book?"
                f"origin={origin}&destination={destination}&departureDate={dep_date}&returnDate={ret_date}&cabin=ECONOMY&adults=1"
            )

            valid_flights.append({
                "flight_key": flight_key,
                "origin": origin,
                "destination": destination,
                "airline": "Etihad Airways",
                "departure_date": dep_date,
                "return_date": ret_date,
                "stay_days": stay_days,
                "outbound_flight_nums": out_flight_nums,
                "inbound_flight_nums": in_flight_nums,
                "outbound_duration_hours": outbound_dur,
                "inbound_duration_hours": inbound_dur,
                "outbound_summary": out_summary,
                "inbound_summary": in_summary,
                "price": price,
                "currency": currency,
                "booking_link": etihad_link
            })

        return valid_flights

    def _build_itinerary_summary(self, segments: List[Dict[str, Any]], total_duration: float) -> str:
        parts = []
        for i, s in enumerate(segments):
            carrier = s.get("carrierCode")
            num = s.get("number")
            dep_code = s.get("departure", {}).get("iataCode")
            arr_code = s.get("arrival", {}).get("iataCode")
            dep_time = s.get("departure", {}).get("at", "").split("T")[-1][:5]
            arr_time = s.get("arrival", {}).get("at", "").split("T")[-1][:5]
            parts.append(f"{carrier}{num} ({dep_code} {dep_time} ➔ {arr_code} {arr_time})")

        return f"{' | '.join(parts)} [סה\"כ {total_duration:.1f} שעות]"

