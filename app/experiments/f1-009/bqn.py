"""Compact CPU Bernstein quantile network; irradiance internally in kW/m²."""
import math
import numpy as np
from scipy.special import betainc, expit

DEGREE, HIDDEN, INPUTS = 12, 16, 27
LEVELS = np.arange(1, 52, dtype=float) / 52
L2 = 1e-6


def basis(levels):
    t = np.asarray(levels, dtype=float)
    return np.stack([math.comb(DEGREE, j) * t**j * (1 - t)**(DEGREE - j)
                     for j in range(DEGREE + 1)], axis=-1)


BASIS = basis(LEVELS)
MEDIAN_BASIS = basis(.5)
CENTERED_BASIS = BASIS - MEDIAN_BASIS
SHAPES = ((INPUTS, HIDDEN), (HIDDEN,), (HIDDEN, DEGREE + 1), (DEGREE + 1,))


def pack(arrays): return np.concatenate([a.ravel() for a in arrays])


def unpack(theta):
    arrays, offset = [], 0
    for shape in SHAPES:
        n = math.prod(shape)
        arrays.append(theta[offset:offset + n].reshape(shape)); offset += n
    if offset != len(theta): raise ValueError('Wrong parameter count')
    return arrays


def initialize():
    rng = np.random.default_rng(17)
    w1 = rng.normal(0, 1 / math.sqrt(INPUTS), SHAPES[0])
    b2 = np.r_[0., np.full(DEGREE, np.log(np.expm1(.1 / DEGREE))) ]
    return pack((w1, np.zeros(HIDDEN), np.zeros(SHAPES[2]), b2))


def coefficients(theta, x, skip):
    w1, b1, w2, b2 = unpack(theta)
    h = np.tanh(x @ w1 + b1)
    z = h @ w2 + b2
    increments = np.logaddexp(0, z[:, 1:])
    cumulative = np.c_[np.zeros(len(x)), np.cumsum(increments, axis=1)]
    alpha = skip[:, None] + z[:, :1] + cumulative - (cumulative @ MEDIAN_BASIS)[:, None]
    if not np.isfinite(alpha).all(): raise ValueError('Nonfinite coefficients')
    return alpha


def objective(theta, x, skip, weather, satellite, joint):
    w1, b1, w2, b2 = unpack(theta)
    h = np.tanh(x @ w1 + b1)
    z = h @ w2 + b2
    cumulative = np.c_[np.zeros(len(x)), np.cumsum(np.logaddexp(0, z[:, 1:]), axis=1)]
    raw = skip[:, None] + z[:, :1] + cumulative @ CENTERED_BASIS.T
    q = np.maximum(0, raw)
    available = np.isfinite(satellite) if joint else np.zeros(len(x), dtype=bool)
    weights = np.where(available, .5, 1.)
    loss, dq = 0., np.zeros_like(q)
    for y, weight in ((weather, weights), (np.where(available, satellite, 0), available * .5)):
        residual = y[:, None] - q
        loss += np.sum(weight[:, None] * np.where(residual >= 0, LEVELS * residual, (LEVELS - 1) * residual))
        derivative = np.where(residual == 0, 0, (residual < 0).astype(float) - LEVELS)
        dq += weight[:, None] * derivative
    divisor = len(x) * len(LEVELS)
    loss /= divisor
    draw = dq * (raw > 0) / divisor
    gc = draw @ CENTERED_BASIS
    increments_grad = np.cumsum(gc[:, :0:-1], axis=1)[:, ::-1]
    gz = np.c_[draw.sum(axis=1), increments_grad * expit(z[:, 1:])]
    gh = (gz @ w2.T) * (1 - h*h)
    grad = pack((x.T @ gh + L2 * w1, gh.sum(axis=0), h.T @ gz + L2 * w2, gz.sum(axis=0)))
    loss += .5 * L2 * (np.sum(w1*w1) + np.sum(w2*w2))
    if not np.isfinite(loss) or not np.isfinite(grad).all(): raise ValueError('Nonfinite objective/gradient')
    return float(loss), grad


def cdf(alpha, value):
    """Rightmost quantile level with uncensored Q(tau)<=value; 60 bisections."""
    lo, hi = np.zeros(len(alpha)), np.ones(len(alpha))
    below, above = alpha[:, -1] <= value, alpha[:, 0] > value
    for _ in range(60):
        mid = (lo + hi) / 2
        q = np.sum(alpha * basis(mid), axis=1)
        at_or_below = q <= value
        lo = np.where(at_or_below, mid, lo)
        hi = np.where(at_or_below, hi, mid)
    return np.where(below, 1., np.where(above, 0., (lo + hi) / 2))


def predict(theta, x, skip):
    alpha = coefficients(theta, x, skip)
    quantiles = np.maximum(0, alpha @ BASIS.T)
    zero = cdf(alpha, 0.)
    j = np.arange(DEGREE + 1)
    integrated = 1 - betainc(j + 1, DEGREE - j + 1, zero[:, None])
    mean = np.sum(alpha * integrated, axis=1) / (DEGREE + 1)
    if np.any(mean < -1e-12): raise ValueError('Negative censored mean')
    result = {'coefficients': alpha, 'quantiles': quantiles * 1000,
              'probability': 1 - cdf(alpha, .6), 'zero_mass': zero,
              'median': np.maximum(0, alpha @ MEDIAN_BASIS) * 1000,
              'mean': np.maximum(0, mean) * 1000,
              'lower': np.maximum(0, alpha @ basis(.05)) * 1000,
              'upper': np.maximum(0, alpha @ basis(.95)) * 1000}
    if any(not np.isfinite(v).all() for v in result.values()): raise ValueError('Nonfinite prediction')
    if np.any(np.diff(alpha, axis=1) < 0) or np.any(np.diff(quantiles, axis=1) < -1e-12): raise ValueError('Quantile crossing')
    return result


def fit_scaler(x):
    if np.isinf(x).any(): raise ValueError('Infinite features')
    count = np.isfinite(x).sum(axis=0)
    if np.any(count == 0): raise ValueError('Entire training feature missing')
    mean = np.nansum(x, axis=0) / count
    filled = np.where(np.isnan(x), mean, x)
    scale = filled.std(axis=0)
    scale[scale == 0] = 1
    return mean, scale


def transform(x, mean, scale):
    result = (np.where(np.isnan(x), mean, x) - mean) / scale
    if not np.isfinite(result).all(): raise ValueError('Invalid scaled features')
    return result
