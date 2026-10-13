"""Prueba contaflow contra la verdad que trae cada XML.

Cada comprobante electronico lleva su propio ResumenFactura, firmado por el
emisor y aceptado por Hacienda. Ese resumen es la respuesta correcta: se lee
aparte, sin pasar por el parser, y se compara con lo que contaflow calcula.

Hipotesis (todas se aceptan o se rechazan con un numero):
  H1 lectura      contaflow lee el 100 % de los comprobantes contabilizables.
  H2 base         la suma de las lineas = TotalVentaNeta del XML (+-1 colon).
  H3 IVA          el IVA de las lineas = TotalImpuesto del XML (+-1 colon).
  H4 total        lo que se registra contra Caja/CxP = TotalComprobante (+-1 colon).
  H5 cuadre       cada asiento cuadra en 0,00.
  H6 velocidad    menos de 1 segundo por comprobante.
Ademas se mide la cobertura del clasificador (lineas resueltas sin ayuda).

Uso:
  PYTHONPATH=src python scripts/experimento.py CARPETA CEDULA
"""
from __future__ import annotations

import sys
import time
from decimal import Decimal
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from contaflow import asientos  # noqa: E402
from contaflow.clasificador import CUENTA_PUENTE, Clasificador  # noqa: E402
from contaflow.parser import leer_carpeta, leer_xml  # noqa: E402

TOL = Decimal("1.00")
CONTRA = {asientos.CAJA, asientos.CXC, asientos.CXP}


def _resumen(ruta: Path) -> dict[str, Decimal]:
    """Lee el ResumenFactura directo del XML, sin usar el parser de contaflow."""
    raiz = etree.parse(str(ruta)).getroot()
    out = {}
    for campo in ("TotalVentaNeta", "TotalImpuesto", "TotalComprobante",
                  "TotalOtrosCargos", "TotalIVADevuelto", "TotalDescuentos"):
        v = raiz.xpath(f"//*[local-name()='ResumenFactura']/*[local-name()='{campo}']/text()")
        out[campo] = Decimal(v[0].strip()) if v else Decimal("0")
    tc = raiz.xpath("//*[local-name()='TipoCambio']/text()")
    out["tc"] = Decimal(tc[0].strip()) if tc else Decimal("1")
    return out


def main(carpeta: Path, cedula: str) -> int:
    rutas = sorted(carpeta.rglob("*.xml"))
    contabilizables = [r for r in rutas if leer_xml(r) is not None]
    por_nombre = {r.name: r for r in rutas}
    t0 = time.perf_counter()
    comps, errores = leer_carpeta(carpeta, cedula)
    clas = Clasificador(RAIZ / "config" / "catalogo_cuentas.csv")
    filas, lineas_tot, lineas_auto = [], 0, 0
    for c in comps:
        movs = asientos.asientos_de(c, clas)
        gt = _resumen(por_nombre[c.archivo])
        tc = gt["tc"] if c.moneda != "CRC" else Decimal("1")
        base = sum((l.subtotal for l in c.lineas), Decimal("0"))
        iva = sum((l.monto_iva for l in c.lineas), Decimal("0"))
        contra = sum((m.haber if c.rol == "compra" else m.debe)
                     for m in movs if m.cuenta in CONTRA)
        cuadre = sum((m.debe - m.haber for m in movs), Decimal("0"))
        for m in movs:
            if m.cuenta not in CONTRA and not m.descripcion.startswith("IVA"):
                lineas_tot += 1
                lineas_auto += m.cuenta != CUENTA_PUENTE
        filas.append({
            "doc": c.emisor_nombre[:28], "tipo": c.tipo,
            "H2": abs(base - gt["TotalVentaNeta"]) <= TOL,
            "H3": abs(iva - gt["TotalImpuesto"]) <= TOL,
            "H4": abs(abs(contra) - gt["TotalComprobante"] * tc) <= TOL,
            "H5": cuadre == 0,
            "dif_total": abs(contra) - gt["TotalComprobante"] * tc,
            "otros_cargos": gt["TotalOtrosCargos"], "iva_devuelto": gt["TotalIVADevuelto"],
        })
    seg = time.perf_counter() - t0

    n = len(filas)
    leidos = n + sum(1 for _, m in errores if "coinciden" in m)
    print(f"Carpeta: {carpeta}   comprobantes contabilizables: {len(contabilizables)}")
    print(f"H1 lectura   : {leidos}/{len(contabilizables)} leidos sin error "
          f"({n} del cliente, {leidos - n} de otra cedula)")
    for h, nombre in (("H2", "base   "), ("H3", "IVA    "), ("H4", "total  "), ("H5", "cuadre ")):
        ok = sum(f[h] for f in filas)
        print(f"{h} {nombre}  : {ok}/{n}  {'ACEPTADA' if ok == n else 'RECHAZADA'}")
    print(f"H6 velocidad : {seg / max(n, 1):.3f} s por comprobante  "
          f"{'ACEPTADA' if seg / max(n, 1) < 1 else 'RECHAZADA'}")
    print(f"Cobertura del clasificador: {lineas_auto}/{lineas_tot} lineas "
          f"({100 * lineas_auto / max(lineas_tot, 1):.1f} %)")
    fallas = [f for f in filas if not (f["H2"] and f["H3"] and f["H4"] and f["H5"])]
    if fallas:
        print("\nComprobantes que no concilian:")
        for f in fallas:
            print(f"  {f['doc']:28} {f['tipo']}  dif. total {f['dif_total']:>12,.2f}  "
                  f"otros cargos {f['otros_cargos']:>10,.2f}  IVA devuelto {f['iva_devuelto']:>10,.2f}  "
                  + " ".join(h for h in ("H2", "H3", "H4", "H5") if not f[h]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]), sys.argv[2]))
