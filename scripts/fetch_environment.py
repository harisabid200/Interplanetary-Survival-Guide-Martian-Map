"""M4 acquisition: source-linked PDS4 MEDA files, certificate verified.

Metadata and raw products are immutable on rerun. The acquisition manifest
records exact URLs, local completion times, bytes and SHA256. No mock data.
"""
import argparse
import hashlib
import json
import re
import shutil
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import certifi

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/environment'
EVIDENCE=ROOT/'evidence/m4'
BASE='https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            self.links.extend(value for key,value in attrs if key=='href' and value)


def download(url,path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        part=path.with_suffix(path.suffix+'.part')
        if part.exists():
            raise FileExistsError(f'Inspect incomplete acquisition before retry: {part}')
        context=ssl.create_default_context(cafile=certifi.where())
        request=urllib.request.Request(url,headers={'User-Agent':'MARSWALK scientific feasibility prototype'})
        with urllib.request.urlopen(request,context=context,timeout=40) as response,part.open('xb') as stream:
            total=0
            while block:=response.read(65536):
                total+=len(block)
                if total>40*1024*1024:
                    raise ValueError('Product exceeds 40 MiB per-file acquisition bound')
                stream.write(block)
        part.rename(path)
    return dict(url=url,path=str(path.relative_to(ROOT)).replace('\\','/'),bytes=path.stat().st_size,
                sha256=sha256(path),download_completed_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat())


def download_ranges(url, path):
    """Bound requests for slow archive transfers; verify every HTTP byte range.

    Existing/incomplete assets are never overwritten. Scientific label checksum
    verification remains a separate mandatory preprocessing gate.
    """
    path=Path(path)
    if path.exists():
        return download(url,path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # The official atmos hostname successfully honors bounded transfers here;
    # the pds-atmospheres alias stalled on this network. Keep the source URL.
    transfer_url=url.replace('https://pds-atmospheres.nmsu.edu/','https://atmos.nmsu.edu/')
    part=path.with_suffix(path.suffix+'.resume.part')
    context=ssl.create_default_context(cafile=certifi.where())
    offset=0;total=None;etag=None
    with part.open('xb') as stream:
        # Preserve failed attempts; resume their bytes into a NEW temporary file.
        # Only the final PDS checksum can accept the recovered scientific file.
        previous=[p for p in path.parent.glob(path.name+'*.part') if p!=part]
        if previous:
            prefix=max(previous,key=lambda p:p.stat().st_size)
            if prefix.stat().st_size>40*1024*1024:
                raise ValueError('Partial file exceeds acquisition bound')
            with prefix.open('rb') as source:
                shutil.copyfileobj(source,stream)
            offset=stream.tell()
        while total is None or offset<total:
            stop=offset+262143 if total is None else min(offset+262143,total-1)
            request=urllib.request.Request(transfer_url,headers={'Range':f'bytes={offset}-{stop}', 'User-Agent':'MARSWALK scientific feasibility prototype'})
            with urllib.request.urlopen(request,context=context,timeout=30) as response:
                match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if response.status!=206 or not match:
                    raise ValueError('Archive did not honor bounded byte range')
                begin,end,size=map(int,match.groups())
                if begin!=offset or end!=min(stop,size-1) or size>40*1024*1024 or (total is not None and size!=total):
                    raise ValueError('Inconsistent archive byte range')
                if etag is not None and etag!=response.headers.get('ETag'):
                    raise ValueError('Archive asset changed during transfer')
                etag=response.headers.get('ETag');total=size
                block=response.read(end-begin+2)
                if len(block)!=end-begin+1:
                    raise ValueError('Truncated archive byte range')
                stream.write(block);stream.flush();offset+=len(block)
                print(f'{path.name}: {offset}/{total} bytes',flush=True)
    part.rename(path)
    return dict(download(url,path), transfer_url=transfer_url)


def links(path):
    parser=Links();parser.feed(Path(path).read_text(encoding='utf-8'))
    return parser.links


def fetch_context(rad_science=False):
    """Pinned historical report and Gale-only archive reference, never weather telemetry."""
    rad='https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/'
    sources=[]
    for url,name in [
        ('https://www.msss.com/msss_images/2022/01/26/','marci-2022-01-26.html'),
        (rad+'AAREADME.TXT','rad-readme.txt'),(rad+'ERRATA.TXT','rad-errata.txt'),
        (rad+'DATA/SOL_00000_00089/','rad-early-sols.html')]:
        sources.append(download(url,RAW/name))
    name='RAD_RDR_2012_220_02_25_0001_V00.LBL'
    assert name in links(RAW/'rad-early-sols.html')
    url=rad+'DATA/SOL_00000_00089/'+name
    sources.append(download(url,RAW/'rad-sol-0001.lbl'))
    # File is explicitly referenced by the detached PDS3 label.
    filename=name.replace('.LBL','.TXT')
    assert filename in (RAW/'rad-sol-0001.lbl').read_text(encoding='ascii')
    if rad_science:
        sources.append(download_ranges(url.replace('.LBL','.TXT'),RAW/'rad-sol-0001.txt'))
    (EVIDENCE/'context-acquisition.json').write_text(json.dumps({'sources':sources},indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sol',type=int,default=15)
    parser.add_argument('--metadata-only',action='store_true')
    parser.add_argument('--context-only',action='store_true')
    parser.add_argument('--rad-science',action='store_true',help='Optional Gale raw science download; not used as Jezero radiation')
    args=parser.parse_args()
    if not 0<args.sol<90:
        raise ValueError('M4 pilot acquisition is restricted to source-listed early mission sols 1–89')
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    if args.context_only:
        fetch_context(args.rad_science)
        return
    sources=[]
    index=RAW/'meda-bundle.html'
    sources.append(download(BASE,index))
    sources.append(download(urllib.parse.urljoin(BASE,'readme.txt'),RAW/'meda-readme.txt'))
    # Collection names and sol directories are discovered, not fabricated files.
    for collection,patterns in [('data_calibrated_env/',['CAL_ATS','CAL_PS']),
                                ('data_derived_env/',['DER_PS','DER_WIND','DER_ANC'])]:
        assert collection in links(index),f'Collection not source-listed: {collection}'
        collection_url=urllib.parse.urljoin(BASE,collection)
        collection_file=RAW/(collection.strip('/')+'.html')
        sources.append(download(collection_url,collection_file))
        group='sol_0000_0089/'
        assert group in links(collection_file)
        group_url=urllib.parse.urljoin(collection_url,group)
        group_file=RAW/(collection.strip('/')+'-early-sols.html')
        sources.append(download(group_url,group_file))
        sol=f'sol_{args.sol:04d}/'
        assert sol in links(group_file),f'Sol not source-listed: {sol}'
        sol_url=urllib.parse.urljoin(group_url,sol)
        sol_file=RAW/(collection.strip('/')+f'-sol-{args.sol:04d}.html')
        sources.append(download(sol_url,sol_file))
        products=[name for name in links(sol_file) if name.lower().endswith('.xml') and any(pattern in name.upper() for pattern in patterns)]
        print(collection,products)
        if args.metadata_only:
            continue
        for name in products:
            label_url=urllib.parse.urljoin(sol_url,name)
            path=RAW/f'sol-{args.sol:04d}'/name
            sources.append(download(label_url,path))
            root=ET.parse(path).getroot()
            for filename in root.findall('.//{*}File/{*}file_name'):
                assert Path(filename.text).name==filename.text
                sources.append(download_ranges(urllib.parse.urljoin(sol_url,filename.text),path.parent/filename.text))
    report=dict(status='downloaded; numerical validation pending',sol=args.sol,
                generated_utc=datetime.now(timezone.utc).isoformat(),certificate_verification='Python ssl default validation + certifi CA bundle; no verification bypass',sources=sources)
    (EVIDENCE/f'meda-acquisition-sol-{args.sol:04d}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not args.metadata_only:
        fetch_context(args.rad_science)


if __name__=='__main__':
    main()
