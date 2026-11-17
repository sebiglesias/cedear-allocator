"""Módulo de integración con Obsidian vault y el gestor de tareas tk."""

import datetime
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional

from cedear_allocator.market import MarketQuote
from cedear_allocator.optimizer import AllocationResult

DEFAULT_VAULT = Path.home() / "obsidian" / "obsidian"
DEFAULT_TK = Path.home() / ".local" / "bin" / "tk"


def get_next_task_id(tk_bin: Path = DEFAULT_TK, items_dir: Optional[Path] = None) -> str:
    """Obtiene el próximo ID libre para el task board mediante 'tk next-id'."""
    if tk_bin.exists():
        try:
            res = subprocess.run([str(tk_bin), "next-id"], capture_output=True, text=True, check=True)
            tid = res.stdout.strip()
            if tid.startswith("T-"):
                return tid
        except Exception:
            pass

    # Fallback si no está tk en el path
    if items_dir and items_dir.exists():
        highest = 0
        for p in items_dir.glob("T-*"):
            num_part = p.name.split()[0].replace("T-", "").split(".")[0]
            if num_part.isdigit():
                highest = max(highest, int(num_part))
        return f"T-{highest + 1:03d}"

    return "T-999"


def create_obsidian_task(
    today: datetime.date,
    quotes: Dict[str, MarketQuote],
    rates: Dict[str, float],
    allocation: Optional[AllocationResult] = None,
    vault_path: Path = DEFAULT_VAULT,
    tk_bin: Path = DEFAULT_TK,
    start_session: bool = False,
) -> Optional[Path]:
    """Crea una nota de tarea en el Obsidian vault y opcionalmente inicia agy con tk start."""
    items_dir = vault_path / "Tasks" / "items"
    if not items_dir.exists():
        return None

    # Evitar duplicados para el mismo mes
    month_code = today.strftime("%Y-%m")
    existing = list(items_dir.glob(f"*CEDEARs*{month_code}*.md"))
    if existing:
        return existing[0]

    task_id = get_next_task_id(tk_bin, items_dir)
    month_name = today.strftime("%B %Y")
    filename = f"{task_id} Evaluar compra mensual de CEDEARs SPY VEA e IEMG - Mes {month_code}.md"
    file_path = items_dir / filename

    # Cotizaciones
    ccl_ref = rates.get("ccl", rates.get("mep", 0.0))
    mep_ref = rates.get("mep", 0.0)
    oficial_ref = rates.get("mayorista", rates.get("oficial", 0.0))

    quotes_table = "| Ticker | Precio ARS | Precio USD | Implied CCL | Desvío vs CCL |\n| :--- | :--- | :--- | :--- | :--- |\n"
    for t, q in quotes.items():
        ccl_str = f"${q.implied_ccl:,.2f}" if q.implied_ccl else "—"
        diff_str = f"{q.ccl_diff_pct:+.2f}%" if q.ccl_diff_pct is not None else "—"
        quotes_table += f"| **{t}** | ${q.price_ars:,.2f} | ${q.price_usd:,.2f} | {ccl_str} | {diff_str} |\n"

    alloc_section = ""
    if allocation:
        alloc_section = f"""
### Plan de asignación calculado (Presupuesto: ${allocation.budget_ars:,.2f} ARS)
| Ticker | Obj % | Real % | Nominales a Comprar | Precio Unitario | Inversión Total |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for p in allocation.positions:
            alloc_section += f"| **{p.ticker}** | {p.target_weight_pct:.1f}% | {p.actual_weight_pct:.1f}% | **{p.nominales}** | ${p.price_ars:,.2f} | ${p.total_ars:,.2f} |\n"
        alloc_section += f"""
- **Total Invertido:** ${allocation.invested_ars:,.2f} ARS
- **Remanente Efectivo:** ${allocation.cash_leftover_ars:,.2f} ARS *(Sugerido: colocar en Caución ARS 1d o Money Market)*
"""

    content = f"""---
id: {task_id}
status: todo
area: Personal
agent: agy
priority: 2
repo:
base:
parent:
depends_on: []
waiting_on:
due: {today.strftime('%Y-%m-%d')}
created: {today.strftime('%Y-%m-%d')}
branch:
worktree:
completed:
tags: [task, finanzas, cedears]
---
# Evaluar compra mensual de CEDEARs SPY VEA e IEMG - Mes {month_code}

## Context
Es el primer día hábil del mes ({month_name}). Corresponde evaluar la asignación de ahorro e inversión en CEDEARs diversificados para el portafolio de largo plazo:
1. **SPY** (S&P 500 — Large Cap Estados Unidos | Ratio 20:1)
2. **VEA** (Mercados Desarrollados ex-EE.UU. — Europa, Japón, Canadá | Ratio 2:1)
3. **IEMG** (Mercados Emergentes — Asia, Latinoamérica | Ratio 3:1)

*Cotizaciones de referencia:*
- **CCL Referencia:** ~${ccl_ref:,.2f} | **MEP:** ~${mep_ref:,.2f} | **Mayorista:** ~${oficial_ref:,.2f}

{quotes_table}
{alloc_section}
### Checklist de optimización previa en Research:
- **Pantalla `/dashboard-general` y `/divisas`:**
  - Chequear el **CCL AL30 / GD30** y el valor del **Canje** (Cable / MEP).
  - Chequear la tasa de **Caución ARS 1d** (TNA/VWAP) y tasas de letras cortas para evaluar calce de liquidación T+1.
- **Pantalla `/monitor-rv?tab=cedears`:**
  - Comparar el **`impliedCcl`** de SPY, VEA e IEMG contra el CCL mayorista de bonos.
  - Si el CEDEAR muestra un CCL con sobreprecio (>1% a 2% sobre AL30), colocar orden límite (*limit order*) en lugar de comprar a mercado.
- **Horario de rueda:**
  - Evitar los primeros 30 minutos de apertura (11:00–11:30 hs) en VEA e IEMG por horquilla de puntas abiertas. Operar preferentemente entre las **12:30 y 15:30 hs**.

## Acceptance criteria
- [ ] Revisar el CCL de referencia y el `impliedCcl` de SPY, VEA e IEMG en `https://research.allaria.cloud/monitor-rv?tab=cedears`.
- [ ] Definir el monto total a invertir y la ponderación por activo (ej. 70% SPY, 20% VEA, 10% IEMG).
- [ ] Comprobar el spread de compra/venta y colocar órdenes con precio límite en horario de alta liquidez (12:30 a 15:30 hs ART).
- [ ] Si la compra se realiza en plazo T+1, evaluar colocación de los fondos en tránsito en Caución 1 día para devengar tasa intradiaria.
- [ ] Registrar en el `## Log` las órdenes emitidas, precio pagado en ARS, nominales de cada CEDEAR y CCL implícito efectivo resultante.

## Subtasks

## Plan

## Log
- {today.strftime('%Y-%m-%d')} 10:00: tarea generada automáticamente por `cedear-allocator` en el 1er día hábil del mes.
"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    if start_session and tk_bin.exists():
        try:
            subprocess.run([str(tk_bin), "start", task_id, "-d"], check=False)
        except Exception:
            pass

    return file_path
