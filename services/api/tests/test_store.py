import pytest

from kirchhoff.store.memory import MemoryStore


def test_list_docs_default_order_is_by_doc_id():
    store = MemoryStore()
    store.set_doc("c/b", {"seq": 2})
    store.set_doc("c/a", {"seq": 1})
    docs = store.list_docs("c")
    assert [d["seq"] for d in docs] == [1, 2]


def test_list_docs_order_by_field_ascending_and_descending():
    store = MemoryStore()
    store.set_doc("c/x1", {"seq": 3})
    store.set_doc("c/x2", {"seq": 1})
    store.set_doc("c/x3", {"seq": 2})
    asc = store.list_docs("c", order_by="seq")
    assert [d["seq"] for d in asc] == [1, 2, 3]
    desc = store.list_docs("c", order_by="seq", descending=True)
    assert [d["seq"] for d in desc] == [3, 2, 1]


def test_list_docs_limit_applies_after_ordering():
    store = MemoryStore()
    for i in range(5):
        store.set_doc(f"c/x{i}", {"seq": i})
    docs = store.list_docs("c", order_by="seq", descending=True, limit=2)
    assert [d["seq"] for d in docs] == [4, 3]


def test_transact_reads_then_writes_atomically():
    store = MemoryStore()
    store.set_doc("a/1", {"count": 1})

    def fn(snapshot):
        assert snapshot == {"a/1": {"count": 1}, "a/2": None}
        return [("a/1", {"count": 2}), ("a/2", {"count": 10})]

    writes = store.transact(["a/1", "a/2"], fn)
    assert writes == [("a/1", {"count": 2}), ("a/2", {"count": 10})]
    assert store.get_doc("a/1") == {"count": 2}
    assert store.get_doc("a/2") == {"count": 10}


def test_transact_raising_fn_writes_nothing():
    store = MemoryStore()
    store.set_doc("a/1", {"count": 1})

    def fn(snapshot):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        store.transact(["a/1"], fn)
    assert store.get_doc("a/1") == {"count": 1}


def test_transact_write_none_deletes_doc():
    store = MemoryStore()
    store.set_doc("a/1", {"count": 1})

    def fn(snapshot):
        return [("a/1", None)]

    store.transact(["a/1"], fn)
    assert store.get_doc("a/1") is None


def test_delete_tree_removes_doc_and_subcollection_docs_only():
    store = MemoryStore()
    store.set_doc("a/1", {"x": 1})
    store.set_doc("a/1/sub/2", {"x": 2})
    store.set_doc("a/1/sub/3", {"x": 3})
    store.set_doc("a/2", {"x": 4})  # unrelated, must survive

    count = store.delete_tree("a/1")
    assert count == 3
    assert store.get_doc("a/1") is None
    assert store.get_doc("a/1/sub/2") is None
    assert store.get_doc("a/1/sub/3") is None
    assert store.get_doc("a/2") == {"x": 4}


def test_update_doc_deep_merges_nested_dicts():
    store = MemoryStore()
    store.set_doc("a/1", {"lease": {"owner": "a", "attempt": 1}})
    store.update_doc("a/1", {"lease": {"attempt": 2}})
    assert store.get_doc("a/1") == {"lease": {"owner": "a", "attempt": 2}}
