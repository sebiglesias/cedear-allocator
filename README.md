# CEDEAR Allocator

Herramienta de línea de comandos (CLI) en Python para optimizar la asignación periódica de ahorro en pesos a CEDEARs indexados (**SPY**, **VEA**, **IEMG**) en el mercado bursátil argentino (BYMA).

## Características principales

- **Cálculo de nominales enteros:** Optimiza las compras sin exceder el presupuesto en pesos, minimizando el desvío respecto a las ponderaciones deseadas (ej. 70/20/10).
- **Detección de feriados bancarios y días hábiles:** Consulta el calendario oficial del BCRA (vía ArgentinaDatos) para evaluar el primer día hábil del mes.
- **Cotizaciones y CCL implícito:** Compara el CCL implícito de cada CEDEAR contra el dólar financiero de referencia para detectar primas o sobreprecios antes de operar.
- **Sin dependencias externas ni secrets:** Funciona exclusivamente con la biblioteca estándar de Python 3 y APIs públicas sin credenciales.

## Instalación rápida

```bash
git clone https://github.com/sebiglesias/cedear-allocator.git
cd cedear-allocator
pip install -e .
```

## Uso

### 1. Consultar cotizaciones y CCL implícito
```bash
cedear-allocator quotes
```

### 2. Calcular nominales para un presupuesto en pesos
```bash
cedear-allocator calc --budget 500000 --weights 70,20,10
```

### 3. Verificar si hoy es el primer día hábil del mes
```bash
cedear-allocator check
```

### 4. Ejecución mensual completa
```bash
cedear-allocator run --budget 500000 --weights 70,20,10
```
