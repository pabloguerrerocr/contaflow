"""Reportes de salida: lo que el cliente recibe cada mes.

  - Libro de compras y libro de ventas
  - Resumen para el Formulario 150 (IVA mensual en TRIBU-CR; sustituyo al D-104)
  - Balance de comprobacion
  - Estado de resultados
  - Excepciones: lo que la maquina no pudo clasificar sola
"""
from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .asientos import Movimiento, r
from .clasificador import CUENTA_PUENTE
from .modelo import Comprobante

CERO = Decimal("0")


def _cuentas(catalogo: Path) -> dict[str, dict]:
    return {f["codigo"]: f for f in csv.DictReader(catalogo.open(encoding="utf-8"))}


# --------------------------------------------------------------- libros
def libro(comprobantes: list[Comprobante], rol: str) -> list[dict]:
    filas = []
    for c in (x for x in comprobantes if x.rol == rol):
        s = c.signo
        contraparte = c.emisor_nombre if rol == "compra" else c.receptor_nombre
        cedula = c.emisor_cedula if rol == "compra" else c.receptor_cedula
        filas.append({
            "fecha": c.fecha.isoformat(),
            "periodo": c.periodo,
            "tipo": c.tipo,
            "consecutivo": c.consecutivo,
            "clave": c.clave,
            "cedula": cedula,
            "contraparte": contraparte,
            "condicion": "contado" if c.condicion_venta == "01" else "credito",
            "moneda": c.moneda,
            "base": r(c.en_colones(c.subtotal) * s),
            "iva": r(c.en_colones(c.total_iva) * s),
            "total": r(c.en_colones(c.total) * s),
        })
    return sorted(filas, key=lambda f: (f["fecha"], f["consecutivo"]))


# ------------------------------------------------- Formulario 150 (IVA)
def resumen_iva(comprobantes: list[Comprobante], periodo: str) -> dict:
    """Desglose por tarifa para llenar el Formulario 150 de TRIBU-CR.

    Ojo: si hay ventas exentas o no sujetas, el credito fiscal no es 100%
    deducible; aplica prorrata (art. 27 Ley 6826). Aca se calcula el credito
    pleno y se marca la bandera para que el contador decida.
    """
    ventas = defaultdict(lambda: {"base": CERO, "iva": CERO})
    compras = defaultdict(lambda: {"base": CERO, "iva": CERO})

    for c in comprobantes:
        if c.periodo != periodo:
            continue
        destino = ventas if c.rol == "venta" else compras
        s = c.signo
        for linea in c.lineas:
            tarifa = str(linea.tarifa_iva.normalize())
            destino[tarifa]["base"] += c.en_colones(linea.subtotal) * s
            destino[tarifa]["iva"] += c.en_colones(linea.monto_iva) * s

    debito = sum((v["iva"] for v in ventas.values()), CERO)
    credito = sum((v["iva"] for v in compras.values()), CERO)
    base_gravada = sum((v["base"] for k, v in ventas.items() if k != "0"), CERO)
    base_exenta = ventas.get("0", {}).get("base", CERO)

    total_ventas = base_gravada + base_exenta
    proporcion = (base_gravada / total_ventas) if total_ventas else Decimal("1")

    return {
        "periodo": periodo,
        "ventas_por_tarifa": {k: {kk: r(vv) for kk, vv in v.items()}
                              for k, v in sorted(ventas.items())},
        "compras_por_tarifa": {k: {kk: r(vv) for kk, vv in v.items()}
                               for k, v in sorted(compras.items())},
        "debito_fiscal": r(debito),
        "credito_fiscal_pleno": r(credito),
        "base_gravada": r(base_gravada),
        "base_exenta": r(base_exenta),
        "aplica_prorrata": base_exenta > 0,
        "proporcion_deducible": round(float(proporcion), 4),
        "credito_fiscal_prorrateado": r(credito * proporcion),
        "saldo": r(debito - credito * proporcion),
    }


# ------------------------------------------------------------ contables
def balance_comprobacion(movs: list[Movimiento], catalogo: Path,
                         periodo: str | None = None) -> list[dict]:
    cuentas = _cuentas(catalogo)
    saldos: dict[str, dict] = defaultdict(lambda: {"debe": CERO, "haber": CERO})
    for m in movs:
        if periodo and m.periodo != periodo:
            continue
        saldos[m.cuenta]["debe"] += m.debe
        saldos[m.cuenta]["haber"] += m.haber

    filas = []
    for codigo in sorted(saldos):
        info = cuentas.get(codigo, {"nombre": "(fuera de catalogo)", "tipo": "?",
                                    "naturaleza": "deudora"})
        debe, haber = saldos[codigo]["debe"], saldos[codigo]["haber"]
        neto = debe - haber if info["naturaleza"] == "deudora" else haber - debe
        filas.append({
            "cuenta": codigo, "nombre": info["nombre"], "tipo": info["tipo"],
            "debe": r(debe), "haber": r(haber), "saldo": r(neto),
        })
    return filas


def estado_resultados(movs: list[Movimiento], catalogo: Path,
                      periodo: str | None = None) -> dict:
    filas = balance_comprobacion(movs, catalogo, periodo)
    por_tipo = defaultdict(list)
    for f in filas:
        por_tipo[f["tipo"]].append(f)

    ingresos = sum((f["saldo"] for f in por_tipo["ingreso"]), CERO)
    costos = sum((f["saldo"] for f in por_tipo["costo"]), CERO)
    gastos = sum((f["saldo"] for f in por_tipo["gasto"]), CERO)
    return {
        "periodo": periodo or "acumulado",
        "ingresos": r(ingresos),
        "costo_de_ventas": r(costos),
        "utilidad_bruta": r(ingresos - costos),
        "gastos_operativos": r(gastos),
        "utilidad_neta": r(ingresos - costos - gastos),
        "margen_neto": round(float((ingresos - costos - gastos) / ingresos), 4) if ingresos else 0.0,
        "detalle_gastos": sorted(por_tipo["gasto"], key=lambda f: -f["saldo"]),
        "detalle_ingresos": por_tipo["ingreso"],
    }


def excepciones(movs: list[Movimiento]) -> list[dict]:
    """Lo que el contador tiene que mirar con los ojos. Este es el reporte que
    hace que el servicio sea confiable: la maquina dice donde no esta segura."""
    filas = []
    for m in movs:
        if m.cuenta == CUENTA_PUENTE or (m.fuente and m.confianza < 0.8):
            filas.append({
                "fecha": m.fecha.isoformat(),
                "comprobante": m.comprobante,
                "contraparte": m.contraparte,
                "descripcion": m.descripcion,
                "cuenta_asignada": m.cuenta,
                "monto": r(m.debe + m.haber),
                "motivo": ("sin clasificar" if m.cuenta == CUENTA_PUENTE
                           else "confianza " + str(m.confianza)),
            })
    return filas


# ---------------------------------------------------------------- Excel
def exportar_excel(destino: Path, hojas: dict[str, list[dict]]) -> Path:
    import pandas as pd

    destino.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destino, engine="openpyxl") as writer:
        for nombre, filas in hojas.items():
            df = pd.DataFrame(filas) if filas else pd.DataFrame({"(vacio)": []})
            df.to_excel(writer, sheet_name=nombre[:31], index=False)
            hoja = writer.sheets[nombre[:31]]
            for col in hoja.columns:
                ancho = max((len(str(c.value)) for c in col if c.value is not None),
                            default=10)
                hoja.column_dimensions[col[0].column_letter].width = min(ancho + 2, 48)
    return destino
