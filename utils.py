import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

DATE_RANGE_RE = re.compile(
    r"^\s*с\s*(\d{2}\.\d{2}\.\d{4})\s*по\s*(\d{2}\.\d{2}\.\d{4})\s*$",
    re.IGNORECASE
)

def user_hash(user_id: int) -> str:
    return hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()[:16]

def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def parse_number_token(token: str) -> Optional[float]:
    """
    Поддерживает:
      - "12000"
      - "12к", "12k" -> 12000
      - "12.5к" -> 12500
      - "12 000" (если пробелы будут убраны до токенизации)
    """
    t = token.strip().lower().replace(" ", "")
    if not t:
        return None

    mult = 1.0
    if t.endswith(("к", "k")):
        mult = 1000.0
        t = t[:-1]

    # заменяем запятую на точку
    t = t.replace(",", ".")

    if not re.fullmatch(r"\d+(\.\d+)?", t):
        return None

    try:
        return float(t) * mult
    except ValueError:
        return None

def parse_one_or_two_numbers(text: str) -> Optional[Tuple[float, Optional[float]]]:
    """
    Возвращает (a, b?) где b может быть None.
    Понимает ввод: "900 45000" / "12000" / "12к"
    """
    raw = text.strip()
    if not raw:
        return None

    # выделяем токены, включая "12к"
    tokens = re.findall(r"[\d\.,]+[кk]?", raw.lower())
    if not tokens:
        return None

    nums = []
    for tok in tokens[:2]:
        v = parse_number_token(tok)
        if v is None:
            return None
        nums.append(v)

    if len(nums) == 1:
        return (nums[0], None)
    return (nums[0], nums[1])

def clamp_reasonable_kwh(kwh: float) -> Tuple[float, Optional[str]]:
    if kwh <= 0:
        return kwh, "Значение должно быть больше 0."
    if kwh > 20000:
        return kwh, "Это очень много для бытового периода. Проверьте, что вводите именно кВт*ч."
    return kwh, None

def clamp_reasonable_money(money: float) -> Tuple[float, Optional[str]]:
    if money <= 0:
        return money, "Значение должно быть больше 0."
    if money > 1_000_000:
        return money, "Сумма выглядит слишком большой. Проверьте ввод (₸)."
    return money, None

@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime
    days: int

def period_last30(now: Optional[datetime] = None) -> Period:
    now = now or datetime.now()
    end = datetime(now.year, now.month, now.day)  # начало текущего дня
    start = end - timedelta(days=30)
    return Period(start=start, end=end, days=30)

def period_prev30(now: Optional[datetime] = None) -> Period:
    now = now or datetime.now()
    end = datetime(now.year, now.month, now.day) - timedelta(days=30)
    start = end - timedelta(days=30)
    return Period(start=start, end=end, days=30)

def parse_custom_period(text: str) -> Optional[Period]:
    m = DATE_RANGE_RE.match(text)
    if not m:
        return None
    try:
        s = datetime.strptime(m.group(1), "%d.%m.%Y")
        e = datetime.strptime(m.group(2), "%d.%m.%Y") + timedelta(days=1)  # включительно до конца дня
        if e <= s:
            return None
        days = (e - s).days
        return Period(start=s, end=e, days=days)
    except ValueError:
        return None
