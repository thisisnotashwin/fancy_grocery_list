import pytest
from pathlib import Path
from fancy_grocery_list.staples import Staple, StapleManager


def test_add_staple(tmp_path):
    mgr = StapleManager(base_dir=tmp_path)
    mgr.add("eggs", "1 dozen")
    staples = mgr.list()
    assert len(staples) == 1
    assert staples[0].name == "eggs"
    assert staples[0].quantity == "1 dozen"


def test_add_staple_no_quantity(tmp_path):
    mgr = StapleManager(base_dir=tmp_path)
    mgr.add("paper towels")
    staples = mgr.list()
    assert staples[0].quantity == ""


def test_add_duplicate_staple_is_idempotent(tmp_path):
    mgr = StapleManager(base_dir=tmp_path)
    mgr.add("eggs", "1 dozen")
    mgr.add("eggs", "1 dozen")
    assert len(mgr.list()) == 1


def test_remove_staple(tmp_path):
    mgr = StapleManager(base_dir=tmp_path)
    mgr.add("eggs", "1 dozen")
    mgr.add("butter", "1 stick")
    mgr.remove("eggs")
    names = [s.name for s in mgr.list()]
    assert "eggs" not in names
    assert "butter" in names


def test_remove_nonexistent_staple_is_silent(tmp_path):
    mgr = StapleManager(base_dir=tmp_path)
    mgr.remove("ghost ingredient")  # should not raise


def test_staples_persist_across_instances(tmp_path):
    StapleManager(base_dir=tmp_path).add("milk", "1 gallon")
    loaded = StapleManager(base_dir=tmp_path).list()
    assert loaded[0].name == "milk"
