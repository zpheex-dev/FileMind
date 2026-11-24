"""Ordered folder-profile rules. Empty conditions match every file."""
from fnmatch import fnmatchcase
import re


def validate_folder(name):
    if (not name or name.startswith(".") or name.rstrip(" .") != name
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or re.fullmatch(r"(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|(?:COM|LPT)[1-9¹²³])",
                            name.split(".")[0].rstrip(" "), re.IGNORECASE)):
        raise ValueError("Use a visible name valid on both Windows and Linux.")


RULE_FIELDS = ("name", "extension", "pattern", "age_days", "size_bytes", "source", "destination")


def validate_destination(template):
    for part in template.replace("<year>", "2000").split("/"):
        validate_folder(part)


def validate_rule(rule):
    if not isinstance(rule, dict) or any(not isinstance(value, str) for value in rule.values()):
        raise ValueError("Invalid folder rule")
    if not rule.get("name") or not rule.get("destination"):
        raise ValueError("Each rule needs a name and destination.")
    validate_destination(rule["destination"])
    for key in ("age_days", "size_bytes"):
        if rule.get(key) and (not rule[key].isascii() or not rule[key].isdecimal()):
            raise ValueError("Minimum age and size must be nonnegative whole numbers.")


def rule_matches(rule, metadata, relative_parent, now):
    return (
        (not rule.get("extension") or metadata.extension.casefold().lstrip(".") ==
         rule["extension"].casefold().lstrip("."))
        and fnmatchcase(metadata.name.casefold(), (rule.get("pattern") or "*").casefold())
        and fnmatchcase(relative_parent.casefold(), (rule.get("source") or "*").casefold())
        and (not rule.get("age_days") or metadata.modified_at is not None
             and (now - metadata.modified_at).days >= int(rule["age_days"]))
        and (not rule.get("size_bytes") or metadata.size_bytes is not None
             and metadata.size_bytes >= int(rule["size_bytes"]))
    )
