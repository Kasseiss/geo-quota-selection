"""A small GPU segmentation MLP using existing CUDA and CuPy.

The frozen deep encoder is extracted on CPU when CUDA PyTorch is unavailable.
Only the MLP is trained on RTX4060; this distinction must be reported.
"""
from __future__ import annotations
import os
from pathlib import Path
import sys
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# NVRTC's Windows include-path handling requires an ASCII spelling of the path.
# A directory junction aliases the same files; it creates no duplicate runtime.
runtime_root = Path(os.environ.get("MDPI_RUNTIME_ROOT", str(PROJECT_ROOT / "runtime")))
runtime_alias = Path.home() / ".codex" / ".tmp" / "mdpi_dl_runtime_20261018"
if os.name == "nt" and not str(runtime_root).isascii() and runtime_alias.is_dir():
    if runtime_alias.resolve() != runtime_root.resolve():
        raise RuntimeError("Runtime junction does not refer to this project's runtime")
    runtime_root = runtime_alias
sys.path.insert(0, str(runtime_root / "site-packages"))
os.environ.setdefault("CUPY_CACHE_DIR", str(runtime_root / "cupy-cache"))
if os.name == "nt" and os.environ.get("CUDA_PATH"):
    _cuda_dll_dir = os.add_dll_directory(str(Path(os.environ["CUDA_PATH"]) / "bin"))
import cupy as cp


def device_info():
    p = cp.cuda.runtime.getDeviceProperties(0)
    return {"name": p["name"].decode(), "cupy": cp.__version__,
            "runtime": cp.cuda.runtime.runtimeGetVersion(),
            "driver": cp.cuda.runtime.driverGetVersion(),
            "total_memory_bytes": int(p["totalGlobalMem"])}


class MLP:
    def __init__(self, features, hidden=128, classes=8, seed=0):
        rng = np.random.default_rng(seed)
        self.p = [cp.asarray(rng.normal(0, np.sqrt(2 / features), (features, hidden)).astype(np.float32)),
                  cp.zeros(hidden, dtype=cp.float32),
                  cp.asarray(rng.normal(0, np.sqrt(2 / hidden), (hidden, classes)).astype(np.float32)),
                  cp.zeros(classes, dtype=cp.float32)]
        self.m = [cp.zeros_like(a) for a in self.p]
        self.v = [cp.zeros_like(a) for a in self.p]
        self.t = 0

    def logits(self, x):
        h = cp.maximum(x @ self.p[0] + self.p[1], 0)
        return h @ self.p[2] + self.p[3]

    def loss_and_grad(self, x, target):
        h = cp.maximum(x @ self.p[0] + self.p[1], 0)
        logits = h @ self.p[2] + self.p[3]
        logits -= logits.max(1, keepdims=True)
        logp = logits - cp.log(cp.exp(logits).sum(1, keepdims=True))
        loss = -(target * logp).sum() / len(x)
        d = (cp.exp(logp) - target) / len(x)
        dh = (d @ self.p[2].T) * (h > 0)
        grad = [x.T @ dh, dh.sum(0), h.T @ d, d.sum(0)]
        return loss, grad

    def step(self, x, target, learning_rate=.001, weight_decay=.0001):
        loss, grad = self.loss_and_grad(x, target)
        self.t += 1
        for i in range(len(self.p)):
            self.m[i] *= .9
            self.m[i] += .1 * grad[i]
            self.v[i] *= .999
            self.v[i] += .001 * grad[i] ** 2
            self.p[i] *= 1 - learning_rate * weight_decay
            self.p[i] -= learning_rate * (self.m[i] / (1 - .9 ** self.t)) / (
                cp.sqrt(self.v[i] / (1 - .999 ** self.t)) + 1e-8)
        return float(loss.get())

    def save(self, path):
        np.savez_compressed(path, **{f"p{i}": cp.asnumpy(a) for i, a in enumerate(self.p)})


class Linear(MLP):
    def __init__(self, features, classes=8, seed=0):
        rng = np.random.default_rng(seed)
        self.p = [cp.asarray(rng.normal(0, np.sqrt(1 / features), (features, classes)).astype(np.float32)),
                  cp.zeros(classes, dtype=cp.float32)]
        self.m = [cp.zeros_like(a) for a in self.p]
        self.v = [cp.zeros_like(a) for a in self.p]
        self.t = 0

    def logits(self, x):
        return x @ self.p[0] + self.p[1]

    def loss_and_grad(self, x, target):
        logits = self.logits(x)
        logits -= logits.max(1, keepdims=True)
        logp = logits - cp.log(cp.exp(logits).sum(1, keepdims=True))
        loss = -(target * logp).sum() / len(x)
        d = (cp.exp(logp) - target) / len(x)
        return loss, [x.T @ d, d.sum(0)]


def verify():
    """Compare GPU loss and derivatives with PyTorch autograd on CPU."""
    import torch
    torch.set_num_threads(2)
    rng = np.random.default_rng(7)
    x = rng.normal(size=(31, 5)).astype(np.float32)
    y = np.eye(3, dtype=np.float32)[rng.integers(0, 3, 31)]
    # Soft targets exercise mixed land-cover cells, not just hard labels.
    y = .8 * y + .2 / 3
    net = MLP(5, hidden=11, classes=3, seed=8)
    loss, grads = net.loss_and_grad(cp.asarray(x), cp.asarray(y))
    p = [torch.tensor(cp.asnumpy(a), requires_grad=True) for a in net.p]
    logits = torch.relu(torch.tensor(x) @ p[0] + p[1]) @ p[2] + p[3]
    reference_loss = -(torch.tensor(y) * torch.log_softmax(logits, dim=1)).sum() / len(x)
    reference_loss.backward()
    errors = [float(np.max(np.abs(cp.asnumpy(a) - b.grad.numpy()))) for a, b in zip(grads, p)]
    assert abs(float(loss.get()) - reference_loss.item()) < 2e-6
    assert max(errors) < 2e-6, errors
    start = float(loss.get())
    for _ in range(150):
        net.step(cp.asarray(x), cp.asarray(y), learning_rate=.02)
    end = float(net.loss_and_grad(cp.asarray(x), cp.asarray(y))[0].get())
    assert end < start - .1
    return {"device": device_info(), "gradient_max_errors": errors,
            "initial_loss": start, "final_loss": end,
            "purpose": "software verification with synthetic arrays; not empirical research evidence"}


if __name__ == "__main__":
    import json
    print(json.dumps(verify(), indent=2))
