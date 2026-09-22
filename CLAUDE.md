# contaflow

Motor de cierre contable mensual sobre comprobantes electrónicos de Hacienda
(Costa Rica). Entra carpeta de XML, sale el Excel del cierre y el número del
Formulario 150.

**Se le vende a contadores, no a PYMEs**, para no cargar con la
responsabilidad profesional del cierre: el contador firma, la herramienta le
quita las horas de digitación.

## Dónde está qué

| Ruta | Qué es |
|---|---|
| `src/contaflow/parser.py` | lee FacturaElectronica / TiqueteElectronico 4.3-4.4 |
| `src/contaflow/clasificador.py` | reglas por texto y por prefijo CABYS, y cuenta puente |
| `src/contaflow/asientos.py` | partida doble, IVA acreditable y por pagar separados |
| `src/contaflow/reportes.py` | libros, diario, balance, resultados, F-150 |
| `scripts/generar_demo.py` | comprobantes sintéticos para demo |

## Reglas al trabajar acá

- **El parser ignora el namespace a propósito.** Hacienda lo cambia en cada
  resolución. No lo "arregles" atándolo al namespace.
- `descuadre()` tiene que dar `0.00` antes de emitir cualquier reporte. Es el
  invariante del proyecto; si un cambio lo rompe, el cambio está mal.
- El texto tiene prioridad sobre el CABYS al clasificar: el prefijo de dos
  dígitos es una sección ancha y el detalle nombra el gasto concreto.
- Los datos de demo son **sintéticos** (`Panadería La Espiga del Sur S.A.`,
  cédula 3101789456). Nunca metás comprobantes de un cliente real al repo, ni
  siquiera para probar.

## Qué no está en este repositorio

La memoria de clasificaciones por cliente y la resolución de conceptos nuevos
con un modelo de lenguaje viven en la versión privada. Si trabajás sobre este
repo, el clasificador resuelve con reglas y manda a la cuenta puente lo que no
reconoce.
