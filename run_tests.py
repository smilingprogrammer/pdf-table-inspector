"""unittest runner with explicit passed/failed/skipped and optional-engine reporting."""
import argparse
import importlib
import json
from pathlib import Path
import unittest


class TestResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.passed_tests=[]

    def addSuccess(self,test):
        self.passed_tests.append(test.id())
        super().addSuccess(test)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--out',type=Path,default=Path('output/tests/summary.json'))
    args=cli.parse_args()
    engines={}
    for name in ('camelot-stream','camelot-lattice'):
        try:
            module=importlib.import_module('camelot')
            engines[name]={'dependency_status':'available','version':module.__version__}
        except ImportError as exc:
            engines[name]={'dependency_status':'unavailable','reason':str(exc)}
    result=unittest.TextTestRunner(verbosity=2,resultclass=TestResult).run(unittest.defaultTestLoader.discover('.',pattern='test_*.py'))
    summary={'tests_run':result.testsRun,
             'passed':len(result.passed_tests),'passed_tests':result.passed_tests,
             'failures':[{'test':str(t),'traceback':detail} for t,detail in result.failures],
             'errors':[{'test':str(t),'traceback':detail} for t,detail in result.errors],
             'skipped':[{'test':str(t),'reason':reason} for t,reason in result.skipped],
             'optional_engines':engines,
             'note':'Dependency availability is not a test pass; skipped optional tests are excluded from passed.'}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(summary,indent=2)+'\n')
    print(f"Passed: {summary['passed']}; failures: {len(result.failures)}; errors: {len(result.errors)}; skipped: {len(result.skipped)}")
    for name,status in engines.items(): print(name,status['dependency_status'])
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__': raise SystemExit(main())
