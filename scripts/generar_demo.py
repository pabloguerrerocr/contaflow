"""Genera un set de comprobantes electronicos 4.4 sinteticos para demo.

Datos 100% inventados. Sirve para enseñar el producto sin tocar informacion
real de ningun cliente.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

NS = "https://cdn.comprobanteselectronicos.go.cr/xml-schemas/v4.4/{doc}"
CR = timezone(timedelta(hours=-6))

CEDULA_CLIENTE = "3101789456"
NOMBRE_CLIENTE = "Panaderia La Espiga del Sur S.A."

PROVEEDORES = [
    ("3101112233", "Distribuidora Harinas del Valle S.A.", "2311100000000", "Harina de trigo fortificada 50kg", "13", "1-01-04"),
    ("3101445566", "Compania Nacional de Fuerza y Luz", "6531100000100", "Servicio electrico comercial marzo", "13", "6-01-02"),
    ("3101778899", "Servicentro El Roble S.A.", "3221100000000", "Diesel 45 litros", "13", "6-01-03"),
    ("112340567", "Ana Rojas Vargas", "6912100010100", "Honorarios contables mensuales", "13", "6-01-06"),
    ("3101990011", "Inmobiliaria Perez Zeledon S.A.", "6811100000000", "Alquiler de local comercial", "13", "6-01-01"),
    ("3102334455", "Seguros del Istmo Ltda.", "6512100000000", "Prima poliza incendio", "2", "6-01-08"),
    ("3101667788", "Suministros de Oficina CR S.A.", "1709100000000", "Resma papel bond carta x10", "13", "6-01-05"),
    ("3101223344", "Refrigeracion Tecnica del Sur S.A.", "8712100000000", "Mantenimiento camara de frio", "13", "6-01-04"),
    ("3101556677", "Transportes Rapidos Zeledon S.A.", "6491100000000", "Flete de mercaderia San Jose", "13", "6-01-11"),
    ("3012456789", "Caja Costarricense de Seguro Social", "0000000000000", "Cuotas obrero patronales", "0", "6-01-09"),
    # --- Los ambiguos: ninguna regla los resuelve. Aca entra el modelo. ---
    ("3101010203", "Comercial Zeta del Sur S.A.", "4759100000000", "Articulos varios segun detalle adjunto", "13", None),
    ("3101040506", "Servicios Integrales GYS S.A.", "8299100000000", "Servicio mensual segun contrato 2026", "13", None),
    ("110220330", "Marvin Solis Mora", "4330100000000", "Trabajo realizado en local comercial", "13", None),
    ("3101070809", "Almacen El Progreso Ltda.", "2599100000000", "Bandejas metalicas industriales x24", "13", None),
]

CLIENTES = [
    ("3101334499", "Supermercado Central del Sur S.A."),
    ("110450678", "Consumidor final"),
    ("3101887766", "Hotel Montaña Verde S.A."),
    ("3101445599", "Soda El Buen Sabor S.R.L."),
]

VENTAS = [
    ("2312100000000", "Pan cuadrado blanco 680g", "1"),
    ("2312100000100", "Pan dulce surtido docena", "1"),
    ("2313100000000", "Queque seco de naranja", "13"),
    ("5610100000000", "Servicio de cafeteria en local", "13"),
]


def _clave(consecutivo: str, cedula: str, fecha: datetime, seq: int) -> str:
    """Estructura de 50 digitos: pais(3) dia(2) mes(2) anio(2) cedula(12)
    consecutivo(20) situacion(1) codigo seguridad(8)."""
    return (
        "506"
        + fecha.strftime("%d%m%y")
        + cedula.rjust(12, "0")
        + consecutivo
        + "1"
        + f"{seq:08d}"
    )


def _consecutivo(tipo: str, seq: int) -> str:
    # casa(3) terminal(5) tipo(2) numero(10)
    return "001" + "00001" + tipo + f"{seq:010d}"


def _linea(i, cabys, detalle, cantidad, precio, tarifa):
    sub = (precio * cantidad).quantize(Decimal("0.01"))
    iva = (sub * tarifa / 100).quantize(Decimal("0.01"))
    codigos = {"13": "08", "4": "04", "2": "03", "1": "02", "0": "01"}
    return f"""    <LineaDetalle>
      <NumeroLinea>{i}</NumeroLinea>
      <CodigoCABYS>{cabys}</CodigoCABYS>
      <Cantidad>{cantidad}</Cantidad>
      <UnidadMedida>Unid</UnidadMedida>
      <Detalle>{detalle}</Detalle>
      <PrecioUnitario>{precio}</PrecioUnitario>
      <MontoTotal>{sub}</MontoTotal>
      <SubTotal>{sub}</SubTotal>
      <BaseImponible>{sub}</BaseImponible>
      <Impuesto>
        <Codigo>01</Codigo>
        <CodigoTarifaIVA>{codigos.get(str(tarifa), "08")}</CodigoTarifaIVA>
        <Tarifa>{tarifa}</Tarifa>
        <Monto>{iva}</Monto>
      </Impuesto>
      <ImpuestoNeto>{iva}</ImpuestoNeto>
      <MontoTotalLinea>{sub + iva}</MontoTotalLinea>
    </LineaDetalle>""", sub, iva


def comprobante(doc, tipo_cod, seq, fecha, emisor, receptor, lineas_spec):
    ns = NS.format(doc=doc)
    cons = _consecutivo(tipo_cod, seq)
    clave = _clave(cons, emisor[0], fecha, seq)
    bloques, subtotal, iva_total = [], Decimal("0"), Decimal("0")
    for i, (cabys, detalle, cantidad, precio, tarifa) in enumerate(lineas_spec, 1):
        b, s, v = _linea(i, cabys, detalle, cantidad, precio, tarifa)
        bloques.append(b)
        subtotal += s
        iva_total += v
    raiz = {"FE": "FacturaElectronica", "TE": "TiqueteElectronico",
            "NC": "NotaCreditoElectronica"}[doc]
    return f"""<?xml version="1.0" encoding="utf-8"?>
<{raiz} xmlns="{ns}">
  <Clave>{clave}</Clave>
  <ProveedorSistemas>3101789456</ProveedorSistemas>
  <CodigoActividadEmisor>107101</CodigoActividadEmisor>
  <CodigoActividadReceptor>471101</CodigoActividadReceptor>
  <NumeroConsecutivo>{cons}</NumeroConsecutivo>
  <FechaEmision>{fecha.isoformat()}</FechaEmision>
  <Emisor>
    <Nombre>{emisor[1]}</Nombre>
    <Identificacion><Tipo>02</Tipo><Numero>{emisor[0]}</Numero></Identificacion>
  </Emisor>
  <Receptor>
    <Nombre>{receptor[1]}</Nombre>
    <Identificacion><Tipo>02</Tipo><Numero>{receptor[0]}</Numero></Identificacion>
  </Receptor>
  <CondicionVenta>0{random.choice([1, 2])}</CondicionVenta>
  <DetalleServicio>
{chr(10).join(bloques)}
  </DetalleServicio>
  <ResumenFactura>
    <CodigoTipoMoneda><CodigoMoneda>CRC</CodigoMoneda><TipoCambio>1.00000</TipoCambio></CodigoTipoMoneda>
    <TotalVenta>{subtotal}</TotalVenta>
    <TotalDescuentos>0.00</TotalDescuentos>
    <TotalVentaNeta>{subtotal}</TotalVentaNeta>
    <TotalImpuesto>{iva_total}</TotalImpuesto>
    <TotalComprobante>{subtotal + iva_total}</TotalComprobante>
  </ResumenFactura>
</{raiz}>
"""


def main(destino: Path, semilla: int = 7):
    random.seed(semilla)
    destino.mkdir(parents=True, exist_ok=True)
    cliente = (CEDULA_CLIENTE, NOMBRE_CLIENTE)
    seq = 0
    base = datetime(2026, 3, 2, 8, 30, tzinfo=CR)

    # --- COMPRAS: el cliente es el receptor ---
    for prov in PROVEEDORES:
        for _ in range(random.randint(1, 3)):
            seq += 1
            fecha = base + timedelta(days=random.randint(0, 28), hours=random.randint(0, 9))
            precio = Decimal(random.choice([12500, 34800, 7650, 91200, 250000, 18400, 5600]))
            lineas = [(prov[2], prov[3], Decimal(random.randint(1, 4)), precio, Decimal(prov[4]))]
            xml = comprobante("FE", "01", seq, fecha, (prov[0], prov[1]), cliente, lineas)
            (destino / f"compra_{seq:03d}.xml").write_text(xml, encoding="utf-8")

    # --- VENTAS: el cliente es el emisor ---
    for _ in range(60):
        seq += 1
        fecha = base + timedelta(days=random.randint(0, 28), hours=random.randint(0, 11))
        receptor = random.choice(CLIENTES)
        lineas = []
        for cabys, detalle, tarifa in random.sample(VENTAS, random.randint(1, 3)):
            lineas.append((cabys, detalle, Decimal(random.randint(8, 60)),
                           Decimal(random.choice([1800, 2500, 4200, 9500])), Decimal(tarifa)))
        doc = "TE" if receptor[0] == "110450678" else "FE"
        xml = comprobante(doc, "01" if doc == "FE" else "04", seq, fecha, cliente, receptor, lineas)
        (destino / f"venta_{seq:03d}.xml").write_text(xml, encoding="utf-8")

    # --- Una nota de credito de venta (devolucion) ---
    seq += 1
    fecha = base + timedelta(days=25)
    xml = comprobante("NC", "03", seq, fecha, cliente, CLIENTES[0],
                      [(VENTAS[0][0], "Devolucion pan cuadrado por vencimiento",
                        Decimal("15"), Decimal("900"), Decimal("1"))])
    (destino / f"nc_{seq:03d}.xml").write_text(xml, encoding="utf-8")

    print(f"Generados {seq} comprobantes en {destino}")


if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/entrada")
    main(salida)
