#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""D_scientific_redesign: remove the Cairo DLL requirement from PDF export.

Run in the project root with the same interpreter used for plotting:
    .\.venv\Scripts\python.exe fix_windows_cairo.py

Python >= 3.10; this patch script uses only the standard library.
It edits ONLY the Cairo import and PDF-export statement in viz/core.py,
keeps your visual edits, creates a byte-exact backup, and never touches
experiment/, overleaf/main.tex, CSV values, or optimization parameters.
The new exporter uses Matplotlib's native PDF backend with Type-3 glyphs.
The PNG/SVG code and the plotted numerical objects remain unchanged.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

MARKER = 'D_NATIVE_PDF_PATCH_V1'
ALIAS = '_native_pdf_backend'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_text(text: str) -> tuple[str, bool]:
    """Return minimally edited source; reject unknown layouts instead of guessing."""
    tree = ast.parse(text)
    if MARKER in text:
        if any(isinstance(n, ast.Import) and any(a.name == 'cairosvg' for a in n.names)
               for n in ast.walk(tree)):
            raise ValueError('发现补丁标记，但仍有cairosvg导入；请先检查core.py。')
        return text, False

    imports = [n for n in tree.body if isinstance(n, ast.Import)
               and len(n.names) == 1 and n.names[0].name == 'cairosvg'
               and n.names[0].asname is None]
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Publisher']
    if len(imports) != 1 or len(classes) != 1:
        raise ValueError('core.py与补丁识别的结构不同：未找到唯一的import cairosvg和Publisher。原文件未改。')
    methods = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == 'save']
    if len(methods) != 1:
        raise ValueError('没有找到唯一的Publisher.save()；原文件未改。')
    method = methods[0]
    if 'fig' not in {a.arg for a in method.args.args}:
        raise ValueError('Publisher.save()没有fig参数，不能安全修复。')
    statements = [n for n in ast.walk(method) if isinstance(n, ast.Expr)
                  and isinstance(n.value, ast.Call)
                  and isinstance(n.value.func, ast.Attribute)
                  and isinstance(n.value.func.value, ast.Name)
                  and n.value.func.value.id == 'cairosvg'
                  and n.value.func.attr == 'svg2pdf']
    if len(statements) != 1:
        raise ValueError('未找到唯一的cairosvg.svg2pdf(...)导出语句；原文件未改。')
    statement = statements[0]
    call = statement.value
    kwargs = {k.arg: k.value for k in call.keywords}
    if call.args or set(kwargs) != {'bytestring', 'write_to'}:
        raise ValueError('导出调用含非标准参数，补丁不会擅自丢弃这些参数。原文件未改。')
    if not any(isinstance(n, ast.Name) and n.id == 'bbox' for n in ast.walk(method)):
        raise ValueError('未找到原导出边界bbox；原文件未改。')
    destination = ast.get_source_segment(text, kwargs['write_to'])
    if not destination:
        raise ValueError('无法读出原PDF输出路径；原文件未改。')

    # Refuse unexpected remaining uses of the old dependency.
    all_uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == 'cairosvg']
    if len(all_uses) != 1:
        raise ValueError('core.py还有其他cairosvg用法，不能用本补丁自动处理。')
    if any(isinstance(n, ast.Name) and n.id == ALIAS for n in ast.walk(tree)):
        raise ValueError('新导入别名与现有变量重名；原文件未改。')

    lines = text.splitlines(keepends=True)
    newline = '\r\n' if '\r\n' in text else '\n'
    indent = lines[statement.lineno - 1][:statement.col_offset]
    before = indent + '# PDF由当前Figure直接导出；不调用Cairo或SVG转换器。'
    replacement = [
        before,
        indent + f'with {ALIAS}.rc_context({{"pdf.fonttype": 3, "pdf.use14corefonts": False}}):',
        indent + '    fig.savefig(',
        indent + f'        {destination},',
        indent + '        format="pdf", backend="pdf",',
        indent + '        bbox_inches=bbox, pad_inches=0,',
        indent + '        metadata={"CreationDate": None, "ModDate": None,',
        indent + '                  "Creator": "D scientific figures / native Matplotlib PDF"},',
        indent + '    )',
    ]
    edits = [
        (imports[0].lineno - 1, imports[0].end_lineno,
         [f'import matplotlib as {ALIAS}  # {MARKER}' + newline]),
        (statement.lineno - 1, statement.end_lineno, [v + newline for v in replacement]),
    ]
    for start, end, new_lines in sorted(edits, reverse=True):
        lines[start:end] = new_lines
    result = ''.join(lines)
    # Update the old exporter comment, without changing numerical or style logic.
    result = result.replace(
        '# SVG中的中文字形已转为路径，PDF从本次原生SVG转换；不嵌入字体文件。',
        '# SVG保留中文字形路径；PDF用原生后端嵌入所需字形，无需系统Cairo动态库。')
    compile(result, 'viz/core.py', 'exec')
    return result, True


def atomic_write(path: Path, content: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', prefix=path.name + '.', suffix='.tmp',
                                         dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description='修复绘图导出对Windows Cairo DLL的依赖；自动备份，不改数据。')
    parser.add_argument('--root', type=Path, help='工程根目录；默认优先当前目录，再使用脚本所在目录。')
    parser.add_argument('--dry-run', action='store_true', help='只检查可否修复，不改任何文件。')
    args = parser.parse_args()
    roots = [args.root] if args.root else [Path.cwd(), Path(__file__).resolve().parent]
    root = next((p.resolve() for p in roots if p and (p / 'viz' / 'core.py').is_file()), None)
    if root is None:
        print('没有找到viz/core.py。请把本脚本放进D_scientific_redesign根目录后运行。', file=sys.stderr)
        return 1
    target = root / 'viz' / 'core.py'
    try:
        raw = target.read_bytes()
        encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
        original = raw.decode(encoding)
        changed_text, changed = patch_text(original)
        if not changed:
            print('补丁已安装，无需重复修改。')
            print('现在重新运行：redraw_selected_local.py F012')
            return 0
        if args.dry_run:
            print('识别成功：只需替换Cairo导入和PDF导出语句。尚未修改文件。')
            return 0
        new_bytes = changed_text.encode(encoding)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = target.with_name(f'core.py.before_cairo_fix_{stamp}.bak')
        # Exclusive create: never overwrite a previous backup.
        with backup.open('xb') as f:
            f.write(raw)
        if target.read_bytes() != raw:
            raise RuntimeError('修复期间core.py被其他程序改动，已停止；请关闭编辑器写入后重试。')
        atomic_write(target, new_bytes)
        print('修复完成：viz/core.py 已改用Matplotlib原生PDF导出。')
        print(f'原文件完整备份：{backup.name}')
        print('PNG/SVG绘图、数据读取、图表样式和论文正文均未改。')
        print('不需要下载Cairo DLL，也不需要重装虚拟环境。')
        print('下一步：使用当前Python重新运行 redraw_selected_local.py F012')
        try:
            audit = root / 'audit'
            audit.mkdir(exist_ok=True)
            report = {'patch': MARKER, 'changed_file': 'viz/core.py',
                      'backup': backup.relative_to(root).as_posix(),
                      'old_sha256': sha(raw), 'new_sha256': sha(new_bytes),
                      'created_utc': stamp, 'python': sys.version,
                      'scope': 'PDF导出依赖修复；未重新求解或更改实验数据。'}
            (audit / f'windows_cairo_fix_{stamp}.json').write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except OSError as exc:
            print(f'提示：补丁已安装，但审计记录未能保存：{exc}', file=sys.stderr)
        return 0
    except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError) as exc:
        print(f'修复停止：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
