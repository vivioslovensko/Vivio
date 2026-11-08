#!/usr/bin/env python3
"""Stiahne podujatia z ajdnes.sk na jeden týždeň (po – ne) aj s detailmi.

Použitie:
    python3 -I tools/ajdnes_fetch.py 2026-11-16 /cesta/k/vystup

Do výstupného priečinka uloží stiahnuté HTML (days/, ev/) a súbor
events.json so zoznamom podujatí: id, url, title, city, place, date,
end, time, ajdnes_cat, price, desc. Dátumy sú vo formáte YYYY-MM-DD.
Na sťahovanie používa curl (rešpektuje proxy prostredia).
"""
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys

BASE = "https://www.ajdnes.sk"


def get(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    subprocess.run(["curl", "-sS", "--fail", "--max-time", "30", "-o", path, url], check=True)


def to_iso(s):
    m = re.match(r"(\d\d)\.(\d\d)\.(\d{4})", s or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def parse_detail(path, eid, year):
    t = open(path, encoding="utf-8", errors="ignore").read()
    url = re.search(r'var uriToShare = "([^"]+)"', t)
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", t, flags=re.S)
    i = t.find("<h1")
    toks = [html.unescape(x).strip() for x in re.split(r"<[^>]+>", t[i:i + 20000])]
    toks = [x for x in toks if x and not x.startswith("(adsbygoogle")]
    o = {"id": eid, "url": url.group(1).replace("\\/", "/") if url else f"{BASE}/podujatie/{eid}",
         "title": toks[0] if toks else ""}
    hdr = []
    if "KATEGÓRIA:" in toks:
        k = toks.index("KATEGÓRIA:")
        o["ajdnes_cat"] = toks[k + 1] if k + 1 < len(toks) else ""
        hdr = toks[1:k]
    # hlavička: MES, deň, [MES, deň,] mesto, [miesto]
    months = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MÁJ": 5, "JÚN": 6, "JÚL": 7,
              "AUG": 8, "SEP": 9, "OKT": 10, "NOV": 11, "DEC": 12}
    dates, rest, mon = [], [], None
    for x in hdr:
        if x in months:
            mon = months[x]
        elif re.fullmatch(r"\d{1,2}", x) and mon:
            dates.append(dt.date(year, mon, int(x)))
        else:
            rest.append(x)
    o["city"] = rest[0] if rest else ""
    o["place"] = rest[1].rstrip(", ") if len(rest) > 1 else ""
    joined = " ¦ ".join(toks)

    def field(label):
        m = re.search(label + r":?\s*¦?\s*([^¦]+)", joined)
        return m.group(1).strip() if m else ""

    o["date"] = to_iso(field("Začiatok podujatia")) or (dates[0].isoformat() if dates else "")
    end = to_iso(field("Koniec podujatia")) or (dates[1].isoformat() if len(dates) > 1 else "")
    if end and end != o["date"]:
        o["end"] = end
    tm = re.match(r"(\d{1,2}):(\d\d)", field("Čas začiatku"))
    o["time"] = f"{int(tm.group(1))}:{tm.group(2)}" if tm else ""
    o["price"] = field("Vstupné")
    cands = [x for x in toks if len(x) > 80 and "{" not in x]
    o["desc"] = re.sub(r"\s+", " ", max(cands, key=len))[:900] if cands else ""
    return o


def main():
    start = dt.date.fromisoformat(sys.argv[1])
    out = sys.argv[2]
    os.makedirs(f"{out}/days", exist_ok=True)
    os.makedirs(f"{out}/ev", exist_ok=True)
    ids = []
    for i in range(7):
        d = (start + dt.timedelta(days=i)).isoformat()
        p = f"{out}/days/{d}.html"
        get(f"{BASE}/podujatia-ajax/{d},0/0/0?single_day=1", p)
        for eid in re.findall(r'data-eid="(\d+)"', open(p, encoding="utf-8", errors="ignore").read()):
            if eid not in ids:
                ids.append(eid)
    events = []
    for eid in ids:
        p = f"{out}/ev/{eid}.html"
        try:
            get(f"{BASE}/podujatie/{eid}", p)
            events.append(parse_detail(p, eid, start.year))
        except Exception as e:  # jedno zlé podujatie nezastaví celý beh
            print(f"preskakujem {eid}: {e}", file=sys.stderr)
    with open(f"{out}/events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)
    print(f"{len(events)} podujatí -> {out}/events.json")


if __name__ == "__main__":
    main()
