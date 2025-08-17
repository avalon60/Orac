from importlib.resources import files
import json
from jsonschema import Draft202012Validator

# Load the bundled schema text (keeps it inside the wheel)
_schema_path = files("orac_protocol.resources.json_schema").joinpath("protocol.schema.json")
schema_text = _schema_path.read_text(encoding="utf-8")
_schema = json.loads(schema_text)

_validator = Draft202012Validator(_schema)

def validate_frame(obj: dict) -> None:
    """Validate a message against the Orac protocol schema."""
    errors = sorted(_validator.iter_errors(obj), key=lambda e: e.path)
    if errors:
        msgs = [f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors]
        raise ValueError("Protocol validation failed: " + "; ".join(msgs))

