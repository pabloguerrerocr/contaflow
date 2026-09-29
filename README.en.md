# contaflow

*[Versión en español](README.md)*

Automated monthly bookkeeping close from the electronic invoices of Costa Rica's
Ministry of Finance (Hacienda). A folder of XML goes in; out come the Excel
workbook the client signs and the figure that goes on Form 150, the monthly VAT
return.

> **About this repository.** The complete accounting engine is published:
> parsing, rules, double-entry bookkeeping, VAT proration and reports. The
> learning layer —per-client classification memory and resolution of new items
> with a language model— is not part of this version.

## What it does

```
XML de Hacienda ──> parser ──> clasificador ──> asientos ──> reportes
   (4.3 / 4.4)                  (reglas)       (partida       (Excel + JSON)
                                                 doble)
```

1. **Parsing.** Reads `FacturaElectronica`, `TiqueteElectronico`, credit notes
   and debit notes. It ignores the XML namespace on purpose: Hacienda changes it
   with every resolution, and a parser tied to the namespace breaks with each
   version. It decides whether each document is a sale or a purchase by comparing
   the client's tax ID against issuer and receiver.
2. **Classification.** Rules by keyword in the line description and by CABYS
   prefix (Costa Rica's goods-and-services catalog). Text beats CABYS: the
   two-digit prefix is a broad section, while the description names the specific
   expense. Anything no rule recognizes falls into the **suspense account
   6-01-99** and is listed on the exceptions sheet, which is the correct
   behavior: the tool does not guess, it flags.
3. **Journal entries.** Double entry, with input VAT and output VAT kept
   separate. The journal is validated: `descuadre()` (the imbalance) must be
   `0.00` or the CLI warns.
4. **Reports.** Purchases ledger, sales ledger, journal, trial balance, income
   statement, Form 150 summary and —the one that builds trust— the **exceptions**
   sheet: what the machine could not classify on its own or classified with low
   confidence.

## Usage

```bash
pip install -r requirements.txt

# Demo data (synthetic, not from any real client)
python scripts/generar_demo.py data/entrada

# Monthly close
PYTHONPATH=src python -m contaflow --cedula 3101789456 --periodo 2026-03

```

Output on the demo set (88 documents, 149 lines):

```
Comprobantes procesados : 88  (149 lineas)
Conceptos sin regla     : 4 (van a la cuenta puente 6-01-99)
Automatizacion          : 94.0%  (9 a revision manual)
Descuadre del diario    : 0.00
  2026-03  IVA a pagar:   737,701.50   utilidad neta:  13,346,200.00
```

That is: 88 documents processed (149 lines), 4 items with no rule (sent to the
suspense account), 94.0% automation (9 to manual review), journal imbalance 0.00,
and for 2026-03 the VAT payable and net income in colones.

The **journal imbalance must be `0.00`**. It is the project's invariant: if a
change breaks it, the change is wrong.

## Per-client configuration

| File | What it is |
|---|---|
| `config/catalogo_cuentas.csv` | Chart of accounts. One copy per client if their chart differs. |
| `REGLAS_TEXTO` in `clasificador.py` | Keyword rules. Whatever repeats for a client moves up here and stops costing tokens. |

## Status and known limits

- **Without the learning layer, new items go to the suspense account.** In the
  demo set that is 4 of 149 lines; with rules calibrated for a specific client
  the number drops, but never to zero: a new supplier always shows up.
- **`REGLAS_CABYS` are approximations,** not the official CABYS catalog. Before
  using this with a real client, the prefixes have to be calibrated against
  Hacienda's catalog. That is why text takes priority over CABYS.
- **VAT credit proration is calculated, not applied automatically.** If there
  are exempt sales, `resumen_iva` flags `aplica_prorrata` and gives both figures.
  The decision belongs to the accountant (art. 27, Law 6826).
- **Ingestion is a local folder.** The obvious next step is reading the client's
  IMAP mailbox, which is how the XML files arrive in real life.
- **It does not issue invoices or file returns.** It prepares the figure; a
  person submits it to TRIBU-CR.

## Regulatory context

- Electronic invoice **version 4.4** mandatory since September 1, 2025.
- **TRIBU-CR** replaced ATV (Hacienda's filing platform) in October 2025.
- The monthly VAT return is no longer the D-104: it is **Form 150**, due within
  the first 15 business days of the following month.

Always check against the current resolution before closing a real month.
