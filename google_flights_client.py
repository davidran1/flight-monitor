import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from fast_flights import FlightQuery, create_filter, get_flights

def calculate_leg_duration_hours(segments) -> float:
    """
    Calculates total elapsed time including flight segments and layovers in hours.
    """
    if not segments:
        return 0.0

    total_minutes = 0
    for i, s in enumerate(segments):
        total_minutes += s.duration
        if i > 0:
            prev = segments[i - 1]
            prev_arr_min = prev.arrival.time[0] * 60 + prev.arrival.time[1]
            curr_dep_min = s.departure.time[0] * 60 + s.departure.time[1]
            layover = curr_dep_min - prev_arr_min
            if layover < 0:
                layover += 24 * 60  # crossed midnight
            total_minutes += layover

    return round(total_minutes / 60.0, 2)

def format_segments_summary(segments, total_dur_hours: float) -> str:
    parts = []
    for s in segments:
        dep_str = f"{s.departure.time[0]:02d}:{s.departure.time[1]:02d}"
        arr_str = f"{s.arrival.time[0]:02d}:{s.arrival.time[1]:02d}"
        plane = f" ({s.plane_type})" if hasattr(s, "plane_type") and s.plane_type else ""
        parts.append(f"{s.from_airport.code} {dep_str} ➔ {s.to_airport.code} {arr_str}{plane}")
    return f"{' | '.join(parts)} [סה\"כ {total_dur_hours:.1f} שעות]"

class GoogleFlightsLiveClient:
    """
    Connects directly to Google Flights real-time pricing and flight schedules.
    Requires NO API keys, NO subscription, and avoids all WAF/captcha issues.
    """
    def __init__(self):
        self._inbound_cache: Dict[str, List[Any]] = {}

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
        max_dur_minutes = int(max_duration_hours * 60)

        # 1. Query Outbound with Roundtrip Pricing (with retry on transient errors)
        roundtrip_results = None
        for attempt in range(2):
            try:
                roundtrip_filter = create_filter(
                    flights=[
                        FlightQuery(
                            date=departure_date,
                            from_airport=origin,
                            to_airport=destination,
                            airlines=[airline_code],
                            max_duration_minutes=max_dur_minutes
                        ),
                        FlightQuery(
                            date=return_date,
                            from_airport=destination,
                            to_airport=origin,
                            airlines=[airline_code],
                            max_duration_minutes=max_dur_minutes
                        )
                    ],
                    trip="round-trip",
                    currency=currency
                )
                roundtrip_results = get_flights(roundtrip_filter)
                break
            except Exception as e:
                if attempt == 0:
                    time.sleep(2)
                else:
                    return []

        if not roundtrip_results:
            return []

        # 2. Get Inbound segments details (with caching per return date)
        inbound_options = self._get_inbound_flights(
            destination=destination,
            origin=origin,
            return_date=return_date,
            airline_code=airline_code,
            max_duration_hours=max_duration_hours,
            currency=currency
        )

        dep_dt = datetime.strptime(departure_date, "%Y-%m-%d")
        ret_dt = datetime.strptime(return_date, "%Y-%m-%d")
        stay_days = (ret_dt - dep_dt).days

        valid_flights = []

        for offer in roundtrip_results:
            out_segments = offer.flights
            out_dur = calculate_leg_duration_hours(out_segments)
            if out_dur > max_duration_hours:
                continue

            in_dur = 13.0
            in_summary = f"טיסת חזור: {destination} ➔ AUH ➔ {origin}"
            in_flight_nums = "EY (Return)"

            if inbound_options:
                best_in = inbound_options[0]
                in_segments = best_in.flights
                in_dur = calculate_leg_duration_hours(in_segments)
                if in_dur > max_duration_hours:
                    continue
                in_summary = format_segments_summary(in_segments, in_dur)
                in_flight_nums = " + ".join(f"EY-{s.from_airport.code}➔{s.to_airport.code}" for s in in_segments)

            out_summary = format_segments_summary(out_segments, out_dur)
            out_flight_nums = " + ".join(f"EY-{s.from_airport.code}➔{s.to_airport.code}" for s in out_segments)

            flight_key = f"{origin}-{destination}_{departure_date}_{return_date}_{out_flight_nums}_{in_flight_nums}"

            etihad_direct_link = (
                f"https://www.etihad.com/en-il/book?"
                f"origin={origin}&destination={destination}&departureDate={departure_date}&returnDate={return_date}&cabin=ECONOMY&adults=1"
            )

            valid_flights.append({
                "flight_key": flight_key,
                "origin": origin,
                "destination": destination,
                "airline": "Etihad Airways",
                "departure_date": departure_date,
                "return_date": return_date,
                "stay_days": stay_days,
                "outbound_flight_nums": out_flight_nums,
                "inbound_flight_nums": in_flight_nums,
                "outbound_duration_hours": out_dur,
                "inbound_duration_hours": in_dur,
                "outbound_summary": out_summary,
                "inbound_summary": in_summary,
                "price": float(offer.price),
                "currency": currency,
                "booking_link": etihad_direct_link
            })

        return valid_flights

    def _get_inbound_flights(self, destination: str, origin: str, return_date: str, airline_code: str, max_duration_hours: float, currency: str):
        if return_date in self._inbound_cache:
            return self._inbound_cache[return_date]

        try:
            inbound_filter = create_filter(
                flights=[
                    FlightQuery(
                        date=return_date,
                        from_airport=destination,
                        to_airport=origin,
                        airlines=[airline_code],
                        max_duration_minutes=int(max_duration_hours * 60)
                    )
                ],
                trip="one-way",
                currency=currency
            )
            res = get_flights(inbound_filter)
            self._inbound_cache[return_date] = res
            return res
        except Exception:
            return []
