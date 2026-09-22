"""Asigna una cuenta contable a cada linea de cada comprobante.

Orden de resolucion:
  1. Reglas: palabras clave del detalle y prefijo CABYS.
  2. Cuenta puente 6-01-99 para revision manual.

Nota sobre esta version
-----------------------
El motor completo resuelve en cuatro niveles, de barato a caro: memoria por
concepto, memoria por proveedor, reglas y, solo para lo que queda suelto, una
llamada en lote a un modelo de lenguaje cuyo resultado se guarda en la memoria
del cliente. Esa cascada es lo que hace que el costo por cierre tienda a cero
conforme se repite el cliente, y no forma parte de este repositorio.

Lo que si esta acá es el motor contable entero: parseo, reglas, partida doble,
prorrata y reportes. Con reglas solas, el set de demo clasifica la mayoria de
las lineas y el resto cae en la cuenta puente, que es exactamente el
comportamiento esperado de la herramienta cuando no reconoce un concepto.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .modelo import Comprobante, Linea

CUENTA_PUENTE = "6-01-99"

# CABYS: los 2 primeros digitos son la seccion del catalogo de bienes y servicios.
REGLAS_CABYS = {
    "23": "1-01-04",   # productos alimenticios -> inventario
    "32": "6-01-03",   # combustibles
    "65": "6-01-02",   # electricidad, agua, telecomunicaciones
    "68": "6-01-01",   # servicios inmobiliarios
    "69": "6-01-06",   # servicios juridicos y contables
    "87": "6-01-04",   # mantenimiento y reparacion
}

REGLAS_TEXTO = [
    (r"alquiler|arrendamiento|renta de local", "6-01-01"),
    (r"electric|energia|agua potable|acueducto|internet|telefon|cable|fibra", "6-01-02"),
    (r"diesel|gasolina|combustible|lubricante", "6-01-03"),
    (r"mantenimiento|reparacion|repuesto|servicio tecnico", "6-01-04"),
    (r"papel|resma|toner|tinta|lapicero|utiles de oficina", "6-01-05"),
    (r"honorarios|asesoria|consultoria|auditoria|servicios profesionales|legal", "6-01-06"),
    (r"publicidad|mercadeo|marketing|pauta|redes sociales|rotulo|volante", "6-01-07"),
    (r"poliza|seguro|prima ", "6-01-08"),
    (r"cuota obrero|patronal|ccss|planilla|aguinaldo|salario", "6-01-09"),
    (r"licencia de software|suscripcion|hosting|dominio|nube|saas|office", "6-01-10"),
    (r"flete|encomienda|transporte|mensajeria|courier", "6-01-11"),
    (r"almuerzo|cafe|alimentacion|catering|atencion a client", "6-01-12"),
    (r"comision bancaria|gastos bancarios|datafono|sinpe", "6-01-13"),
]


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes, sin numeros: para que 'Diesel 45 litros'
    y 'Diesel 30 litros' se traten como el mismo concepto."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\d+([.,]\d+)?", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Decision:
    cuenta: str
    fuente: str        # regla | puente
    confianza: float


class Clasificador:
    def __init__(self, catalogo: Path):
        self.cuentas = {
            f["codigo"]: f["nombre"]
            for f in csv.DictReader(catalogo.open(encoding="utf-8"))
        }
        self.sin_resolver: dict[str, dict] = {}

    def _por_reglas(self, linea: Linea) -> str | None:
        # El texto manda sobre el CABYS: el prefijo de 2 digitos es una seccion
        # ancha ("Prima poliza incendio" y "Servicio electrico" pueden caer en
        # la misma) mientras que el detalle nombra el gasto concreto.
        detalle = normalizar(linea.detalle)
        for patron, cuenta in REGLAS_TEXTO:
            if re.search(patron, detalle):
                return cuenta
        return REGLAS_CABYS.get(linea.cabys[:2])

    def clasificar(self, comp: Comprobante, linea: Linea) -> Decision:
        # Las ventas no necesitan mas que el CABYS: el catalogo de ingresos
        # es de dos cuentas.
        if comp.rol == "venta":
            es_servicio = linea.cabys.startswith(("5", "6", "7", "8", "9"))
            return Decision("4-01-01" if es_servicio else "4-01-02", "regla", 1.0)

        cuenta = self._por_reglas(linea)
        if cuenta:
            return Decision(cuenta, "regla", 0.8)

        llave = comp.emisor_cedula + "|" + normalizar(linea.detalle)
        self.sin_resolver.setdefault(llave, {
            "proveedor": comp.emisor_nombre,
            "detalle": linea.detalle,
            "cabys": linea.cabys,
        })
        return Decision(CUENTA_PUENTE, "puente", 0.0)
