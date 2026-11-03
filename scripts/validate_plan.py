#!/usr/bin/env python3
"""Optional checks for a brief slide plan and supplied geometry; no aesthetic approval."""
import argparse,json,math
from pathlib import Path

def validate(p):
    errors=[];warnings=[]
    width=960;height=540
    def error(msg): errors.append(msg)
    def bbox(b,label):
        if not isinstance(b,list) or len(b)!=4 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in b):error(label+': invalid bbox');return None
        x,y,w,h=b
        if min(x,y)<0 or min(w,h)<=0 or x+w>width+.5 or y+h>height+.5:error(label+': outside canvas')
        return b
    def intersect(a,b):return min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0]) and min(a[1]+a[3],b[1]+b[3])>max(a[1],b[1])
    if not isinstance(p,dict):return {'errors':['plan must be object'],'warnings':[]}
    canvas=p.get('canvas',{'width':960,'height':540})
    if not isinstance(canvas,dict) or any(isinstance(canvas.get(k),bool) or not isinstance(canvas.get(k),(int,float)) or not math.isfinite(canvas[k]) or canvas[k]<=0 for k in ('width','height')):
        error('canvas needs positive finite width/height')
    else:width=canvas['width'];height=canvas['height']
    spacing=p.get('spacing_system',{})
    if not isinstance(spacing,dict) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in spacing.values()):error('spacing values must be positive finite numbers')
    slides=p.get('slides')
    if not isinstance(slides,list) or not slides:return {'errors':errors+['slides must be non-empty array'],'warnings':warnings}
    seen_pages=set()
    for n,s in enumerate(slides,1):
        label=f'slide {n}'
        if not isinstance(s,dict):error(label+': must be object');continue
        number=s.get('slide_no')
        if isinstance(number,bool) or not isinstance(number,int) or number<1 or number in seen_pages:error(label+': slide_no must be a unique positive integer')
        else:seen_pages.add(number)
        for k in ('key_message','composition'):
            if not isinstance(s.get(k),str) or not s[k].strip():error(label+': missing '+k)
        if 'layout_constraints' in s and not isinstance(s['layout_constraints'],list):error(label+': layout_constraints must be an array')
        bleeds=s.get('bleed_objects',[])
        if not isinstance(bleeds,list):error(label+': bleed_objects must be array');bleeds=[]
        bleed_ids=set()
        for o in bleeds:
            if not isinstance(o,dict):error(label+': invalid bleed object');continue
            oid=o.get('id');where=label+': bleed '+str(oid)
            if not isinstance(oid,str) or not oid or oid in bleed_ids:error(where+': missing/duplicate ID')
            else:bleed_ids.add(oid)
            b=o.get('logical_bbox')
            if not isinstance(b,list) or len(b)!=4 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in b) or min(b[2:])<=0:
                error(where+': invalid logical_bbox');continue
            x,y,w,h=b;left=max(0,x);top=max(0,y);right=min(width,x+w);bottom=min(height,y+h)
            if right<=left or bottom<=top:error(where+': no visible area');continue
            actual=[left,top,right-left,bottom-top]
            visible=bbox(o.get('visible_bbox'),where)
            if visible and any(abs(a-b)>0.5 for a,b in zip(visible,actual)):error(where+': visible_bbox must equal canvas intersection')
            edges={k for k,yes in [('left',x<0),('top',y<0),('right',x+w>width),('bottom',y+h>height)] if yes}
            declared=o.get('edges')
            if not isinstance(declared,list) or not all(isinstance(k,str) for k in declared) or set(declared)!=edges or not edges:error(where+': edges must match actual crop')
            if not o.get('crop_reason'):error(where+': missing crop_reason')
            regions=o.get('protected_regions')
            if not isinstance(regions,list) or not regions:error(where+': protected_regions required');regions=[]
            for r in regions:
                rb=bbox(r,where+': protected region')
                if rb and (rb[0]<left or rb[1]<top or rb[0]+rb[2]>right+0.5 or rb[1]+rb[3]>bottom+0.5):error(where+': protected region is cropped')
        chars=s.get('characters',[]);texts=s.get('text_boxes',[]);ids=set();tb=[]
        if not isinstance(chars,list):error(label+': characters must be array');chars=[]
        for c in chars:
            if not isinstance(c,dict):error(label+': character must be object');continue
            cid=c.get('id')
            if not isinstance(cid,str) or not cid or cid in ids:error(label+': duplicate/missing character ID')
            else:ids.add(cid)
            bbox(c.get('visible_bbox'),label+': '+str(cid))
        if not isinstance(texts,list):error(label+': text_boxes must be array');texts=[]
        for t in texts:
            if not isinstance(t,dict):error(label+': text box must be object');continue
            tid=t.get('id')
            if not isinstance(tid,str) or not tid or tid in ids:error(label+': duplicate/missing text ID')
            else:ids.add(tid)
            b=bbox(t.get('bbox'),label+': '+str(tid));fs=t.get('font_size')
            if not isinstance(fs,(float,int)) or isinstance(fs,bool) or not math.isfinite(fs) or fs<=0:error(label+': invalid font_size')
            elif fs<16*width/960:warnings.append(label+': '+str(tid)+' small text; verify at use size')
            if b:tb.append((tid,b))
        for i,(tid,b) in enumerate(tb):
            for oid,ob in tb[i+1:]:
                if intersect(b,ob):error(label+': text boxes overlap '+str(tid)+'/'+str(oid))
    return {'errors':errors,'warnings':warnings}

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('plan',type=Path);args=a.parse_args()
    try:r=validate(json.loads(args.plan.read_text()))
    except (OSError,ValueError) as e:r={'errors':[str(e)],'warnings':[]}
    print(json.dumps(r,ensure_ascii=False,indent=2));return bool(r['errors'])
if __name__=='__main__':raise SystemExit(main())
