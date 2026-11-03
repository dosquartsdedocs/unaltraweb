"""Snapshot adapters to the factory's native visual freshness/resolution code."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re

from .editorial_sources import digest, strict_json, yaml_mapping
from .runtime_lifecycle import inspect_image
from . import site_tools


def module(factory, path):
    spec = importlib.util.spec_from_file_location("unaltraweb_context_" + path.replace("/", "_"), factory / path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    # Status needs only local image observation. Use the bounded lifecycle
    # adapter (no pull/prepare) instead of the standalone scripts' unbounded CLI.
    images = {}
    def image(reference):
        if reference not in images:
            observed = inspect_image(reference)
            images[reference] = {"available": "true" if observed["state"] == "matched" else "false",
                                 "id": observed.get("observed_image_id") or "",
                                 "digest": ",".join(observed.get("registry_digests", []))}
        return images[reference]
    loaded.inspect_image = image
    return loaded


class Sources:
    def __init__(self, snapshot, factory, manual):
        self.snapshot, self.factory, self.manual = snapshot, factory, manual
        self.root = snapshot.root
        self.records, self.outputs, self.evidence = {}, {}, {}
        self._computations()
        self._companions()
        self._captures()

    def dependency(self, name):
        if name not in {"_config.yml", "Gemfile", "Gemfile.lock", "Dockerfile", "requirements.txt", "renv.lock"}:
            self.snapshot.public(name)
        names = self.snapshot.reader.walk(name)
        if not names:
            raise ValueError(f"Missing declared public dependency: {name}")
        for path in names:
            self.snapshot.copy(path)

    def record(self, source, outputs, kind, status, receipt):
        if source in self.records:
            raise ValueError(f"Ambiguous generated source ownership: {source}")
        self.records[source] = {"kind": kind, "status": status, "receipt": receipt, "outputs": outputs}
        for output in outputs:
            if output in self.outputs and self.outputs[output] != source:
                raise ValueError(f"Ambiguous generated output ownership: {output}")
            self.outputs[output] = source

    def _computations(self):
        native = module(self.factory, "scripts/computations/render.py")
        self.snapshot.copy(str(native.CONFIG_PATH), optional=True)
        config, config_path = native.load_config(self.root)
        config["project_name"] = self.snapshot.reader.root.name
        for root in config["source_roots"]:
            self.snapshot.public(root)
            self.snapshot.tree(root, native.SUPPORTED_SUFFIXES)
        # Populate declared dependencies before native discover's existence checks.
        for root in config["source_roots"]:
            for path in self.snapshot.reader.walk(root):
                if Path(path).suffix.lower() not in native.SUPPORTED_SUFFIXES:
                    continue
                front = native.read_front_matter(self.root / path)
                meta = front.get("unaltraweb_compute") or {}
                if not isinstance(meta, dict):
                    raise ValueError(f"Invalid computation metadata: {path}")
                for name in meta.get("inputs", []):
                    self.dependency(name)
        for settings in config["engines"].values():
            for name in ([settings["dockerfile"]] if settings.get("dockerfile") else []) + settings.get("lockfiles", []) + settings.get("fingerprint_paths", []):
                self.dependency(name)
        records = native.discover_sources(self.root, config)
        raw_lock = self.snapshot.copy(str(native.LOCK_PATH), optional=True)
        lock = strict_json(raw_lock.decode()) if raw_lock else {"version": 1, "records": {}}
        if lock.get("version") != 1 or not isinstance(lock.get("records"), dict):
            raise ValueError("Invalid computations lock; run manual_computation_check")
        if set(lock["records"]) - {record["source_path"] for record in records}:
            raise ValueError("Orphaned computation receipts; resolve manual_computation_check before export")
        for record in records:
            source = record["source_path"]
            if record["mode"] == "figure":
                outputs = record["output_paths"]
            else:
                outputs = [record["output_path"], *self.snapshot.reader.walk(record["figures_path"]) ]
            for path in outputs:
                self.snapshot.public(path)
                self.snapshot.copy(path, optional=True)
                if Path(path).suffix.lower() in native.GENERATED_MEDIA_SUFFIXES:
                    self.snapshot.copy(Path(path).with_suffix(".edited.svg").as_posix(), optional=True)
            saved = lock["records"].get(source, {})
            status = native.status_item(self.root, config, config_path, record, saved)
            if not saved or not status["current"] or status["reason"] != "current":
                raise ValueError(f"{source}: computation {status['reason']}; run manual_computation_check and explicitly render/adopt through the producer")
            if record["mode"] == "figure" and {entry.get("path") for entry in saved.get("outputs", [])} != set(outputs):
                raise ValueError(f"{source}: computation output receipt is incomplete")
            self.record(source, outputs, "computation", status, digest(raw_lock))
            self.records[source]["language"] = record["front"]["lang"]
            for path in outputs:
                edited = Path(path).with_suffix(".edited.svg").as_posix()
                if (self.root / edited).is_file():
                    self.outputs[edited] = source

    def _companions(self):
        paths = set()
        for root in {"assets", "_chapters", "_documentation", *[r for r in self.snapshot.public_roots if r.startswith("_") and r not in {"_data", "_includes", "_bibliography", "_layouts", "_plugins", "_sass", "_pages"}]}:
            paths.update(self.snapshot.reader.walk(root))
        diagrams = [path for path in sorted(paths) if Path(path).suffix.lower() in site_tools.DIAGRAM_SOURCE_SUFFIXES]
        vega = [path for path in sorted(paths) if path.lower().endswith(site_tools.VEGA_SOURCE_SUFFIXES)]
        for path in [*diagrams, *vega]:
            self.snapshot.copy(path)
        for path in diagrams:
            self.snapshot.copy(path + ".svg", optional=True)
            self.snapshot.copy(path + ".edited.svg", optional=True)
        manifest = self.snapshot.copy(".vegavisuals.yml", optional=True)
        if vega and not manifest:
            raise ValueError("Vega sources require .vegavisuals.yml and a current visualization_check receipt")
        if manifest:
            data = yaml_mapping(manifest.decode())
            for item in data.get("visualizations", []):
                self.snapshot.copy(self.snapshot.public(item["source"]))
                self.snapshot.copy(self.snapshot.public(item["output"]), optional=True)
            sources = site_tools._companion_input_paths(self.root, "vegavisuals")
            for path in site_tools._companion_expected_inputs(self.root, "vegavisuals", sources):
                self.dependency(path.relative_to(self.root).as_posix())
            raw = self.snapshot.copy(".unaltraweb/receipts/vegavisuals.json", optional=True)
            status = site_tools._companion_receipt_status(self.root, "vegavisuals", sources)
            if not status["ok"]:
                raise ValueError(f"Vega receipt {status['state']}: {status.get('error')}; run vegavisuals visualization_check after explicit rendering")
            for item in self.manual.load_vega_manifest(self.root):
                self.record(item["source"], [item["output"]], "vega", status, digest(raw))
        if diagrams:
            raw = self.snapshot.copy(".unaltraweb/receipts/diavisuals.json", optional=True)
            sources = [self.root / path for path in diagrams]
            status = site_tools._companion_receipt_status(self.root, "diavisuals", sources)
            if not status["ok"]:
                raise ValueError(f"Diagram receipt {status['state']}: {status.get('error')}; run diavisuals project_check after explicit rendering")
            for path in diagrams:
                output = path + (".edited.svg" if (self.root / (path + ".edited.svg")).is_file() else ".svg")
                if self.snapshot.mtimes[path] > self.snapshot.mtimes[output]:
                    raise ValueError(f"{path}: diagram stale; explicitly render/review and refresh the provider receipt")
                self.record(path, [output], "diagram", status, digest(raw))

    def _captures(self):
        native = module(self.factory, "scripts/web_captures/render.py")
        # Select the same factory implementation; never infer it from a consumer.
        native.factory_root = lambda: self.factory
        for path in self.snapshot.reader.walk("assets"):
            if path.lower().endswith(native.SOURCE_SUFFIXES):
                recipe = yaml_mapping(self.snapshot.copy(path).decode())
                for dependency in recipe.get("inputs", []):
                    self.dependency(dependency)
            elif path.endswith((".capture.png", ".capture.svg", ".capture.edited.svg")):
                self.snapshot.copy(path)
        records = native.discover(self.root)
        raw = self.snapshot.copy(str(native.LOCK_PATH), optional=True)
        if raw:
            strict_json(raw.decode())
        for record in records:
            for key in ("png", "svg", "edited"):
                self.snapshot.copy(record[key].relative_to(self.root).as_posix(), optional=True)
        status = native.status(self.root)
        if not status["ok"]:
            detail = [(row["source"], row["reason"]) for row in status["captures"] if not row["current"]]
            raise ValueError(f"Web captures are not current: {detail or status['orphaned_records'] or status['orphaned_artifacts']}; run web_capture_check and explicitly render/review")
        for row in status["captures"]:
            self.record(row["source"], [row["png"], row["svg"], row["edited_svg"]], "web-capture", row, digest(raw))

    def resolve(self, selected):
        source = self.outputs.get(selected, selected)
        record = self.records.get(source)
        if record is None:
            if Path(selected).suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
                raise ValueError(f"{selected}: no declared producer/receipt; configure and run its native check before exporting")
            data = self.snapshot.copy(selected)
            if (".capture." in selected or re.search(rb"unaltracaptura|qgis[-_ ]?capture", data, re.I)
                    or any(selected.endswith(s + ".svg") or selected.endswith(s + ".edited.svg") for s in site_tools.DIAGRAM_SOURCE_SUFFIXES)):
                raise ValueError(f"{selected}: capture/diagram provenance is not verifiable; reference its declared source and native freshness receipt (QGIS capture handoff is not supported in v1)")
            return selected, selected, {"kind": "static", "edited": selected.endswith(".edited.svg")}
        effective = self.manual.resolve_visual_source(self.root, selected)
        # A direct generated image reference still uses its declared source's
        # current effective selection, including edited overrides.
        if record["kind"] == "computation" and effective.endswith(".edited.svg"):
            bases = [path for path in record["outputs"] if Path(path).with_suffix(".edited.svg").as_posix() == effective]
            if not bases:
                raise ValueError(f"{effective}: edited override has no declared base output")
            base = bases[0]
            if self.snapshot.mtimes.get(effective, 0) < max(self.snapshot.mtimes[base], self.snapshot.mtimes[source]):
                raise ValueError(f"{effective}: edited computation override predates its current source/output; review it explicitly")
        data = self.snapshot.copy(effective)
        from .manual_context import canonical
        evidence = {"kind": record["kind"], "source": source, "source_sha256": digest(self.snapshot.copy(source)),
                    "effective": effective, "effective_sha256": digest(data), "native_receipt_sha256": record["receipt"],
                    "native_status": record["status"]}
        # Bind NEW evidence to the actual edited bytes; never attribute new bytes
        # to an older renderer receipt. The evidence is retained beside the tar.
        sha = digest(canonical(evidence))
        self.evidence[sha] = evidence
        return source, effective, {"kind": record["kind"], "edited": effective.endswith(".edited.svg"), "receipt_sha256": sha}
