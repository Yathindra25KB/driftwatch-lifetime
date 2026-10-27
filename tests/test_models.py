"""Detector interface, logistic regression and LightGBM (ADR-0006, models-metrics rules).

Scaling is fitted on the training window only, the decision threshold is fixed, a fit
carries its window id, and nothing here is evidence about detectors (synthetic data).
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest
import scipy.sparse as sp

from driftwatch.models import MODEL_NAMES, make_model
from driftwatch.models.base import Detector, NotFittedError, WindowMismatch
from driftwatch.models.lgbm import PROFILES, LightGBMDetector
from driftwatch.models.linear import LogisticDetector


def _data(n: int = 600, d: int = 24, seed: int = 0, shift: float = 0.0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.35).astype(np.int8)
    X = rng.normal(size=(n, d)).astype(np.float32) + shift
    X[:, 0] += 2.5 * y
    X[:, 1] -= 1.5 * y
    return X, y


def _sparse_data(n: int = 600, d: int = 40, seed: int = 0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.35).astype(np.int8)
    dense = (rng.random((n, d)) < 0.05).astype(np.int8) * rng.integers(1, 5, size=(n, d))
    dense[:, 0] = np.where(y == 1, rng.integers(1, 4, size=n), 0)
    dense[:, 1] = np.where((y == 0) & (rng.random(n) < 0.3), 1, 0)
    return sp.csr_matrix(dense.astype(np.int8)), y


MODELS = [("lr", {}), ("lgbm", {"profile": "fast"}), ("lgbm", {"profile": "default"})]


@pytest.fixture(params=MODELS, ids=["lr", "lgbm-fast", "lgbm-default"])
def model(request) -> Detector:
    name, extra = request.param
    return make_model({"name": name, **extra}, seed=3)


# --- interface -------------------------------------------------------------------------------


def test_registry_names() -> None:
    assert set(MODEL_NAMES) == {"lr", "lgbm"}
    with pytest.raises(ValueError, match="unknown model"):
        make_model({"name": "mlp"}, seed=0)


def test_unknown_hyperparameter_is_an_error() -> None:
    with pytest.raises(ValueError, match="unknown"):
        make_model({"name": "lr", "learning_rate": 0.1}, seed=0)


def test_predict_proba_is_the_malware_probability_and_threshold_is_fixed(model: Detector) -> None:
    X, y = _data()
    model.fit(X, y, "w0")
    p = model.predict_proba(X, "w0")
    assert p.shape == (len(y),) and p.dtype == np.float64
    assert ((p >= 0.0) & (p <= 1.0)).all()
    assert model.threshold == 0.5
    assert np.array_equal(model.predict(X, "w0"), (p > 0.5).astype(np.int8))
    # it separates the planted signal, so the probability is for class 1
    assert p[y == 1].mean() > p[y == 0].mean() + 0.3


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.2, 1.5])
def test_threshold_must_lie_strictly_between_zero_and_one(bad: float) -> None:
    with pytest.raises(ValueError, match="threshold"):
        LogisticDetector(seed=0, threshold=bad)


def test_a_custom_threshold_changes_only_the_decision() -> None:
    X, y = _data()
    low = LogisticDetector(seed=0, threshold=0.2).fit(X, y, "w")
    high = LogisticDetector(seed=0, threshold=0.8).fit(X, y, "w")
    assert np.array_equal(low.predict_proba(X, "w"), high.predict_proba(X, "w"))
    assert low.predict(X, "w").sum() > high.predict(X, "w").sum()


def test_predict_needs_a_fit_and_the_matching_window(model: Detector) -> None:
    X, y = _data(n=200)
    with pytest.raises(NotFittedError):
        model.predict_proba(X, "w0")
    model.fit(X, y, "w0")
    assert model.fitted_window_id == "w0"
    with pytest.raises(WindowMismatch):
        model.predict_proba(X, "w1")  # scored under another window's id
    model.fit(X, y, "w1")  # a refit moves the id
    assert model.fitted_window_id == "w1"
    model.predict_proba(X, "w1")


def test_scoring_methods_cannot_receive_labels(model: Detector) -> None:
    for method in (model.predict_proba, model.predict):
        assert "y" not in inspect.signature(method).parameters


def test_fit_rejects_one_class_and_misaligned_labels(model: Detector) -> None:
    X, y = _data(n=100)
    with pytest.raises(ValueError, match="both classes"):
        model.fit(X, np.zeros_like(y), "w")
    with pytest.raises(ValueError, match="line up"):
        model.fit(X, y[:-1], "w")
    with pytest.raises(ValueError, match="0 or 1"):
        model.fit(X, y + 1, "w")


def test_same_seed_gives_identical_probabilities(model: Detector) -> None:
    X, y = _data()
    again = make_model(model.spec(), seed=model.seed)
    a = model.fit(X, y, "w").predict_proba(X, "w")
    b = again.fit(X, y, "w").predict_proba(X, "w")
    assert a.tobytes() == b.tobytes()


def test_fit_info_is_recorded(model: Detector) -> None:
    X, y = _data(n=300)
    model.fit(X, y, "w")
    info = model.fit_info
    assert info["fit_seconds"] >= 0.0
    assert info["n_train"] == 300 and info["n_features"] == X.shape[1]
    assert info["window_id"] == "w"


def test_spec_round_trips_every_hyperparameter(model: Detector) -> None:
    spec = model.spec()
    assert spec["name"] == model.name and spec["threshold"] == 0.5
    assert make_model(spec, seed=model.seed).spec() == spec


# --- logistic regression: scaling --------------------------------------------------------------


def test_dense_scaler_is_fitted_on_the_training_window_only() -> None:
    X, y = _data(seed=1)
    m = LogisticDetector(seed=0).fit(X, y, "w")
    Xd = X.astype(np.float64)
    assert np.allclose(m.scaler_.mean_, Xd.mean(axis=0))
    assert np.allclose(m.scaler_.scale_, Xd.std(axis=0))
    # scoring a very different evaluation slot must not move the fitted statistics
    mean, scale = m.scaler_.mean_.copy(), m.scaler_.scale_.copy()
    Xe, _ = _data(seed=9, shift=50.0)
    m.predict_proba(Xe, "w")
    assert np.array_equal(m.scaler_.mean_, mean) and np.array_equal(m.scaler_.scale_, scale)


def test_refit_on_a_new_window_replaces_the_statistics() -> None:
    X0, y0 = _data(seed=1)
    X1, y1 = _data(seed=2, shift=5.0)
    m = LogisticDetector(seed=0).fit(X0, y0, "w0")
    first = m.scaler_.mean_.copy()
    m.fit(X1, y1, "w1")
    assert not np.allclose(first, m.scaler_.mean_)
    assert np.allclose(m.scaler_.mean_, X1.astype(np.float64).mean(axis=0))


def test_sparse_input_stays_sparse_and_is_not_centred(monkeypatch: pytest.MonkeyPatch) -> None:
    X, y = _sparse_data()

    def boom(*_a, **_k):
        raise AssertionError("a sparse matrix was densified")

    for cls in (sp.csr_matrix, sp.csc_matrix, sp.csr_array):
        monkeypatch.setattr(cls, "toarray", boom, raising=True)
        monkeypatch.setattr(cls, "todense", boom, raising=False)
    m = LogisticDetector(seed=0).fit(X, y, "w")
    assert m.scaler_.with_mean is False  # centring would destroy sparsity
    scaled = m.scaler_.transform(X)
    assert sp.issparse(scaled) and scaled.nnz == X.nnz  # zeros stay zeros
    assert np.all(m.scaler_.scale_ > 0)
    p = m.predict_proba(X, "w")
    assert p[y == 1].mean() > p[y == 0].mean()


def test_non_convergence_is_flagged_not_hidden() -> None:
    X, y = _data(n=400)
    m = LogisticDetector(seed=0, max_iter=1).fit(X, y, "w")
    assert m.fit_info["converged"] is False
    ok = LogisticDetector(seed=0, max_iter=300).fit(X, y, "w")
    assert ok.fit_info["converged"] is True


# --- LightGBM --------------------------------------------------------------------------------


def test_profiles_are_documented_and_fast_is_a_cheaper_default() -> None:
    d, f = PROFILES["default"], PROFILES["fast"]
    assert d["max_bin"] == 255 and d["colsample_bytree"] == 1.0 and d["subsample"] == 1.0
    assert f["max_bin"] == 63 and f["colsample_bytree"] == 0.5 and f["subsample"] == 0.8
    assert f["n_estimators"] == d["n_estimators"] == 100
    with pytest.raises(ValueError, match="profile"):
        LightGBMDetector(seed=0, profile="turbo")


def test_lightgbm_is_deterministic_and_seed_matters_under_bagging() -> None:
    X, y = _data()
    a = LightGBMDetector(seed=1, profile="fast").fit(X, y, "w").predict_proba(X, "w")
    b = LightGBMDetector(seed=1, profile="fast").fit(X, y, "w").predict_proba(X, "w")
    c = LightGBMDetector(seed=2, profile="fast").fit(X, y, "w").predict_proba(X, "w")
    assert a.tobytes() == b.tobytes()
    assert a.tobytes() != c.tobytes()


def test_lightgbm_accepts_sparse_int8_without_densifying(monkeypatch: pytest.MonkeyPatch) -> None:
    X, y = _sparse_data()

    def boom(*_a, **_k):
        raise AssertionError("a sparse matrix was densified")

    monkeypatch.setattr(sp.csr_matrix, "toarray", boom, raising=True)
    m = LightGBMDetector(seed=0, profile="fast").fit(X, y, "w")
    p = m.predict_proba(X, "w")
    assert p.shape == (X.shape[0],) and p[y == 1].mean() > p[y == 0].mean()
