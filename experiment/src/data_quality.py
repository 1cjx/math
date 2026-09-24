"""阶段1：全量数据校验与保守清洗。所有原始值只读，逐项记录来源。
Python 3.13.5；numpy/scipy/rasterio/pyproj/shapely/h5py版本见requirements.txt。
对关键输入发现无依据可修复的错误即报错，而不是虚构数据或静默删除货箱。
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, json, math, re, zipfile
import numpy as np
import rasterio
from scipy.io import loadmat
from pyproj import CRS, Transformer
import h5py
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, mapping
from shapely.validation import explain_validity
from config import CFG
from io_utils import xlsx_read, block, read_csv, write_csv, save_json, sha256, first_file

# 业务字段映射：类型和单位在字段名内固定；不依赖Excel视觉排版。
SCHEMAS={
 'depots':(['调度中心编号','调度中心名称','经度（°）','纬度（°）','海拔（m）'],
           ['node_id','name','lon_deg','lat_deg','ground_elevation_m'],[str,str,float,float,float]),
 'services':(['服务区编号','服务区名称','经度（°）','纬度（°）','海拔（m）','本次需保障人口（人）'],
             ['node_id','name','lon_deg','lat_deg','ground_elevation_m','population'],[str,str,float,float,float,int]),
 'transport_models':(['机型编号','机型名称','含电池空载总质量（kg）','最大载货质量（kg）','可用装载体积（m³）','计划巡航速度（m/s）','空载标准航程（m）','满载标准航程（m）','电池可用能量（kWh）','返航电量下限（%）','工位固定准备时间（s）','每箱装载时间（s）','接收点基础交接时间（s）','每箱增加交接时间（s）','最大爬升速度（m/s）','最大下降速度（m/s）','爬升能耗效率','下降能耗效率'],
   ['model_id','name','empty_mass_kg','max_payload_kg','volume_m3','cruise_speed_mps','empty_range_m','full_range_m','usable_energy_kwh','reserve_percent','prepare_s','load_per_box_s','handoff_base_s','handoff_per_box_s','climb_speed_mps','descent_speed_mps','climb_efficiency','descent_efficiency'],[str,str]+[float]*16),
 'transport_drones':(['无人机编号','机型编号','初始位置'],['drone_id','model_id','initial_node'],[str,str,str]),
 'transport_batteries':(['机型编号','共享电池组总数（组）','等效完全充电时间（s）'],['model_id','count','full_charge_s'],[str,int,float]),
 'relay_models':(['机型编号','机型名称','含能源组件空载总质量（kg）','中继通信模块质量（kg）','计划起飞总质量（kg）','计划巡航速度（m/s）','巡航功率（kW）','能源组件可用能量（kWh）','返航电量下限（%）','工位固定准备时间（s）','建链时间（s）','架次周转时间（s）','最大爬升速度（m/s）','最大下降速度（m/s）','爬升能耗效率','下降能耗效率','悬停功率（kW）','通信附加功率（kW）','最大悬停离地高度（m）'],
   ['model_id','name','empty_mass_kg','module_mass_kg','takeoff_mass_kg','cruise_speed_mps','cruise_power_kw','usable_energy_kwh','reserve_percent','prepare_s','link_setup_s','turnaround_s','climb_speed_mps','descent_speed_mps','climb_efficiency','descent_efficiency','hover_power_kw','communication_power_kw','max_hover_agl_m'],[str,str]+[float]*17),
 'relay_drones':(['中继无人机编号','机型编号','初始位置'],['drone_id','model_id','initial_node'],[str,str,str]),
 'relay_energy':(['机型编号','共享能源组件总数（组）','等效完全充电时间（s）'],['model_id','count','full_charge_s'],[str,int,float]),
 'demand':(['服务区编号','物资类型','总需求箱数','首批必须送达箱数','单箱质量（kg）','单箱体积（m³）','应急优先系数','首批截止时间（s）','期望送达时间（s）'],
   ['service_id','material_type','box_count','first_batch_count','weight_kg','volume_m3','priority','first_deadline_s','expected_s'],[str,str,int,int,float,float,int,float,float]),
 'boxes':(['货箱编号','服务区编号','物资类型','单箱质量（kg）','单箱体积（m³）','是否首批保障','首批截止时间（s）','期望送达时间（s）','应急优先系数'],
   ['box_id','service_id','material_type','weight_kg','volume_m3','first_batch_text','first_deadline_s','expected_s','priority'],[str,str,str,float,float,str,float,float,int]),
}
TABLE_SOURCES={
 'depots':('调度中心与服务区.xlsx','数据'), 'services':('调度中心与服务区.xlsx','数据'),
 'transport_models':('运输无人机数据.xlsx','数据'),'transport_drones':('运输无人机数据.xlsx','数据'),'transport_batteries':('运输无人机数据.xlsx','数据'),
 'relay_models':('中继无人机数据.xlsx','数据'),'relay_drones':('中继无人机数据.xlsx','数据'),'relay_energy':('中继无人机数据.xlsx','数据'),
 'demand':('物资需求与配送时限.xlsx','数据'),'boxes':('物资需求与配送时限.xlsx','逐箱货箱清单'),
}
GEO_COLS={'点位编号':'feature_id','道路要素编号':'feature_id','水系要素编号':'feature_id','水体要素编号':'feature_id',
 '多边形编号':'polygon_id','环编号':'ring_id','点序号':'vertex_index','名称':'name','类别':'category','位置':'location',
 '道路类型':'category','水系类型':'category','水体类型':'category','OSM编号':'osm_id','长度_km':'length_km','经度':'lon_deg','纬度':'lat_deg'}
GEO_NUMERIC={'polygon_id':int,'ring_id':int,'vertex_index':int,'length_km':float,'lon_deg':float,'lat_deg':float}

class Audit:
    def __init__(self):self.issues=[];self.checks=[];self.profiles=[];self.outliers=[];self.changes=[]
    def issue(self,code,scope,count,meaning,action,severity='info',details=''):
        self.issues.append({'code':code,'severity':severity,'scope':scope,'count':int(count),'meaning':meaning,'action':action,'details':details})
    def check(self,name,ok,details=''):
        self.checks.append({'check':name,'pass':bool(ok),'details':str(details)})
        if not ok:self.issue('FAILED_CHECK',name,1,str(details),'停止核心输入建模并人工审核','error')
    def profile(self,name,rows,keys,optional=None):
        optional=optional or set()
        for k in keys:
            vals=[r[k] for r in rows];valid=[v for v in vals if v is not None and v!='']
            missing=len(vals)-len(valid)
            p={'table':name,'field':k,'rows':len(rows),'missing_count':missing,'missing_rate':missing/max(1,len(rows)),
               'missing_class':'not_applicable' if k in optional else ('unexpected' if missing else 'none'),
               'unique_values':len(set(valid)),'min':None,'q1':None,'median':None,'q3':None,'max':None,'mean':None,'std_population':None,'iqr_flags':0,'mad_flags':0}
            if valid and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in valid):
                a=np.asarray(valid,dtype=float);q1,med,q3=np.quantile(a,[.25,.5,.75]);iqr=q3-q1;mad=float(np.median(abs(a-med)))
                p.update({'min':float(a.min()),'q1':float(q1),'median':float(med),'q3':float(q3),'max':float(a.max()),'mean':float(a.mean()),'std_population':float(a.std())})
                if len(a)>=4:
                    for i,r in enumerate(rows):
                        v=r[k]
                        if v is None:continue
                        iq=iqr>0 and (v<q1-CFG.iqr_multiplier*iqr or v>q3+CFG.iqr_multiplier*iqr)
                        mz=abs(CFG.modified_z_scale*(v-med)/mad) if mad>0 else None
                        mf=mz is not None and mz>CFG.modified_z_threshold
                        p['iqr_flags']+=int(iq);p['mad_flags']+=int(mf)
                        if iq or mf:
                            self.outliers.append({'table':name,'record_key':r.get(keys[0],i+1),'field':k,'value':v,
                              'iqr_flag':bool(iq),'modified_z':mz,'mad_flag':bool(mf),'action':'retain_after_domain_checks'})
            self.profiles.append(p)

def coerce(value,typ):
    if value is None:return None
    if typ is str:return str(value).strip()
    if isinstance(value,bool):raise ValueError('布尔值不能充当数值参数')
    v=float(value)
    if not math.isfinite(v):raise ValueError('非有限数值')
    if typ is int and not v.is_integer():raise ValueError(f'非整数：{value}')
    return typ(v)

def read_mat_table_compare(path,raw_rows):
    """读取本附件v7.3 MATLAB table内部列，含MCOS字符串；逐字段对照CSV。
    对字符串打包格式进行显式校验，不是通用MATLAB对象反序列化器。
    """
    headers=list(raw_rows[0]);n=len(raw_rows);count=0;mismatches=[]
    with h5py.File(path,'r') as f:
        mc=f['#subsystem#/MCOS'][()].ravel();groups=[];name_groups=[]
        for obj in f['#refs#'].values():
            if not isinstance(obj,h5py.Dataset) or obj.dtype!=h5py.ref_dtype or obj.size!=len(headers):continue
            refs=[f[r] for r in obj[()].ravel()]
            if all(isinstance(x,h5py.Dataset) and x.attrs.get('MATLAB_class')==b'char' and not x.attrs.get('MATLAB_empty',0) for x in refs):
                names=[''.join(chr(int(v)) for v in x[()].ravel()) for x in refs]
                if names==headers:name_groups.append(obj.name)
            else:groups.append(refs)
        if len(name_groups)!=1:raise ValueError(f'MAT变量名不匹配：{path.name}')
        usable=[]
        for refs in groups:
            if all(x.size==n or (x.dtype==np.dtype('uint32') and x.size==6) for x in refs):usable.append(refs)
        if len(usable)!=1:raise ValueError(f'MAT数据列识别失败：{path.name}')
        for key,obj in zip(headers,usable[0]):
            a=obj[()].ravel()
            if a.dtype==np.dtype('uint32') and a.size==6:
                packed=f[mc[int(a[4])]][()].ravel()
                if packed.dtype!=np.dtype('uint64') or list(packed[:4])!=[1,2,n,1]:raise ValueError('不支持的MAT字符串封装')
                lengths=packed[4:4+n].astype(int)
                text=packed[4+n:].astype('<u8').tobytes().decode('utf-16-le')
                values=[];pos=0
                for length in lengths:values.append(text[pos:pos+length]);pos+=length
                is_string=True
            else:values=a.tolist();is_string=False
            for i,(v,r) in enumerate(zip(values,raw_rows)):
                ok=(v==r[key]) if is_string else math.isclose(float(v),float(r[key]),rel_tol=0,abs_tol=CFG.geometry_tolerance)
                count+=1
                if not ok:mismatches.append({'row':i+2,'field':key,'mat':v,'csv':r[key]})
    return {'file':path.name,'rows':n,'columns':len(headers),'compared_cells':count,'mismatch_count':len(mismatches),'all_equal':not mismatches}

def run_quality(root):
    root=Path(root);raw=root/'data/raw';clean=root/'data/cleaned';out=root/'results/quality'
    clean.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    (clean/'geospatial').mkdir(parents=True,exist_ok=True)
    au=Audit();books={};sheet_meta=[]
    for path in sorted(raw.rglob('*.xlsx')):
        books[path.name],meta=xlsx_read(path);sheet_meta+=meta
    data={};dictionary=[]
    for key,(filename,sheet) in TABLE_SOURCES.items():
        header,fields,types=SCHEMAS[key]; rows=[]
        for rowno,vals in block(books[filename][sheet],header):
            r={f:coerce(v,t) for f,v,t in zip(fields,vals,types)}
            r.update(source_workbook=filename,source_sheet=sheet,source_excel_row=rowno)
            rows.append(r)
            for f,v in zip(fields,vals):
                if v!=r[f]:au.changes.append({'table':key,'row':rowno,'field':f,'old':v,'new':r[f],'reason':'type_or_whitespace_normalization'})
        data[key]=rows
        for h,f,t in zip(header,fields,types):dictionary.append({'table':key,'field':f,'original_header':h,'dtype':t.__name__,'source_file':filename,'nullable':f=='first_deadline_s'})
        optional={'first_deadline_s'} if key in ('demand','boxes') else set()
        au.profile(key,rows,fields,optional)
        for p in au.profiles:
            if p['table']==key and p['missing_count'] and p['missing_class']=='unexpected':au.check(key+'.'+p['field']+' required',False,p)
    # 通信表含B:C合并单元格；只映射有定义的A/B/D/E，不把C列当缺测。
    comm=[]
    for rowno,r in enumerate(books['通信链路参数.xlsx']['数据'],1):
        if len(r)>=5 and isinstance(r[4],(int,float)):
            comm.append({'category':str(r[0]).strip(),'parameter':str(r[1]).strip(),'symbol':str(r[3]).strip(),'value':float(r[4]),
                         'source_workbook':'通信链路参数.xlsx','source_sheet':'数据','source_excel_row':rowno})
    data['communication']=comm;au.profile('communication',comm,['category','parameter','symbol','value'])
    au.check('communication parameter keys unique',len({(r['category'],r['parameter']) for r in comm})==len(comm))
    # 标识、类别与跨表一致性。
    unique_keys={'depots':['node_id'],'services':['node_id'],'transport_models':['model_id'],'transport_drones':['drone_id'],
                 'transport_batteries':['model_id'],'relay_models':['model_id'],'relay_drones':['drone_id'],'relay_energy':['model_id'],
                 'demand':['service_id','material_type'],'boxes':['box_id']}
    duplicates=0
    for name,keys in unique_keys.items():
        n=len(data[name])-len({tuple(r[k] for k in keys) for r in data[name]});duplicates+=n
        au.check(name+' unique primary key',n==0,f'duplicate keys={n}')
    au.check('one depot',len(data['depots'])==1)
    au.check('service count',len(data['services'])==CFG.expected_services)
    au.check('box count',len(data['boxes'])==CFG.expected_boxes)
    au.check('model count',len(data['transport_models'])==CFG.expected_transport_models)
    au.check('transport drone count',len(data['transport_drones'])==CFG.expected_transport_drones)
    service_ids={r['node_id'] for r in data['services']};all_nodes=service_ids|{r['node_id'] for r in data['depots']}
    type_codes={'医疗物资':'MED','饮用水':'WAT','应急食品':'FOD','生活卫生用品':'HYG'}
    # 货箱编号后缀以原始表为准，检查类别前缀，不自行重编号。
    actual_codes=defaultdict(set)
    for r in data['boxes']:actual_codes[r['material_type']].add(r['box_id'].split('-')[1])
    au.check('id codes match defined material classes',all(actual_codes[k]=={v} for k,v in type_codes.items()),dict(actual_codes))
    for r in data['boxes']:
        au.check(r['box_id']+' known service/material',r['service_id'] in service_ids and r['material_type'] in type_codes)
        au.check(r['box_id']+' id prefix',r['box_id'].startswith(r['service_id']+'-') and bool(re.fullmatch(r'S\d{3}-[A-Z]+-\d{2}',r['box_id'])))
        au.check(r['box_id']+' positive dimensions',r['weight_kg']>0 and r['volume_m3']>0)
        au.check(r['box_id']+' first batch boolean',r['first_batch_text'] in ('是','否'))
        r['is_first_batch']=r['first_batch_text']=='是';r['has_first_deadline']=r['first_deadline_s'] is not None
        au.check(r['box_id']+' deadline semantics',r['has_first_deadline']==r['is_first_batch'])
        au.check(r['box_id']+' times',r['expected_s']>0 and (not r['has_first_deadline'] or 0<r['first_deadline_s']<=r['expected_s']))
    demand_comparison=[]
    for r in data['demand']:
        matching=[b for b in data['boxes'] if (b['service_id'],b['material_type'])==(r['service_id'],r['material_type'])]
        first=sum(b['is_first_batch'] for b in matching)
        ok=len(matching)==r['box_count'] and first==r['first_batch_count']
        for b in matching:
            ok=ok and all(b[k]==r[k] for k in ['weight_kg','volume_m3','priority','expected_s'])
            if b['is_first_batch']:ok=ok and b['first_deadline_s']==r['first_deadline_s']
        ok=ok and ((r['first_deadline_s'] is None)==(r['first_batch_count']==0))
        demand_comparison.append({'service_id':r['service_id'],'material_type':r['material_type'],'declared_count':r['box_count'],
            'listed_count':len(matching),'declared_first_count':r['first_batch_count'],'listed_first_count':first,'consistent':bool(ok)})
        au.check('demand '+r['service_id']+'/'+r['material_type'],ok)
    au.check('total demand equals boxes',sum(r['box_count'] for r in data['demand'])==len(data['boxes']))
    for name in ('transport_models','relay_models'):
        for r in data[name]:
            au.check(name+'/'+r['model_id']+' energy efficiency',r['usable_energy_kwh']>0 and 0<r['reserve_percent']<100 and 0<r['climb_efficiency']<=1 and r['descent_efficiency']==0)
            au.check(name+'/'+r['model_id']+' speeds',all(r[k]>0 for k in ['cruise_speed_mps','climb_speed_mps','descent_speed_mps']))
            r['reserve_fraction']=r['reserve_percent']/CFG.percent_base
            if name=='transport_models':
                au.check(r['model_id']+' ranges and capacities',r['empty_range_m']>=r['full_range_m']>0 and r['max_payload_kg']>0 and r['volume_m3']>0)
            else:au.check('relay total mass',abs(r['takeoff_mass_kg']-r['empty_mass_kg']-r['module_mass_kg'])<CFG.capacity_tolerance_kg)
    for prefix,inventory in [('transport','batteries'),('relay','energy')]:
        models={r['model_id'] for r in data[prefix+'_models']}
        for r in data[prefix+'_drones']:au.check(r['drone_id']+' resource references',r['model_id'] in models and r['initial_node'] in all_nodes)
        count=Counter(r['model_id'] for r in data[prefix+'_drones'])
        for r in data[prefix+'_'+inventory]:au.check(prefix+' energy stock '+r['model_id'],r['model_id'] in models and r['count']>=count[r['model_id']] and r['full_charge_s']>0)
    missing_demand=sum(r['first_deadline_s'] is None for r in data['demand'])
    missing_box=sum(r['first_deadline_s'] is None for r in data['boxes'])
    au.issue('NOT_APPLICABLE_DEADLINE','demand.first_deadline_s',missing_demand,'无首批要求的品类，不是未知截止时间','保留null；增加has_first_deadline，不填0或均值')
    au.issue('NOT_APPLICABLE_DEADLINE','boxes.first_deadline_s',missing_box,'非首批货箱，不适用首批约束','保留null；以is_first_batch启用约束')
    for r in data['demand']:r['has_first_deadline']=r['first_deadline_s'] is not None
    au.issue('MIXED_TABLE_LAYOUT','5 input workbooks',5,'标题、表头、多个业务区块和合并单元格不能作为样本','按业务表头解析并转为11张整洁表；保留来源行')
    merges=sum(len(m['merge_ranges']) for m in sheet_meta)
    au.issue('MERGED_CELLS','all workbooks',merges,'合并单元格的从属空白是版式结构，不是业务缺失','只读取定义字段；通信表B:C合并时忽略C列')
    au.issue('EMPTY_RESULT_TEMPLATE','结果提交模板.xlsx',len(books['结果提交模板.xlsx']),'模板仅含字段定义，空白结果不计入输入数据缺失','填充Q1—Q4六张源表，另附Q3运输与逐箱补充；Q4配置与缺口解释见独立报告')
    # DEM整幅数值、坐标、NoData和MAT对照。
    tif=first_file(raw,'*.tif');mat=first_file(raw,'*DEM.mat')
    with rasterio.open(tif) as ds:
        arr=ds.read(1);profile=ds.profile.copy();transform=ds.transform;crs=ds.crs;original_nodata=ds.nodata
    m=loadmat(mat);valid=np.isfinite(arr)&(arr!=CFG.nodata_value);av=arr[valid].astype(float)
    au.check('DEM 1-band WGS84',profile['count']==1 and crs.to_epsg()==4326)
    au.check('DEM valid cells all',bool(valid.all()),f'invalid={int((~valid).sum())}')
    au.check('DEM MAT values exact',arr.shape==m['dem'].shape and np.array_equal(arr,m['dem']))
    au.check('DEM MAT coordinate transform',np.allclose(np.asarray(tuple(transform)[:6]),m['transform'].ravel(),rtol=0,atol=CFG.geometry_tolerance))
    lon=transform.c+(np.arange(arr.shape[1])+.5)*transform.a
    lat=transform.f+(np.arange(arr.shape[0])+.5)*transform.e
    au.check('DEM MAT longitude axis',np.allclose(lon,m['longitude'].ravel(),rtol=0,atol=CFG.geometry_tolerance))
    au.check('DEM MAT latitude axis',np.allclose(lat,m['latitude'].ravel(),rtol=0,atol=CFG.geometry_tolerance))
    au.check('DEM MAT EPSG/nodata',int(m['epsg_code'][0,0])==crs.to_epsg() and float(m['nodata'][0,0])==CFG.nodata_value)
    profile.update(nodata=CFG.nodata_value,compress='deflate',predictor=3)
    with rasterio.open(clean/'geospatial/dem_clean.tif','w',**profile) as dst:dst.write(arr,1)
    np.savez_compressed(clean/'geospatial/dem_clean.npz',dem=arr,longitude=lon,latitude=lat,transform=np.asarray(tuple(transform)[:6]),epsg=np.int32(4326),nodata=np.float32(CFG.nodata_value))
    if original_nodata is None:au.issue('MISSING_NODATA_METADATA',tif.name,1,'说明与MAT约定-32767，但GeoTIFF未声明NoData','仅补齐NoData元数据，全部高程值保持不变','warning','实际不存在-32767或非有限像元')
    q1,med,q3=np.quantile(av,[.25,.5,.75]);iqr=q3-q1
    tail=(arr<q1-CFG.iqr_multiplier*iqr)|(arr>q3+CFG.iqr_multiplier*iqr)
    jj,ii=np.where(tail&valid)
    demstats={'rows':int(arr.shape[0]),'cols':int(arr.shape[1]),'total_cells':int(arr.size),'valid_cells':int(valid.sum()),'invalid_cells':int((~valid).sum()),
       'min_m':float(av.min()),'max_m':float(av.max()),'mean_m':float(av.mean()),'std_m':float(av.std()),'q1_m':q1,'median_m':med,'q3_m':q3,
       'iqr_tail_cells':int(tail.sum()),'tail_row_min':int(jj.min()) if len(jj) else None,'tail_row_max':int(jj.max()) if len(jj) else None,
       'tail_col_min':int(ii.min()) if len(ii) else None,'tail_col_max':int(ii.max()) if len(ii) else None,
       'max_adjacent_elevation_difference_m':float(max(np.abs(np.diff(arr,axis=0)).max(),np.abs(np.diff(arr,axis=1)).max())),
       'epsg':4326,'pixel_lon_deg':transform.a,'pixel_lat_deg':abs(transform.e),'original_nodata':original_nodata,'clean_nodata':CFG.nodata_value,
       'mat_values_identical':True,'modified_elevation_cells':0}
    au.issue('DEM_STATISTICAL_TAIL','DEM full raster',int(tail.sum()),'全局IQR高程尾部可对应真实山地，不足以证明坏像元','保留山峰；不截尾、不平滑；输出精确尾部掩码')
    np.savez_compressed(out/'dem_statistical_flags.npz',iqr_tail_mask=tail)
    save_json(out/'dem_quality.json',demstats)
    # 节点统一坐标属性；题定海拔与DEM差异只审核不覆盖。
    depot=data['depots'][0];aeqd=CRS.from_proj4(f'+proj=aeqd +lat_0={depot["lat_deg"]} +lon_0={depot["lon_deg"]} +datum=WGS84 +units=m +no_defs')
    trans=Transformer.from_crs('EPSG:4326',aeqd,always_xy=True);nodes=[];elev=[]
    for rr,role in [(r,'depot') for r in data['depots']]+[(r,'service') for r in data['services']]:
        r=rr.copy();r['role']=role;r['population']=r.get('population');c0,r0=(~transform)*(r['lon_deg'],r['lat_deg']);row,col=math.floor(r0),math.floor(c0)
        inside=0<=row<arr.shape[0] and 0<=col<arr.shape[1]
        au.check(r['node_id']+' valid coordinates',inside and -180<=r['lon_deg']<=180 and -90<=r['lat_deg']<=90)
        if not inside:continue
        r['dem_at_node_m']=float(arr[row,col]);r['elevation_difference_m']=r['ground_elevation_m']-r['dem_at_node_m']
        r['x_m'],r['y_m']=trans.transform(r['lon_deg'],r['lat_deg']);r['dem_row']=row;r['dem_col']=col
        r['work_altitude_m']=r['ground_elevation_m']+(CFG.depot_work_height_m if role=='depot' else CFG.service_work_height_m)
        nodes.append(r);elev.append({'node_id':r['node_id'],'given_ground_m':r['ground_elevation_m'],'dem_pixel_m':r['dem_at_node_m'],
             'difference_m':r['elevation_difference_m'],'review_gt_threshold':abs(r['elevation_difference_m'])>CFG.elevation_review_threshold_m,'action':'retain_given_node_elevation'})
    data['nodes']=nodes
    large=[r for r in elev if r['review_gt_threshold']]
    au.issue('NODE_DEM_ELEVATION_DIFFERENCE','nodes',len(large),'题定点高程与DSM像元高程差异超过审核阈值，不等于数据错误',
             '节点作业高度仍用xlsx；航线净空用DEM；另做全部节点取DEM的敏感性对照','warning',','.join(r['node_id'] for r in large))
    repeated_names={k:v for k,v in Counter(r['name'] for r in data['services']).items() if v>1}
    au.issue('REPEATED_SERVICE_NAMES','services.name',sum(repeated_names.values()),'不同服务区可以同名，不能按名称去重','以S001—S015唯一ID为主键保留',details=str(repeated_names))
    # GeoCSV全行、全字段扫描 + MAT逐单元格交叉验证 + 拓扑审核。
    geo_summaries=[];matcomp=[];geofeatures={};name_placeholders=0;georows=0;geofieldprofiles=[];name_changes=[]
    for p in sorted(raw.rglob('*.csv')):
        original=read_csv(p);georows+=len(original)
        basename=('settlements' if '村镇点位' in p.name else 'roads' if '道路' in p.name else 'water_polygons' if '水体' in p.name else 'water_lines')
        rows=[]
        for i,rr in enumerate(original):
            r={GEO_COLS[k]:coerce(v,GEO_NUMERIC.get(GEO_COLS[k],str)) for k,v in rr.items()}
            r['name_raw']=r['name'];r['name_missing']=r['name'] in ('','未记录')
            if r['name_missing']:r['name']=None
            r['source_csv_row']=i+2;rows.append(r)
        namenum=sum(r['name_missing'] for r in rows);name_placeholders+=namenum
        for col in original[0]:
            vals=[r[col] for r in original]
            geofieldprofiles.append({'dataset':basename,'source_field':col,'rows':len(vals),
                'literal_empty_count':sum(v=='' for v in vals),'placeholder_unknown_count':sum(v=='未记录' for v in vals),
                'unique_values':len(set(vals)),'clean_field':GEO_COLS[col]})
        for r in rows:
            if r['name_missing']:name_changes.append({'source_file':p.name,'source_row':r['source_csv_row'],'feature_id':r['feature_id'],
                 'field':'name','old':'未记录','new':None,'rule':'保留原文于name_raw，语义缺失转null并标志'})
        if namenum:au.issue('UNKNOWN_FEATURE_NAME',p.name,namenum,'未记录是名称未知的语义占位，坐标与要素仍有效','name置null，name_raw保留原文，并新增name_missing标志')
        keyfields=['feature_id']+([k for k in ('polygon_id','ring_id','vertex_index') if k in rows[0]])
        au.check(basename+' unique row keys',len(rows)==len({tuple(r[k] for k in keyfields) for r in rows}))
        au.check(basename+' finite coordinates',all(math.isfinite(r[k]) for r in rows for k in ('lon_deg','lat_deg')))
        au.check(basename+' DEM coverage',all(0<=(~transform*(r['lon_deg'],r['lat_deg']))[0]<arr.shape[1] and 0<=(~transform*(r['lon_deg'],r['lat_deg']))[1]<arr.shape[0] for r in rows))
        au.check(basename+' category present',all(r['category'] for r in rows))
        groups=defaultdict(list)
        groupfields=['feature_id']+([k for k in ('polygon_id','ring_id') if k in rows[0]])
        for r in rows:groups[tuple(r[k] for k in groupfields)].append(r)
        closed=0;adjdup=0;invalid=0;features=[];polygon_parts=defaultdict(list)
        for key,grp in groups.items():
            xy=[(r['lon_deg'],r['lat_deg']) for r in grp]
            if 'vertex_index' in grp[0]:
                au.check(basename+str(key)+' vertex ordering',[r['vertex_index'] for r in grp]==list(range(1,len(grp)+1)))
                adjdup+=sum(a==b for a,b in zip(xy,xy[1:]));closed+=int(xy[0]==xy[-1])
            if basename=='water_polygons':
                geo=Polygon(xy)
                au.check(basename+str(key)+' ring closure',xy[0]==xy[-1] and len(xy)>=4)
                polygon_parts[key[:2]].append((key[2],xy))
            else:geo=Point(xy[0]) if basename=='settlements' else LineString(xy)
            invalid+=int(not geo.is_valid)
            au.check(basename+str(key)+' geometry',geo.is_valid,explain_validity(geo))
            if basename!='water_polygons':
                prop={k:grp[0][k] for k in ('feature_id','name','name_raw','name_missing','category','osm_id')}
                features.append({'type':'Feature','properties':prop,'geometry':mapping(geo)})
        if basename=='water_polygons':
            for key,parts in polygon_parts.items():
                parts.sort();geo=Polygon(parts[0][1],[xy for _,xy in parts[1:]])
                au.check('polygon with holes '+str(key),geo.is_valid,explain_validity(geo))
                r=next(r for r in rows if (r['feature_id'],r['polygon_id'])==key)
                prop={k:r[k] for k in ('feature_id','name','name_raw','name_missing','category','osm_id','polygon_id')}
                features.append({'type':'Feature','properties':prop,'geometry':mapping(geo)})
        write_csv(clean/'geospatial'/f'{basename}.csv',rows)
        save_json(clean/'geospatial'/f'{basename}.geojson',{'type':'FeatureCollection','features':features})
        geofeatures[basename]=features
        comp=read_mat_table_compare(p.with_suffix('.mat'),original);matcomp.append(comp)
        au.check(basename+' full MAT CSV equality',comp['all_equal'],comp)
        geo_summaries.append({'dataset':basename,'source':p.name,'rows':len(rows),'features':len({r['feature_id'] for r in rows}),
            'parts':len(groups),'literal_empty_cells':sum(v=='' for rr in original for v in rr.values()),'unknown_name_rows':namenum,'unknown_name_features':len({r['feature_id'] for r in rows if r['name_missing']}),
            'duplicate_primary_keys':len(rows)-len({tuple(r[k] for k in keyfields) for r in rows}),
            'closed_paths_or_rings':closed,'consecutive_duplicate_vertices':adjdup,'invalid_ring_or_line_count':invalid,
            'lon_min':min(r['lon_deg'] for r in rows),'lon_max':max(r['lon_deg'] for r in rows),
            'lat_min':min(r['lat_deg'] for r in rows),'lat_max':max(r['lat_deg'] for r in rows),
            'mat_compared_cells':comp['compared_cells'],'mat_mismatch_cells':comp['mismatch_count']})
    # 不把闭环末点、线要素连接端点当重复样本删除。
    au.issue('LEGITIMATE_CLOSURE_POINTS','geospatial rings/roads',sum(r['closed_paths_or_rings'] for r in geo_summaries),
             '闭环首末坐标重复是拓扑结构；不是重复记录','保留顶点顺序与闭合点；去重检查使用复合主键')
    # HTML/PDF/DOCX结构完整性覆盖；不把底图文件当作新的独立观测数据重复建模。
    inventory=[]
    for path in sorted(raw.rglob('*')):
        if not path.is_file():continue
        crc_ok=True
        if path.suffix in ('.xlsx','.docx'):
            with zipfile.ZipFile(path) as z:crc_ok=z.testzip() is None
        if path.suffix=='.pdf':crc_ok=path.read_bytes().startswith(b'%PDF-') and b'%%EOF' in path.read_bytes()[-1024:]
        if path.suffix=='.html':
            text=path.read_text('utf-8-sig');crc_ok='<html' in text.lower() and '</html>' in text.lower()
            external=len(re.findall(r'https?://',text))
            au.issue('HTML_EXTERNAL_RESOURCES',path.name,external,'交互地图含在线底图/脚本引用，离线展示不保证可用','保留原始HTML；计算只使用本地数值数据，另输出离线PNG')
        au.check('file structure '+path.name,crc_ok)
        inventory.append({'relative_path':str(path.relative_to(raw)),'bytes':path.stat().st_size,'sha256':sha256(path),'structure_ok':crc_ok,
         'role': 'source_statement' if path.suffix=='.docx' else 'documentation' if path.suffix in ('.pdf','.html') else 'result_template' if path.name=='结果提交模板.xlsx' else 'input_data'})
    au.issue('ENERGY_SUBFORMULA_NOT_EXPANDED','题面 附录2',2,'题面定义E=E_hor+E_up但未展开两分项；不是可从表格直接核验的确定公式',
      '在解题文档明确列为补充假设：E_hor=E_use*d/L(q)，E_up=(m0+q)gh/(eta*3.6e6)；结果以此口径为条件','warning')
    au.issue('GEOSPATIAL_DOCUMENT_EXTENSION','题面附录1与实际附件',1,'题面写地理说明docx，压缩包实际提供同名pdf','以实际PDF作为附件说明，保留原文件，不视为缺少DEM')
    for name,rows in data.items():write_csv(clean/f'{name}.csv',rows)
    save_json(clean/'model_inputs.json',data)
    save_json(clean/'schema.json',{'tables':dictionary,'null_policy':'CSV空字符串/JSON null；只表示不适用或有标志的名称未知；核心必填字段不得缺失',
           'coordinate_crs':'EPSG:4326','local_feature_crs_wkt':aeqd.to_wkt(),'note':'物理模型保留m、s、kg、m³、kWh，不做破坏单位意义的z-score转换。'})
    write_csv(out/'file_inventory.csv',inventory)
    write_csv(out/'field_quality_profiles.csv',au.profiles)
    write_csv(out/'statistical_outliers.csv',au.outliers,fields=['table','record_key','field','value','iqr_flag','modified_z','mad_flag','action'])
    write_csv(out/'cleaning_changes.csv',au.changes,fields=['table','row','field','old','new','reason'])
    write_csv(out/'demand_box_reconciliation.csv',demand_comparison)
    distribution=[]
    for r in data['services']:
        bb=[b for b in data['boxes'] if b['service_id']==r['node_id']]
        distribution.append({'service_id':r['node_id'],'population':r['population'],'boxes':len(bb),
          'weight_kg':sum(b['weight_kg'] for b in bb),'volume_m3':sum(b['volume_m3'] for b in bb),
          'first_batch_boxes':sum(b['is_first_batch'] for b in bb),'box_per_person':len(bb)/r['population']})
    write_csv(out/'service_demand_distribution.csv',distribution)
    write_csv(out/'node_dem_comparison.csv',elev)
    write_csv(out/'geospatial_quality.csv',geo_summaries)
    write_csv(out/'mat_csv_crosscheck.csv',matcomp)
    write_csv(out/'geospatial_field_profiles.csv',geofieldprofiles)
    write_csv(out/'geospatial_name_changes.csv',name_changes)
    write_csv(out/'business_checks.csv',au.checks)
    write_csv(out/'issues_and_actions.csv',au.issues)
    save_json(out/'xlsx_layout_audit.json',[{k:v for k,v in m.items() if k!='cells'} for m in sheet_meta])
    save_json(out/'xlsx_cells_audit.json',sheet_meta)
    before_after=[]
    for key,rows in data.items():
        before_after.append({'dataset':key,'before_business_rows':len(rows),'after_rows':len(rows),'deleted_business_rows':0,'imputed_physical_values':0})
    for r in geo_summaries:before_after.append({'dataset':r['dataset'],'before_business_rows':r['rows'],'after_rows':r['rows'],'deleted_business_rows':0,'imputed_physical_values':0})
    before_after.append({'dataset':'DEM_pixels','before_business_rows':arr.size,'after_rows':arr.size,'deleted_business_rows':0,'imputed_physical_values':0})
    write_csv(out/'before_after.csv',before_after)
    summary={'raw_file_count':len(inventory),'input_workbooks':5,'template_sheets':len(books['结果提交模板.xlsx']),
        'normalized_business_tables':len(data)-1,'nodes':len(nodes),'services':len(data['services']),'boxes':len(data['boxes']),
        'demand_rows':len(data['demand']),'total_weight_kg':sum(b['weight_kg'] for b in data['boxes']),
        'total_volume_m3':sum(b['volume_m3'] for b in data['boxes']),'total_population':sum(s['population'] for s in data['services']),
        'first_batch_boxes':sum(b['is_first_batch'] for b in data['boxes']),
        'not_applicable_demand_deadlines':missing_demand,'not_applicable_box_deadlines':missing_box,
        'unexpected_missing_core_cells':sum(p['missing_count'] for p in au.profiles if p['missing_class']=='unexpected'),
        'duplicate_core_primary_keys':duplicates,'geospatial_vertex_rows':georows,'unknown_feature_name_rows':name_placeholders,
        'statistical_flagged_field_records':len(au.outliers),'node_elevation_review_count':len(large),
        'max_abs_node_dem_difference_m':max(abs(r['difference_m']) for r in elev),
        'valid_dem_cells':int(valid.sum()),'dem_iqr_tail_cells':demstats['iqr_tail_cells'],
        'mat_csv_compared_cells':sum(r['compared_cells'] for r in matcomp),'mat_csv_mismatch_cells':sum(r['mismatch_count'] for r in matcomp),
        'checks_total':len(au.checks),'checks_passed':sum(r['pass'] for r in au.checks),'checks_failed':sum(not r['pass'] for r in au.checks),
        'physical_values_overwritten':0,'boxes_removed':0,'issues':au.issues,'dataset_row_counts':{k:len(v) for k,v in data.items()},
        'material_counts':dict(Counter(b['material_type'] for b in data['boxes']))}
    save_json(out/'quality_summary.json',summary)
    if summary['checks_failed']:raise ValueError(f'质量检查有{summary["checks_failed"]}项失败，详情见results/quality/business_checks.csv')
    return data,summary
