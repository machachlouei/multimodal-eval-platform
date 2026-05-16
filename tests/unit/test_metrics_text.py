from melp.metrics.text import bleu, meteor, rouge_1, rouge_2, rouge_l, semantic_equivalence


def test_bleu_identical():
    r = bleu(["the cat sat on the mat"], ["the cat sat on the mat"])
    assert r.aggregate > 0.99


def test_bleu_disjoint_lower_than_identical():
    same = bleu(["hello world"], ["hello world"]).aggregate
    diff = bleu(["hello world"], ["completely different words"]).aggregate
    assert diff < same


def test_rouge_l_partial():
    r = rouge_l(["the quick brown fox"], ["the quick brown fox jumps"])
    assert 0.6 < r.aggregate < 1.0


def test_rouge_1_2_basic():
    r1 = rouge_1(["a b c d"], ["a b c d"])
    r2 = rouge_2(["a b c d"], ["a b c d"])
    assert r1.aggregate == 1.0
    assert r2.aggregate == 1.0


def test_meteor_overlap():
    r = meteor(["the cat sat"], ["the cat ran"])
    assert 0 < r.aggregate < 1


def test_semantic_equivalence_uses_judge_scores():
    r = semantic_equivalence(["a"], ["b"], judge_scores=[1, 0, 1])
    assert r.aggregate == 2 / 3
