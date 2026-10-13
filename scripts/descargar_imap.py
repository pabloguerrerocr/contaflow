"""Baja los XML de comprobantes electronicos de un buzon IMAP a una carpeta.

En la vida real los XML le llegan al contador por correo; esto reemplaza el
paso manual de descargarlos uno por uno. Solo libreria estandar.

Credenciales: un archivo de texto FUERA del repo con dos lineas, el correo y
una contrasena de aplicacion (no la contrasena normal de la cuenta):

    %USERPROFILE%\\.contaflow\\imap.txt

Uso:
  python scripts/descargar_imap.py DESTINO [--desde 2025-09-01] [--servidor imap.gmail.com]
"""
from __future__ import annotations

import argparse
import email
import imaplib
import re
import sys
from datetime import date
from email.header import decode_header, make_header
from pathlib import Path

CREDENCIALES = Path.home() / ".contaflow" / "imap.txt"


def _credenciales() -> tuple[str, str]:
    if not CREDENCIALES.exists():
        sys.exit(f"Falta {CREDENCIALES}: dos lineas, correo y contrasena de aplicacion.")
    lineas = [l.strip() for l in CREDENCIALES.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(lineas) < 2:
        sys.exit(f"{CREDENCIALES} debe tener dos lineas: correo y contrasena de aplicacion.")
    return lineas[0], lineas[1].replace(" ", "")


def _buzon_todo(m: imaplib.IMAP4_SSL) -> str:
    """El buzon con todos los correos. En Gmail el nombre cambia con el idioma
    ("[Gmail]/All Mail", "[Gmail]/Todos"), asi que se busca por la marca \\All."""
    _, lista = m.list()
    for fila in lista or []:
        texto = fila.decode(errors="replace")
        if "\\All" in texto:
            return texto.rsplit(' "/" ', 1)[-1].strip()
    return "INBOX"


def _nombre(parte) -> str:
    bruto = parte.get_filename() or ""
    return str(make_header(decode_header(bruto))) if bruto else ""


def descargar(destino: Path, desde: date | None, servidor: str) -> int:
    usuario, clave = _credenciales()
    destino.mkdir(parents=True, exist_ok=True)
    m = imaplib.IMAP4_SSL(servidor)
    m.login(usuario, clave)
    m.select(_buzon_todo(m), readonly=True)

    if "gmail" in servidor:
        consulta = "filename:xml" + (f" after:{desde:%Y/%m/%d}" if desde else "")
        _, datos = m.uid("SEARCH", "X-GM-RAW", f'"{consulta}"')
    else:
        criterio = f'SINCE {desde:%d-%b-%Y}' if desde else "ALL"
        _, datos = m.uid("SEARCH", None, criterio)
    uids = datos[0].split() if datos and datos[0] else []

    guardados = 0
    for uid in uids:
        _, msg = m.uid("FETCH", uid, "(RFC822)")
        if not msg or not isinstance(msg[0], tuple):
            continue
        correo = email.message_from_bytes(msg[0][1])
        for parte in correo.walk():
            nombre = _nombre(parte)
            if not nombre.lower().endswith(".xml"):
                continue
            contenido = parte.get_payload(decode=True)
            if not contenido:
                continue
            seguro = re.sub(r"[^\w.\-]", "_", nombre)
            (destino / f"{uid.decode()}_{seguro}").write_bytes(contenido)
            guardados += 1
    m.logout()
    print(f"Correos revisados: {len(uids)}  XML guardados: {guardados}  en {destino}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("destino", type=Path)
    p.add_argument("--desde", type=date.fromisoformat)
    p.add_argument("--servidor", default="imap.gmail.com")
    a = p.parse_args(argv)
    return descargar(a.destino, a.desde, a.servidor)


if __name__ == "__main__":
    raise SystemExit(main())
