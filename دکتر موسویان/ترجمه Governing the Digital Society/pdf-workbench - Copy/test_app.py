import os
import tempfile
import time
from pathlib import Path

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
    os.environ['DATA_DIR'] = temp
    import fitz
    from fastapi.testclient import TestClient
    import app

    calls = []

    async def fake_translate(text, job):
        calls.append(text)
        return 'FA[' + text.strip() + ']'  # echo source so tests can assert on a known string

    app.translate = fake_translate
    pdf = fitz.open()
    for n in range(2):
        page = pdf.new_page()
        page.insert_text((72, 72), f'English test page {n + 1}')
    payload = pdf.tobytes()
    pdf.close()
    with TestClient(app.app) as client:
        assert client.get('/').status_code == 200
        settings = {'base_url': 'https://example.org/api', 'model': 'saved-model', 'api_key': 'test-key'}
        assert client.put('/api/settings', json=settings).status_code == 200
        assert client.get('/api/settings').json() == settings
        response = client.post('/api/jobs', files={'file': ('sample.pdf', payload, 'application/pdf')})
        assert response.status_code == 200, response.text
        job = response.json()['id']

        # ---- Case A: a page whose translation raises must be skipped, not fail the job.
        async def flaky_translate(text, job):
            calls.append(text)
            if 'page 1' in text:
                raise RuntimeError('model exploded on page 1')
            return 'FA[' + text.strip() + ']'
        app.translate = flaky_translate
        assert client.post(f'/api/jobs/{job}/start', json={'base_url': 'http://localhost:1234/v1', 'model': 'test'}).status_code == 200
        for _ in range(200):
            state = client.get(f'/api/jobs/{job}').json()
            if state['status'] in ('done', 'error'):
                break
            time.sleep(.05)
        # Job must be 'done' (not 'error'); page 1 skipped, page 2 done.
        assert state['status'] == 'done', state
        statuses = {p['number']: p['status'] for p in state['pages']}
        assert statuses == {1: 'skipped', 2: 'done'}, statuses
        assert 'model exploded' in state['pages'][0]['error'], state['pages'][0]
        # Page 2 was still processed after page 1 failed.
        assert len(calls) == 2
        for suffix in ('png', 'en.txt', 'fa.txt', 'docx'):
            assert (Path(temp) / job / f'page-0002.{suffix}').exists()
        # Retry the skipped page: it goes back to 'pending'.
        r = client.post(f'/api/jobs/{job}/retry', json=[])
        assert r.status_code == 200
        state = client.get(f'/api/jobs/{job}').json()
        statuses = {p['number']: p['status'] for p in state['pages']}
        assert statuses[1] == 'pending', statuses
        # Now with a healthy translator, the retried page should complete.
        app.translate = fake_translate
        calls.clear()
        assert client.post(f'/api/jobs/{job}/start', json={'base_url': 'http://localhost/v1', 'model': 'test'}).status_code == 200
        for _ in range(200):
            state = client.get(f'/api/jobs/{job}').json()
            if state['status'] == 'done':
                break
            time.sleep(.05)
        statuses = {p['number']: p['status'] for p in state['pages']}
        assert statuses == {1: 'done', 2: 'done'}, statuses
        assert len(calls) == 1  # only the retried page was sent

        # ---- Case B: a page with no extractable text is also skipped, not fatal.
        pdf = fitz.open()
        for n in range(2):
            page = pdf.new_page()
            if n == 1:
                pass  # leave page 2 blank
            else:
                page.insert_text((72, 72), f'English test page {n + 1}')
        blank_payload = pdf.tobytes()
        pdf.close()
        resp2 = client.post('/api/jobs', files={'file': ('blank.pdf', blank_payload, 'application/pdf')})
        assert resp2.status_code == 200
        job2 = resp2.json()['id']
        assert client.post(f'/api/jobs/{job2}/start', json={'base_url': 'http://localhost/v1', 'model': 'test'}).status_code == 200
        for _ in range(200):
            state2 = client.get(f'/api/jobs/{job2}').json()
            if state2['status'] in ('done', 'error'):
                break
            time.sleep(.05)
        assert state2['status'] == 'done', state2
        # Blank page is now COMPLETED with a placeholder (not an error/skip).
        s2 = {p['number']: p['status'] for p in state2['pages']}
        assert s2 == {1: 'done', 2: 'done'}, s2
        assert state2['pages'][1]['error'] == '', state2['pages'][1]
        # Screenshot was still taken for the blank page.
        assert (Path(temp) / job2 / 'page-0002.png').exists()
        # Placeholder text written.
        assert (Path(temp) / job2 / 'page-0002.en.txt').read_text(encoding='utf-8').strip() == 'Not Found'
        assert (Path(temp) / job2 / 'page-0002.fa.txt').read_text(encoding='utf-8').strip() == 'فاقد متن'

        # ---- Regression: export and 404
        export = client.get(f'/api/jobs/{job}/download')
        assert export.status_code == 200
        assert export.content[:2] == b'PK'
        assert client.get('/api/jobs/nonexistent').status_code == 404

        # ---- Text export endpoints (english / persian): blank page shows placeholder.
        # job2 has page1=done (real english), page2=done (blank -> placeholder).
        en = client.get(f'/api/jobs/{job2}/download/english')
        assert en.status_code == 200
        assert en.headers['content-type'].startswith('text/plain')
        en_text = en.text
        assert '===== صفحه 1 =====' in en_text
        assert 'English test page 1' in en_text
        # Page 2 (blank) must contain the English placeholder.
        assert '===== صفحه 2 =====' in en_text
        p2_slice = en_text.split('===== صفحه 2 =====', 1)[1].strip()
        assert p2_slice == 'Not Found', repr(p2_slice)
        fa = client.get(f'/api/jobs/{job2}/download/persian')
        assert fa.status_code == 200
        fa_text = fa.text
        assert '===== صفحه 1 =====' in fa_text
        assert 'FA[English test page 1]' in fa_text  # fake translator echoes the source
        # Page 2 (blank) must contain the Persian placeholder.
        fa_p2 = fa_text.split('===== صفحه 2 =====', 1)[1].strip()
        assert fa_p2 == 'فاقد متن', repr(fa_p2)
        # A job with no completed pages should still 400 on the Word export but
        # the text endpoints require at least the job to exist; job2 has page1 done so ok.
    # Simulate interrupted process and verify recovery on service startup.
    app.execute("UPDATE jobs SET status='running' WHERE id=?", (job,))
    app.execute("UPDATE pages SET status='processing' WHERE job_id=? AND number=2", (job,))
    with TestClient(app.app) as client:
        assert client.get('/api/settings').json() == settings
        state = client.get(f'/api/jobs/{job}').json()
        assert state['status'] == 'paused'
        assert state['pages'][0]['status'] == 'done'
        assert state['pages'][1]['status'] == 'pending'
    print('PASS: upload, extraction, image/text/DOCX persistence, export, skip completed, restart recovery')
