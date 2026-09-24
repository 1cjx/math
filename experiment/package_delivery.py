#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包已求解且通过模板验收的完整工程。Python 3.13.5；仅用标准库。
先运行 python run_all.py --check-reference，再运行本脚本。
不重新优化；打包前会从最终结果工作簿独立重算并验证，失败则停止。
"""
from __future__ import annotations
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
DEFAULT_ARCHIVE = 'D题_四问闭环验证_中文图与论文大纲_最终交付.zip'
EXCLUDED_DIRECTORIES = frozenset({'__pycache__', '.matplotlib_cache', '.venv', '.git'})
EXCLUDED_SUFFIXES = frozenset({'.pyc', '.pyo', '.nbc', '.nbi', '.ttf', '.otf', '.ttc', '.woff', '.woff2'})
COMPRESSION_LEVEL = 6


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def visible_files() -> list[Path]:
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
                  and not EXCLUDED_DIRECTORIES.intersection(p.relative_to(ROOT).parts)
                  and p.suffix not in EXCLUDED_SUFFIXES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / DEFAULT_ARCHIVE)
    args = parser.parse_args()
    output = args.output.resolve()
    if ROOT == output or ROOT in output.parents:
        raise ValueError('压缩包请放在工程目录之外，避免递归打包。')
    sys.path.insert(0, str(ROOT/'src'))
    from final_consistency import run_final_consistency
    run_final_consistency(ROOT)
    subprocess.run([sys.executable, str(ROOT / 'validate_submission.py')], cwd=ROOT, check=True)
    acceptance = json.loads((ROOT / 'submission/提交验收.json').read_text(encoding='utf-8'))
    if any(acceptance[k] for k in ('cell_checks_failed', 'q1_workbook_physics_failed', 'q2_workbook_physics_failed','q3_workbook_physics_failed','companion_cell_checks_failed','q4_workbook_partition_failed','q4_workbook_inheritance_failed','q4_workbook_physics_failed')):
        raise AssertionError('结果模板未通过验收，禁止打包。')
    source_files = list((ROOT / 'data/raw').rglob('*'))
    source_count = sum(p.is_file() for p in source_files)
    files = [p for p in visible_files() if p.name not in ('manifest.json', 'MANIFEST.sha256')]
    manifest = {
        'delivery': 'D题全量清洗及Q1—Q4完整求解、冻结继承与独立核验',
        'scope': ['数据质量与标准化清洗', '问题一', '问题二', '问题三', '问题四'],
        'not_solved': [],
        'official_template': 'submission/结果提交.xlsx',
        'required_Q3_companion': 'submission/Q3运输与逐箱补充.xlsx',
        'Q4_condition': '最终Q3已满足严格三分区；Q4不复制或重排任何中继任务，独立执行资源需求仍需按类型增补；见提交必读' ,
        'source_files': source_count,
        'content_files_excluding_manifests': len(files),
        'bytes_excluding_manifests': sum(p.stat().st_size for p in files),
        'files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in files],
        'note': 'SHA-256用于文件完整性，不表示物理假设获得外部确认；数学适用条件见报告。'
    }
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    checksum_files = [p for p in visible_files() if p.name != 'MANIFEST.sha256']
    (ROOT / 'MANIFEST.sha256').write_text(''.join(f'{sha256(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in checksum_files), encoding='utf-8')
    files = visible_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=COMPRESSION_LEVEL) as archive:
        for path in files:
            archive.write(path, arcname=(Path(ROOT.name) / path.relative_to(ROOT)).as_posix())
    with zipfile.ZipFile(output) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise AssertionError('压缩包CRC校验失败：' + bad_member)
        for item in manifest['files']:
            payload=archive.read(str(Path(ROOT.name)/item['path']))
            if hashlib.sha256(payload).hexdigest()!=item['sha256']:
                raise AssertionError('压缩包逐项SHA-256失败：'+item['path'])
    checksum = sha256(output)
    output.with_suffix('.sha256.txt').write_text(f'{checksum}  {output.name}\n', encoding='utf-8')
    print(json.dumps({'archive': str(output), 'files': len(files), 'bytes': output.stat().st_size,
                      'MiB': output.stat().st_size / (1024 ** 2), 'crc_verified': True,
                      'sha256': checksum}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
