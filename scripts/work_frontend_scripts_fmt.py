import os,sys,json,re
def fmt(src):
    out=[]; i=0; n=len(src); lines=[]; cur=0
    prev=''  # last significant char
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
            prev=q
            continue
        if c=='/' and i+1<n and src[i+1]=='/':
            j=src.find('\n',i); j=n if j<0 else j
            out.append(src[i:j]); i=j; prev=';'; continue
        if c=='/' and i+1<n and src[i+1]=='*':
            j=src.find('*/',i+2); j=n if j<0 else j+2
            out.append(src[i:j]); i=j; prev=';'; continue
        if c=='/' and prev in '(=,:[!&|?{};+-*%<>~^' :
            # regex literal
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
                out.append('\n'); cur+=1
        i+=1
    return ''.join(out)
p=sys.argv[1]; out=sys.argv[2]
src=open(p,encoding='utf-8',errors='replace').read()
r=fmt(src)
open(out,'w',encoding='utf-8',newline='\n').write(r)
print(p,'->',out,'in',len(src),'out',len(r),'lines',r.count(chr(10)))
