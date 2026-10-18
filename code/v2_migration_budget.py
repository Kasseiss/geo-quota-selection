"""Conservative logical-byte accounting for a quiescent, single-writer migration."""
from pathlib import Path
import threading


class MigrationBudgetError(RuntimeError):
    pass


class MigrationBudget:
    """No payload writes; caller charges every allocation before creating it.

    The caller must first establish that all other writers have stopped. This
    is accounting, not protection against arbitrary external concurrent writes.
    Failed writes retain their charge. Replacements charge the full temporary
    file without credit for the old file; same-root moves charge zero.
    """
    _guard = threading.RLock()
    _active = None

    @staticmethod
    def _bytes(value):
        if type(value) is not int or value < 0:
            raise ValueError("byte amounts must be nonnegative integers")
        return value

    def __init__(self, root, allowance, cap, logical_bytes_fn):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("budget root must be an existing directory")
        self.allowance = self._bytes(allowance)
        self.cap = self._bytes(cap)
        self.scan = logical_bytes_fn
        self.ledger = dict(baseline=None, allowance=self.allowance, cap=self.cap,
                           charged=0, final=None, foreign_delta=None, passed=False,
                           state="new", scans=0)

    def _scan(self):
        self.ledger["scans"] += 1
        return self._bytes(self.scan(self.root))

    def start(self):
        with MigrationBudget._guard:
            if self.ledger["state"] != "new" or MigrationBudget._active is not None:
                raise MigrationBudgetError("nested or reused migration budget")
            MigrationBudget._active = self
            try:
                self.ledger["baseline"] = self._scan()
                if self.ledger["baseline"] + self.allowance >= self.cap:
                    raise MigrationBudgetError("full allowance does not fit strict cap")
                self.ledger["state"] = "active"
            except BaseException:
                self.ledger["state"] = "start_failed"
                MigrationBudget._active = None
                raise
        return self

    def check(self, extra=0):
        extra = self._bytes(extra)
        with MigrationBudget._guard:
            if MigrationBudget._active is not self or self.ledger["state"] != "active":
                raise MigrationBudgetError("migration budget is not active")
            total = self.ledger["charged"] + extra
            if total > self.allowance or self.ledger["baseline"] + total >= self.cap:
                raise MigrationBudgetError("allocation exceeds reserved migration budget")
        return True

    def charge(self, n):
        with MigrationBudget._guard:
            self.check(n)
            self.ledger["charged"] += n
        return self.ledger["charged"]

    def finish(self):
        with MigrationBudget._guard:
            self.check()
            try:
                actual = self._scan()
                self.ledger["final"] = actual
                foreign = actual - self.ledger["baseline"] - self.ledger["charged"]
                self.ledger["foreign_delta"] = foreign
                if actual >= self.cap or foreign > 0:
                    raise MigrationBudgetError("final cap or unaccounted growth violation")
                self.ledger["passed"] = True
                return dict(self.ledger, state="finished")
            finally:
                self.ledger["state"] = "finished" if self.ledger["passed"] else "finish_failed"
                MigrationBudget._active = None

    __enter__ = start

    def __exit__(self, exc_type, exc, traceback):
        self.ledger["body_exception"] = None if exc_type is None else exc_type.__name__
        self.finish()
        return False
