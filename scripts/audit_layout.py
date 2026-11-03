#!/usr/bin/env python3
"""Check named spacing constraints; not an aesthetic score."""
import argparse,json,math
from pathlib import Path

def union_area(rects):
    """Union of clipped image ink boxes; gaps and overlaps are not counted twice."""
    xs=sorted({x for r in rects for x in (r[0],r[2])});area=0
    for left,right in zip(xs,xs[1:]):
        intervals=sorted((r[1],r[3]) for r in rects if r[0]<right and r[2]>left)
        end=None;covered=0
        for top,bottom in intervals:
            covered+=max(0,bottom-max(top,end if end is not None else top))
            end=bottom if end is None else max(end,bottom)
        area+=(right-left)*covered
    return area

def audit(doc):
    errors=[];warnings=[];measurements=[]
    tokens=doc.get('spacing_system',{})
    if not isinstance(tokens,dict):
        errors.append('spacing_system must be an object when supplied')
        return {'errors':errors,'warnings':warnings,'measurements':measurements}
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in tokens.values()):
        return {'errors':['Spacing tokens must be positive finite numbers'],'warnings':[],'measurements':[]}
    canvas=doc.get('canvas',{'width':960,'height':540})
    if not isinstance(canvas,dict) or any(isinstance(canvas.get(k),bool) or not isinstance(canvas.get(k),(int,float)) or not math.isfinite(canvas[k]) or canvas[k]<=0 for k in ('width','height')):
        return {'errors':['canvas needs positive finite width/height'],'warnings':[],'measurements':[]}
    width,height=canvas['width'],canvas['height']
    slides=doc.get('slides',[])
    if not isinstance(slides,list) or not slides:
        return {'errors':['No slides to audit'],'warnings':[],'measurements':[]}
    for si,s in enumerate(slides,1):
        constraints=s.get('layout_constraints',[])
        if not isinstance(constraints,list) or not constraints:
            errors.append(f'slide {si}: no declared layout constraints');continue
        objects={o['id']:o for o in s.get('objects',[])+s.get('groups',[])}
        def bound(ids,basis):
            bs=[]
            for oid in ids:
                if oid not in objects:raise ValueError('Unknown object '+str(oid))
                o=objects[oid];key='ink_bbox' if basis=='ink' else 'bbox'
                b=o.get(key)
                if not isinstance(b,list) or len(b)!=4 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in b):raise ValueError('Missing/invalid '+key+' for '+str(oid))
                bs.append(b)
            if not bs:raise ValueError('Empty constraint group')
            x=min(b[0]for b in bs);y=min(b[1]for b in bs)
            return [x,y,max(b[0]+b[2]for b in bs)-x,max(b[1]+b[3]for b in bs)-y]
        for c in constraints:
            label=f'slide {si} / '+str(c.get('id','constraint'))
            try:
                basis=c.get('basis','layout');kind=c['kind'];tol=c.get('tolerance',4)
                if basis not in ('layout','ink'):raise ValueError('basis must be layout or ink')
                if isinstance(tol,bool) or not isinstance(tol,(int,float)) or not math.isfinite(tol) or tol<0:raise ValueError('invalid tolerance')
                if kind=='align':
                    if len(c['ids'])<2:raise ValueError('alignment needs at least two objects')
                    vals=[]
                    for oid in c['ids']:
                        b=bound([oid],basis);edge=c.get('edge','left')
                        vals.append({'left':b[0],'right':b[0]+b[2],'top':b[1],'bottom':b[1]+b[3],'center_x':b[0]+b[2]/2,'center_y':b[1]+b[3]/2}[edge])
                    value=max(vals)-min(vals);ok=value<=tol
                elif kind in ('gap','gutter'):
                    if c.get('axis','x') not in ('x','y'):raise ValueError('axis must be x or y')
                    a=bound(c['a'],basis);b=bound(c['b'],basis)
                    value=b[0]-(a[0]+a[2]) if c.get('axis','x')=='x' else b[1]-(a[1]+a[3])
                    if 'token'in c:
                        target=tokens[c['token']];ok=abs(value-target)<=tol
                    else:ok=c['min']<=value<=c['max']
                elif kind=='generated_visual_coverage':
                    if basis!='ink':raise ValueError('generated coverage requires measured ink bounds')
                    minimum=c.get('min_ratio')
                    if isinstance(minimum,bool) or not isinstance(minimum,(int,float)) or not math.isfinite(minimum) or not 0<=minimum<=1:raise ValueError('coverage requires an explicit min_ratio between 0 and 1')
                    ids=c['ids']
                    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):raise ValueError('list distinct generated image object IDs')
                    rects=[]
                    for oid in ids:
                        if oid not in objects or objects[oid].get('type')!='image':raise ValueError('coverage IDs must be actual image objects')
                        x,y,w,h=bound([oid],'ink')
                        if w<0 or h<0:raise ValueError('negative ink dimensions')
                        left,top,right,bottom=max(0,x),max(0,y),min(width,x+w),min(height,y+h)
                        if right>left and bottom>top:rects.append((left,top,right,bottom))
                    value=union_area(rects)/(width*height);ok=value+1e-12>=minimum
                else:raise ValueError('Unknown constraint kind')
                item={'slide':si,'id':c.get('id'),'value':round(value,2),'basis':basis,'passed':ok};measurements.append(item)
                if not ok:
                    (warnings if c.get('severity')=='warning' else errors).append(label+': '+str(round(value,2))+' outside declared constraint')
            except (ValueError,KeyError,TypeError)as e:errors.append(label+': '+str(e))
    return {'errors':errors,'warnings':warnings,'measurements':measurements,'note':'Constraint checks only; local ink estimates do not prove target rendering or good composition.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('measured_json',type=Path);a=p.parse_args()
    try:r=audit(json.loads(a.measured_json.read_text()))
    except (OSError,ValueError)as e:r={'errors':[str(e)],'warnings':[],'measurements':[]}
    print(json.dumps(r,ensure_ascii=False,indent=2));return bool(r['errors'])
if __name__=='__main__':raise SystemExit(main())
