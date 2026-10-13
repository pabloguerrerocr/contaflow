# contaflow

*[English version](README.en.md)*

Cierre contable mensual automatizado a partir de los comprobantes electrónicos
del Ministerio de Hacienda (Costa Rica). Entra una carpeta de XML, sale el
Excel que el cliente firma y el número que va en el Formulario 150.

> **Sobre este repositorio.** Está publicado el motor contable completo:
> parseo, reglas, partida doble, prorrata y reportes. La capa de aprendizaje
> —memoria de clasificaciones por cliente y resolución de conceptos nuevos con
> un modelo de lenguaje— no forma parte de esta versión.

## Validación con comprobantes reales

La demo sintética daba 94 % de automatización y cero errores. La primera prueba
con XML reales (5 emisores, versiones 4.3 y 4.4) encontró **tres errores que la
demo escondía**: un descuadre de ₡0,01 por redondeo, prefijos CABYS que mandaban
papel a combustibles y `OtrosCargos` (911, Cruz Roja) que se perdían.

Corregidos los tres, `scripts/experimento.py` prueba seis hipótesis contra el
`ResumenFactura` de cada XML —firmado por el emisor y aceptado por Hacienda—,
leído aparte, sin pasar por el parser:

| Hipótesis | Reales | Demo |
|---|---|---|
| Lee todo sin error | 11 / 11 | 88 / 88 |
| Base, IVA y total = resumen del XML | 9 / 9 | 88 / 88 |
| Cada asiento cuadra en 0,00 | 9 / 9 | 88 / 88 |
| Clasificado sin intervención | 25 % | 94 % |

Control negativo: al reinyectar el error de `OtrosCargos`, la conciliación marca
los 3 comprobantes afectados. Muestra real chica (9 comprobantes de compras
personales, que no se publican): sirve para encontrar errores, no para prometer
un porcentaje.

## Qué hace

```
XML de Hacienda ──> parser ──> clasificador ──> asientos ──> reportes
   (4.3 / 4.4)                  (reglas)       (partida       (Excel + JSON)
                                                 doble)
```

1. **Parseo.** Lee `FacturaElectronica`, `TiqueteElectronico`, notas de crédito
   y débito. Ignora el namespace a propósito: Hacienda lo cambia en cada
   resolución y un parser atado al namespace se rompe con cada versión.
   Decide si cada comprobante es venta o compra comparando la cédula del
   cliente contra emisor y receptor.
2. **Clasificación.** Reglas por palabra clave del detalle y por prefijo CABYS.
   El texto manda sobre el CABYS: el prefijo de dos dígitos es una sección
   ancha, mientras que el detalle nombra el gasto concreto. Lo que ninguna
   regla reconoce cae en la **cuenta puente 6-01-99** y sale listado en la hoja
   de excepciones, que es el comportamiento correcto: la herramienta no
   adivina, avisa.
3. **Asientos.** Partida doble, con IVA acreditable y por pagar separados.
   El diario se valida: `descuadre()` tiene que dar `0.00` o el CLI avisa.
4. **Reportes.** Libro de compras, libro de ventas, diario, balance de
   comprobación, estado de resultados, resumen del Formulario 150, la hoja de
   **excepciones** (lo que la máquina no pudo clasificar sola) y la de
   **conciliación XML**: cada comprobante contra el total firmado en su XML.

## Uso

```bash
pip install -r requirements.txt

# Datos de demo (sintéticos, no son de ningún cliente real)
python scripts/generar_demo.py data/entrada

# Cierre del mes
PYTHONPATH=src python -m contaflow --cedula 3101789456 --periodo 2026-03

```

Salida sobre el set de demo (88 comprobantes, 149 líneas):

```
Comprobantes procesados : 88  (149 lineas)
Conceptos sin regla     : 4 (van a la cuenta puente 6-01-99)
Automatizacion          : 94.0%  (9 a revision manual)
Descuadre del diario    : 0.00
  2026-03  IVA a pagar:   737,701.50   utilidad neta:  13,346,200.00
```

El **descuadre del diario tiene que dar `0.00`**. Es el invariante del
proyecto: si un cambio lo rompe, el cambio está mal.

## Configuración por cliente

| Archivo | Qué es |
|---|---|
| `config/catalogo_cuentas.csv` | Plan de cuentas. Una copia por cliente si su catálogo difiere. |
| `REGLAS_TEXTO` en `clasificador.py` | Reglas por palabra clave. Lo que se repite en un cliente se sube acá y deja de costar tokens. |

## Estado y límites conocidos

- **Sin la capa de aprendizaje, los conceptos nuevos van a la cuenta puente.**
  En el set de demo son 4 de 149 líneas; con reglas calibradas para un cliente
  concreto bajan, pero nunca a cero: siempre aparece un proveedor nuevo.
- **`REGLAS_CABYS` mapean divisiones CPC 2.1 (2 dígitos),** no el catálogo
  completo: solo las que no dependen del giro del cliente. El texto tiene
  prioridad sobre el CABYS.
- **La prorrata de crédito fiscal se calcula, no se aplica sola.** Si hay ventas
  exentas, `resumen_iva` marca `aplica_prorrata` y da ambas cifras. La decisión
  es del contador (art. 27, Ley 6826).
- **La ingesta es una carpeta local.** `scripts/descargar_imap.py` baja los XML
  de un buzón IMAP a esa carpeta; todavía no está integrado al CLI.
- **No emite comprobantes ni presenta declaraciones.** Prepara el número; el
  envío a TRIBU-CR lo hace una persona.

## Contexto normativo

- Factura electrónica **versión 4.4** obligatoria desde el 1 de setiembre de 2025.
- **TRIBU-CR** sustituyó a ATV en octubre de 2025.
- La declaración mensual de IVA ya no es el D-104: es el **Formulario 150**,
  dentro de los primeros 15 días hábiles del mes siguiente.

Verificar siempre contra la resolución vigente antes de cerrar un mes real.
