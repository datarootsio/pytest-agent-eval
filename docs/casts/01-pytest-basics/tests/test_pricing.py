def discount(subtotal: int, code: str) -> float:
    if code == "SPRING":
        return subtotal * 0.9
    return subtotal


def test_discount_applies_to_subtotal():
    assert discount(subtotal=100, code="SPRING") == 90


def test_discount_dont_apply_to_subtotal():
    assert discount(subtotal=100, code="SPRINGS") == 90
