"""Modelo de datos de un comprobante electronico de Hacienda (CR)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


# Tipos de comprobante segun el nodo raiz del XML de Hacienda.
TIPOS_COMPROBANTE = {
    "FacturaElectronica": "FE",
    "TiqueteElectronico": "TE",
    "NotaCreditoElectronica": "NC",
    "NotaDebitoElectronica": "ND",
    "FacturaElectronicaCompra": "FEC",
    "FacturaElectronicaExportacion": "FEE",
    "ReciboElectronicoPago": "REP",
}

# Los NC restan; el resto suma. Se aplica como signo a todos los montos.
SIGNO = {"NC": Decimal("-1")}


@dataclass
class Linea:
    numero: int
    cabys: str
    detalle: str
    cantidad: Decimal
    unidad: str
    subtotal: Decimal          # antes de IVA, ya con descuentos
    base_imponible: Decimal
    tarifa_iva: Decimal        # porcentaje, ej. Decimal("13")
    codigo_tarifa: str         # CodigoTarifaIVA de Hacienda, solo etiqueta
    monto_iva: Decimal
    total_linea: Decimal


@dataclass
class Comprobante:
    clave: str
    tipo: str                  # FE / TE / NC / ND / ...
    consecutivo: str
    fecha: date
    emisor_nombre: str
    emisor_cedula: str
    receptor_nombre: str
    receptor_cedula: str
    moneda: str
    tipo_cambio: Decimal
    condicion_venta: str
    subtotal: Decimal
    total_iva: Decimal
    total: Decimal
    lineas: list[Linea] = field(default_factory=list)
    archivo: str = ""

    # --- rol del comprobante respecto al cliente que estamos contabilizando ---
    rol: str = ""              # "venta" | "compra"

    @property
    def signo(self) -> Decimal:
        return SIGNO.get(self.tipo, Decimal("1"))

    def en_colones(self, monto: Decimal) -> Decimal:
        """Convierte a CRC. Hacienda ya exige el tipo de cambio en el XML."""
        if self.moneda == "CRC":
            return monto
        return monto * self.tipo_cambio

    @property
    def periodo(self) -> str:
        return self.fecha.strftime("%Y-%m")
