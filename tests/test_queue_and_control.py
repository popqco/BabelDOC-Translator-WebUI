import sys
import shutil
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.task_manager import TaskManager, DocumentTask, BatchRecord

class TestQueueAndControlFlow(unittest.TestCase):
    def setUp(self):
        self.tm = TaskManager()
        self.tm.pending_queue.clear()
        self.tm.active_batch = None
        self.tm.stop_requested_mode = None

        self.test_root = BASE_DIR / "tests" / "test_scratch2"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.f1 = self.test_root / "chip_a.pdf"
        self.f2 = self.test_root / "chip_b.pdf"
        self.f1.write_bytes(b"%PDF-1.4 dummy A")
        self.f2.write_bytes(b"%PDF-1.4 dummy B")

    def tearDown(self):
        shutil.rmtree(self.test_root, ignore_errors=True)

    def test_queue_append_and_hash_dedup(self):
        added, names = self.tm.add_to_pending([str(self.f1), str(self.f2)])
        self.assertEqual(added, 2)
        self.assertEqual(len(self.tm.pending_queue), 2)

        added2, names2 = self.tm.add_to_pending([str(self.f1)])
        self.assertEqual(added2, 0)
        self.assertEqual(len(self.tm.pending_queue), 2)

        self.tm.remove_from_pending(1)
        self.assertEqual(len(self.tm.pending_queue), 1)
        self.assertEqual(self.tm.pending_queue[0]["name"], "chip_a.pdf")

        self.tm.clear_pending()
        self.assertEqual(len(self.tm.pending_queue), 0)

    def test_dynamic_append_during_running_batch(self):
        batch_dir = self.test_root / "RunningBatch"
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch = BatchRecord(
            batch_id="batch_dynamic",
            created_at="2026-09-18T00:00:00",
            output_dir=str(batch_dir),
            status="running",
            options={},
            tasks=[
                DocumentTask(
                    id="t1",
                    original_path=str(self.f1),
                    filename=self.f1.name,
                    file_hash="hash_a",
                    status="processing"
                )
            ]
        )
        self.tm.active_batch = batch

        added, msg = self.tm.append_to_active_batch([str(self.f2)])
        self.assertEqual(added, 1)
        self.assertEqual(len(self.tm.active_batch.tasks), 2)
        self.assertEqual(self.tm.active_batch.tasks[1].filename, "chip_b.pdf")
        self.assertEqual(self.tm.active_batch.tasks[1].status, "pending")

    def test_stop_policies(self):
        batch_dir = self.test_root / "StopBatch"
        batch_dir.mkdir(parents=True, exist_ok=True)
        batch = BatchRecord(
            batch_id="batch_stop",
            created_at="2026-09-18T00:00:00",
            output_dir=str(batch_dir),
            status="running",
            options={},
            tasks=[]
        )
        self.tm.active_batch = batch

        self.tm.request_stop("stop_after_current")
        self.assertEqual(self.tm.stop_requested_mode, "stop_after_current")

        self.tm.request_stop("cancel_immediately")
        self.assertEqual(self.tm.stop_requested_mode, "cancel_immediately")

if __name__ == "__main__":
    unittest.main(verbosity=2)