"""Write coordinator receipts; component implementations own their own receipts."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import Receipt

parser=argparse.ArgumentParser(description=__doc__)
for name in ['run','stage','started','code','input_path','output_path']:
    parser.add_argument(name)
parser.add_argument('failures',nargs='*')
parser.add_argument('--resumed-from')
parser.add_argument('--reason')
args=parser.parse_args()
if bool(args.resumed_from)!=bool(args.reason):
    parser.error('resume receipts require both --resumed-from and --reason')
run,stage,started,code,input_path,output_path=(getattr(args,name) for name in ['run','stage','started','code','input_path','output_path'])
receipt = Receipt(run,stage,['bash','python3'])
receipt.started = started
if args.resumed_from:
    receipt.details.update(resumed_from=args.resumed_from,reason=args.reason)
for name,path in [('input_count',input_path),('output_count',output_path)]:
    count = sum(1 for line in Path(path).read_text().splitlines() if line.strip()) if path != '-' and Path(path).is_file() else None
    setattr(receipt,name,count)
receipt.errors = [{'stage':stage_name,'message':'stage returned exit '+exit_code} for stage_name,exit_code in (value.split('=',1) for value in args.failures)]
receipt.finish(int(code))
