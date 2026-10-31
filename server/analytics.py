"""Shared filtering and alert aggregations for logs and charts."""
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

RANGES = {'1h': 1, '24h': 24, '7d': 168, '30d': 720}
LEVELS = ('info', 'warning', 'critical')


def filtered_events(db, query, limit=None):
    conditions, values = [], []
    def value(key): return query.get(key, [''])[0]
    endpoint = value('endpoint_id')
    if endpoint == 'legacy':
        conditions.append('v.endpoint_id IS NULL')
    elif endpoint:
        conditions.append('v.endpoint_id=?'); values.append(endpoint)
    if value('group'):
        conditions.append("COALESCE(e.group_name,'')=?"); values.append('' if value('group') == '__none__' else value('group'))
    if value('provider'):
        if value('provider') not in ('chatgpt','claude','gemini'):
            raise ValueError('Invalid provider')
        conditions.append('v.provider=?'); values.append(value('provider'))
    if value('q'):
        conditions.append('instr(casefold(v.prompt),?)>0'); values.append(value('q').casefold())
    if value('severity'):
        if value('severity') not in LEVELS:
            raise ValueError('Invalid severity')
        conditions.append("EXISTS (SELECT 1 FROM json_each(v.matches) m WHERE json_extract(m.value,'$.severity')=?)")
        values.append(value('severity'))
    if value('alerts') == '1':
        conditions.append("v.matches!='[]'")
    if value('action'):
        if value('action') not in ('observed','allowed','blocked'):
            raise ValueError('Invalid action')
        conditions.append('v.action=?'); values.append(value('action'))
    period = value('range') or 'all'
    if period != 'all':
        if period not in RANGES:
            raise ValueError('Invalid time range')
        since = datetime.now(timezone.utc) - timedelta(hours=RANGES[period])
        conditions.append('v.received_at>=?'); values.append(since.isoformat())
    sql = ('SELECT v.*,e.name AS endpoint_name,e.group_name AS endpoint_group FROM events v '
           'LEFT JOIN endpoints e ON e.id=v.endpoint_id')
    if conditions: sql += ' WHERE ' + ' AND '.join(conditions)
    sql += ' ORDER BY v.received_at DESC'
    if limit is not None:
        sql += ' LIMIT ?'; values.append(limit)
    result = []
    for row in db.execute(sql, values):
        event = dict(row); event['matches'] = json.loads(event['matches']); result.append(event)
    return result


def summarize(events, period='24h'):
    now = datetime.now(timezone.utc)
    hours = RANGES.get(period)
    if hours is None:
        stamps = [datetime.fromisoformat(e['received_at']).astimezone(timezone.utc) for e in events]
        start = min(stamps, default=now - timedelta(hours=24))
        hours = max(24, (now-start).total_seconds()/3600)
        start = now - timedelta(hours=hours)
    else:
        start = now - timedelta(hours=hours)
    count = 24 if hours <= 24 else 28 if hours <= 168 else 30
    step = timedelta(hours=hours/count)
    buckets = [{'at':(start+i*step).isoformat(),'events':0,'alerts':0,**{k:0 for k in LEVELS}} for i in range(count)]
    severity, providers, groups, rules = Counter(), Counter(), Counter(), Counter()
    flagged = 0
    for event in events:
        providers[event['provider']] += 1
        groups[event['endpoint_group'] or 'Bez grupy'] += 1
        matches = event['matches']
        highest = max((m['severity'] for m in matches),key=LEVELS.index,default=None)
        if highest:
            flagged += 1; severity[highest] += 1
            rules.update(m['name'] for m in matches)
        stamp = datetime.fromisoformat(event['received_at'])
        if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
        index = max(0,min(count-1,int((stamp-start)/step)))
        buckets[index]['events'] += 1
        if highest:
            buckets[index]['alerts'] += 1; buckets[index][highest] += 1
    return {'blocked':sum(e.get('action')=='blocked' for e in events),'total':len(events),'alerts':flagged,'critical':severity['critical'],
            'endpoints':len({e['endpoint_id'] for e in events if e['endpoint_id']}),
            'severity':{k:severity[k] for k in LEVELS},'providers':dict(providers),
            'groups':dict(groups),'top_rules':[{'name':k,'count':v} for k,v in rules.most_common(6)],
            'buckets':buckets,'generated_at':now.isoformat()}
