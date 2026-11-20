"""Payload-free diagnostic projection; no network, subprocess or mutation."""
import re
PREFIX='catalog configuration diagnostic '
ROW=re.compile(r'catalog configuration diagnostic scope_hash=([0-9a-f]{16}) provider=(bankone|banktwo|aggregate|unknown) stage=(provider_configuration|provider_resolution|provider_projection|row_persistence|coverage_persistence) outcome=(unconfigured|failed|incomplete|not_persisted) error_type=([A-Za-z_][A-Za-z0-9_]{0,63}) row_count=(-?[0-9]{1,10})\Z')
ERRORS={'none','OtherError','TimeoutError','ConnectionError','OSError','ValueError','TypeError','KeyError','SourceConnectorError','S3Error','OperationalError','InterfaceError','IntegrityError','ReadOnlySqlTransaction','InsufficientPrivilege','UndefinedTable','UndefinedColumn','_ConfigurationHydrationStopped'}

def safe_diagnostics(raw,scope_hash):
    if not isinstance(raw,bytes) or len(raw)>524288:raise ValueError('diagnostic_output_limit')
    try:text=raw.decode('utf-8',errors='strict')
    except UnicodeError:raise ValueError('diagnostic_encoding_unknown') from None
    events=[];rejected=0
    for line in text.splitlines():
        framed=re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{1,9}Z (.*)',line)
        if not framed:
            if PREFIX in line:rejected+=1
            continue
        message=framed[1]
        if message.startswith('WARNING:autodata_ingestion.catalog_service:'):
            message=message[len('WARNING:autodata_ingestion.catalog_service:'):]
        if not message.startswith(PREFIX):continue
        row=ROW.fullmatch(message) if len(message)<=1024 else None
        if not row:rejected+=1;continue
        scope,provider,stage,outcome,error,count=row.groups()
        if scope!=scope_hash:continue
        count=int(count)
        if error not in ERRORS or not -1<=count<=1000000000:rejected+=1;continue
        events.append({'scope_hash':scope,'provider':provider,'stage':stage,'outcome':outcome,'error_type':error,'row_count':count})
    return {'events':events,'rejected_rows':rejected,'correlation':'scope-only diagnostics; budget attempt proof is separate'}
