"""Shabbat / Yom-Tov block (no internet, no extra libraries: the Hebrew calendar is computed here).

Fixed clock times, as he decided (NOT candle-lighting times):
  Friday (or erev chag) from 16:00  ->  Saturday (or the chag's last day) until 21:00.
Blocked days: every Saturday + the Israeli Yom-Tov days: Rosh Hashana (1-2 Tishrei), Yom Kippur (10 Tishrei),
Sukkot (15 Tishrei), Shemini Atzeret/Simchat Torah (22 Tishrei), Pesach 1 (15 Nisan), Pesach 7 (21 Nisan), Shavuot (6 Sivan).
Chol hamoed and Chanukah are NOT blocked. A Shabbat next to a chag joins into one continuous range.
Podcast addition (user, 2026-11-24): Purim (14 Adar) and its eve (13 Adar) are blocked for the WHOLE calendar day
(00:00-24:00). Shushan Purim and everything else stay as above.
"""
import datetime as dt
import os

START_HOUR = 16     # on the day before the block day
END_HOUR = 21       # at the end of the block day

_RD_EPOCH = -1373427   # fixed day number (= date.toordinal()) of the Hebrew epoch


def _delay1(y):
    months = (235 * y - 234) // 19
    parts = 12084 + 13753 * months
    day = months * 29 + parts // 25920
    if (3 * (day + 1)) % 7 < 3:
        day += 1
    return day


def _delay2(y):
    last, present, nxt = _delay1(y - 1), _delay1(y), _delay1(y + 1)
    if nxt - present == 356:
        return 2
    if present - last == 382:
        return 1
    return 0


def new_year(y):
    """Gregorian date of 1 Tishrei of Hebrew year y."""
    return dt.date.fromordinal(_RD_EPOCH + _delay1(y) + _delay2(y))


_cache = {}


def _holidays(y):
    """{date: name} of the blocked Yom-Tov days that fall in Hebrew year y (Tishrei..Elul)."""
    if y in _cache:
        return _cache[y]
    ny = new_year(y)
    d = lambda n: ny + dt.timedelta(days=n)
    pesach = new_year(y + 1) - dt.timedelta(days=163)      # 15 Nisan is always 163 days before the next 1 Tishrei
    m = {
        d(0): "ראש השנה", d(1): "ראש השנה", d(9): "יום כיפור", d(14): "סוכות",
        d(21): "שמיני עצרת / שמחת תורה",
        pesach: "פסח (יום ראשון)", pesach + dt.timedelta(days=6): "שביעי של פסח",
        pesach + dt.timedelta(days=50): "שבועות",
        # Purim (14 Adar / Adar II) is exactly 30 days before 15 Nisan; its eve (13 Adar) one day earlier.
        # Podcast rule (user, 2026-11-24): both are blocked for the WHOLE calendar day (00:00-24:00), not from 16:00 the day before.
        pesach - dt.timedelta(days=30): "פורים", pesach - dt.timedelta(days=31): "ערב פורים",
    }
    _cache[y] = m
    return m


def block_name(day):
    """Name of the reason this DATE is a block day (Shabbat / a chag), or None."""
    hol = {}
    for y in (day.year + 3760, day.year + 3761):
        hol.update(_holidays(y))
    if day in hol:
        return hol[day]
    return "שבת" if day.weekday() == 5 else None


FULL_DAY = ("פורים", "ערב פורים")      # blocked 00:00-24:00 of that day; everything else: 16:00 the day before -> 21:00


def _interval(day):
    if block_name(day) in FULL_DAY:
        return (dt.datetime.combine(day, dt.time(0)), dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0)))
    return (dt.datetime.combine(day - dt.timedelta(days=1), dt.time(START_HOUR)),
            dt.datetime.combine(day, dt.time(END_HOUR)))


def now():
    f = os.environ.get("COLLAB_FAKE_NOW")      # for tests only: 'YYYY-MM-DD HH:MM'
    return dt.datetime.strptime(f, "%Y-%m-%d %H:%M") if f else dt.datetime.now()


def blocked(at=None):
    """None if allowed, else (until_datetime, reason_text). Contiguous ranges are merged."""
    at = at or now()
    names, end = [], None
    for k in (0, 1):                       # the block day is today or tomorrow (the evening before)
        # (a full-day block like Purim is found with k=0; its interval is checked below)
        day = at.date() + dt.timedelta(days=k)
        n = block_name(day)
        if n:
            a, b = _interval(day)
            if a <= at < b:
                end = max(end, b) if end else b
                names.append(n)
    if not end:
        return None
    # extend through adjacent block days (Shabbat after a chag, chag after Shabbat, 2-day chag)
    while True:
        grown = False
        for day in (end.date(), end.date() + dt.timedelta(days=1)):
            n = block_name(day)
            if not n:
                continue
            a, b = _interval(day)
            if a <= end < b:               # that range already started before this one ended
                end = b
                names.append(n)
                grown = True
                break
        if not grown:
            break
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    return end, " + ".join(seen)


def text(at=None):
    """Hebrew one-liner for logs/panel, or '' when allowed."""
    r = blocked(at)
    if not r:
        return ""
    end, why = r
    days = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    return "שבת/חג (%s). חסום עד יום %s %s ב-%s" % (why, days[end.weekday()], end.strftime("%d/%m"), end.strftime("%H:%M"))


def next_allowed_run(hhmm, after=None):
    """The next datetime >= `after` at clock time hhmm (daily task) that is NOT blocked."""
    after = after or now()
    h, mi = [int(x) for x in hhmm.split(":")]
    d = after.date()
    for _ in range(40):
        t = dt.datetime.combine(d, dt.time(h, mi))
        if t >= after and not blocked(t):
            return t
        d += dt.timedelta(days=1)
    return None
