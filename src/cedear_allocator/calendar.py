"""Módulo de calendario bancario y feriados para el mercado argentino."""

import datetime
import json
import urllib.request
from typing import Optional, Set, Tuple

ART_TZ = datetime.timezone(datetime.timedelta(hours=-3))


def fetch_holidays(year: int) -> Set[str]:
    """Obtiene el conjunto de fechas de feriados bancarios y nacionales para Argentina.
    
    Consume la API pública de ArgentinaDatos (sin credenciales ni secrets).
    """
    url = f"https://api.argentinadatos.com/v1/feriados/{year}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cedear-allocator/0.1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            return {h["fecha"] for h in data if "fecha" in h}
    except Exception:
        # Fallback a conjunto vacío (usará lunes a viernes estándar)
        return set()


def get_first_business_day(year: int, month: int, holidays: Optional[Set[str]] = None) -> datetime.date:
    """Calcula la fecha exacta del primer día hábil para un mes y año dados."""
    if holidays is None:
        holidays = fetch_holidays(year)

    cur = datetime.date(year, month, 1)
    while cur.month == month:
        # 0 = Lunes, 4 = Viernes
        if cur.weekday() < 5 and cur.strftime("%Y-%m-%d") not in holidays:
            return cur
        cur += datetime.timedelta(days=1)

    return datetime.date(year, month, 1)


def is_first_business_day(target_date: Optional[datetime.date] = None) -> Tuple[bool, datetime.date]:
    """Evalúa si la fecha objetivo (o hoy en huso horario ART) es el primer día hábil del mes."""
    if target_date is None:
        target_date = datetime.datetime.now(ART_TZ).date()

    first_bday = get_first_business_day(target_date.year, target_date.month)
    return (target_date == first_bday), first_bday
