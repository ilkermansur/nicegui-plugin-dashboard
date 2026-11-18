from harness import locale_keys, used_keys


def test_tr_and_en_have_the_same_keys():
    keys = locale_keys()
    assert keys["tr"] == keys["en"]


def test_every_used_key_exists():
    assert used_keys() - locale_keys()["en"] == set()
