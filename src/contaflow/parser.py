"""Lector de XML de comprobantes electronicos del Ministerio de Hacienda (CR).

Deliberadamente ignora el namespace: Hacienda lo cambia en cada version
(v4.3, v4.4, ...) y un parser atado al namespace se rompe en cada resolucion.
Aqui se trabaja sobre el nombre local de la etiqueta.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from lxml import etree

from .modelo import TIPOS_COMPROBANTE, Comprobante, Linea


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _hijo(nodo, *nombres):
    """Primer descendiente cuyo nombre local coincida, siguiendo la ruta dada."""
    actual = nodo
    for nombre in nombres:
        encontrado = None
        for h in actual:
            if _local(h.tag) == nombre:
                encontrado = h
                break
        if encontrado is None:
            return None
        actual = encontrado
    return actual


def _hijos(nodo, nombre):
    return [h for h in nodo if _local(h.tag) == nombre]


def _txt(nodo, *nombres, default=""):
    n = _hijo(nodo, *nombres) if nombres else nodo
    if n is None or n.text is None:
        return default
    return n.text.strip()


def _dec(nodo, *nombres, default="0"):
    bruto = _txt(nodo, *nombres, default=default)
    if not bruto:
        return Decimal(default)
    try:
        return Decimal(bruto)
    except InvalidOperation:
        return Decimal(default)


def _fecha(bruto: str) -> date:
    """FechaEmision viene en ISO-8601 con offset, ej. 2026-03-14T10:22:31-06:00."""
    if not bruto:
        return date.today()
    try:
        return datetime.fromisoformat(bruto).date()
    except ValueError:
        return datetime.strptime(bruto[:10], "%Y-%m-%d").date()


def _linea(nodo, indice: int) -> Linea:
    impuesto = _hijo(nodo, "Impuesto")
    tarifa = Decimal("0")
    codigo_tarifa = ""
    monto_iva = Decimal("0")
    if impuesto is not None:
        # La tarifa real se toma del elemento Tarifa, no del codigo: el catalogo
        # de CodigoTarifaIVA cambia entre versiones y no queremos depender de el.
        tarifa = _dec(impuesto, "Tarifa")
        codigo_tarifa = _txt(impuesto, "CodigoTarifaIVA") or _txt(impuesto, "CodigoTarifa")
        monto_iva = _dec(impuesto, "Monto")

    subtotal = _dec(nodo, "SubTotal")
    base = _dec(nodo, "BaseImponible")
    return Linea(
        numero=int(_txt(nodo, "NumeroLinea", default=str(indice)) or indice),
        cabys=_txt(nodo, "CodigoCABYS") or _txt(nodo, "Codigo"),
        detalle=_txt(nodo, "Detalle"),
        cantidad=_dec(nodo, "Cantidad", default="1"),
        unidad=_txt(nodo, "UnidadMedida"),
        subtotal=subtotal,
        base_imponible=base or subtotal,
        tarifa_iva=tarifa,
        codigo_tarifa=codigo_tarifa,
        monto_iva=monto_iva,
        total_linea=_dec(nodo, "MontoTotalLinea"),
    )


def leer_xml(ruta: Path) -> Comprobante | None:
    """Devuelve el Comprobante, o None si el XML no es un comprobante conocido
    (por ejemplo un MensajeReceptor, que no lleva detalle de lineas)."""
    arbol = etree.parse(str(ruta))
    raiz = arbol.getroot()
    nombre_raiz = _local(raiz.tag)
    tipo = TIPOS_COMPROBANTE.get(nombre_raiz)
    if tipo is None:
        return None

    emisor = _hijo(raiz, "Emisor")
    receptor = _hijo(raiz, "Receptor")
    resumen = _hijo(raiz, "ResumenFactura")
    detalle = _hijo(raiz, "DetalleServicio")

    moneda, tipo_cambio = "CRC", Decimal("1")
    if resumen is not None:
        cod_moneda = _hijo(resumen, "CodigoTipoMoneda")
        if cod_moneda is not None:
            moneda = _txt(cod_moneda, "CodigoMoneda", default="CRC")
            tipo_cambio = _dec(cod_moneda, "TipoCambio", default="1")

    lineas = []
    if detalle is not None:
        for i, nodo in enumerate(_hijos(detalle, "LineaDetalle"), start=1):
            lineas.append(_linea(nodo, i))

    return Comprobante(
        clave=_txt(raiz, "Clave"),
        tipo=tipo,
        consecutivo=_txt(raiz, "NumeroConsecutivo"),
        fecha=_fecha(_txt(raiz, "FechaEmision")),
        emisor_nombre=_txt(emisor, "Nombre") if emisor is not None else "",
        emisor_cedula=_txt(emisor, "Identificacion", "Numero") if emisor is not None else "",
        receptor_nombre=_txt(receptor, "Nombre") if receptor is not None else "",
        receptor_cedula=_txt(receptor, "Identificacion", "Numero") if receptor is not None else "",
        moneda=moneda,
        tipo_cambio=tipo_cambio or Decimal("1"),
        condicion_venta=_txt(raiz, "CondicionVenta"),
        subtotal=_dec(resumen, "TotalVentaNeta") if resumen is not None else Decimal("0"),
        total_iva=_dec(resumen, "TotalImpuesto") if resumen is not None else Decimal("0"),
        total=_dec(resumen, "TotalComprobante") if resumen is not None else Decimal("0"),
        lineas=lineas,
        archivo=ruta.name,
    )


def leer_carpeta(carpeta: Path, cedula_cliente: str) -> tuple[list[Comprobante], list[tuple[str, str]]]:
    """Lee todos los XML de la carpeta y marca cada uno como venta o compra
    segun si la cedula del cliente aparece como emisor o como receptor.

    Devuelve (comprobantes, errores) donde errores es [(archivo, motivo)].
    """
    comprobantes: list[Comprobante] = []
    errores: list[tuple[str, str]] = []
    cedula_cliente = cedula_cliente.strip()

    for ruta in sorted(carpeta.rglob("*.xml")):
        try:
            c = leer_xml(ruta)
        except etree.XMLSyntaxError as exc:
            errores.append((ruta.name, f"XML invalido: {exc}"))
            continue
        if c is None:
            errores.append((ruta.name, "No es un comprobante contabilizable (posible MensajeReceptor)"))
            continue
        if c.emisor_cedula == cedula_cliente:
            c.rol = "venta"
        elif c.receptor_cedula == cedula_cliente:
            c.rol = "compra"
        else:
            errores.append((ruta.name, f"Ni emisor ni receptor coinciden con la cedula {cedula_cliente}"))
            continue
        comprobantes.append(c)

    return comprobantes, errores
