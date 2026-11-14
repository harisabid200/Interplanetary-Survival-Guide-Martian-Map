"""Run real-data comparisons: python -m backend.cli --start LON LAT --end LON LAT."""
import argparse
import json
import sys
from pathlib import Path

from .routing import DEFAULT_REGION, RoutingError, TerrainGrid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=float,nargs=2,required=True,metavar=('LON','LAT'))
    parser.add_argument('--end',type=float,nargs=2,required=True,metavar=('LON','LAT'))
    parser.add_argument('--terrain-weight',type=float,default=100.)
    parser.add_argument('--max-cell-slope-deg',type=float)
    parser.add_argument('--region',type=Path,default=DEFAULT_REGION)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        result=TerrainGrid.load(args.region).compare(args.start,args.end,args.terrain_weight,args.max_cell_slope_deg)
    except RoutingError as error:
        print(json.dumps(dict(status='invalid_request',code=error.code,message=str(error))),file=sys.stderr)
        return 2
    except (OSError,KeyError,json.JSONDecodeError) as error:
        print(json.dumps(dict(status='data_unavailable',message='Run and verify the M1 preprocessing pipeline first.',detail=str(error))),file=sys.stderr)
        return 2
    serialized=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:
        try:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            # Exclusive creation protects existing results and all source files.
            with args.output.open('x',encoding='utf-8') as stream:
                stream.write(serialized)
        except OSError as error:
            print(json.dumps(dict(status='output_error',message='Output could not be created; existing files are never overwritten.',detail=str(error))),file=sys.stderr)
            return 2
        print(f'Wrote {args.output}',file=sys.stderr)
    else:
        print(serialized,end='')
    return 0


if __name__=='__main__':
    sys.exit(main())
