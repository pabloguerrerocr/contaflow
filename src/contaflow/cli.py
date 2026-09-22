"""contaflow - cierre contable mensual a partir de comprobantes electronicos.

  python -m contaflow --cedula 3101789456 --periodo 2026-03
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from . import asientos, reportes
from .clasificador import CUENTA_PUENTE, Clasificador
from .parser import leer_carpeta

RAIZ = Path(__file__).resolve().parents[2]


def _json(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(type(obj))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="contaflow", description=__doc__)
    p.add_argument("--cedula", required=True,
                   help="Cedula juridica o fisica del cliente que se contabiliza")
    p.add_argument("--periodo", help="Periodo AAAA-MM. Por defecto, todos los que aparezcan")
    p.add_argument("--entrada", type=Path, default=RAIZ / "data" / "entrada")
    p.add_argument("--salida", type=Path, default=RAIZ / "salida")
    p.add_argument("--catalogo", type=Path, default=RAIZ / "config" / "catalogo_cuentas.csv")
    args = p.parse_args(argv)

    t0 = time.time()

    comprobantes, errores = leer_carpeta(args.entrada, args.cedula)
    if not comprobantes:
        print(f"No se encontraron comprobantes de {args.cedula} en {args.entrada}",
              file=sys.stderr)
        for archivo, motivo in errores[:10]:
            print(f"  {archivo}: {motivo}", file=sys.stderr)
        return 1

    periodos = sorted({c.periodo for c in comprobantes})
    if args.periodo:
        comprobantes = [c for c in comprobantes if c.periodo == args.periodo]
        periodos = [args.periodo]

    clas = Clasificador(args.catalogo)

    movs = asientos.generar(comprobantes, clas)
    pendientes = len(clas.sin_resolver)

    desc = asientos.descuadre(movs)
    if desc != 0:
        print(f"AVISO: el libro no cuadra por {desc}", file=sys.stderr)

    hojas = {
        "Libro de compras": reportes.libro(comprobantes, "compra"),
        "Libro de ventas": reportes.libro(comprobantes, "venta"),
        "Diario": [asdict(m) | {"fecha": m.fecha.isoformat()} for m in movs],
        "Balance comprobacion": reportes.balance_comprobacion(movs, args.catalogo),
        "Excepciones": reportes.excepciones(movs),
    }

    resumen = {"cedula": args.cedula, "periodos": {}}
    for per in periodos:
        iva = reportes.resumen_iva(comprobantes, per)
        er = reportes.estado_resultados(movs, args.catalogo, per)
        resumen["periodos"][per] = {"formulario_150": iva, "estado_resultados": er}
        hojas[f"F150 {per}"] = [
            {"concepto": "Debito fiscal (ventas)", "monto": iva["debito_fiscal"]},
            {"concepto": "Credito fiscal (compras)", "monto": iva["credito_fiscal_pleno"]},
            {"concepto": "Proporcion deducible", "monto": iva["proporcion_deducible"]},
            {"concepto": "Credito aplicable", "monto": iva["credito_fiscal_prorrateado"]},
            {"concepto": "IVA a pagar" if iva["saldo"] >= 0 else "Saldo a favor",
             "monto": abs(iva["saldo"])},
        ]

    args.salida.mkdir(parents=True, exist_ok=True)
    etiqueta = args.periodo or "todos"
    xlsx = reportes.exportar_excel(args.salida / f"cierre_{args.cedula}_{etiqueta}.xlsx", hojas)
    (args.salida / f"resumen_{args.cedula}_{etiqueta}.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False, default=_json), encoding="utf-8")

    excep = hojas["Excepciones"]
    total_lineas = sum(len(c.lineas) for c in comprobantes)
    automatico = 100 * (1 - len(excep) / total_lineas) if total_lineas else 0

    print(f"Comprobantes procesados : {len(comprobantes)}  ({total_lineas} lineas)")
    print(f"Descartados             : {len(errores)}")
    print(f"Periodos                : {', '.join(periodos)}")
    print(f"Conceptos sin regla: {pendientes} (van a la cuenta puente {CUENTA_PUENTE})")
    print(f"Automatizacion          : {automatico:.1f}%  ({len(excep)} a revision manual)")
    print(f"Descuadre del diario    : {desc}")
    for per, d in resumen["periodos"].items():
        f150 = d["formulario_150"]
        er = d["estado_resultados"]
        signo = "a pagar" if f150["saldo"] >= 0 else "a favor"
        print(f"  {per}  IVA {signo}: {abs(f150['saldo']):>12,.2f}   "
              f"utilidad neta: {er['utilidad_neta']:>14,.2f}")
    print(f"Excel                   : {xlsx}")
    print(f"Tiempo                  : {time.time() - t0:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
