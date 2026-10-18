"""Record existing research dependencies without installing or importing GPU code."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
import platform


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    isolated = {
        d.metadata.get("Name", "").lower().replace("_", "-"): d.version
        for d in metadata.distributions(path=[str(ROOT / "runtime/site-packages")])
    }
    packages = {}
    for name in ("numpy", "Pillow", "torch", "torchvision", "matplotlib",
                 "pyproj", "scipy", "requests", "cupy-cuda12x",
                 "cuda-pathfinder", "fastrlock"):
        try:
            version, scope = metadata.version(name), "interpreter-visible metadata"
        except metadata.PackageNotFoundError:
            version = isolated.get(name.lower().replace("_", "-"))
            scope = "project-isolated metadata" if version else "not found"
        packages[name] = {"version": version, "scope": scope}
    old_path = ROOT / "evidence/v2/environment_source_record.json"
    if not old_path.exists():
        source = ROOT / "evidence/environment.json"
        old_path.write_bytes(source.read_bytes())
    calibration_path = ROOT / "evidence/v2/calibration/calibration.json"
    old = json.loads(old_path.read_text(encoding="utf-8-sig"))
    calibration = json.loads(calibration_path.read_text())
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Existing dependency metadata, SHA-bound CPU calibration identity, "
                 "and an earlier observed GPU identity; not clean-install validation.",
        "python": platform.python_version(),
        "platform": platform.system() + " " + platform.release(),
        "package_metadata_observed_now": packages,
        "full_model_calibration_environment": calibration["environment"],
        "gpu_runtime_previously_observed": old["gpu_runtime"],
        "source_records": {
            "evidence/v2/environment_source_record.json": sha(old_path),
            "evidence/v2/calibration/calibration.json": sha(calibration_path),
        },
        "recording_code_sha256": sha(Path(__file__)),
        "no_dependencies_installed": True,
        "gpu_runtime_reprobed_now": False,
        "a100_execution_claimed": False,
    }
    output = ROOT / "evidence/v2/environment_record.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print("Recorded existing dependency locations; no installation, GPU probe or fitting.")


if __name__ == "__main__":
    main()
