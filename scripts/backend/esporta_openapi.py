#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scrive lo schema OpenAPI del server in docs/openapi.json (il contratto fra Backend e Frontend) e l'elenco degli
endpoint in docs/Endpoint.md, ricavato dallo stesso schema così non si disallinea.
Il Frontend può rigenerare i propri tipi anche a server spento:
    npm run tipi:file -- ../perfez-2526-Backend-Leopizzi/docs/openapi.json

Uso (dalla radice del repo):
    uv run scripts/backend/esporta_openapi.py [--out docs/openapi.json]

Non avvia il server e non legge nessun dato: importa l'applicazione FastAPI e ne chiede lo schema.
"""

import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))

from localhost.server.main import app  # noqa: E402


def _tabella_endpoint(schema):
    righe = ["# Endpoint", "",
             f"API locale di OneHealth, versione **{schema['info']['version']}**. File generato da `scripts/backend/esporta_openapi.py` "
             "dallo schema [`openapi.json`](openapi.json): non modificarlo a mano. Documentazione interattiva a server avviato su "
             "`http://127.0.0.1:8000/docs`.", "",
             "Dove un periodo non è coperto dai dati scaricati, gli endpoint rispondono `404` con il motivo (mai un `500`). "
             "La correlazione fra i domini è sempre esplorativa, non causale.", "",
             "| Metodo | Percorso | Cosa fa | Parametri |", "|---|---|---|---|"]
    for percorso, operazioni in schema["paths"].items():
        for metodo, op in operazioni.items():
            parametri = []
            for par in op.get("parameters", []):
                parametri.append(f"`{par['name']}`" + ("" if par.get("required") else "?"))
            if "requestBody" in op:
                parametri.append("corpo JSON")
            riassunto = (op.get("summary") or "").replace("|", "/")
            righe.append(f"| {metodo.upper()} | `{percorso}` | {riassunto} | {', '.join(parametri) or '—'} |")
    righe += ["", "`?` = parametro facoltativo.", ""]
    return "\n".join(righe)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(RADICE / "docs" / "openapi.json"), help="file di destinazione")
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.parent / "Endpoint.md").write_text(_tabella_endpoint(schema), encoding="utf-8")
    print(f"scritto {out} e Endpoint.md (API {schema['info']['version']}, {len(schema['paths'])} percorsi)")


if __name__ == "__main__":
    main()
