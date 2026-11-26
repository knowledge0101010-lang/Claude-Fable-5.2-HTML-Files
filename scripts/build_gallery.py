"""Build the static gallery from the numbered HTML and prompt files.

The supplied builder split only TITLE / PROMPT / DESCRIPTION / VISUAL TECHNIQUES,
which folded each study's INTERACTION MODEL into the techniques block and then
never displayed it. This version keeps all five sections and renders the two
that were lost, plus an optional spec score from the regression harness when
`reports/static.json` exists.
"""
from pathlib import Path
import html
import json
import re

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = ("TITLE", "PROMPT", "DESCRIPTION", "VISUAL TECHNIQUES", "INTERACTION MODEL")
HEAD = re.compile(r"^(" + "|".join(re.escape(s) for s in SECTIONS) + r")[ \t]*$", re.M)


def studies():
    result = []
    for page in sorted(ROOT.glob('[0-9][0-9][0-9]-*.html')):
        source = page.with_suffix('.txt')
        text = source.read_text(encoding='utf-8')
        parts = HEAD.split(text)
        sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
        for key in ('TITLE', 'PROMPT', 'DESCRIPTION'):
            if not sections.get(key):
                raise ValueError(f'{source.name}: missing {key}')
        result.append(dict(file=page.name, stem=page.stem, number=page.name[:3],
                           title=sections['TITLE'], prompt=sections['PROMPT'],
                           description=sections['DESCRIPTION'], source=source.name,
                           techniques=sections.get('VISUAL TECHNIQUES', ''),
                           interaction=sections.get('INTERACTION MODEL', '')))
    if not result:
        raise ValueError('No studies found')
    return result


def scores():
    """Optional: the harness writes per-study conformance scores."""
    path = ROOT / 'reports' / 'static.json'
    if not path.exists():
        return {}
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return {}
    return {s['file']: s['score']['composite'] for s in report.get('studies', [])}


def bullet_list(text):
    items = [line[2:].strip() for line in text.splitlines() if line.startswith('- ')]
    if not items:
        return ''
    return '<ul class="tech-list">' + ''.join(f'<li>{html.escape(i)}</li>' for i in items) + '</ul>'


def derived():
    """Studies that also ship a derived version under studies/<stem>/index.html."""
    return {p.parent.name for p in (ROOT / 'studies').glob('*/index.html')}


def build():
    items = studies()
    derived_stems = derived()
    score_by_file = scores()
    cards = []
    esc = html.escape
    for item in items:
        f, title, num = esc(item['file']), esc(item['title']), item['number']
        techniques = bullet_list(item['techniques'])
        interaction = f'<p class="interaction-text">{esc(item["interaction"])}</p>' if item['interaction'] else ''
        score = score_by_file.get(item['file'])
        badge = (
            f'<span class="spec" title="Spec conformance measured by harness/static_audit.py">'
            f'spec {score:.2f}</span>' if isinstance(score, (int, float)) else ''
        )
        if techniques or interaction:
            extra = (
                ('<div class="interaction-panel"><h4>Interaction model</h4>' + interaction + '</div>')
                if interaction else ''
            ) + (
                ('<div class="interaction-panel"><h4>Visual techniques</h4>' + techniques + '</div>')
                if techniques else ''
            )
        else:
            extra = ''
        compare = (
            f'<a class="btn btn-study" href="studies/{esc(item["stem"])}/index.html" target="_blank" '
            f'rel="noopener" aria-label="Open the derived version of {title}">✦ Derived</a>'
            if item['stem'] in derived_stems else ''
        )
        cards.append(f'''<article class="card" id="study-{num}">
  <a class="thumb" href="{f}" target="_blank" rel="noopener" aria-label="Open {title}">
    <img src="thumbs/{esc(item['stem'])}.jpg" alt="{title} screenshot" width="1440" height="1000" loading="lazy" decoding="async">
    <span class="preview-missing" hidden>Screenshot will appear after the gallery is published.<br><span>Open {title} ↗</span></span>
  </a>
  <div class="card-top">
    <span class="num">{num}</span>
    <div class="main"><h2><a href="{f}" target="_blank" rel="noopener">{title}</a></h2>
    <p class="desc">{esc(item['description'])}</p></div>
    <div class="actions"><a class="btn btn-open" href="{f}" target="_blank" rel="noopener" aria-label="Open {title}">↗ Open</a>
    <button class="btn btn-prompt" type="button" aria-expanded="false" aria-controls="prompt-{num}">☰ Prompt</button>{compare}</div>
  </div>
  <div class="prompt-panel" id="prompt-{num}" hidden><h3>Original prompt {badge}</h3>
    <div class="prompt-text">{esc(item['prompt'])}</div>
    {extra}
    <a class="file-name" href="{esc(item['source'])}" target="_blank" rel="noopener">{esc(item['source'])}</a>
  </div>
</article>''')
    template = (ROOT / 'scripts/gallery-template.html').read_text(encoding='utf-8')
    output = template.replace('<!-- CARDS -->', '\n'.join(cards)).replace('{{COUNT}}', str(len(items)))
    (ROOT / 'index.html').write_text(output, encoding='utf-8')
    print(f'Built index.html with {len(items)} studies, full prompts, techniques and interaction models.')


def check():
    """index.html must be exactly what the template + specs produce."""
    import sys
    before = (ROOT / 'index.html').read_text(encoding='utf-8')
    build()
    after = (ROOT / 'index.html').read_text(encoding='utf-8')
    if before == after:
        print('PASS gallery-reproducible')
        return 0
    (ROOT / 'index.html').write_text(before, encoding='utf-8')
    print('FAIL gallery-reproducible — index.html drifted from scripts/build_gallery.py')
    return 1


if __name__ == '__main__':
    import sys
    raise SystemExit(check() if '--check' in sys.argv else build())
