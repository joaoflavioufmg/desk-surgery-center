#!/usr/bin/env python3
import json
from datetime import date

# ====== Project constants (DESK) ======
TITLE = "DESK — Discrete Event Simulation Kit"
VERSION = "v1.1.4"
DOI = "10.5281/zenodo.18088013"
REPO = "https://github.com/joaoflavioufmg/desk"
README = "https://raw.githubusercontent.com/joaoflavioufmg/desk/main/README.md"
DOCS = "https://desk-sim.readthedocs.io"

AUTHOR = {
    "@type": "Person",
    "givenName": "João Flávio",
    "familyName": "de Freitas Almeida",
    "email": "joao.flavio@dep.ufmg.br",
    "affiliation": {
        "@type": "Organization",
        "name": "Universidade Federal de Minas Gerais (UFMG), PPGEP"
    }
}

DESCRIPTION = (
    "DESK (Discrete Event Simulation Kit) is an open-source Python framework for "
    "discrete-event simulation with support for replication analysis, factorial "
    "experiments, model validation, visualization, and statistical input "
    "distribution fitting."
)

KEYWORDS = [
    "discrete-event simulation",
    "simulation",
    "operations research",
    "experiment design",
    "replication analysis",
    "factorial experiments",
    "simpy",
    "open source"
]

# Use today's date for publication and modification (Zenodo will override anyway)
TODAY = date.today().isoformat()

# ====== Codemeta object ======
codemeta = {
    "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
    "@type": "SoftwareSourceCode",
    "name": TITLE,
    "version": VERSION,
    "identifier": DOI,
    "description": DESCRIPTION,
    "license": "GPL-3.0-only",
    "codeRepository": REPO,
    "readme": README,
    "issueTracker": f"{REPO}/issues",
    "relatedLink": [REPO, DOCS],
    "programmingLanguage": "Python",
    "runtimePlatform": "Python >=3.10",
    "author": [AUTHOR],
    "keywords": KEYWORDS,
    "datePublished": TODAY,
    "dateModified": TODAY
}

# ====== Write codemeta.json ======
with open("codemeta.json", "w", encoding="utf-8") as f:
    json.dump(codemeta, f, indent=2, ensure_ascii=False)

print("codemeta.json generated successfully.")
