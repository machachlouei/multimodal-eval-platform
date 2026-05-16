from melp.metrics.classic import accuracy, exact_match, f1_macro, mae, mse


def test_accuracy_basic():
    r = accuracy([1, 0, 1, 1], [1, 1, 1, 0])
    assert r.aggregate == 0.5
    assert r.n == 4


def test_exact_match_strips_whitespace():
    r = exact_match(["hello", " world "], ["hello", "world"])
    assert r.aggregate == 1.0


def test_f1_macro_perfect():
    r = f1_macro([0, 1, 2, 0, 1, 2], [0, 1, 2, 0, 1, 2])
    assert r.aggregate == 1.0


def test_mse_mae():
    m = mse([1.0, 2.0, 3.0], [1.0, 2.5, 3.0])
    assert abs(m.aggregate - 0.0833333) < 1e-5
    a = mae([1.0, 2.0, 3.0], [1.0, 2.5, 3.0])
    assert abs(a.aggregate - 0.1666666) < 1e-5
