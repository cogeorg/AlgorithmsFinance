"""Render the local dashboard after measurement; save visual and DOM checks."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess

GROUP=Path(__file__).resolve().parent
ROOT=GROUP.parent.parent
chrome=Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
profile=GROUP/"_chrome_verify"
assert not profile.exists()
assert profile.resolve().parent==GROUP.resolve()
shot=GROUP/"dashboard.png"
dom=GROUP/"_dashboard_dom.html"
with dom.open("wb") as output,(GROUP/"dashboard_browser.log").open("wb") as error:
    process=subprocess.run([str(chrome),"--headless=new","--disable-gpu","--no-first-run",
        "--no-default-browser-check","--disable-background-networking","--disable-extensions",
        "--hide-scrollbars","--user-data-dir="+str(profile),"--screenshot="+str(shot),
        "--window-size=1440,1100","--virtual-time-budget=1500","--dump-dom",
        (ROOT/"dashboard.html").as_uri()],stdout=output,stderr=error,timeout=45)
assert process.returncode==0,process.returncode
assert shot.is_file() and shot.stat().st_size>10000

class DashboardDOM(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_body=False
        self.rows=0
        self.current=None
        self.cards={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="tbody" and attrs.get("id")=="body":self.in_body=True
        if self.in_body and tag=="tr":self.rows+=1
        if tag=="b" and attrs.get("id") in ("complete","stopped","missing","pairs"):
            self.current=attrs["id"]
    def handle_endtag(self,tag):
        if tag=="tbody":self.in_body=False
        if tag=="b":self.current=None
    def handle_data(self,data):
        if self.current:self.cards[self.current]=data.strip()

parser=DashboardDOM()
parser.feed(dom.read_text(encoding="utf-8"))
assert parser.rows==15,parser.rows
assert parser.cards==dict(complete="8",stopped="12",missing="10",pairs="1"),parser.cards
result=dict(status="passed",rendered_rows=parser.rows,cards=parser.cards,
            screenshot=str(shot),browser=str(chrome),
            scope="Local default 100000-event view; no measurement run or network service")
(GROUP/"dashboard_check.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result))

