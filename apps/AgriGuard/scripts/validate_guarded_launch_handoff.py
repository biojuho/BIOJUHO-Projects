from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SCHEMA_PATH = SCRIPT_DIR / "guarded_launch_handoff.schema.json"
VALIDATION_FAILURE_EXIT_CODE = 2
VALIDATION_REPORT_SCHEMA_VERSION = 1


def read_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"{path}: file not found"]
    except json.JSONDecodeError as exc:
        return None, [f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"]
    if not isinstance(payload, dict):
        return None, [f"{path}: expected a JSON object"]
    return payload, []


def schema_type_matches(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return False


def validate_schema_subset(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}, got {value!r}")

    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(schema_type_matches(value, option) for option in expected_type):
            errors.append(f"{path}: expected type {'/'.join(expected_type)}, got {type(value).__name__}")
            return errors
        if value is None:
            return errors
    elif isinstance(expected_type, str) and not schema_type_matches(value, expected_type):
        errors.append(f"{path}: expected type {expected_type}, got {type(value).__name__}")
        return errors

    if isinstance(value, dict):
        properties = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
        required = schema.get("required", []) if isinstance(schema.get("required"), list) else []
        for key in required:
            if isinstance(key, str) and key not in value:
                errors.append(f"{path}.{key}: missing required property")
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                errors.append(f"{path}: unexpected properties: {', '.join(unexpected)}")
        for key, nested_schema in properties.items():
            if key in value and isinstance(nested_schema, dict):
                errors.extend(validate_schema_subset(value[key], nested_schema, f"{path}.{key}"))

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_schema_subset(item, item_schema, f"{path}[{index}]"))

    if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool) and value < schema["minimum"]:
        errors.append(f"{path}: expected minimum {schema['minimum']}, got {value}")
    if "minItems" in schema and isinstance(value, list) and len(value) < schema["minItems"]:
        errors.append(f"{path}: expected minItems {schema['minItems']}, got {len(value)}")
    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        errors.append(f"{path}: expected minLength {schema['minLength']}, got {len(value)}")
    if "pattern" in schema and isinstance(value, str):
        pattern = schema["pattern"]
        if not isinstance(pattern, str):
            errors.append(f"{path}: schema pattern must be a string")
        else:
            try:
                pattern_matches = re.search(pattern, value) is not None
            except re.error as exc:
                errors.append(f"{path}: invalid schema pattern {pattern!r}: {exc}")
            else:
                if not pattern_matches:
                    errors.append(f"{path}: expected pattern {pattern!r}, got {value!r}")

    return errors


def validate_handoff(handoff: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    if schema is None:
        schema, errors = read_json(DEFAULT_SCHEMA_PATH)
        if errors:
            return errors
        assert schema is not None
    return validate_schema_subset(handoff, schema)


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError:
        return None


def write_validation_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an AgriGuard guarded-launch handoff JSON artifact.")
    parser.add_argument("handoff_json", type=Path)
    parser.add_argument("--schema-json", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    schema, schema_errors = read_json(args.schema_json)
    handoff, handoff_errors = read_json(args.handoff_json)
    errors = schema_errors + handoff_errors
    if schema is not None and handoff is not None:
        errors.extend(validate_handoff(handoff, schema))

    result = {
        "validation_report_schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "handoff_json": str(args.handoff_json),
        "handoff_sha256": sha256_file(args.handoff_json),
        "schema_json": str(args.schema_json),
        "schema_sha256": sha256_file(args.schema_json),
        "status": "fail" if errors else "pass",
        "errors": errors,
    }
    if args.json_out is not None:
        write_validation_result(args.json_out, result)

    if errors:
        print("AgriGuard guarded-launch handoff validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return VALIDATION_FAILURE_EXIT_CODE
    print(f"AgriGuard guarded-launch handoff valid: {args.handoff_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
