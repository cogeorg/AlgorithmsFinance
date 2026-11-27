"""Run the existing Hypothesis test with explicit near-tie exception logging."""
import json
import sys
from pathlib import Path


def main():
    root=Path.cwd()
    sys.path[:0]=[str(root/'01_code'),str(root/'02_tests')]
    import test_differential as test
    original=test.compare
    records=[]; count=0
    def report(a,b,K):
        nonlocal count
        count+=1
        exceptions=original(a,b,K)
        if exceptions:
            records.append(dict(N=len(a.boundary)-1,K=K,A_value=a.value,B_value=b.value,boundary_exceptions=exceptions))
        return exceptions
    test.compare=report
    test.test_hypothesis_A_B()
    result=dict(cases=count,cases_with_near_tie_boundary_exceptions=records)
    (root/'00_docs/HYPOTHESIS_BOUNDARY_REPORT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f'HYPOTHESIS BOUNDARY REPORT: PASS ({count} cases, {len(records)} cases with permitted near-tie boundary exceptions)')


if __name__=='__main__':
    main()
