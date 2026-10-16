"""Shared JSON I/O and receipts, without collection or storage logic."""
import datetime as dt
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

class StageFailure(RuntimeError):
    """A safe, actionable operational error that may be written to a receipt."""
    pass

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')

def read_json(path):
    return json.loads(Path(path).read_text())

def read_lines(stream):
    for number, line in enumerate(stream, 1):
        if line.strip():
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('record must be an object')
                yield row
            except (ValueError, TypeError) as error:
                raise ValueError('malformed JSONL at line %d' % number) from error

def emit(row):
    print(json.dumps(row, ensure_ascii=False), flush=True)

class Receipt:
    def __init__(self, run_dir, stage, tools=None):
        self.run_dir = Path(run_dir) if run_dir else None
        self.stage = stage
        self.started = now()
        self.input_count = 0
        self.output_count = 0
        self.errors = []
        self.tools = tools or ['python3']
        self.models = []
        self.cost = 0.0  # Measured: no paid calls unless explicitly added.
        self.details = {}

    def finish(self, code=0):
        if self.run_dir:
            logs = self.run_dir / 'logs'
            logs.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            row = dict(stage=self.stage, status='completed' if code == 0 else 'failed',
                       exit_code=code, input_count=self.input_count, output_count=self.output_count,
                       started_at=self.started, finished_at=now(), tools=self.tools,
                       models=self.models, cost_usd=self.cost,
                       cost_is_estimate=bool(self.models), errors=self.errors, **self.details)
            (logs / ('%s-%s-%s.json' % (self.stage, stamp, os.getpid()))).write_text(json.dumps(row, indent=2)+'\n')

def stage_main(stage, function, tools=None):
    run_dir = sys.argv[1] if len(sys.argv) == 2 else os.environ.get('RUN_DIR')
    receipt = Receipt(run_dir, stage, tools)
    code = 0
    try:
        if len(sys.argv) != 2 or not Path(run_dir, 'run.json').is_file():
            raise ValueError('usage: stage RUN_DIR (containing run.json)')
        os.environ['RUN_DIR'] = str(run_dir)
        code = function(Path(run_dir), receipt) or 0
    except StageFailure as error:
        receipt.errors.append({'message':str(error)})
        code = 1
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        receipt.errors.append({'message': str(error)})
        code = 2
    except Exception as error:
        # Never include request headers, response bodies, or environment values.
        receipt.errors.append({'message': type(error).__name__})
        code = 1
    for error in receipt.errors:
        print(stage + ': ' + error.get('message', 'failed'), file=sys.stderr)
    receipt.finish(code)
    sys.exit(code)
