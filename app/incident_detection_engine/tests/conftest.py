"""pytest configuration for incident detection engine tests."""
import sys
import importlib
from pathlib import Path

engine_dir = Path(__file__).resolve().parent.parent
if str(engine_dir) not in sys.path:
    sys.path.insert(0, str(engine_dir))

# Alias incident engine sub-modules into app namespace for tests
sub_modules = [
    "clustering",
    "risk_scoring",
    "data_processing",
    "geo_utils",
    "analysis_engine",
    "event_service",
    "weather_service",
    "routes",
]

for mod in sub_modules:
    try:
        imported = importlib.import_module(f"app.incident_detection_engine.app.{mod}")
        sys.modules[f"app.{mod}"] = imported
    except Exception as e:
        pass
