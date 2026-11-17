"""Storico verificabile: disponibilità, requisiti e metadati di download distinti.

Non scarica pacchetti di gioco. L'unico fetch implementato legge il catalogo
pubblico Microsoft; il catalogo può indicare massimi, non traffico effettivo.
"""

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request


XBOX_PRODUCT_ID = "9NL3WWNZLZZN"  # Componente gioco, non bundle Standard.
METRICS = {"availability", "storage_required", "download", "install", "patch_delta",
           "max_download", "max_install", "package"}
TIERS = {"primary", "firsthand", "secondary", "community"}
VERIFICATIONS = {"verified", "reported", "unknown"}
QUALIFIERS = {"exact", "maximum", "minimum", "up_to", "approximate", "not_applicable"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("observed_at richiede un timestamp UTC")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("observed_at richiede il fuso orario")
    return stamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _https(value):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source_url deve essere un URL HTTPS senza credenziali")
    return value


def normalize_record(original):
    record = dict(original)
    for field in ("game", "platform", "region", "event_type", "metric_kind", "source_url", "source_tier", "verification"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"Campo storico mancante: {field}")
    if record["metric_kind"] not in METRICS:
        raise ValueError("Tipo di misura storico non riconosciuto")
    if record["source_tier"] not in TIERS or record["verification"] not in VERIFICATIONS:
        raise ValueError("Provenienza o stato di verifica non riconosciuto")
    if record["verification"] == "verified" and record["source_tier"] not in {"primary", "firsthand"}:
        raise ValueError("Una fonte derivata non diventa una verifica primaria")
    _https(record["source_url"])
    record["observed_at"] = _utc(record.get("observed_at") or utc_now())
    record.setdefault("version", None)
    record.setdefault("sku", None)
    record.setdefault("package_id", None)
    record.setdefault("occurred_at", None)
    record.setdefault("date_precision", "unknown")
    record.setdefault("size_bytes", None)
    record.setdefault("value", None)
    record.setdefault("unit_original", None)
    record.setdefault("qualifier", "not_applicable" if record["metric_kind"] == "availability" else "exact")
    if record["qualifier"] not in QUALIFIERS:
        raise ValueError("Qualificatore della misura non riconosciuto")
    size = record["size_bytes"]
    if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
        raise ValueError("size_bytes richiede byte interi non negativi oppure null")
    if record["version"] is not None and (not isinstance(record["version"], str) or not record["version"].strip()):
        raise ValueError("version richiede una stringa non vuota oppure null")
    if record["occurred_at"]:
        if record["date_precision"] == "date":
            date.fromisoformat(record["occurred_at"])
        elif record["date_precision"] == "local_time":
            stamp = datetime.fromisoformat(record["occurred_at"])
            if stamp.tzinfo is not None:
                raise ValueError("local_time indica un orario locale senza conversione UTC")
        elif record["date_precision"] == "timestamp":
            _utc(record["occurred_at"])
        else:
            raise ValueError("Indicare la precisione di occurred_at")
    if record["metric_kind"] == "availability" and size is not None:
        raise ValueError("La disponibilità non è una dimensione download")
    identity = {field: record.get(field) for field in (
        "game", "platform", "region", "sku", "package_id", "version", "event_type",
        "occurred_at", "date_precision", "metric_kind", "value", "unit_original",
        "size_bytes", "qualifier", "source_url", "source_tier", "verification")}
    # La data di lettura non crea una nuova build ad ogni controllo.
    record["record_id"] = hashlib.sha256(_json(identity).encode()).hexdigest()
    return record


def init_history(db):
    db.execute("""CREATE TABLE IF NOT EXISTS download_history (
      record_id TEXT PRIMARY KEY, game TEXT NOT NULL, platform TEXT NOT NULL,
      region TEXT NOT NULL, version TEXT, occurred_at TEXT, metric_kind TEXT NOT NULL,
      size_bytes INTEGER, source_url TEXT NOT NULL, source_tier TEXT NOT NULL,
      verification TEXT NOT NULL, first_observed_at TEXT NOT NULL,
      last_observed_at TEXT NOT NULL, record_json TEXT NOT NULL
    )""")
    db.execute("CREATE TABLE IF NOT EXISTS history_metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
    db.execute("CREATE INDEX IF NOT EXISTS history_platform_date ON download_history(platform, occurred_at)")


def _merge_metadata(db, key, value):
    old = db.execute("SELECT value_json FROM history_metadata WHERE key=?", (key,)).fetchone()
    previous = json.loads(old[0]) if old else None
    if isinstance(previous, list) and isinstance(value, list):
        combined = {(item.get("id") or _json(item)): item for item in previous}
        combined.update({(item.get("id") or _json(item)): item for item in value})
        value = list(combined.values())
    elif isinstance(previous, dict) and isinstance(value, dict):
        value = {**previous, **value}
    db.execute("INSERT OR REPLACE INTO history_metadata VALUES (?,?)", (key, _json(value)))


def import_history(db, records):
    """Importa un array di record o un seed {records, gaps, coverage}; mai invia post.

    Ritorna solo il numero dei nuovi fatti, non delle osservazioni ripetute.
    Un lotto non valido non lascia record parzialmente importati.
    """
    init_history(db)
    payload = records if isinstance(records, dict) else {"records": records}
    normalized = [normalize_record(record) for record in payload.get("records", [])]
    inserted = 0
    with db:
        for record in normalized:
            observed = record["observed_at"]
            cursor = db.execute("""INSERT OR IGNORE INTO download_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                record["record_id"], record["game"], record["platform"], record["region"], record["version"],
                record["occurred_at"], record["metric_kind"], record["size_bytes"], record["source_url"],
                record["source_tier"], record["verification"], observed, observed, _json(record)))
            inserted += cursor.rowcount
            if not cursor.rowcount:
                db.execute("""UPDATE download_history SET
                    first_observed_at=min(first_observed_at,?),
                    record_json=CASE WHEN ?>=last_observed_at THEN ? ELSE record_json END,
                    last_observed_at=max(last_observed_at,?) WHERE record_id=?""",
                    (observed, observed, _json(record), observed, record["record_id"]))
        for key in ("gaps", "coverage", "research_candidates"):
            if key in payload:
                _merge_metadata(db, key, payload[key])
    return inserted


def export_history(db, path):
    init_history(db)
    records = []
    for row in db.execute("""SELECT record_json,first_observed_at,last_observed_at FROM download_history
                             ORDER BY coalesce(occurred_at,first_observed_at),platform,metric_kind,record_id"""):
        record = json.loads(row[0])
        record.update(first_observed_at=row[1], last_observed_at=row[2])
        records.append(record)
    exported = {"schema_version": 1, "generated_at": utc_now(), "records": records}
    exported.update({row[0]: json.loads(row[1]) for row in db.execute("SELECT key,value_json FROM history_metadata")})
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(json.dumps(exported, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(destination)
    return exported


def xbox_catalog_url(market="US", language="en-us"):
    if len(market) != 2 or not market.isalpha():
        raise ValueError("market richiede un codice paese di due lettere")
    query = urllib.parse.urlencode({"market": market.upper(), "languages": language, "fieldsTemplate": "details"})
    return f"https://displaycatalog.mp.microsoft.com/v7.0/products/{XBOX_PRODUCT_ID}?{query}"


def parse_xbox_catalog(data, *, source_url=None, observed_at=None, market="US"):
    """Estrae massimi dichiarati dal catalogo, non dimensioni effettive o patch delta.

    Version='0', versione vuota, dimensioni nulle/zero restano sconosciute.
    Un package ripetuto sotto più SKU non viene contato più volte.
    """
    source_url = source_url or xbox_catalog_url(market)
    observed_at = _utc(observed_at or utc_now())
    product = data.get("Product")
    if product is None:
        products = data.get("Products", [])
        product = next((item for item in products if item.get("ProductId") == XBOX_PRODUCT_ID), None)
    if not isinstance(product, dict) or product.get("ProductId") != XBOX_PRODUCT_ID:
        raise ValueError("Il catalogo non contiene il componente GTA VI richiesto")
    records = {}
    for entry in product.get("DisplaySkuAvailabilities", []):
        sku = entry.get("Sku", {})
        properties = sku.get("Properties", {})
        for package in properties.get("Packages", []) or []:
            raw_version = str(package.get("Version") or properties.get("VersionString") or "")
            version = raw_version if raw_version not in {"", "0", "0.0", "0.0.0.0"} else None
            package_id = package.get("PackageId") or package.get("ContentId")
            for key, metric, label in (
                ("MaxDownloadSizeInBytes", "max_download", "Limite dimensione download catalogo"),
                ("MaxInstallSizeInBytes", "max_install", "Limite dimensione installazione catalogo"),
            ):
                size = package.get(key)
                if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
                    continue
                identity = (package_id, metric, size, version)
                if identity in records:
                    ids = records[identity]["metadata"]["sku_ids"]
                    if sku.get("SkuId") not in ids:
                        ids.append(sku.get("SkuId"))
                    continue
                record = {"game": "GTA VI", "platform": "Xbox Series X|S", "region": market.upper(),
                          "sku": XBOX_PRODUCT_ID, "package_id": package_id, "version": version,
                          "event_type": "catalog_observation", "occurred_at": None, "date_precision": "unknown",
                          "observed_at": observed_at, "metric_kind": metric, "metric_label": label,
                          "size_bytes": size, "value": size, "unit_original": "bytes", "qualifier": "maximum",
                          "source_url": source_url, "source_tier": "primary", "verification": "verified",
                          "metadata": {"catalog_field": key, "sku_ids": [sku.get("SkuId")],
                                       "package_version_raw": package.get("Version"),
                                       "catalog_last_modified_at": product.get("LastModifiedDate")},
                          "notes": "Misura del catalogo Microsoft. Non prova download effettivo, patch delta o data di rilascio della build."}
                records[identity] = record
    result = []
    for record in records.values():
        record["metadata"]["sku_ids"] = sorted(value for value in record["metadata"]["sku_ids"] if value is not None)
        result.append(normalize_record(record))
    return result


def catalog_signal(record):
    """Dati per il renderer: l'etichetta conserva esplicitamente la semantica max."""
    if record["metric_kind"] not in {"max_download", "max_install"}:
        raise ValueError("Il segnale catalogo richiede una misura massima dichiarata")
    return {"id": record["record_id"], "topic": record["game"], "game": record["game"],
            "category": "TECNICA", "platforms": [record["platform"]], "region": record["region"],
            "version": record["version"], "metric_kind": record["metric_kind"],
            "metric_label": record["metric_label"], "value_bytes": record["size_bytes"],
            "source_url": record["source_url"], "source_name": "Catalogo Microsoft", "trust": "observation",
            "verification": "verified", "observed_at": record["observed_at"],
            "headline": record["metric_label"],
            "facts": [f"{record['size_bytes']} byte", "Numero build non pubblicato" if record["version"] is None else record["version"],
                      "Non equivale a download effettivo o dimensione patch"]}


def fetch_xbox_catalog(market="US", language="en-us", timeout=25):
    """GET pubblico senza chiavi/costi API; rispetta proxy e trust TLS di sistema.

    Ritorna records per il ledger, signals per i post ed evidence minima.
    Errori HTTP/rete restano errori e non producono un segnale di aggiornamento.
    """
    url = xbox_catalog_url(market, language)
    request = urllib.request.Request(url, headers={"User-Agent": "GTAFanMonitor/3.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Risposta catalogo oltre il limite di metadati")
    data = json.loads(raw)
    stamp = utc_now()
    records = parse_xbox_catalog(data, source_url=url, observed_at=stamp, market=market)
    evidence_hash = hashlib.sha256(raw).hexdigest()
    for record in records:
        record["evidence_sha256"] = evidence_hash
    evidence = {"source_url": url, "observed_at": stamp, "response_sha256": evidence_hash,
                "response_bytes": len(raw), "records": records}
    gaps = [{"id": "xbox-first-build", "platform": "Xbox Series X|S", "status": "incomplete",
             "missing": ["first_downloadable_build", "historical_versions", "effective_download_bytes", "patch_delta_bytes"],
             "source_url": url, "notes": "Il catalogo espone lo stato corrente; Version=0 non identifica una build utilizzabile come prima versione."}]
    return {"records": records, "signals": [catalog_signal(record) for record in records], "evidence": evidence, "gaps": gaps}
