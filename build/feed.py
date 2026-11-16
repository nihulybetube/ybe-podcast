#!/usr/bin/env python3
"""Builds feed.xml for every series folder in the site (reads series.json + schedule.json).

Runs both on the home PC (after a sync) and on GitHub (every 30 minutes). It only LISTS an episode
once its release time has passed, and it never changes the feed during Shabbat / chag
(Friday or erev-chag 16:00 -> Saturday or chag 21:00, see shabbat.py).
"""
import datetime as dt
import sys
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
sys.path.insert(0, str(HERE))
import shabbat  # noqa: E402

IL = ZoneInfo("Asia/Jerusalem")


def parse_utc(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def build_feed(series, episodes, now_utc):
    base = series["base_url"].rstrip("/")
    sid = series["id"]
    live = [e for e in episodes if parse_utc(e["release_at"]) <= now_utc]
    live.sort(key=lambda e: e["release_at"], reverse=True)
    out = []
    w = out.append
    w('<?xml version="1.0" encoding="UTF-8"?>')
    w('<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
      'xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">')
    w("<channel>")
    w("<title>%s</title>" % escape(series["title"]))
    w("<link>%s</link>" % escape(series.get("link", base)))
    w('<atom:link href=%s rel="self" type="application/rss+xml"/>' % quoteattr("%s/%s/feed.xml" % (base, sid)))
    w("<description>%s</description>" % escape(series["description"]))
    w("<language>%s</language>" % series.get("language", "he"))
    w("<copyright>%s</copyright>" % escape(series.get("author", "")))
    w("<itunes:author>%s</itunes:author>" % escape(series.get("author", "")))
    w("<itunes:summary>%s</itunes:summary>" % escape(series["description"]))
    w("<itunes:explicit>false</itunes:explicit>")
    w("<itunes:type>episodic</itunes:type>")
    w("<itunes:owner><itunes:name>%s</itunes:name><itunes:email>%s</itunes:email></itunes:owner>"
      % (escape(series.get("owner_name", series.get("author", ""))), escape(series["owner_email"])))
    w("<itunes:image href=%s/>" % quoteattr("%s/%s/cover.jpg" % (base, sid)))
    w("<image><url>%s</url><title>%s</title><link>%s</link></image>"
      % (escape("%s/%s/cover.jpg" % (base, sid)), escape(series["title"]), escape(series.get("link", base))))
    w('<itunes:category text="Religion &amp; Spirituality"><itunes:category text="Judaism"/></itunes:category>')
    for e in live:
        url = "%s/%s/audio/%s" % (base, sid, e["file"])
        pub = format_datetime(parse_utc(e["release_at"]))
        desc = e.get("description", "")
        w("<item>")
        w("<title>%s</title>" % escape(e["title"]))
        w("<description><![CDATA[%s]]></description>" % desc.replace("]]>", "]]]]><![CDATA[>"))
        w("<guid isPermaLink=\"false\">%s</guid>" % escape(e["id"]))
        w("<pubDate>%s</pubDate>" % pub)
        w("<enclosure url=%s length=\"%d\" type=\"audio/mpeg\"/>" % (quoteattr(url), e["size"]))
        w("<itunes:duration>%d</itunes:duration>" % int(e["duration"]))
        if e.get("cover"):
            w("<itunes:image href=%s/>" % quoteattr("%s/%s/%s" % (base, sid, e["cover"])))
        w("<itunes:explicit>false</itunes:explicit>")
        w("<itunes:episodeType>full</itunes:episodeType>")
        w("</item>")
    w("</channel>")
    w("</rss>")
    return "\n".join(out) + "\n", len(live)


def main():
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_il = now_utc.astimezone(IL).replace(tzinfo=None)
    why = shabbat.text(now_il)
    changed = 0
    for sj in sorted(SITE.glob("*/series.json")):
        import json
        d = sj.parent
        series = json.loads(sj.read_text(encoding="utf-8"))
        sched_f = d / "schedule.json"
        episodes = json.loads(sched_f.read_text(encoding="utf-8")) if sched_f.exists() else []
        feed_f = d / "feed.xml"
        if why and feed_f.exists():
            print("%s: %s — הרשימה לא עודכנה." % (series["id"], why))
            continue
        xml, n = build_feed(series, episodes, now_utc)
        old = feed_f.read_text(encoding="utf-8") if feed_f.exists() else None
        if xml != old:
            feed_f.write_text(xml, encoding="utf-8", newline="\n")
            changed += 1
            print("%s: עודכן — %d פרקים ברשימה." % (series["id"], n))
        else:
            print("%s: ללא שינוי (%d פרקים)." % (series["id"], n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
