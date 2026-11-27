"""Build a standalone dashboard from saved results; never runs experiments."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    data = {}
    for name in ['environment', 'summary', 'correctness']:
        data[name] = json.loads((ROOT/'results'/f'{name}.json').read_text(encoding='utf-8'))
    data['raw'] = [json.loads(s) for s in (ROOT/'results/raw.jsonl').read_text(encoding='utf-8').splitlines()]
    data['tests'] = (ROOT/'results/tests_final.txt').read_text(encoding='utf-8')
    template = (ROOT/'dashboard_template.html').read_text(encoding='utf-8')
    html = template.replace('__SAVED_DATA__',json.dumps(data).replace('</','<\\/'))
    (ROOT/'dashboard.html').write_text(html,encoding='utf-8')
    print('Wrote dashboard.html from saved results (no experiments executed).')


if __name__=='__main__':
    main()
