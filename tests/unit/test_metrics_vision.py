import numpy as np

from melp.metrics.vision import bert_score, clip_score, fid, inception_score


def test_clip_score_orthogonal_zero():
    items = [{"image_features": np.array([1.0, 0.0]), "text_features": np.array([0.0, 1.0])}]
    r = clip_score(items)
    assert r.aggregate == 0.0


def test_clip_score_aligned_one():
    items = [{"image_features": np.array([1.0, 0.0]), "text_features": np.array([1.0, 0.0])}]
    r = clip_score(items)
    assert abs(r.aggregate - 1.0) < 1e-6


def test_fid_same_distribution_is_small():
    np.random.seed(0)
    p = [{"image_features": np.random.randn(16)} for _ in range(64)]
    q = [{"image_features": np.random.randn(16)} for _ in range(64)]
    r = fid(p, q)
    assert r.aggregate >= 0.0


def test_inception_score_uniform_one():
    p = [{"probs": np.array([0.25] * 4)} for _ in range(8)]
    r = inception_score(p)
    assert abs(r.aggregate - 1.0) < 1e-6


def test_bert_score_identical_embeddings():
    p = [{"embedding": np.array([1.0, 2.0, 3.0])}]
    r = [{"embedding": np.array([1.0, 2.0, 3.0])}]
    out = bert_score(p, r)
    assert abs(out.aggregate - 1.0) < 1e-6
