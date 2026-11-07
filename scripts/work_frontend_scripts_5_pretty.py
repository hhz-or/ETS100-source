import os,sys,json,re
sys.path.insert(0,'data/frontend\\scripts')
OUT=r'data/frontend'; BUND=os.path.join(OUT,'bundles'); PRETTY=os.path.join(OUT,'pretty')
os.makedirs(PRETTY,exist_ok=True)
def fmt(src):
    out=[]; i=0; n=len(src); prev=''; linemap=[]
    while i<n:
        c=src[i]
        if c in '\'"`':
            q=c; out.append(c); i+=1
            while i<n:
                ch=src[i]
                if ch=='\\':
                    out.append(src[i:i+2]); i+=2; continue
                out.append(ch); i+=1
                if ch==q: break
            prev=q; continue
        if c=='/' and i+1<n and src[i+1]=='/':
            j=src.find('\n',i); j=n if j<0 else j
            out.append(src[i:j]); i=j; prev=';'; continue
        if c=='/' and i+1<n and src[i+1]=='*':
            j=src.find('*/',i+2); j=n if j<0 else j+2
            out.append(src[i:j]); i=j; prev=';'; continue
        if c=='/' and prev in '(=,:[!&|?{};+-*%<>~^':
            j=i+1; incls=False
            while j<n:
                ch=src[j]
                if ch=='\\': j+=2; continue
                if ch=='[': incls=True
                elif ch==']': incls=False
                elif ch=='/' and not incls: j+=1; break
                j+=1
            out.append(src[i:j]); i=j; prev='x'; continue
        out.append(c)
        if c not in ' \t\r\n':
            prev=c
            if c in ';{}':
                out.append('\n'); linemap.append(len(src[:i])) if False else None
        i+=1
    return ''.join(out)
man=json.load(open(os.path.join(OUT,'manifest.json')))
types={'js':'js','css':'css','html':'html','json':'json','txt':'txt','svg':'svg'}
done=[]
for m in man:
    if m['type'] not in types: continue
    srcp=os.path.join(BUND,m['file'])
    if not os.path.exists(srcp): continue
    base=os.path.basename(m['file'])
    outp=os.path.join(PRETTY,base)
    if os.path.exists(outp): 
        m['pretty']=os.path.relpath(outp,OUT).replace('\\','/'); continue
    txt=open(srcp,encoding='utf-8',errors='replace').read()
    r=fmt(txt)
    open(outp,'w',encoding='utf-8',newline='\n').write(r)
    m['pretty']=os.path.relpath(outp,OUT).replace('\\','/')
    m['pretty_lines']=r.count('\n')+1
    done.append((base,len(txt),len(r)))
json.dump(man,open(os.path.join(OUT,'manifest.json'),'w'),ensure_ascii=False,indent=1)
print('formatted',len(done))
for d in done[:8]: print(d)
