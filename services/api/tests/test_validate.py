import json
import math

from kirchhoff.store.validate import firestore_safe_problems, json_size_bytes


def test_nested_array_in_array_is_a_problem():
    problems = firestore_safe_problems([[1, 2]])
    assert any("$[0]" in p for p in problems)


def test_nested_array_in_array_inside_dict():
    problems = firestore_safe_problems({"a": [[1, 2]]})
    assert any("$.a[0]" in p for p in problems)


def test_clean_value_has_no_problems():
    assert firestore_safe_problems({"a": [1, 2, {"b": "x"}], "c": None, "d": True}) == []


def test_tuple_is_a_problem():
    problems = firestore_safe_problems((1, 2))
    assert len(problems) == 1


def test_tuple_nested_is_a_problem():
    problems = firestore_safe_problems({"a": (1, 2)})
    assert any("$.a" in p for p in problems)


def test_nan_and_infinity_are_problems():
    problems = firestore_safe_problems({"a": math.nan, "b": math.inf})
    assert len(problems) == 2


def test_non_string_dict_key_is_a_problem():
    problems = firestore_safe_problems({1: "x"})
    assert len(problems) == 1


def test_empty_string_dict_key_is_a_problem():
    problems = firestore_safe_problems({"": "x"})
    assert len(problems) == 1


def test_non_json_type_is_a_problem():
    class Weird:
        pass

    problems = firestore_safe_problems({"a": Weird()})
    assert len(problems) == 1


def test_json_size_bytes_matches_compact_json_encoding():
    value = {"a": 1, "b": "x"}
    assert json_size_bytes(value) == len(
        json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()
    )
