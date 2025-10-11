import argparse
import base64
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Dict, Tuple

from bs4 import BeautifulSoup, Comment, NavigableString
from bs4.element import Tag
from htmlmin import minify


@dataclass
class SizeReport:
    file_size: int
    minified_size: int
    text_chars: int
    comments_bytes: int
    scripts_bytes: int
    styles_bytes: int
    inline_style_attr_bytes: int
    data_uri_bytes: int
    images_count: int
    scripts_count: int
    styles_count: int

    def to_pretty(self) -> str:
        lines = [
            f"File size: {self.file_size:,} B",
            f"Minified (no removals) size: {self.minified_size:,} B",
            f"Visible text characters (approx): {self.text_chars:,}",
            f"Comments total bytes: {self.comments_bytes:,}",
            f"<script> content bytes: {self.scripts_bytes:,} (count: {self.scripts_count})",
            f"<style> content bytes: {self.styles_bytes:,} (count: {self.styles_count})",
            f"Inline style attribute bytes: {self.inline_style_attr_bytes:,}",
            f"Inline data: URI bytes (img/src, css): {self.data_uri_bytes:,} (images: {self.images_count})",
        ]
        return "\n".join(lines)


def _len_bytes(s: str) -> int:
    return len(s.encode('utf-8', errors='ignore'))


def analyze_html(html: str) -> SizeReport:
    soup = BeautifulSoup(html, 'lxml')

    # Text length (rough approximation of visible text)
    # Exclude script/style
    for tag in soup(['script', 'style']):
        tag.extract()
    text_chars = len(soup.get_text(" ", strip=True))

    # Re-parse original for other counts
    soup_full = BeautifulSoup(html, 'lxml')

    # Comments
    comments = soup_full.find_all(string=lambda x: isinstance(x, Comment))
    comments_bytes = sum(_len_bytes(c) for c in comments)

    # Scripts
    scripts = soup_full.find_all('script')
    scripts_bytes = 0
    for s in scripts:
        scripts_bytes += _len_bytes(s.get_text() or '')
        # include src attribute length
        if s.has_attr('src'):
            scripts_bytes += _len_bytes(s['src'])

    # Styles
    styles = soup_full.find_all('style')
    styles_bytes = sum(_len_bytes(st.get_text() or '') for st in styles)

    # Inline style attributes
    inline_style_attr_bytes = 0
    for el in soup_full.find_all(True):
        if el.has_attr('style'):
            inline_style_attr_bytes += _len_bytes(el['style'])

    # Data URIs in img/src and style attributes and <source src>
    data_uri_pattern = re.compile(r"data:[^;]+;base64,([A-Za-z0-9+/=]+)")
    data_uri_bytes = 0
    images_count = 0

    def count_data_uri(s: str):
        nonlocal data_uri_bytes, images_count
        if not s:
            return
        for m in data_uri_pattern.finditer(s):
            b64 = m.group(1)
            try:
                data_uri_bytes += len(base64.b64decode(b64, validate=False))
            except Exception:
                # Fallback to length estimate (3/4 of base64 length)
                data_uri_bytes += int(len(b64) * 0.75)

    for img in soup_full.find_all(['img', 'source']):
        src = img.get('src') or img.get('srcset')
        if src and src.startswith('data:'):
            images_count += 1
            count_data_uri(src)

    for el in soup_full.find_all(True):
        style_attr = el.get('style')
        if style_attr:
            count_data_uri(style_attr)

    # Compute minified size (no removals, just whitespace/comment minification)
    minified_html = minify(
        html,
        remove_comments=True,
        remove_empty_space=True,
        reduce_boolean_attributes=True,
        remove_all_empty_space=False,
        keep_pre=True,
    )

    return SizeReport(
        file_size=_len_bytes(html),
        minified_size=_len_bytes(minified_html),
        text_chars=text_chars,
        comments_bytes=comments_bytes,
        scripts_bytes=scripts_bytes,
        styles_bytes=styles_bytes,
        inline_style_attr_bytes=inline_style_attr_bytes,
        data_uri_bytes=data_uri_bytes,
        images_count=images_count,
        scripts_count=len(scripts),
        styles_count=len(styles),
    )


def minify_only(html: str) -> str:
    return minify(
        html,
        remove_comments=True,
        remove_empty_space=True,
        reduce_boolean_attributes=True,
        remove_all_empty_space=False,
        keep_pre=True,
    )


def strip_nontext(html: str, keep_images: bool = True, flatten_inputs: bool = False) -> str:
    """
    Aggressive: remove <script>, <style>, link[rel=stylesheet], inline event handlers,
    tracking iframes, etc., while keeping textual content. Optionally keep images.
    """
    soup = BeautifulSoup(html, 'lxml')

    # Remove scripts/styles and external stylesheets
    for tag in soup.find_all(['script', 'style']):
        tag.decompose()
    for link in soup.find_all('link'):
        rel = ' '.join(link.get('rel', [])).lower()
        if 'stylesheet' in rel or 'preload' in rel or 'preconnect' in rel:
            link.decompose()

    # Remove iframes and embeds that are unlikely to be content of questions
    for tag in soup.find_all(['iframe', 'embed', 'object']):
        tag.decompose()

    # Remove inline event handler attributes (onclick, onload, etc.)
    for el in soup.find_all(True):
        attrs_to_remove = [a for a in el.attrs.keys() if isinstance(a, str) and a.lower().startswith('on')]
        for a in attrs_to_remove:
            del el.attrs[a]

    # Optionally remove images; if keeping images, preserve them as-is (including data URIs)
    for img in soup.find_all('img'):
        if not keep_images:
            img.decompose()
        # else: keep image unchanged

    # Remove comments
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()

    # Optionally replace checkbox/radio inputs with plain text markers so state remains visible
    if flatten_inputs:
        # 1) Native inputs
        for inp in soup.find_all('input'):
            t = (inp.get('type') or '').lower()
            if t in ('checkbox', 'radio'):
                checked = inp.has_attr('checked') and (inp['checked'] in [True, 'true', 'checked', '', None] or inp['checked'] == inp.get('checked'))
                if t == 'checkbox':
                    marker = '[x] ' if checked else '[ ] '
                else:
                    marker = '(•) ' if checked else '( ) '

                # Insert marker text before the input and remove the input
                inp.insert_before(NavigableString(marker))
                inp.decompose()

        # 2) Custom visual markers used by uuCourseKit (no native inputs)
        # Pattern observed: a wrapper div with a preceding <span> acting as checkbox/radio visual,
        # followed by a sibling <div> containing the answer text. Classes like:
        # - uu-coursekit-result-state / uu-coursekit-wrong-state / uu-coursekit-dark-text
        # - inner element with style visibility:hidden when UNchecked; visible when checked
        def is_checked_marker(marker_span) -> Tuple[bool, str]:
            # Determine shape (checkbox vs radio)
            style = (marker_span.get('style') or '').lower()
            is_radio = 'border-radius: 100%' in style or 'border-radius:100%' in style or 'width: 32px' in style
            # Heuristics for checked state
            classes = ' '.join(marker_span.get('class', [])).lower()
            if 'result-state' in classes:
                return True, '(•) ' if is_radio else '[x] '
            # inner icon / background visibility
            inner = None
            # prefer explicit inner indicator elements
            for sel in ['.fa', '.uu-coursekit-result-state-background', '.uu-coursekit-wrong-state-background']:
                inner = marker_span.select_one(sel)
                if inner:
                    break
            if inner:
                inner_style = (inner.get('style') or '').lower()
                checked = 'visibility: hidden' not in inner_style
                return checked, '(•) ' if is_radio else '[x] '
            # Fallback: opacity on surrounding text usually 0.6 for unselected
            sibling_text = marker_span.find_next_sibling('div')
            if sibling_text:
                sib_style = (sibling_text.get('style') or '').lower()
                if 'opacity: 0.6' in sib_style or 'opacity:.6' in sib_style:
                    return False, '( ) ' if is_radio else '[ ] '
            # Default to unchecked if unsure
            return False, '( ) ' if is_radio else '[ ] '

        # find blocks that look like answers: span marker + following div text
        for marker in soup.find_all('span'):
            # quick filter to avoid touching random spans
            if not isinstance(marker, Tag):
                continue
            cls = ' '.join((marker.attrs or {}).get('class', [])).lower()
            if 'uu-coursekit' not in cls:
                continue
            # must have sibling div with text
            text_div = marker.find_next_sibling('div')
            if not text_div or not text_div.get_text(strip=True):
                continue
            checked, base_marker = is_checked_marker(marker)
            marker_text = base_marker if checked else (base_marker.replace('x', ' ') if '[' in base_marker else base_marker.replace('•', ' '))
            # insert textual marker before the text div (ensure spacing)
            text_div.insert_before(NavigableString(marker_text))
            # drop the visual marker span
            marker.decompose()

    # Finally, minify the result to collapse whitespace
    return minify_only(str(soup))


def process_file(path: str, mode: str, output: str = None, keep_images: bool = True, flatten_inputs: bool = False) -> Tuple[SizeReport, str, str]:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()
    report = analyze_html(html)

    if mode == 'analyze':
        return report, path, None
    elif mode == 'minify':
        out_html = minify_only(html)
    elif mode == 'aggressive':
        out_html = strip_nontext(html, keep_images=keep_images, flatten_inputs=flatten_inputs)
    else:
        raise ValueError('Unknown mode')

    out_path = output or _default_output_path(path, suffix=f'.{mode}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(out_html)
    return report, path, out_path


def _default_output_path(path: str, suffix: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}{suffix}"


def main():
    parser = argparse.ArgumentParser(description='Analyze and minimize HTML files (safe minify or aggressive strip modes).')
    parser.add_argument('input', help='Path to HTML file')
    parser.add_argument('--mode', choices=['analyze', 'minify', 'aggressive'], default='minify', help='Operation mode')
    parser.add_argument('-o', '--output', help='Output file path (for minify/aggressive modes)')
    parser.add_argument('--keep-images', action='store_true', help='In aggressive mode, keep <img> elements (strip data URIs)')
    parser.add_argument('--flatten-inputs', action='store_true', help='In aggressive mode, convert checkbox/radio inputs to plain text markers preserving checked state')

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    report, in_path, out_path = process_file(
        args.input,
        args.mode,
        args.output,
        keep_images=args.keep_images,
        flatten_inputs=args.flatten_inputs,
    )

    print('=== Analysis ===')
    print(report.to_pretty())
    if out_path:
        orig = report.file_size
        new_size = os.path.getsize(out_path)
        savings = orig - new_size
        pct = (savings / orig * 100) if orig else 0
        print('\n=== Output ===')
        print(f"Wrote: {out_path}")
        print(f"New size: {new_size:,} B (saved {savings:,} B, {pct:.2f}%)")


if __name__ == '__main__':
    main()
