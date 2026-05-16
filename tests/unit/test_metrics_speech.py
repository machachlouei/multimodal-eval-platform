from melp.metrics.speech import cer, wer


def test_wer_perfect():
    r = wer(["the quick brown fox"], ["the quick brown fox"])
    assert r.aggregate == 0.0


def test_wer_one_substitution():
    r = wer(["the quick brown cat"], ["the quick brown fox"])
    assert abs(r.aggregate - 0.25) < 1e-6


def test_cer_basic():
    r = cer(["hello"], ["hellp"])
    assert abs(r.aggregate - 0.2) < 1e-6
