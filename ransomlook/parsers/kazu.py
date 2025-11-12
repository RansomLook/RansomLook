import os, json
from typing import Dict, List

def extract_companies_block(raw: str) -> str:
    i = raw.find("const companies")
    if i == -1: raise ValueError("const companies not found")
    j = raw.find("=", i)
    k = raw.find("[", j)
    if k == -1: raise ValueError("No '[' after '='")
    depth = 0; in_str = False; esc = False; quote = ''
    for idx, ch in enumerate(raw[k:], start=k):
        if in_str:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == quote: in_str = False
        else:
            if ch in ("'", '"'): in_str = True; quote = ch
            elif ch == '[': depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0: return raw[k:idx+1]
    raise ValueError("']' final not found")

def jsarray_to_json(js: str) -> str:
    out=[]; i=0; n=len(js); in_str=False; esc=False; quote=''
    while i<n:
        ch = js[i]
        if in_str:
            out.append(ch)
            if esc: esc=False
            elif ch == '\\': esc=True
            elif ch == quote: in_str=False
            i+=1
        else:
            if ch in ("'", '"'):
                in_str=True; quote=ch; out.append(ch); i+=1
            elif ch=='/' and i+1<n and js[i+1] in ('/','*'):
                if js[i+1]=='/':
                    i+=2
                    while i<n and js[i] not in '\r\n': i+=1
                else:
                    i+=2
                    while i+1<n and not (js[i]=='*' and js[i+1]=='/'): i+=1
                    i+=2
            else:
                out.append(ch); i+=1
    s=''.join(out)

    out=[]; i=0; n=len(s); in_str=False; esc=False; quote=''
    while i<n:
        ch=s[i]
        if in_str:
            out.append(ch)
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch==quote: in_str=False
            i+=1
        else:
            if ch in ("'", '"'):
                in_str=True; quote=ch; out.append(ch); i+=1
            elif ch in '{,':
                out.append(ch); i+=1
                while i<n and s[i].isspace(): out.append(s[i]); i+=1
                j=i
                if j<n and (s[j].isalpha() or s[j]=='_'):
                    j+=1
                    while j<n and (s[j].isalnum() or s[j]=='_'): j+=1
                    k=j
                    while k<n and s[k].isspace(): k+=1
                    if k<n and s[k]==':':
                        key=s[i:j]
                        out.append('"'+key+'":')
                        i=k+1
                        continue
            else:
                out.append(ch); i+=1
    s=''.join(out)

    out=[]; in_str=False; esc=False; quote=''; prev=[]
    for ch in s:
        if in_str:
            out.append(ch)
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch==quote: in_str=False
        else:
            if ch in ("'", '"'):
                in_str=True; quote=ch; out.append(ch)
            elif ch in '}]':
                t=len(out)-1
                while t>=0 and out[t].isspace(): t-=1
                if t>=0 and out[t]==',':
                    del out[t]
                out.append(ch)
            else:
                out.append(ch)
    s=''.join(out)

    out=[]; in_str=False; esc=False; quote=''
    for ch in s:
        code=ord(ch)
        if in_str:
            if esc:
                out.append(ch); esc=False
            else:
                if ch=='\\': out.append(ch); esc=True
                elif ch==quote: out.append(ch); in_str=False
                else: out.append('\\u%04x'%code if code<0x20 else ch)
        else:
            if ch in ("'", '"'):
                in_str=True; quote=ch; out.append(ch)
            else:
                out.append(ch if code>=0x20 or ch in '\t\n\r' else ' ')
    return ''.join(out)

def parse_file(path: str):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        raw=f.read().lstrip("\ufeff")
    block = extract_companies_block(raw)
    json_text = jsarray_to_json(block)
    data = json.loads(json_text)
    return data


def main() -> List[Dict[str, str]] :
    list_div=[]

    for filename in os.listdir('source'):
        try:
            if filename.startswith(__name__.split('.')[-1]+'-'):
                html_doc='source/'+filename
                data = parse_file(html_doc)
                for entry in data:
                    list_div.append({'title': entry['name'], 'description': entry['description']})
        except:
            print("Failed during : " + filename)
            pass
    print(list_div)
    return list_div
