"""打包已核验的绘图和论文工程。不会重新求解，也不会替换任何实算数据。"""
from pathlib import Path
import json,hashlib,zipfile,shutil,html,re
import fitz
ROOT=Path(__file__).resolve().parent
DEST=ROOT.parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def putzip(path,files,prefix=''):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p,rel in files:z.write(p,prefix+rel)
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        assert all(not x.lower().endswith(('.ttf','.otf','.ttc','.woff','.woff2','.pfb','.pfa')) for x in z.namelist())
    return {'path':path.name,'files':len(files),'bytes':path.stat().st_size,'sha256':sha(path)}

def main():
    status=json.loads((ROOT/'audit/figure_validation.json').read_text());assert status['failed']==0
    ov=ROOT/'overleaf';selected=['main.tex','my_paper.cls','.latexmkrc','README.md','figure_catalog.csv','论文完整源码_可复制.txt','optional_panels.tex']
    files=[(ov/n,n) for n in selected]+[(p,p.relative_to(ov).as_posix()) for p in sorted((ov/'figures').glob('*.pdf'))]
    full=DEST/'D题_科学图表原生重绘_Overleaf工程.zip';fullinfo=putzip(full,files)
    replacement=DEST/'D题_科学图表原生重绘_Overleaf替换包.zip'
    patchfiles=[(ov/n,n) for n in ['main.tex','figure_catalog.csv','optional_panels.tex','README.md']]+[(p,p.relative_to(ov).as_posix()) for p in sorted((ov/'figures').glob('*.pdf'))]
    patchinfo=putzip(replacement,patchfiles)
    shutil.copy2(ov/'main.pdf',DEST/'D题_科学图表原生重绘_论文预览.pdf')
    shutil.copy2(ROOT/'论文联合诊断图册.pdf',DEST/'D题_科学图表联合诊断图册.pdf')
    package_dir=ROOT/'直接上传包';package_dir.mkdir(exist_ok=True)
    shutil.copy2(full,package_dir/full.name);shutil.copy2(replacement,package_dir/replacement.name)
    # 离线图件浏览器，无卡片UI，无网络脚本。
    rows=json.loads((ROOT/'audit/render_manifest.json').read_text());panels=json.loads((ROOT/'audit/panels_manifest.json').read_text())
    doc=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>科学图表原生重绘</title><style>body{max-width:1400px;margin:30px auto;font:16px sans-serif;color:#253342;background:white}h1{font-size:26px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:32px}figure{margin:0}img{width:100%;height:auto}figcaption{font-size:14px;margin:10px 0}a{color:#466c96}</style><h1>科学图表原生重绘</h1><p>所有图均由实算CSV、JSON或DEM重画；模型扫参和横截面分布不是新增现场实验。</p><h2>六幅联合诊断图</h2><div class="grid">']
    for row in panels:
        c=row['图号'];doc.append(f'<figure><a href="figures/{c}.pdf"><img loading="lazy" src="figures/{c}.png"></a><figcaption>{c} {html.escape(row["中文图题"])}<br>{html.escape(row["说明"])}</figcaption></figure>')
    doc.append('</div><h2>163幅独立图</h2><div class="grid">')
    for row in rows:
        c=row['图号'];doc.append(f'<figure><a href="figures/{c}.pdf"><img loading="lazy" src="figures/{c}.png"></a><figcaption>{c} {html.escape(row["中文图题"])} · <a href="plot_data/{c}.json">数据与来源</a></figcaption></figure>')
    doc.append('</div></html>');(ROOT/'图表浏览.html').write_text('\n'.join(doc),encoding='utf-8')
    # 保留可运行源程序和原求解包；移除无用Python缓存和TeX中间文件。
    prohibited={'.aux','.xdv','.fdb_latexmk','.fls','.toc','.out','.gz'}
    payload=[]
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.name in ('MANIFEST.sha256','package_summary.json'):continue
        rel=p.relative_to(ROOT).as_posix()
        if rel.startswith('overleaf/') and (p.suffix in prohibited or p.name=='main.log'):continue
        payload.append((p,rel))
    manifest='\n'.join(sha(p)+'  '+rel for p,rel in payload)+'\n';(ROOT/'MANIFEST.sha256').write_text(manifest,encoding='utf-8');payload.append((ROOT/'MANIFEST.sha256','MANIFEST.sha256'))
    master=DEST/'D题_科学图表原生重绘_完整交付.zip';masterinfo=putzip(master,payload,'D_scientific_redesign/')
    with zipfile.ZipFile(master) as z:
        for line in manifest.splitlines():
            h,rel=line.split('  ',1)
            assert hashlib.sha256(z.read('D_scientific_redesign/'+rel)).hexdigest()==h
    summary={'master':masterinfo,'overleaf':fullinfo,'replacement':patchinfo,'plots_independent':163,'plots_composites':6,'figure_formats':['PNG','SVG','PDF'],'selected_in_paper':29,'paper_pages':len(fitz.open(ov/'main.pdf')),'plot_checks':status,'zip_crc_ok':True,'all_payload_hashes_ok':True,'font_files_distributed':False}
    (ROOT/'package_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(DEST/'D题_原生重绘交付核验.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
