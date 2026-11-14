"""Label-driven historical MEDA import. No spatial interpolation or forecasts."""
import csv
import hashlib
import math
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def load_environment(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    path=directory/'environment.json'
    if path.stat().st_size>2*1024*1024:
        raise ValueError('Environmental artifact exceeds local API size bound')
    if manifest['path']!='environment.json' or path.stat().st_size!=manifest['bytes'] or digest(path)!=manifest['sha256']:
        raise ValueError('Environmental artifact checksum mismatch')
    data=json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite environment JSON')))
    if data['schema_version']!=1 or data['kind']!='historical_environment_context' or data['spatial_overlays']!=[]:
        raise ValueError('Unsupported environmental contract')
    data['artifact_sha256']=manifest['sha256']
    return data


def digest(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def read_product(label):
    """Validate bytes, PDS checksum, table shape and column order before use."""
    label = Path(label)
    root = ET.parse(label).getroot()
    text = lambda node, key: node.findtext('{*}'+key)
    file = root.find('.//{*}File')
    name = text(file, 'file_name')
    if Path(name).name != name:
        raise ValueError('Product filename must be a basename')
    path = label.parent/name
    if path.stat().st_size != int(text(file, 'file_size')):
        raise ValueError('PDS file size mismatch')
    if digest(path, 'md5') != text(file, 'md5_checksum').lower():
        raise ValueError('PDS MD5 mismatch')
    table = root.find('.//{*}Table_Delimited')
    fields = []
    for f in table.findall('.//{*}Field_Delimited'):
        fields.append(dict(name=text(f, 'name'), unit=text(f, 'unit'),
                           description=' '.join((text(f, 'description') or '').split()),
                           special_constants=[e.text for e in f.findall('.//{*}Special_Constants/*')]))
    with path.open(newline='', encoding='ascii') as stream:
        reader = csv.DictReader(stream)
        # Explicit, product/version-scoped archive inconsistency. Preserve the
        # original name and unit; this uncertainty variable is NOT displayed.
        if (root.findtext('.//{*}logical_identifier') == 'urn:nasa:pds:mars2020_meda:data_derived_env:we__0015___________der_ps__________________p'
                and root.findtext('.//{*}version_id') == '2.0'
                and len(fields)==6 and fields[4]['name']=='PRESSURE UNCERTAINTY'
                and reader.fieldnames==[f['name'] if i!=4 else 'PRESSURE_UNCERTAINTY' for i,f in enumerate(fields)]):
            fields[4]['label_name']=fields[4]['name']
            fields[4]['name']='PRESSURE_UNCERTAINTY'
        if reader.fieldnames != [f['name'] for f in fields]:
            raise ValueError('CSV header differs from PDS label')
        rows = list(reader)
    if len(rows) != int(text(table, 'records')) or any(None in r or None in r.values() for r in rows):
        raise ValueError('PDS record count/shape mismatch')
    meta = dict(product_id=root.findtext('.//{*}logical_identifier'), version=root.findtext('.//{*}version_id'),
                start_utc=root.findtext('.//{*}start_date_time'), stop_utc=root.findtext('.//{*}stop_date_time'),
                sol=int(root.findtext('.//{*}start_sol_number')), records=len(rows),
                label_sha256=digest(label), data_sha256=digest(path), bytes=path.stat().st_size,
                filename=name, fields=fields)
    clocks=[float(row['SCLK']) for row in rows]
    if not all(math.isfinite(v) for v in clocks) or any(b<=a for a,b in zip(clocks,clocks[1:])):
        raise ValueError('Invalid/non-increasing source spacecraft clock')
    steps=Counter(round(b-a,6) for a,b in zip(clocks,clocks[1:]))
    meta['sampling_sclk_seconds']=dict(dominant_step=steps.most_common(1)[0][0],
                                      largest_gap=max(steps),interval_counts=[dict(seconds=k,count=v) for k,v in sorted(steps.items())])
    return meta, rows


def lmst_seconds(value, sol):
    match = re.fullmatch(r'(\d+)M(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)', value)
    if not match or int(match[1]) != sol:
        raise ValueError('Unexpected MEDA sol/LMST')
    h, m, s = int(match[2]), int(match[3]), float(match[4])
    if h >= 24 or m >= 60 or s >= 60:
        raise ValueError('Invalid LMST clock')
    return h*3600+m*60+s


def number(value, field):
    if value.strip() == '' or value in field['special_constants']:
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def summarize(meta, rows, name, unit, quality_field=None):
    field = next(f for f in meta['fields'] if f['name'] == name)
    if field['unit'] != unit:
        raise ValueError(f'Unexpected unit for {name}: {field["unit"]}')
    bins = [[] for _ in range(288)]
    samples, clocks, sclk, rejected = [], [], [], 0
    for row in rows:
        clock = lmst_seconds(row['LMST'], meta['sol'])
        value = number(row[name], field)
        if value is None or (quality_field and row[quality_field] != '1'):
            rejected += 1
            continue
        samples.append(value); clocks.append(clock); sclk.append(float(row['SCLK']))
        bins[int(clock//300)].append(value)
    if not samples:
        raise ValueError(f'No accepted samples: {name}')
    if any(b <= a for a,b in zip(sclk,sclk[1:])) or any(b < a for a,b in zip(clocks,clocks[1:])):
        raise ValueError('Expected increasing observation clocks')
    return dict(field=name, unit=unit, description=field['description'], accepted=len(samples), rejected=rejected,
                minimum=min(samples), maximum=max(samples), sample_mean=math.fsum(samples)/len(samples),
                first_lmst_seconds=clocks[0], last_lmst_seconds=clocks[-1],
                sclk_range=[sclk[0],sclk[-1]], max_accepted_gap_sclk_seconds=max((b-a for a,b in zip(sclk,sclk[1:])), default=0),
                quality=f'{quality_field}=1 only; empty/nonfinite/special constants excluded' if quality_field else
                        'No per-row quality flag in this product label. Empty/nonfinite/special constants excluded; finite does not mean quality-certified.',
                bins=[dict(lmst_start_seconds=i*300, count=len(v), mean=math.fsum(v)/len(v) if v else None,
                           minimum=min(v) if v else None, maximum=max(v) if v else None) for i,v in enumerate(bins)])
