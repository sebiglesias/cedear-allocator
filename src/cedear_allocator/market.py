"""Módulo de datos de mercado, ratios y cálculo de CCL implícito."""

import json
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CedearMeta:
    ticker: str
    name: str
    underlying: str
    ratio_str: str  # ej. "60:1"
    cedears_per_share: float
    shares_per_cedear: float


# Ratios oficiales actualizados según Banco Comafi / BYMA
DEFAULT_CEDEARS: Dict[str, CedearMeta] = {
    "SPY": CedearMeta(
        ticker="SPY",
        name="SPDR S&P 500 ETF Trust",
        underlying="S&P 500 (USA Large Cap)",
        ratio_str="60:1",
        cedears_per_share=60.0,
        shares_per_cedear=1.0 / 60.0,
    ),
    "VEA": CedearMeta(
        ticker="VEA",
        name="Vanguard FTSE Developed Markets ETF",
        underlying="Desarrollados ex-EE.UU. (Europa, Japón, Canadá)",
        ratio_str="10:1",
        cedears_per_share=10.0,
        shares_per_cedear=1.0 / 10.0,
    ),
    "IEMG": CedearMeta(
        ticker="IEMG",
        name="iShares Core MSCI Emerging Markets ETF",
        underlying="Mercados Emergentes (China, India, Brasil)",
        ratio_str="12:1",
        cedears_per_share=12.0,
        shares_per_cedear=1.0 / 12.0,
    ),
    "QQQ": CedearMeta(
        ticker="QQQ",
        name="Invesco QQQ Trust",
        underlying="Nasdaq-100 (Tech)",
        ratio_str="60:1",
        cedears_per_share=60.0,
        shares_per_cedear=1.0 / 60.0,
    ),
    "DIA": CedearMeta(
        ticker="DIA",
        name="SPDR Dow Jones Industrial Average ETF",
        underlying="Dow Jones 30",
        ratio_str="60:1",
        cedears_per_share=60.0,
        shares_per_cedear=1.0 / 60.0,
    ),
}


@dataclass
class MarketQuote:
    ticker: str
    price_ars: float
    price_usd: float
    implied_ccl: Optional[float]
    ccl_diff_pct: Optional[float]  # Desvío % respecto al CCL de referencia


def fetch_yahoo_chart_price(symbol: str) -> Optional[float]:
    """Obtiene el último precio disponible desde el endpoint público de gráficos de Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
        with urllib.request.urlopen(req, timeout=6) as res:
            data = json.loads(res.read().decode("utf-8"))
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is not None and price > 0:
                return float(price)
            # Fallback a último cierre del array
            closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
            valid = [c for c in closes if c is not None and c > 0]
            return float(valid[-1]) if valid else None
    except Exception:
        return None


def fetch_dolar_rates() -> Dict[str, float]:
    """Obtiene cotizaciones de referencia de dólares financieros desde ArgentinaDatos."""
    url = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
    rates = {}
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cedear-allocator/0.1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode("utf-8"))
            by_casa = {}
            for item in data:
                casa = item.get("casa")
                fecha = item.get("fecha", "")
                if casa and (casa not in by_casa or fecha > by_casa[casa]["fecha"]):
                    by_casa[casa] = item
            for casa, item in by_casa.items():
                venta = item.get("venta") or item.get("compra") or 0.0
                rates[casa] = float(venta)

            # Mapeos convenientes
            if "contadoconliqui" in rates:
                rates["ccl"] = rates["contadoconliqui"]
            if "bolsa" in rates:
                rates["mep"] = rates["bolsa"]
    except Exception:
        pass
    return rates


def calculate_implied_ccl(price_ars: float, ratio_str: str, price_usd: float) -> Optional[float]:
    """Calcula el tipo de cambio CCL implícito de un CEDEAR:
    
    implied_ccl = (price_ars * cedears) / (shares * price_usd)
    """
    try:
        cedears, shares = [float(x) for x in ratio_str.split(":")]
        if price_ars > 0 and price_usd > 0 and cedears > 0 and shares > 0:
            return (price_ars * cedears) / (shares * price_usd)
    except Exception:
        pass
    return None


def get_market_quotes(tickers: List[str], ccl_ref: Optional[float] = None) -> Dict[str, MarketQuote]:
    """Obtiene cotizaciones en pesos, cotizaciones en USD del subyacente y calcula el CCL implícito."""
    quotes = {}
    for t in tickers:
        meta = DEFAULT_CEDEARS.get(t)
        if not meta:
            continue

        p_ars = fetch_yahoo_chart_price(f"{t}.BA") or 0.0
        p_usd = fetch_yahoo_chart_price(t) or 0.0

        ccl_imp = calculate_implied_ccl(p_ars, meta.ratio_str, p_usd) if (p_ars > 0 and p_usd > 0) else None

        diff_pct = None
        if ccl_imp and ccl_ref and ccl_ref > 0:
            diff_pct = ((ccl_imp - ccl_ref) / ccl_ref) * 100.0

        quotes[t] = MarketQuote(
            ticker=t,
            price_ars=p_ars,
            price_usd=p_usd,
            implied_ccl=ccl_imp,
            ccl_diff_pct=diff_pct,
        )
    return quotes
