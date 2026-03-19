try:
    from rocksdict import Rdict, Options, WriteOptions
    _HAS_ROCKSDB = True
except ImportError:
    _HAS_ROCKSDB = False

    class Options:
        def set_write_buffer_size(self, size): pass
        def set_compression_type(self, t): pass

    class WriteOptions:
        def set_sync(self, v): pass

    class Rdict(dict):
        """In-memory fallback when rocksdict is not installed."""
        def __init__(self, path=None, options=None):
            super().__init__()

        def create_checkpoint(self, path):
            pass

        def flush(self):
            pass

        def close(self):
            pass


class OperatorStateStore:
    def __init__(self, operator_id: str, db_path: str):
        self._operator_id = operator_id
        opt = Options()
        opt.set_write_buffer_size(64 * 1024 * 1024)
        opt.set_compression_type("lz4")
        self._db = Rdict(f"{db_path}/{operator_id}", options=opt)
        self._write_opt = WriteOptions()
        self._write_opt.set_sync(False)

    def get(self, key: str) -> bytes | None:
        return self._db.get(key.encode())

    def put(self, key: str, value: bytes) -> None:
        self._db[key.encode()] = value

    def delete(self, key: str) -> None:
        del self._db[key.encode()]

    def items(self) -> list[tuple[str, bytes]]:
        return [(k.decode(), v) for k, v in self._db.items()]

    def checkpoint(self, checkpoint_dir: str) -> str:
        import os
        path = os.path.join(checkpoint_dir, self._operator_id)
        os.makedirs(path, exist_ok=True)
        self._db.create_checkpoint(path)
        return path

    def close(self, flush: bool = True) -> None:
        if flush:
            self._db.flush()
        self._db.close()
