"""Genera asientos de diario en partida doble a partir de los comprobantes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .clasificador import Clasificador
from .modelo import Comprobante

CENTIMO = Decimal("0.01")

IVA_ACREDITABLE = "1-01-03"      # credito fiscal (compras)
IVA_POR_PAGAR = "2-01-02"        # debito fiscal (ventas)
CAJA = "1-01-01"
CXC = "1-01-02"
CXP = "2-01-01"

CONTADO = {"01"}                 # CondicionVenta 01 = contado


def r(monto: Decimal) -> Decimal:
    return monto.quantize(CENTIMO, rounding=ROUND_HALF_UP)


@dataclass
class Movimiento:
    fecha: date
    periodo: str
    comprobante: str          # consecutivo
    clave: str
    tipo: str
    rol: str
    contraparte: str
    cuenta: str
    descripcion: str
    debe: Decimal
    haber: Decimal
    fuente: str               # de donde salio la clasificacion
    confianza: float


def _mov(comp: Comprobante, cuenta: str, desc: str, debe=Decimal("0"),
         haber=Decimal("0"), fuente="", confianza=1.0) -> Movimiento:
    contraparte = comp.receptor_nombre if comp.rol == "venta" else comp.emisor_nombre
    return Movimiento(
        fecha=comp.fecha, periodo=comp.periodo, comprobante=comp.consecutivo,
        clave=comp.clave, tipo=comp.tipo, rol=comp.rol, contraparte=contraparte,
        cuenta=cuenta, descripcion=desc, debe=r(debe), haber=r(haber),
        fuente=fuente, confianza=confianza,
    )


def asientos_de(comp: Comprobante, clas: Clasificador) -> list[Movimiento]:
    """Un comprobante -> N movimientos que cuadran entre si.

    Compra:  gasto/inventario + IVA acreditable   contra  caja o CxP
    Venta:   caja o CxC                           contra  ingreso + IVA por pagar
    Una nota de credito invierte todos los signos (comp.signo == -1).
    """
    s = comp.signo
    movs: list[Movimiento] = []
    base_total = Decimal("0")
    iva_total = Decimal("0")

    for linea in comp.lineas:
        d = clas.clasificar(comp, linea)
        base = comp.en_colones(linea.subtotal) * s
        iva = comp.en_colones(linea.monto_iva) * s
        base_total += base
        iva_total += iva
        if comp.rol == "compra":
            movs.append(_mov(comp, d.cuenta, linea.detalle, debe=base,
                             fuente=d.fuente, confianza=d.confianza))
        else:
            movs.append(_mov(comp, d.cuenta, linea.detalle, haber=base,
                             fuente=d.fuente, confianza=d.confianza))

    if comp.rol == "compra":
        if iva_total:
            movs.append(_mov(comp, IVA_ACREDITABLE, "IVA soportado", debe=iva_total))
        contra = CAJA if comp.condicion_venta in CONTADO else CXP
        movs.append(_mov(comp, contra, "Pago a " + comp.emisor_nombre,
                         haber=base_total + iva_total))
    else:
        if iva_total:
            movs.append(_mov(comp, IVA_POR_PAGAR, "IVA repercutido", haber=iva_total))
        contra = CAJA if comp.condicion_venta in CONTADO else CXC
        movs.append(_mov(comp, contra, "Cobro a " + comp.receptor_nombre,
                         debe=base_total + iva_total))

    return movs


def generar(comprobantes: list[Comprobante], clas: Clasificador) -> list[Movimiento]:
    movs: list[Movimiento] = []
    for comp in comprobantes:
        movs.extend(asientos_de(comp, clas))
    return movs


def descuadre(movs: list[Movimiento]) -> Decimal:
    """Debe - Haber sobre todo el libro. Debe dar 0.00."""
    return r(sum((m.debe for m in movs), Decimal("0"))
             - sum((m.haber for m in movs), Decimal("0")))
