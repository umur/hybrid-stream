import json
import threading
from pathlib import Path


class SchemaRegistry:
    """
    Loads operator schemas from etcd (production) or local JSON files (dev/test).
    Caches one schema per operator class per process lifetime — no per-record overhead.
    """

    def __init__(self, etcd_client=None, local_schema_dir: str | None = None):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._etcd = etcd_client
        self._local_dir = Path(local_schema_dir) if local_schema_dir else None

    def get_schema(self, operator_class: str, version: int = 1) -> dict:
        cache_key = f"{operator_class}:v{version}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
            schema = self._load(operator_class, version)
            self._cache[cache_key] = schema
            return schema

    def _load(self, operator_class: str, version: int) -> dict:
        if self._local_dir:
            path = self._local_dir / f"v{version}" / f"{operator_class}.json"
            if path.exists():
                return json.loads(path.read_text())
        if self._etcd:
            key = f"/hybridstream/schema/v{version}/{operator_class}"
            result = self._etcd.get(key)
            if result and result[0]:
                return json.loads(result[0].decode())
        raise KeyError(f"Schema not found: {operator_class} v{version}")

    def register_all_from_dir(self, schema_dir: str) -> None:
        """Bootstrap: write all local JSON schemas to etcd."""
        if not self._etcd:
            raise RuntimeError("etcd client required for registration")
        for path in Path(schema_dir).rglob("*.json"):
            data = json.loads(path.read_text())
            key = f"/hybridstream/schema/v{data['schema_version']}/{data['operator_class']}"
            self._etcd.put(key, json.dumps(data))
