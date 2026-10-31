"""Bounded built-in detectors; no user-supplied regular expressions."""
import re
from datetime import date

EMAIL = re.compile(r"(?<![\w.!#$%&'*+/=?^\x60{|}~@-])[A-Za-z0-9!#$%&'*+/=?^_\x60{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_\x60{|}~-]+)*@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?![\w@-])")
PESEL = re.compile(r'(?<!\w)[0-9]{11}(?!\w)')


def valid_pesel(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{11}', value):
        return False
    digits = [int(c) for c in value]
    year, month, day = int(value[:2]), int(value[2:4]), int(value[4:6])
    centuries = {0: 1900, 1: 2000, 2: 2100, 3: 2200, 4: 1800}
    century = centuries.get(month // 20)
    if century is None:
        return False
    try:
        date(century + year, month % 20, day)
    except ValueError:
        return False
    return (10 - sum(d * w for d, w in zip(digits[:10], [1, 3, 7, 9, 1, 3, 7, 9, 1, 3])) % 10) % 10 == digits[10]


def matches(rule, text):
    kind = rule.get('type', 'contains')
    if not rule.get('enabled', 1):
        return False
    if kind == 'email':
        return EMAIL.search(text) is not None
    if kind == 'pesel':
        return any(valid_pesel(m.group()) for m in PESEL.finditer(text))
    return rule['contains'].casefold() in text.casefold()


def validate_rule(data):
    name = data.get('name')
    kind = data.get('type', 'contains')
    contains = data.get('contains', '')
    severity = data.get('severity')
    enabled = data.get('enabled', True)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Invalid rule name')
    if kind not in ('contains', 'email', 'pesel'):
        raise ValueError('Invalid rule type')
    if not isinstance(contains, str) or len(contains) > 500 or (kind == 'contains' and not contains.strip()):
        raise ValueError('Invalid rule text')
    if severity not in ('info', 'warning', 'critical') or type(enabled) not in (bool, int) or enabled not in (0, 1):
        raise ValueError('Invalid severity or enabled state')
    return dict(name=name.strip(), type=kind, contains=contains.strip() if kind == 'contains' else '',
                severity=severity, enabled=int(enabled))
