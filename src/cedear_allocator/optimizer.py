"""Módulo de optimización de asignación entera de capital para CEDEARs."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PositionPlan:
    ticker: str
    target_weight_pct: float
    actual_weight_pct: float
    price_ars: float
    nominales: int
    total_ars: float


@dataclass
class AllocationResult:
    budget_ars: float
    invested_ars: float
    cash_leftover_ars: float
    positions: List[PositionPlan]


def optimize_allocation(
    budget_ars: float,
    prices_ars: Dict[str, float],
    weights: Dict[str, float],
) -> AllocationResult:
    """Calcula la cantidad entera de nominales a comprar por cada CEDEAR para
    respetar al máximo las ponderaciones objetivo sin exceder el presupuesto.
    
    Parámetros:
      budget_ars: Presupuesto total en pesos argentinos.
      prices_ars: Diccionario {ticker: precio_ars}.
      weights: Diccionario {ticker: ponderación_objetivo} (deben sumar 100 o 1.0).
    """
    # Normalizar pesos a proporciones (suman 1.0)
    total_w = sum(weights.values())
    if total_w <= 0:
        raise ValueError("La suma de las ponderaciones debe ser mayor a 0.")
    norm_w = {k: v / total_w for k, v in weights.items()}

    # Filtrar solo tickers que tienen precio válido (> 0)
    valid_tickers = [t for t in norm_w if prices_ars.get(t, 0) > 0]
    if not valid_tickers:
        return AllocationResult(
            budget_ars=budget_ars,
            invested_ars=0.0,
            cash_leftover_ars=budget_ars,
            positions=[],
        )

    # 1. Asignación base redondeada hacia abajo (floor)
    nominales = {}
    for t in valid_tickers:
        target_amount = budget_ars * norm_w[t]
        nominales[t] = int(target_amount // prices_ars[t])

    # 2. Asignación greedy del remanente de efectivo
    def current_invested() -> float:
        return sum(nominales[t] * prices_ars[t] for t in valid_tickers)

    while True:
        leftover = budget_ars - current_invested()
        # Encontrar qué tickers entran en el saldo restante
        affordable = [t for t in valid_tickers if prices_ars[t] <= leftover]
        if not affordable:
            break

        # Elegir el ticker cuya ponderación actual esté más por debajo del objetivo
        inv = current_invested()
        best_ticker = None
        best_deficiency = -float("inf")

        for t in affordable:
            curr_weight = (nominales[t] * prices_ars[t]) / (inv if inv > 0 else 1.0)
            deficiency = norm_w[t] - curr_weight
            if deficiency > best_deficiency:
                best_deficiency = deficiency
                best_ticker = t

        if best_ticker is None:
            break

        nominales[best_ticker] += 1

    total_invested = current_invested()
    cash_leftover = budget_ars - total_invested

    # Construir el plan detallado
    positions = []
    for t in valid_tickers:
        tot = nominales[t] * prices_ars[t]
        act_pct = (tot / total_invested * 100.0) if total_invested > 0 else 0.0
        positions.append(
            PositionPlan(
                ticker=t,
                target_weight_pct=norm_w[t] * 100.0,
                actual_weight_pct=act_pct,
                price_ars=prices_ars[t],
                nominales=nominales[t],
                total_ars=tot,
            )
        )

    return AllocationResult(
        budget_ars=budget_ars,
        invested_ars=total_invested,
        cash_leftover_ars=cash_leftover,
        positions=positions,
    )
