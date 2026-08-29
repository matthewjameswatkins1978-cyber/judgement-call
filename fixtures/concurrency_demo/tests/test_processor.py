import inspect

from demoqueue.processor import process_items


def test_process_items_signature():
    sig = inspect.signature(process_items)
    assert list(sig.parameters.keys()) == ["items", "worker"]


def test_process_items_successful_values():
    items = [1, 2, 3, 4]

    def worker(x: int) -> int:
        return x * 10

    results = process_items(items, worker)
    assert results == [10, 20, 30, 40]


def test_process_items_order_preservation():
    items = ["a", "b", "c"]

    def worker(x: str) -> str:
        return x.upper()

    results = process_items(items, worker)
    assert results == ["A", "B", "C"]
