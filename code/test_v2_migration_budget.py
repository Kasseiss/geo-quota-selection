"""Temporary fixtures only; never touches a scientific payload."""
import tempfile
import unittest
from pathlib import Path
from v2_migration_budget import MigrationBudget, MigrationBudgetError


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "protected-v1").write_bytes(b"original")
        self.calls = 0

    def scan(self, root):
        self.calls += 1
        return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())

    def test_allowance_boundary_and_midway_refusal(self):
        for allowance in (92, 93):
            b = MigrationBudget(self.root, allowance, 100, self.scan)
            with self.assertRaises(MigrationBudgetError):
                b.start()
            self.assertEqual(b.ledger["charged"], 0)
        with MigrationBudget(self.root, 10, 100, self.scan) as b:
            self.assertTrue(b.check(10))
            self.assertEqual(b.ledger["charged"], 0)
            b.charge(6)
            b.charge(4)
            with self.assertRaises(MigrationBudgetError):
                b.charge(1)
            self.assertEqual(b.ledger["charged"], 10)
        self.assertEqual(b.ledger["foreign_delta"], -10)

    def test_two_scans_many_charges_move_and_replacement(self):
        with MigrationBudget(self.root, 50, 100, self.scan) as b:
            for i in range(20):
                b.charge(1)
                (self.root / str(i)).write_bytes(b"x")
                b.check(0)
            (self.root / "0").rename(self.root / "moved")  # MOVE adds no bytes.
            b.charge(8)  # Replacement temp charged fully, no old-file credit.
            tmp = self.root / "tmp"
            tmp.write_bytes(b"replaced")
            tmp.replace(self.root / "1")
            self.assertEqual(self.calls, 1)
        self.assertEqual(self.calls, 2)
        self.assertEqual(b.ledger["charged"], 28)
        self.assertEqual(b.ledger["foreign_delta"], -1)
        self.assertEqual((self.root / "protected-v1").read_bytes(), b"original")

    def test_foreign_growth_and_cap_fail_closed(self):
        for uncharged in (1, 92):
            b = MigrationBudget(self.root, 0, 100, self.scan).start()
            outsider = self.root / "outsider"
            outsider.write_bytes(b"x" * uncharged)
            with self.assertRaises(MigrationBudgetError):
                b.finish()
            self.assertFalse(b.ledger["passed"])
            self.assertEqual(b.ledger["foreign_delta"], uncharged)
            self.assertEqual(outsider.stat().st_size, uncharged)
            outsider.unlink()  # Fixture cleanup, never helper action.

    def test_exception_keeps_charge_and_files_and_blocks_nesting(self):
        b = MigrationBudget(self.root, 20, 100, self.scan)
        with self.assertRaisesRegex(RuntimeError, "write failed"):
            with b:
                b.charge(9)
                (self.root / "partial").write_bytes(b"part")
                with self.assertRaises(MigrationBudgetError):
                    MigrationBudget(self.root, 0, 100, self.scan).start()
                raise RuntimeError("write failed")
        self.assertEqual(b.ledger["charged"], 9)
        self.assertEqual(b.ledger["body_exception"], "RuntimeError")
        self.assertEqual((self.root / "partial").read_bytes(), b"part")
        self.assertEqual((self.root / "protected-v1").read_bytes(), b"original")
        with self.assertRaises(MigrationBudgetError):
            b.charge(1)
        with MigrationBudget(self.root, 0, 100, self.scan):
            pass

    def test_invalid_amounts_and_failed_scan_release_ownership(self):
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                MigrationBudget(self.root, value, 100, self.scan)
        def broken(root):
            raise OSError("scan failed")
        with self.assertRaises(OSError):
            MigrationBudget(self.root, 0, 100, broken).start()
        b = MigrationBudget(self.root, 0, 100, self.scan).start()
        b.scan = broken
        with self.assertRaises(OSError):
            b.finish()
        self.assertEqual(b.ledger["state"], "finish_failed")
        with MigrationBudget(self.root, 0, 100, self.scan):
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
