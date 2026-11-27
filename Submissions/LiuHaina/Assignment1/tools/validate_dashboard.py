"""Check generated dashboard against source data and current browser evidence."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.external=[]
        self.in_data=False
        self.data=[]

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        for key in ("src","href"):
            if attrs.get(key,"").startswith(("http:","https:","//")):
                self.external.append(attrs[key])
        if tag=="script" and attrs.get("id")=="saved-data":
            self.in_data=True

    def handle_endtag(self,tag):
        if tag=="script":
            self.in_data=False

    def handle_data(self,text):
        if self.in_data:
            self.data.append(text)


def main():
    html=(ROOT/"dashboard.html").read_text()
    page=Document()
    page.feed(html)
    assert len(page.ids)==len(set(page.ids)),"duplicate document IDs"
    assert not page.external,"dashboard requires external resources"
    embedded=json.loads("".join(page.data))
    folder=ROOT/"results/benchmark"
    rows=[json.loads(s) for s in (folder/"raw_results.jsonl").read_text().splitlines()]
    assert embedded["raw"]==rows,"raw data changed during embedding"
    assert embedded["summary"]==json.loads((folder/"summary.json").read_text()),"summary mismatch"
    assert embedded["validation"]==json.loads((folder/"validation.json").read_text()),"validation mismatch"
    total=0
    for row in rows:
        if row["phase"]=="latency" and row.get("raw_file"):
            hist=embedded["histograms"][row["job_id"]]
            assert sum(hist["counts"])==hist["samples"]==row["samples"]
            total+=hist["samples"]
    assert total==embedded["validation"]["latency_samples"]
    script=(ROOT/"dashboard/app.js").read_text()
    assert script in html and (ROOT/"dashboard/style.css").read_text() in html,"stale built asset"
    assert not re.search(r"\b(fetch|XMLHttpRequest|WebSocket)\s*\(",script),"unexpected browser network API"
    assert set(re.findall(r'\$\("([^"\n]+)"\)',script))<=set(page.ids),"missing referenced control"
    for name,expected in embedded["settings"]["code_sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,f"measured source changed: {name}"
    qa=json.loads((ROOT/"evidence/dashboard_browser_qa.json").read_text())
    assert qa["status"]=="passed" and qa["dashboard_sha256"]==hashlib.sha256(html.encode()).hexdigest(),"browser QA is stale"
    assert qa["unit_labels_preserve_case"],"case-sensitive time/memory units were transformed"
    result=dict(status="passed",raw_records=len(rows),latency_samples=total,
        histogram_series=len(embedded["histograms"]),all_raw_and_summary_data_identical=True,
        measured_source_hashes_unchanged=True,no_external_assets_or_requests=True,
        current_browser_qa_matches_html=True,duplicate_ids=False)
    (ROOT/"evidence/dashboard_data_validation.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()
