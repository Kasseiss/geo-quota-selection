"""Rebuild every submission file and check the upload package.

Outputs in paper/v3/submission/:
  manuscript.docx                  Word main text on the MDPI Sensors template (upload option A)
  manuscript_latex.zip             LaTeX main text: manuscript.tex + Definitions/ + figures/ (upload option B)
  manuscript.pdf                   PDF compiled from the LaTeX source (optional "upload PDF")
  manuscript_word.pdf              PDF of the Word version, for checking
  supplementary_materials.docx/.pdf  uploaded separately as supplementary files, never inside the zip
  cover_letter.docx
The LaTeX zip is unpacked into a fresh temporary folder and compiled there to prove it is self-contained.
"""
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.shared import Pt

import v3_text as T
import v3_build_docx
import v3_build_latex
import v3_build_supplement
from v3_common import ROOT

SUB = ROOT / 'paper/v3/submission'


def word_to_pdf(src, dst):
    ps = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0; "
          f"try {{ $d = $w.Documents.Open('{src}', $false, $true); $d.Repaginate(); "
          f"$d.ExportAsFixedFormat('{dst}', 17); $d.Close($false) }} finally {{ $w.Quit() }}")
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps], check=True, timeout=300)


def cover_letter():
    d = Document()
    st = d.styles['Normal']; st.font.name = 'Palatino Linotype'; st.font.size = Pt(11)
    for text in [
        'Dear Editor,',
        f'We submit the manuscript "{T.TITLE}" for consideration as an Article in Sensors.',
        'Choosing which few images to label is often the first decision in a new land cover mapping project. The '
        'standard answer, picking images that are as different as possible in a pretrained feature space, turns out to '
        'select unusual images at very small budgets. Across 576 main fits and a complete second execution of the eight '
        'base rules, farthest-point selection was the weakest rule, and a simple allocation of images across source '
        'regions repaired most of the loss (+1.68 and +2.24 mIoU points on 24 regions never used for training). '
        'Size-matched placebo groups and an equal-label experiment separate this gain from grouping as such and from '
        'labeled-pixel counts, and we report openly which effects survive these controls and which do not.',
        'The study uses public OpenEarthMap imagery and requires no ethics approval. The complete record of selections, '
        'per-image confusion matrices, training logs and plotting code accompanies the submission, and every number in '
        'the paper can be recomputed from it. Generative AI assistance is declared in the manuscript.',
        'This manuscript has not been published and is not under consideration elsewhere. All authors have approved '
        'the submission and declare no conflicts of interest. [Authors: please confirm or edit these statements.]',
        'Sincerely,',
        '[Corresponding author name, affiliation, e-mail]',
    ]:
        d.add_paragraph(text)
    d.save(SUB / 'cover_letter.docx')


def main():
    SUB.mkdir(parents=True, exist_ok=True)
    v3_build_docx.main()
    assert v3_build_latex.main() == 0
    v3_build_supplement.main()
    cover_letter()
    tex = v3_build_latex.TEX_DIR
    shutil.copy(tex / 'manuscript.pdf', SUB / 'manuscript.pdf')
    word_to_pdf(SUB / 'manuscript.docx', SUB / 'manuscript_word.pdf')
    word_to_pdf(SUB / 'supplementary_materials.docx', SUB / 'supplementary_materials.pdf')

    zpath = SUB / 'manuscript_latex.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(tex / 'manuscript.tex', 'manuscript.tex')
        for f in sorted((tex / 'Definitions').rglob('*')) + sorted((tex / 'figures').rglob('*')):
            if f.is_file():
                z.write(f, f.relative_to(tex).as_posix())
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tmp)
            names = z.namelist()
        for _ in range(2):
            r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'manuscript.tex'], cwd=tmp,
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        ok = r.returncode == 0 and (Path(tmp) / 'manuscript.pdf').exists()
    assert not any('supplement' in n.lower() for n in names), 'supplementary file inside the main-text zip'
    print(f'zip: {len(names)} files, {zpath.stat().st_size / 1e6:.1f} MB, clean-folder compile ok = {ok}')
    for f in sorted(SUB.iterdir()):
        if f.is_file():
            print(f'  {f.name:34s} {f.stat().st_size / 1e6:6.2f} MB')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
