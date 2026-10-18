"""Render through the bundled DOCX rasterizer with installed Word on Windows."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess

SKILL = Path.home() / '.codex/plugins/cache/openai-primary-runtime/documents/26.1017.11052/skills/documents/render_docx.py'
POPPLER = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler'


def convert(doc_path, user_profile, convert_tmp_dir, stem, verbose):
    destination = str(Path(convert_tmp_dir) / (stem + '.pdf'))
    environment = os.environ.copy()
    environment['MDPI_DOCX_INPUT'] = str(Path(doc_path).resolve())
    environment['MDPI_PDF_OUTPUT'] = destination
    script = r'''
$ErrorActionPreference = 'Stop'
$wordApp = $null
$wordDocument = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordApp.AutomationSecurity = 3
    $wordDocument = $wordApp.Documents.Open($env:MDPI_DOCX_INPUT, $false, $true, $false)
    $wordDocument.Repaginate()
    $wordDocument.ExportAsFixedFormat($env:MDPI_PDF_OUTPUT, 17)
} finally {
    if ($null -ne $wordDocument) {
        $wordDocument.Close($false)
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordDocument)
    }
    if ($null -ne $wordApp) {
        $wordApp.Quit()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp)
    }
}
'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env=environment, capture_output=True, timeout=120)
    if result.returncode or not Path(destination).is_file():
        raise RuntimeError('Word conversion failed: ' + result.stderr.decode('utf-8', errors='replace'))
    return destination, 'Installed Word isolated hidden COM conversion'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dpi', type=int, default=140)
    args = parser.parse_args()
    bins = list(POPPLER.rglob('pdftoppm.exe'))
    if not bins: raise RuntimeError('Bundled Poppler missing')
    os.environ['PATH'] = str(bins[0].parent) + os.pathsep + os.environ['PATH']
    spec = importlib.util.spec_from_file_location('v2_packaged_docx_renderer', SKILL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.convert_to_pdf = convert
    pages = module.rasterize(str(args.input.resolve()), str(args.output.resolve()),
                             args.dpi, False, True)
    print(json.dumps({'converter': 'Microsoft Word', 'renderer': str(SKILL),
                      'pages': len(pages), 'output': str(args.output.resolve())}))


if __name__ == '__main__': main()
