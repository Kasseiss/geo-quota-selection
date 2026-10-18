"""Write the LaTeX submission on the official MDPI class (template folder), copy figures as vector PDFs, compile with
pdflatex, and pack the upload zip (main text only; supplementary files are uploaded separately).
"""
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import v3_text as T
from v3_common import ROOT, OUT
from v3_content import REFS, ABBREVIATIONS, Citer, outline

TEMPLATE_ZIP = ROOT.parents[1] / 'template/MDPI_template_ACS (1).zip'
TEX_DIR = ROOT / 'paper/v3/submission/latex'
JOURNAL = 'sensors'

UNI = {'\u2212': '$-$', '\u00d7': '$\\times$', '\u03b2': '$\\beta$', '\u03c1': '$\\rho$', '\u221d': '$\\propto$',
       '\u00b2': '$^{2}$', '\u207b\u2074': '$^{-4}$', '\u207b\u00b3': '$^{-3}$', '\u1d63': '$_{r}$', '\u00b1': '$\\pm$',
       '\u2013': '--', '\u2014': '---', '\u2019': "'", '\u2018': '`', '\u201c': '``', '\u201d': "''", '\u2264': '$\\leq$',
       '\u2265': '$\\geq$', '\u2248': '$\\approx$', '\u00a0': '~', '\u2009': '\\,'}


def esc(text):
    """Escape plain text for LaTeX and map the few non-Latin symbols the manuscript uses."""
    out = []
    for ch in text:
        if ch in '&%$#_{}':
            out.append('\\' + ch)
        elif ch == '~':
            out.append('\\textasciitilde{}')
        elif ch == '^':
            out.append('\\textasciicircum{}')
        elif ch == '\\':
            out.append('\\textbackslash{}')
        else:
            out.append(ch)
    s = ''.join(out)
    for k in sorted(UNI, key=len, reverse=True):
        s = s.replace(k, UNI[k])
    s = re.sub(r'"([^"]+)"', r"``\1''", s)
    s = s.replace('$$', '')  # merge adjacent math produced by consecutive symbols
    return s


def body(text, citer):
    parts, last = [], 0
    for start, end, keys in citer.keys(text):
        parts.append(esc(text[last:start]).rstrip() + '~\\cite{' + ','.join(keys) + '}')
        last = end
    parts.append(esc(text[last:]))
    s = ''.join(parts)
    s = re.sub(r'\bFigure (\d)', r'Figure~\\ref{fig\1}', s)
    s = re.sub(r'\bTable (\d)', r'Table~\\ref{tab\1}', s)
    s = re.sub(r'\bSection (\d)', r'Section~\\ref{sec\1}', s)
    return s


def ref_tex(runs):
    out = []
    for text, style in runs:
        if style == 'url':
            out.append(' \\url{' + text.strip() + '}')
        elif style == 'i':
            out.append('{\\em ' + esc(text) + '}')
        elif style == 'b':
            out.append('{\\bf ' + esc(text) + '}')
        else:
            # URLs inside plain runs ("Available online: ...")
            pieces = re.split(r'(https?://[^\s)]+)', text)
            out.append(''.join('\\url{' + x.rstrip('.') + '}' + ('.' if x.endswith('.') else '')
                               if x.startswith('http') else esc(x) for x in pieces))
    return ''.join(out)


def table_tex(spec, n):
    ncol = len(spec['headers'][-1])
    wide = sum(spec['widths']) > 5.2
    # short columns take their natural width; only long-text columns stretch
    cols = list(zip(*([spec['headers'][-1]] + spec['rows'])))
    short = [max(len(str(v or '')) for v in col) <= 16 for col in cols]
    if all(short):
        short[0] = False
    colspec = ''.join(a if sh else ('L' if a == 'l' else 'C') for a, sh in zip(spec['align'], short))
    lines = ['\\begin{table}[H]', f'\\caption{{{esc(spec["caption"])}\\label{{tab{n}}}}}', '\\small']
    if wide:
        lines += ['\\begin{adjustwidth}{-\\extralength}{0cm}', f'\\begin{{tabularx}}{{\\fulllength}}{{{colspec}}}']
    else:
        lines += [f'\\begin{{tabularx}}{{\\textwidth}}{{{colspec}}}']
    lines.append('\\toprule')
    hdrs = spec['headers']
    if len(hdrs) == 2:
        top, cells, k = hdrs[0], [], 0
        cmid = []
        while k < ncol:
            span = 1
            while k + span < ncol and top[k + span] is None:
                span += 1
            label = top[k]
            if span > 1:
                cells.append(f'\\multicolumn{{{span}}}{{c}}{{\\textbf{{{esc(label)}}}}}')
                cmid.append(f'\\cmidrule(lr){{{k + 1}-{k + span}}}')
            else:
                cells.append(f'\\textbf{{{esc(label)}}}' if label else '')
            k += span
        lines.append(' & '.join(cells) + ' \\\\')
        lines.append(' '.join(cmid))
    lines.append(' & '.join(f'\\textbf{{{esc(h)}}}' if h else '' for h in hdrs[-1]) + ' \\\\')
    lines.append('\\midrule')
    for i, row in enumerate(spec['rows']):
        cells = [f'\\textbf{{{esc(v)}}}' if (i, j) in spec['bold'] else esc(v) for j, v in enumerate(row)]
        lines.append(' & '.join(cells) + ' \\\\')
    lines.append('\\bottomrule')
    lines.append('\\end{tabularx}')
    if wide:
        lines.append('\\end{adjustwidth}')
    lines.append(f'\\noindent{{\\footnotesize{{{esc(spec["notes"])}}}}}')
    lines.append('\\end{table}')
    return '\n'.join(lines)


def figure_tex(name, caption, n, citer):
    return '\n'.join([
        '\\begin{figure}[H]', '\\begin{adjustwidth}{-\\extralength}{0cm}', '\\centering',
        f'\\includegraphics[width=\\fulllength,height=0.74\\textheight,keepaspectratio]{{figures/{name}.pdf}}',
        '\\end{adjustwidth}',
        f'\\caption{{{body(caption, citer)}\\label{{fig{n}}}}}', '\\end{figure}'])


def main():
    if TEX_DIR.exists():
        shutil.rmtree(TEX_DIR)
    (TEX_DIR / 'figures').mkdir(parents=True)
    with zipfile.ZipFile(TEMPLATE_ZIP) as z:
        for m in z.namelist():
            if m.startswith('Definitions/') and not m.endswith('/'):
                (TEX_DIR / m).parent.mkdir(parents=True, exist_ok=True)
                (TEX_DIR / m).write_bytes(z.read(m))
    citer = Citer()
    fig_n = tab_n = sec_n = 0
    parts = []
    for b in outline():
        kind = b[0]
        if kind == 'h1':
            sec_n += 1
            parts.append(f'\\section{{{esc(b[1])}}}\\label{{sec{sec_n}}}')
        elif kind == 'h2':
            parts.append(f'\\subsection{{{esc(b[1])}}}')
        elif kind == 'p':
            parts.append(body(b[1], citer))
        elif kind == 'enum':
            parts.append('\\begin{enumerate}[leftmargin=*,labelsep=4.9mm]\n' +
                         '\n'.join('\\item ' + body(x, citer) for x in b[1]) + '\n\\end{enumerate}')
        elif kind == 'fig':
            fig_n += 1
            shutil.copy(OUT / f'{b[1]}.pdf', TEX_DIR / 'figures' / f'{b[1]}.pdf')
            parts.append(figure_tex(b[1], b[2], fig_n, citer))
        elif kind == 'table':
            tab_n += 1
            parts.append(table_tex(b[1], tab_n))
    back = dict(T.BACK)
    abbrev = '\n'.join(f'{esc(a)} & {esc(b)}\\\\' for a, b in ABBREVIATIONS)
    bib = '\n'.join(f'\\bibitem{{{k}}}\n{ref_tex(REFS[k])}' for k in citer.order)
    unused = set(REFS) - set(citer.order)
    assert not unused, unused
    hl = lambda xs: '\n'.join('\\item ' + esc(x) for x in xs)
    tex = rf"""%  MDPI LaTeX template (Definitions/mdpi.cls), journal option set to {JOURNAL}.
\documentclass[{JOURNAL},article,submit,pdftex,moreauthors]{{Definitions/mdpi}}

\firstpage{{1}}
\makeatletter
\setcounter{{page}}{{\@firstpage}}
\makeatother
\pubvolume{{1}}
\issuenum{{1}}
\articlenumber{{0}}
\pubyear{{2026}}
\copyrightyear{{2026}}
\datereceived{{ }}
\daterevised{{ }}
\dateaccepted{{ }}
\datepublished{{ }}

\newcolumntype{{L}}{{>{{\raggedright\arraybackslash}}X}}

\Title{{{esc(T.TITLE)}}}

% Authors: replace the placeholders below with the real author list, ORCID iDs, affiliations and contact details.
\newcommand{{\orcidauthorA}}{{0000-0000-0000-000X}}
\Author{{Firstname Lastname $^{{1}}$\orcidA{{}}, Firstname Lastname $^{{2}}$ and Firstname Lastname $^{{2,}}$*}}
\AuthorNames{{Firstname Lastname, Firstname Lastname and Firstname Lastname}}
\address{{%
$^{{1}}$ \quad Affiliation 1; e-mail@e-mail.com\\
$^{{2}}$ \quad Affiliation 2; e-mail@e-mail.com}}
\corres{{Correspondence: e-mail@e-mail.com}}

\abstract{{{esc(T.ABSTRACT)}}}

\keyword{{{esc(T.KEYWORDS)}}}

\addhighlights{{yes}}
\renewcommand{{\addhighlights}}{{%

\noindent \textbf{{What are the main findings?}}
\begin{{itemize}}[labelsep=2.5mm,topsep=-3pt]
{hl(T.HIGHLIGHTS_FINDINGS)}
\end{{itemize}}\vspace{{3pt}}
\textbf{{What are the implications of the main findings?}}
\begin{{itemize}}[labelsep=2.5mm,topsep=-3pt]
{hl(T.HIGHLIGHTS_IMPLICATIONS)}
\end{{itemize}}
}}

\begin{{document}}

{chr(10).join(parts)}

\vspace{{6pt}}

\supplementary{{{esc(T.SUPP)}}}

\authorcontributions{{{esc(back['Author Contributions'])}}}

\funding{{{esc(back['Funding'])}}}

\institutionalreview{{Not applicable.}}

\informedconsent{{Not applicable.}}

\dataavailability{{{ref_tex([(back['Data Availability Statement'], '')])}}}

\acknowledgments{{{esc(back['Use of Generative AI'])}}}

\conflictsofinterest{{{esc(back['Conflicts of Interest'])}}}

\abbreviations{{Abbreviations}}{{%
The following abbreviations are used in this manuscript:\\

\noindent
\begin{{tabular}}{{@{{}}ll}}
{abbrev}
\end{{tabular}}
}}

\begin{{adjustwidth}}{{-\extralength}}{{0cm}}

\reftitle{{References}}

\begin{{thebibliography}}{{999}}
{bib}
\end{{thebibliography}}

\PublishersNote{{}}
\end{{adjustwidth}}
\end{{document}}
"""
    (TEX_DIR / 'manuscript.tex').write_text(tex, encoding='utf-8')
    for _ in range(2):
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', 'manuscript.tex'], cwd=TEX_DIR,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
    log = (TEX_DIR / 'manuscript.log').read_text(encoding='utf-8', errors='replace')
    errors = [l for l in log.splitlines() if l.startswith('!')]
    undefined = re.findall(r"(?:Reference|Citation) `([^']+)' .*undefined", log)
    overfull = len(re.findall(r'Overfull \\hbox', log))
    print('pdflatex rc', r.returncode, '| errors', errors[:5], '| undefined', sorted(set(undefined)), '| overfull', overfull)
    if r.returncode:
        print(r.stdout[-3000:])
    return r.returncode


if __name__ == '__main__':
    raise SystemExit(main())
