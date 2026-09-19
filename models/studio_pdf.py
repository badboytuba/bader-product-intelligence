# -*- coding: utf-8 -*-
"""Isolated bounded PDF extraction worker. No Odoo or network dependencies.

Run only by content_studio.extract_file with raw PDF on stdin. Resource limits
are established before importing the parser so a compressed-stream bomb cannot
exhaust an Odoo worker. Never log document content or parser exception details.
"""
import json
import sys


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        import io
        from PyPDF2 import PdfReader
        raw = sys.stdin.buffer.read(10 * 1024 * 1024 + 1)
        if not raw.startswith(b'%PDF-') or len(raw) > 10 * 1024 * 1024:
            raise ValueError()
        reader = PdfReader(io.BytesIO(raw), strict=True)
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 50:
            raise ValueError()
        sections = []
        total = 0
        for page in reader.pages:
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 5 * 1024 * 1024:
                raise ValueError()
            text = (page.extract_text() or '') if contents else ''
            total += len(text)
            if total > 100000:
                raise ValueError()
            sections.append(text)
        sys.stdout.write(json.dumps({'ok': True, 'text': '\n'.join(sections), 'pages': len(reader.pages)}))
    except BaseException:
        sys.stdout.write('{"ok":false}')


if __name__ == '__main__':
    main()
