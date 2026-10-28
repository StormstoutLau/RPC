import sys, re, json

# O-21 (2026-09-05) rev-2: config-level fix, corrected field.
# Deep-dive (option B) proved opencode reads the model-level `context` / `limit.input`
# (NOT `limit.context`) for the request-cap check ("available context size 65536").
# So bumping only `limit.context` was INEFFECTIVE. This rev injects, idempotently,
# on the cluster-litellm gpt-oss + nemotron model entries:
#   - top-level `context`   (the field that kills AI_APICallError)
#   - `limit.input`         (the field that delays compaction; #21564)
# and keeps the provider `options.timeout`/`chunkTimeout`.
# Scope stays cluster-litellm only (never cluster-local / top-level dup blocks).

def find_block(text, start):
    i = start; depth = 0; n = len(text)
    while i < n:
        c = text[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1

def inject_model(models, key):
    m = re.search(r'("' + re.escape(key) + r'"\s*:\s*)\{', models)
    if not m:
        return models, '%s:absent' % key
    sb = m.end() - 1                 # '{'
    se = find_block(models, sb)
    inner = models[sb:se]
    parsed = json.loads(inner)
    changed = False
    if parsed.get('context') != CTX:
        parsed['context'] = CTX
        changed = True
    limit = parsed.setdefault('limit', {})
    if limit.get('input') != CTX:
        limit['input'] = CTX
        changed = True
    if not changed:
        return models, '%s:nochange' % key
    # models[:sb] already ends with the '"key":' prefix; rebuilt must START at '{'
    # (do NOT restate m.group(1), else key prefix duplicates -> invalid JSON).
    ls = models.rfind('\n', 0, m.start()) + 1
    lead = models[ls:m.start()]          # whitespace before '"key"'
    dump = json.dumps(parsed, indent=2, ensure_ascii=False).split('\n')
    rebuilt = dump[0] + ''.join('\n' + lead + L for L in dump[1:])
    return models[:sb] + rebuilt + models[se:], '%s:set(ctx=%d/in=%d)' % (key, CTX, CTX)

CTX = 120000
p = sys.argv[1]
s = open(p, encoding='utf-8').read()

# --- cluster-litellm block ---
k = s.find('"cluster-litellm"')
assert k != -1, 'no cluster-litellm provider'
kb = s.find('{', k)
cl_end = find_block(s, kb)
cl = s[kb:cl_end]

# --- models block within cluster-litellm ---
mk = cl.find('"models"')
assert mk != -1, 'no models in cluster-litellm'
mb = cl.find('{', mk)
m_end = find_block(cl, mb)
models = cl[mb:m_end]

notes = []
for key in ('gpt-oss', 'nemotron'):
    models, note = inject_model(models, key)
    notes.append(note)

cl = cl[:mb] + models + cl[m_end:]

# --- provider options timeout/chunkTimeout (idempotent) ---
if '"timeout"' not in cl:
    oi = cl.find('"options"')
    if oi != -1:
        ob = cl.find('{', oi)
        if ob != -1:
            oe = find_block(cl, ob)
            opts = cl[ob:oe]
            apm = re.search(r'("apiKey"\s*:\s*"[^"]*")', opts)
            if apm:
                ins = ',\n        "timeout": 1800000,\n        "chunkTimeout": 600000'
                cl = cl[:ob] + opts[:apm.end()] + ins + opts[apm.end():] + cl[oe:]
                print('INJECTED timeout/chunkTimeout')
            else:
                print('SKIP timeout: no apiKey')
        else:
            print('SKIP timeout: no options brace')
    else:
        print('SKIP timeout: no options')
else:
    print('SKIP timeout already present')

out = s[:kb] + cl + s[cl_end:]

new = json.loads(out)               # hard validation before write
lit = new['provider']['cluster-litellm']['models']
g = lit['gpt-oss']; nm = lit['nemotron']
open(p, 'w', encoding='utf-8').write(out)
print('NOTES:', '; '.join(notes))
print('VALIDATED_OK gpt-oss: context=%s limit.input=%s | nemotron: context=%s limit.input=%s' %
      (g.get('context'), g['limit'].get('input'), nm.get('context'), nm['limit'].get('input')))