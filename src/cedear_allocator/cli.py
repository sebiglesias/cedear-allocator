"""CLI principal de CEDEAR Allocator."""

import argparse
import datetime
import json
import os
import sys
from typing import Dict, List

from cedear_allocator import __version__
from cedear_allocator.calendar import ART_TZ, get_first_business_day, is_first_business_day
from cedear_allocator.market import DEFAULT_CEDEARS, fetch_dolar_rates, get_market_quotes
from cedear_allocator.optimizer import optimize_allocation

# ANSI Colors
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def parse_weights(weights_str: str, tickers: List[str]) -> Dict[str, float]:
    """Parsea una cadena de pesos separados por coma (ej. '70,20,10')."""
    parts = [float(x.strip()) for x in weights_str.split(",")]
    if len(parts) != len(tickers):
        raise ValueError(f"Se esperaban {len(tickers)} ponderaciones para los tickers {tickers}, se recibieron {len(parts)}.")
    return dict(zip(tickers, parts))


def cmd_check(args):
    """Comprueba si hoy es el primer día hábil del mes."""
    today = datetime.datetime.now(ART_TZ).date()
    is_first, first_bday = is_first_business_day(today)

    if args.json:
        print(json.dumps({
            "today": str(today),
            "first_business_day": str(first_bday),
            "is_first_business_day": is_first,
        }, indent=2))
        return 0 if is_first else 1

    print(f"\n{BOLD}🗓️  Verificador de Calendario Bancario (Argentina){RESET}")
    print(f"• Fecha actual:             {CYAN}{today}{RESET}")
    print(f"• 1er día hábil del mes:    {CYAN}{first_bday}{RESET}")
    if is_first:
        print(f"• Estado:                   {GREEN}¡Hoy es el primer día hábil del mes!{RESET}\n")
        return 0
    else:
        print(f"• Estado:                   {YELLOW}Hoy no es el primer día hábil del mes.{RESET}\n")
        return 1


def cmd_quotes(args):
    """Muestra cotizaciones de CEDEARs, subyacentes y CCL implícito."""
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    print(f"\n{BOLD}📈 Consultando mercado para {', '.join(tickers)}...{RESET}")

    rates = fetch_dolar_rates()
    ccl_ref = rates.get("ccl", rates.get("mep", 0.0))
    quotes = get_market_quotes(tickers, ccl_ref=ccl_ref)

    if args.json:
        out = {
            "rates": rates,
            "quotes": {
                t: {
                    "price_ars": q.price_ars,
                    "price_usd": q.price_usd,
                    "implied_ccl": q.implied_ccl,
                    "ccl_diff_pct": q.ccl_diff_pct,
                }
                for t, q in quotes.items()
            },
        }
        print(json.dumps(out, indent=2))
        return 0

    print(f"• Dólar CCL Referencia: {CYAN}${ccl_ref:,.2f}{RESET} | MEP: {CYAN}${rates.get('mep', 0):,.2f}{RESET}\n")
    print(f"{'Ticker':<8} {'Ratio':<8} {'Precio ARS':<14} {'Precio USD':<12} {'Implied CCL':<14} {'Desvío vs CCL':<14}")
    print("-" * 72)
    for t in tickers:
        q = quotes.get(t)
        meta = DEFAULT_CEDEARS.get(t)
        ratio = meta.ratio_str if meta else "—"
        if not q or q.price_ars == 0:
            print(f"{t:<8} {ratio:<8} {'—':<14} {'—':<12} {'—':<14} {'—':<14}")
            continue

        ccl_str = f"${q.implied_ccl:,.2f}" if q.implied_ccl else "—"
        if q.ccl_diff_pct is not None:
            color = RED if q.ccl_diff_pct > 1.5 else (GREEN if q.ccl_diff_pct < -0.5 else RESET)
            diff_str = f"{color}{q.ccl_diff_pct:+.2f}%{RESET}"
        else:
            diff_str = "—"

        print(f"{BOLD}{t:<8}{RESET} {ratio:<8} ${q.price_ars:<13,.2f} ${q.price_usd:<11,.2f} {ccl_str:<14} {diff_str:<14}")
    print()
    return 0


def cmd_calc(args):
    """Calcula la asignación entera óptima para un presupuesto dado."""
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    weights = parse_weights(args.weights, tickers)

    print(f"\n{BOLD}💰 Optimizador de Asignación de CEDEARs{RESET}")
    print(f"• Presupuesto: {CYAN}${args.budget:,.2f} ARS{RESET}")
    print(f"• Objetivos:   {', '.join(f'{k}: {v:.0f}%' for k, v in weights.items())}")

    rates = fetch_dolar_rates()
    ccl_ref = rates.get("ccl", rates.get("mep", 0.0))
    quotes = get_market_quotes(tickers, ccl_ref=ccl_ref)

    prices_ars = {t: q.price_ars for t, q in quotes.items()}
    missing = [t for t, p in prices_ars.items() if p <= 0]
    if missing:
        print(f"{YELLOW}Aviso: no se pudo obtener precio para {', '.join(missing)}.{RESET}")

    result = optimize_allocation(args.budget, prices_ars, weights)

    if args.json:
        out = {
            "budget_ars": result.budget_ars,
            "invested_ars": result.invested_ars,
            "cash_leftover_ars": result.cash_leftover_ars,
            "positions": [
                {
                    "ticker": p.ticker,
                    "nominales": p.nominales,
                    "price_ars": p.price_ars,
                    "total_ars": p.total_ars,
                    "target_weight_pct": p.target_weight_pct,
                    "actual_weight_pct": p.actual_weight_pct,
                }
                for p in result.positions
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    print(f"\n{'Ticker':<8} {'Objetivo':<10} {'Efectivo':<10} {'Nominales':<12} {'Precio Unit.':<14} {'Inversión Total':<16}")
    print("-" * 74)
    for p in result.positions:
        print(
            f"{BOLD}{p.ticker:<8}{RESET} "
            f"{p.target_weight_pct:>6.1f}%    "
            f"{p.actual_weight_pct:>6.1f}%    "
            f"{BOLD}{p.nominales:>8}{RESET}    "
            f"${p.price_ars:<13,.2f} "
            f"${p.total_ars:<15,.2f}"
        )
    print("-" * 74)
    print(f"• {BOLD}Total Invertido:{RESET}    {GREEN}${result.invested_ars:,.2f} ARS{RESET} ({result.invested_ars/result.budget_ars*100:.1f}%)")
    print(f"• {BOLD}Efectivo Restante:{RESET}  {YELLOW}${result.cash_leftover_ars:,.2f} ARS{RESET}")
    print(f"  {DIM}➔ Sugerencia: colocar el saldo restante en Caución ARS 1d o Money Market.{RESET}\n")
    return 0


def cmd_run(args):
    """Rutina mensual de ejecución completa en terminal."""
    today = datetime.datetime.now(ART_TZ).date()
    is_first, first_bday = is_first_business_day(today)

    if not is_first and not args.force:
        print(f"\n{YELLOW}Hoy ({today}) no es el primer día hábil del mes (fue/es {first_bday}).{RESET}")
        print("Usa --force si deseas ejecutar la rutina de todas formas.\n")
        return 0

    print(f"\n{BOLD}🚀 Ejecutando rutina mensual de CEDEARs ({today.strftime('%B %Y')})...{RESET}")
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    weights = parse_weights(args.weights, tickers)

    rates = fetch_dolar_rates()
    ccl_ref = rates.get("ccl", rates.get("mep", 0.0))
    quotes = get_market_quotes(tickers, ccl_ref=ccl_ref)

    cmd_quotes(args)
    if args.budget and args.budget > 0:
        prices_ars = {t: q.price_ars for t, q in quotes.items()}
        allocation = optimize_allocation(args.budget, prices_ars, weights)
        cmd_calc(args)

    print(f"\n{GREEN}✓ Rutina mensual finalizada.{RESET}\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="cedear-allocator",
        description="Optimizador de asignación mensual de sueldo a CEDEARs (SPY, VEA, IEMG).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # Command: check
    p_check = subparsers.add_parser("check", help="Comprueba si hoy es el primer día hábil del mes.")
    p_check.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    # Command: quotes
    p_quotes = subparsers.add_parser("quotes", help="Muestra cotizaciones de CEDEARs, subyacentes y CCL implícito.")
    p_quotes.add_argument("--tickers", default="SPY,VEA,IEMG", help="Tickers separados por coma (default: SPY,VEA,IEMG).")
    p_quotes.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    # Command: calc
    p_calc = subparsers.add_parser("calc", help="Calcula la cantidad entera de nominales para un presupuesto dado.")
    p_calc.add_argument("--budget", type=float, required=True, help="Presupuesto a invertir en pesos (ARS).")
    p_calc.add_argument("--weights", default="70,20,10", help="Ponderaciones objetivo (default: 70,20,10).")
    p_calc.add_argument("--tickers", default="SPY,VEA,IEMG", help="Tickers separados por coma (default: SPY,VEA,IEMG).")
    p_calc.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    # Command: run
    p_run = subparsers.add_parser("run", help="Ejecuta la rutina mensual completa.")
    p_run.add_argument("--budget", type=float, default=0.0, help="Presupuesto a invertir en pesos (opcional).")
    p_run.add_argument("--weights", default="70,20,10", help="Ponderaciones objetivo (default: 70,20,10).")
    p_run.add_argument("--tickers", default="SPY,VEA,IEMG", help="Tickers separados por coma (default: SPY,VEA,IEMG).")
    p_run.add_argument("--force", action="store_true", help="Fuerza ejecución aunque no sea el 1er día hábil.")
    p_run.add_argument("--json", action="store_true", help="Salida en formato JSON.")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "check": cmd_check,
        "quotes": cmd_quotes,
        "calc": cmd_calc,
        "run": cmd_run,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
