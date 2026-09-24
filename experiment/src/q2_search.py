"""核心优化模块：箱级/服务点级邻域 + 固定种子退火 + 破坏-重建。
Python 3.13.5；只用标准库和已验证的q2_physics。完整允许1~15服务点。
这是联合可行解搜索，不声称全空间的全局最优；结果均由独立模块复核。
"""
from __future__ import annotations
import math, random
from collections import Counter
from q2_config import Q2CFG


def objective(m, mode='time', cap=None):
    if m is None:return (math.inf,)*5
    hard=round(m['hard_late_s'],6);late=round(m['weighted_tardiness_s'],6)
    c=round(m['makespan_s'],6);e=round(m['energy_kwh'],9);n=m['trips']
    if mode=='energy':return (hard,late,round(max(0,c-cap),6) if cap is not None else 0,e,n,c)
    if mode=='trips':return (hard,late,n,e,c)
    return (hard,late,c,e,n)


def anneal_score(m, mode='time', cap=None):
    if m is None:return math.inf
    penalty=Q2CFG.hard_lateness_penalty*m['hard_late_s']+Q2CFG.soft_lateness_penalty*m['weighted_tardiness_s']
    if mode=='energy':
        return penalty+Q2CFG.hard_lateness_penalty*max(0,m['makespan_s']-(cap or math.inf))+100*m['energy_kwh']+0.01*m['makespan_s']+0.001*m['trips']
    if mode=='trips':return penalty+1000*m['trips']+m['energy_kwh']+0.001*m['makespan_s']
    return penalty+m['makespan_s']+Q2CFG.energy_tiebreak_s_per_kwh*m['energy_kwh']+Q2CFG.trip_tiebreak_s*m['trips']


def urgency_order(pb,trips):
    return sorted(trips,key=lambda t:(pb.evaluate(t)['hard_latest_start'],pb.evaluate(t)['soft_latest_start'],-len(t[2]),t))


def greedy_initial(pb,seed=0,maxstops=15):
    rng=random.Random(seed);trips=[]
    ids=sorted(range(len(pb.boxes)),key=lambda i:(min(pb.hard[i],pb.expected[i]),0 if math.isfinite(pb.hard[i]) else 1,-pb.priority[i],rng.random()))
    for i in ids:
        best=None;key=None
        for j,tr in enumerate(trips):
            for tt in pb.options_insert(tr,(i,)):
                if len(tt[1])>maxstops or pb.evaluate(tt) is None:continue
                cand=trips[:];cand[j]=tt;cand=urgency_order(pb,cand)
                mm=pb.schedule(cand);kk=objective(mm)
                if key is None or kk<key:best=cand;key=kk
        for g in pb.models:
            tt=pb.trip(g,(pb.sid[i],),(i,))
            if pb.evaluate(tt) is None:continue
            # 各模型的最早截止优先列表是初始构造，不等同于最终固定执行顺序。
            cand=urgency_order(pb,trips+[tt]);mm=pb.schedule(cand);kk=objective(mm)
            if key is None or kk<key:best=cand;key=kk
        if best is None:raise ValueError(f'没有物理可行的单箱候选：{pb.bid[i]}')
        trips=best
    return trips


def _update(pb,tr,remove=(),add=(),rng=None):
    ids=tuple(i for i in tr[2] if i not in remove)
    if not ids and not add:return None
    base=pb.trip(tr[0],tr[1],ids)
    if add:
        options=pb.options_insert(base,add)
        # 一次移动最多插入一个服务区；若是成批移动仍完整列出插入次序。
        if rng is not None:return rng.choice(options)
        return next((x for x in options if pb.evaluate(x) is not None),None)
    return base


def mutate(pb,trips,rng,maxstops=15):
    n=len(trips);out=trips[:];op=rng.randrange(10)
    if n<2:op=7
    if op in (0,1):
        # 改变同机型的任务先后；不同机型列表互不争用设备，无效交换可省略。
        a=rng.randrange(n);js=[j for j in range(n) if j!=a and trips[j][0]==trips[a][0]]
        if not js:return None
        b=rng.choice(js)
        if op==0:out[a],out[b]=out[b],out[a]
        else:out.insert(b,out.pop(a))
    elif op==2:
        a=rng.randrange(n);tr=trips[a];g=rng.choice([g for g in pb.models if g!=tr[0]])
        out[a]=(g,tr[1],tr[2])
    elif op in (3,4,5):
        a,b=rng.sample(range(n),2);ta,tb=trips[a],trips[b]
        ia=rng.choice(ta[2]);rem=(ia,) if op!=5 else tuple(i for i in ta[2] if pb.sid[i]==pb.sid[ia])
        if op==4:
            ib=rng.choice(tb[2]);na=_update(pb,ta,(ia,),(ib,),rng);nb=_update(pb,tb,(ib,),(ia,),rng)
        else:na=_update(pb,ta,rem,(),rng);nb=_update(pb,tb,(),rem,rng)
        out[a]=na;out[b]=nb;out=[t for t in out if t is not None]
    elif op==6:
        a=rng.randrange(n);tr=trips[a]
        if len(tr[1])<2:return None
        ss=list(tr[1]);i,j=rng.sample(range(len(ss)),2);ss[i],ss[j]=ss[j],ss[i]
        out[a]=(tr[0],tuple(ss),tr[2])
    elif op==7:
        a=rng.randrange(n);tr=trips[a]
        if len(tr[2])<2:return None
        count=rng.randint(1,len(tr[2])-1);ix=tuple(rng.sample(tr[2],count));rem=tuple(i for i in tr[2] if i not in ix)
        ng=rng.choice(tuple(pb.models));nt=pb.trip(ng,tr[1],ix);out[a]=pb.trip(tr[0],tr[1],rem)
        out.insert(rng.randrange(len(out)+1),nt)
    elif op==8:
        a,b=rng.sample(range(n),2);ta,tb=trips[a],trips[b];g=rng.choice(tuple(pb.models))
        stops=tuple(dict.fromkeys(ta[1]+tb[1]));out[a]=pb.trip(g,stops,ta[2]+tb[2]);out.pop(b)
    else:
        a=rng.randrange(n);tr=trips[a];i=rng.choice(tr[2]);rem=tuple(x for x in tr[2] if x!=i)
        if not rem:return None
        out[a]=pb.trip(tr[0],tr[1],rem)
        out.insert(rng.randrange(n+1),pb.trip(rng.choice(tuple(pb.models)),(pb.sid[i],),(i,)))
    if any(len(t[1])>maxstops or pb.evaluate(t) is None for t in out):return None
    return out


def rebuild(pb,base,rng,mode='time',cap=None,maxstops=15):
    """移除2~9个货箱后重插；保留真实箱身份，全部物理与时限逐次重算。"""
    k=rng.randint(Q2CFG.destroy_size_min,Q2CFG.destroy_size_max)
    ids=rng.sample(range(len(pb.boxes)),k);idsset=set(ids)
    trips=[]
    for tr in base:
        ix=tuple(i for i in tr[2] if i not in idsset)
        if ix:trips.append(pb.trip(tr[0],tr[1],ix))
    ids.sort(key=lambda i:(min(pb.hard[i],pb.expected[i]),-pb.priority[i],rng.random()))
    for i in ids:
        candidates=[]
        for j,tr in enumerate(trips):
            for tt in pb.options_insert(tr,(i,)):
                if len(tt[1])>maxstops or pb.evaluate(tt) is None:continue
                cand=trips[:];cand[j]=tt;m=pb.schedule(cand)
                candidates.append((objective(m,mode,cap),cand))
        for g in pb.models:
            tt=pb.trip(g,(pb.sid[i],),(i,))
            if pb.evaluate(tt) is None:continue
            # 新任务在同型队列的每个有意义位置枚举插入，而不是只追加。
            positions=sorted(set([0,len(trips)]+[j+1 for j,t in enumerate(trips) if t[0]==g]))
            for j in positions:
                cand=trips[:j]+[tt]+trips[j:];m=pb.schedule(cand)
                candidates.append((objective(m,mode,cap),cand))
        if not candidates:return None
        candidates.sort(key=lambda x:x[0]);rank=0 if rng.random()<0.90 else rng.randrange(min(3,len(candidates)))
        trips=candidates[rank][1]
    return trips


def search(pb,initial,seed,iterations=None,mode='time',cap=None,maxstops=15,lns=None):
    rng=random.Random(seed);iterations=iterations if iterations is not None else Q2CFG.iterations_per_seed
    lns=Q2CFG.lns_iterations if lns is None else lns
    best=initial[:];bm=pb.schedule(best);current=best[:];cm=bm
    history=[{'iteration':0,'phase':'initial','seed':seed,**{k:v for k,v in bm.items() if k!='records'}}]
    accepted=0;phys=0
    for it in range(1,iterations+1):
        cand=mutate(pb,current,rng,maxstops)
        if cand is None:continue
        phys+=1;nm=pb.schedule(cand)
        frac=(it%Q2CFG.reheat_interval)/Q2CFG.reheat_interval
        temp=Q2CFG.temperature_start_s*(Q2CFG.temperature_end_s/Q2CFG.temperature_start_s)**frac
        delta=anneal_score(nm,mode,cap)-anneal_score(cm,mode,cap)
        if delta<=0 or (delta/temp<700 and rng.random()<math.exp(-delta/temp)):
            current=cand;cm=nm;accepted+=1
        if objective(nm,mode,cap)<objective(bm,mode,cap):
            best=cand;bm=nm
            history.append({'iteration':it,'phase':'anneal','seed':seed,**{k:v for k,v in bm.items() if k!='records'}})
        if it%Q2CFG.reheat_interval==0:current=best[:];cm=bm
    for it in range(1,lns+1):
        cand=rebuild(pb,best,rng,mode,cap,maxstops)
        if cand is None:continue
        mm=pb.schedule(cand)
        if objective(mm,mode,cap)<objective(bm,mode,cap):
            best=cand;bm=mm
            history.append({'iteration':iterations+it,'phase':'destroy_repair','seed':seed,**{k:v for k,v in bm.items() if k!='records'}})
    stats={'seed':seed,'iterations':iterations,'lns_iterations':lns,'physically_feasible_moves':phys,'accepted_moves':accepted,
           'mode':mode,'max_stops_permitted':maxstops,**{k:v for k,v in bm.items() if k!='records'}}
    return best,bm,history,stats
