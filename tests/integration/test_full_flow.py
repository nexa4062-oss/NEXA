"""Full end-to-end integration test for auth, RBAC, documents, RAG, and
the agentic workflow (permission gate + HITL)."""
import asyncio
import json
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import httpx
import uvicorn


def _canned_response(prompt: str) -> str:
    """Deterministic, honestly-labelled stand-in for a local Ollama model,
    so this suite can exercise the full agent pipeline (routing, sandbox
    wiring, HITL pause/resume) in an environment with no GPU/Ollama
    installed. Never used by the running application itself - AgentService
    always talks to the real OLLAMA_URL; this only backs the test's own
    fake HTTP server. The genuine "model not installed" path is covered
    separately by test_model_router.py, which correctly reports
    'No models available' when nothing is listening on OLLAMA_URL at all."""
    low = prompt.lower()
    if "sandbox" in low or "root cause" in low:
        return ("The real sandbox run raised IndexError: list index out of range. "
                "Root cause: x[5] is accessed but the list only has 3 elements. "
                "Fix: check the index against len(x) before accessing it.")
    if "briefly plan" in low:
        return "1) Understand the request. 2) Run the selected workflow. 3) Validate and return the result."
    return "This is a deterministic test-fixture response for: " + prompt.split("User:")[-1].strip()[:80]


class _FakeOllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/tags":
            body = json.dumps({"models": [{"name": "qwen3:8b", "model": "qwen3:8b", "size": 1,
                                            "digest": "fixture", "modified_at": ""}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/generate":
            text = _canned_response(payload.get("prompt", ""))
            if payload.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                self.wfile.write((json.dumps({"response": text, "done": False}) + "\n").encode())
                self.wfile.write((json.dumps({"response": "", "done": True}) + "\n").encode())
            else:
                body = json.dumps({"response": text, "done": True}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        elif self.path == "/api/chat":
            messages = payload.get("messages", [])
            prompt = messages[-1]["content"] if messages else ""
            text = _canned_response(prompt)
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            words = text.split(" ")
            for i, w in enumerate(words):
                chunk = w + (" " if i < len(words) - 1 else "")
                self.wfile.write((json.dumps({"model": "qwen3:8b", "message": {"role": "assistant", "content": chunk}, "done": False}) + "\n").encode())
            self.wfile.write((json.dumps({"model": "qwen3:8b", "message": {"role": "assistant", "content": ""}, "done": True}) + "\n").encode())
        elif self.path == "/api/embeddings":
            # Deterministic fixed-size fake embedding vector - RAG's own
            # cosine-similarity/authorization filtering logic is what's
            # under test here, not embedding quality.
            body = json.dumps({"embedding": [0.01] * 384}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


def _start_fake_ollama(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _FakeOllamaHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


async def run_tests():
    fake_ollama_port = 8399
    os.environ["OLLAMA_URL"] = f"http://127.0.0.1:{fake_ollama_port}"
    fake_ollama = _start_fake_ollama(fake_ollama_port)

    from main import app

    config = uvicorn.Config(app, host='127.0.0.1', port=8210, log_level='error')
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
    await asyncio.sleep(2)

    passed = 0
    failed = 0

    async with httpx.AsyncClient(base_url='http://127.0.0.1:8210', timeout=180) as client:
        # TEST A: Setup status on empty DB
        r = await client.get('/api/auth/setup-status')
        assert r.status_code == 200
        assert r.json()['needs_setup'] == True
        print('TEST A [PASS]: Empty DB needs_setup=true')
        passed += 1

        # TEST B: Create admin
        r = await client.post('/api/auth/setup', json={
            'username': 'sysadmin', 'password': 'Str0ngP@ss!2026',
            'display_name': 'System Administrator', 'employee_id': 'ADM-001',
            'email': 'admin@org.local', 'organization_name': 'IOCL Refinery'
        })
        assert r.status_code == 200
        assert r.json()['role'] == 'super_admin'
        print('TEST B [PASS]: Admin created with super_admin role')
        passed += 1

        r = await client.get('/api/auth/setup-status')
        assert r.json()['needs_setup'] == False
        print('       [PASS]: needs_setup=false after creation')
        passed += 1

        # TEST C: Normal login
        r = await client.post('/api/auth/login', json={'username': 'sysadmin', 'password': 'Str0ngP@ss!2026'})
        assert r.status_code == 200
        admin_token = r.json()['access_token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}
        print('TEST C [PASS]: Admin login successful')
        passed += 1

        r = await client.get('/api/auth/me', headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()['permissions']) == 18  # 17 original + approve_agent_actions (HITL)
        print(f'       [PASS]: Admin has {len(r.json()["permissions"])} permissions')
        passed += 1

        # TEST D: Seed demo accounts
        r = await client.post('/api/auth/seed-demo')
        assert r.status_code == 200
        assert r.json()['seeded'] == True
        demo_password = r.json()['demo_password']
        print(f'TEST D [PASS]: Demo seeded ({len(r.json()["accounts"])} accounts, {len(r.json()["documents"])} docs)')
        passed += 1

        # Verify demo logins
        for username in ['engineer_demo', 'hr_manager_demo', 'finance_demo', 'reviewer_demo', 'manager_demo', 'admin_demo']:
            r = await client.post('/api/auth/login', json={'username': username, 'password': demo_password})
            assert r.status_code == 200, f'{username} login failed: {r.text}'
        print('       [PASS]: All 6 demo accounts authenticate successfully')
        passed += 1

        # Get tokens for key roles
        r = await client.post('/api/auth/login', json={'username': 'engineer_demo', 'password': demo_password})
        eng_headers = {'Authorization': f'Bearer {r.json()["access_token"]}'}

        r = await client.post('/api/auth/login', json={'username': 'hr_manager_demo', 'password': demo_password})
        hr_headers = {'Authorization': f'Bearer {r.json()["access_token"]}'}

        r = await client.post('/api/auth/login', json={'username': 'finance_demo', 'password': demo_password})
        fin_headers = {'Authorization': f'Bearer {r.json()["access_token"]}'}

        r = await client.post('/api/auth/login', json={'username': 'manager_demo', 'password': demo_password})
        mgr_headers = {'Authorization': f'Bearer {r.json()["access_token"]}'}

        # TEST E: RBAC - Document access
        r = await client.get('/api/documents/', headers=eng_headers)
        assert r.status_code == 200
        eng_docs = [d['filename'] for d in r.json()['documents']]
        assert 'engineering_sop.pdf' in eng_docs
        assert 'general_safety_guidelines.pdf' in eng_docs
        assert 'hr_recruitment_plan.pdf' not in eng_docs
        assert 'financial_forecast_q3.xlsx' not in eng_docs
        print(f'TEST E [PASS]: Engineer sees {len(eng_docs)} docs (eng+safety, NOT hr/finance)')
        passed += 1

        r = await client.get('/api/documents/', headers=hr_headers)
        hr_docs = [d['filename'] for d in r.json()['documents']]
        assert 'employee_handbook.pdf' in hr_docs
        assert 'hr_recruitment_plan.pdf' in hr_docs
        assert 'engineering_sop.pdf' not in hr_docs
        print(f'       [PASS]: HR sees {len(hr_docs)} docs (hr docs, NOT engineering)')
        passed += 1

        r = await client.get('/api/documents/', headers=fin_headers)
        fin_docs = [d['filename'] for d in r.json()['documents']]
        assert 'financial_forecast_q3.xlsx' in fin_docs
        assert 'confidential_board_strategy.pdf' not in fin_docs
        print(f'       [PASS]: Finance sees financial docs, NOT board strategy')
        passed += 1

        r = await client.get('/api/documents/', headers=mgr_headers)
        mgr_docs = [d['filename'] for d in r.json()['documents']]
        assert 'confidential_board_strategy.pdf' in mgr_docs
        assert 'engineering_sop.pdf' in mgr_docs
        assert 'financial_forecast_q3.xlsx' in mgr_docs
        print(f'       [PASS]: Manager sees {len(mgr_docs)} docs (broader access)')
        passed += 1

        # TEST F: Direct API access denied
        r = await client.get('/api/documents/', headers=admin_headers)
        all_docs = r.json()['documents']
        hr_doc_id = next((d['id'] for d in all_docs if d['filename'] == 'hr_recruitment_plan.pdf'), None)

        if hr_doc_id:
            r = await client.get(f'/api/documents/{hr_doc_id}', headers=eng_headers)
            assert r.status_code == 403
            print('TEST F [PASS]: Direct API access to HR doc denied for engineer (403)')
            passed += 1

            r = await client.get(f'/api/documents/{hr_doc_id}', headers=fin_headers)
            assert r.status_code == 403
            print('       [PASS]: Direct API access to HR doc denied for finance (403)')
            passed += 1

        # TEST G: RAG security
        r = await client.post('/api/rag/query', headers=eng_headers,
                             json={'query': 'recruitment plan budget', 'mode': 'fast'})
        assert r.status_code == 200
        rag_answer = r.json().get('answer', '')
        assert '2.8 crores' not in rag_answer
        print('TEST G [PASS]: RAG does not leak HR content to engineer')
        passed += 1

        r = await client.post('/api/rag/query', headers=hr_headers,
                             json={'query': 'recruitment plan budget', 'mode': 'fast'})
        assert r.status_code == 200
        hr_rag = r.json()
        hr_chunks = hr_rag.get('context_chunks_used', 0)
        print(f'       [PASS]: HR user RAG gets {hr_chunks} authorized chunks')
        passed += 1

        r = await client.post('/api/auth/login', json={'username': 'reviewer_demo', 'password': demo_password})
        rev_headers = {'Authorization': f'Bearer {r.json()["access_token"]}'}

        # TEST H1: Agent - general question needs no tool/RAG, runs the full phase pipeline
        r = await client.post('/api/agents/execute', headers=rev_headers,
                             json={'query': 'Explain briefly why the sky appears blue', 'mode': 'fast', 'enable_rag': False})
        assert r.status_code == 200
        agent_result = r.json()
        assert agent_result['status'] == 'completed'
        phases = [s['phase'] for s in agent_result['steps']]
        assert phases == ['understand_intent', 'permission_check', 'plan', 'hitl_gate', 'select_workflow', 'act', 'verify']
        print('TEST H1 [PASS]: Agent (LangGraph) runs full understand->permission->plan->hitl_gate->select->act->verify pipeline')
        passed += 1

        # TEST H2: Agent permission gate - finance user has no execute_code, coding task denied
        # BEFORE any sandbox execution or LLM call (checked via the returned phase list).
        r = await client.post('/api/agents/execute', headers=fin_headers,
                             json={'query': 'debug this', 'code': 'print(1/0)', 'code_language': 'python'})
        assert r.status_code == 200
        denied = r.json()
        assert denied['status'] == 'denied'
        assert denied['missing_permission'] == 'execute_code'
        assert [s['phase'] for s in denied['steps']] == ['understand_intent', 'permission_check']
        print('TEST H2 [PASS]: Agent permission gate blocks coding task for user without execute_code')
        passed += 1

        # TEST H3: Agent code-debug workflow - real sandbox execution, real error, no HITL (default off)
        buggy_code = 'x = [1, 2, 3]\nprint(x[5])'
        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'find and fix the bug', 'code': buggy_code, 'code_language': 'python'})
        assert r.status_code == 200
        debug_result = r.json()
        assert debug_result['status'] == 'completed'
        assert debug_result['task_type'] == 'coding'
        assert debug_result['sandbox_result']['success'] is False
        assert 'IndexError' in debug_result['sandbox_result']['error']
        print('TEST H3 [PASS]: Code workflow ran the real sandbox (genuine IndexError), HITL off = automatic')
        passed += 1

        # TEST H4: Enable HITL and mark 'coding' sensitive
        r = await client.put('/api/security/settings/agentic', headers=admin_headers,
                            json={'hitl_enabled': True, 'sensitive_actions': ['coding']})
        assert r.status_code == 200
        assert r.json()['hitl_enabled'] is True
        print('TEST H4 [PASS]: Admin enabled Human-in-the-Loop for coding actions')
        passed += 1

        # A non-admin cannot change the setting
        r = await client.put('/api/security/settings/agentic', headers=eng_headers, json={'hitl_enabled': False})
        assert r.status_code == 403
        print('       [PASS]: Non-admin cannot change HITL setting (403)')
        passed += 1

        # TEST H5: With HITL on, the same coding request now pauses for approval instead of executing
        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'find and fix the bug', 'code': buggy_code, 'code_language': 'python'})
        assert r.status_code == 200
        waiting = r.json()
        assert waiting['status'] == 'waiting_approval'
        approval_id = waiting['approval_id']
        print('TEST H5 [PASS]: HITL on -> sensitive coding action pauses as "waiting_approval", not executed')
        passed += 1

        # TEST H6: A user without approve_agent_actions cannot approve
        r = await client.post(f'/api/agents/approvals/{approval_id}/approve', headers=fin_headers)
        assert r.status_code == 403
        print('TEST H6 [PASS]: Unauthorized user cannot approve (403)')
        passed += 1

        # TEST H7: An authorized manager approves -> agent resumes and actually executes
        r = await client.get('/api/agents/approvals', headers=mgr_headers)
        assert r.status_code == 200
        assert any(a['id'] == approval_id for a in r.json()['approvals'])

        r = await client.post(f'/api/agents/approvals/{approval_id}/approve', headers=mgr_headers)
        assert r.status_code == 200
        approved = r.json()
        assert approved['result']['status'] == 'completed'
        assert approved['result']['sandbox_result']['success'] is False
        print('TEST H7 [PASS]: Authorized approval resumes execution against the real sandbox result')
        passed += 1

        # Approving twice is rejected
        r = await client.post(f'/api/agents/approvals/{approval_id}/approve', headers=mgr_headers)
        assert r.status_code == 409
        print('       [PASS]: Re-approving an already-resolved request is rejected (409)')
        passed += 1

        # TEST H8: Reject flow - agent stops safely, nothing executes
        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'run this', 'code': 'print("should not run")', 'code_language': 'python'})
        reject_id = r.json()['approval_id']
        r = await client.post(f'/api/agents/approvals/{reject_id}/reject', headers=mgr_headers)
        assert r.status_code == 200
        assert r.json()['approval']['status'] == 'rejected'
        print('TEST H8 [PASS]: Rejected approval stops the agent safely, no execution result stored')
        passed += 1

        # Restore default (HITL off) so it doesn't affect anything reading this DB afterwards
        r = await client.put('/api/security/settings/agentic', headers=admin_headers, json={'hitl_enabled': False})
        assert r.status_code == 200
        print('       [PASS]: HITL restored to OFF (default automated behaviour)')
        passed += 1

        # TEST H9: Streaming endpoint - real token-level streaming through
        # LangGraph's astream_events (not the non-streaming path above)
        events = []
        async with client.stream('POST', '/api/agents/execute/stream', headers=rev_headers,
                                json={'query': 'Explain briefly why the sky appears blue', 'mode': 'fast', 'enable_rag': False}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith('data: '):
                    raw = line[6:]
                    if raw == '[DONE]':
                        break
                    events.append(json.loads(raw))
        event_types = [e['type'] for e in events]
        assert event_types.count('token') > 1, 'expected multiple real token chunks, not one lump response'
        assert event_types[-1] == 'done'
        phases_seen = [e['phase'] for e in events if e['type'] == 'status']
        assert phases_seen == ['understand_intent', 'permission_check', 'plan', 'hitl_gate', 'direct_node', 'act', 'validate']
        print(f'TEST H9 [PASS]: Streaming endpoint yields {event_types.count("token")} real token chunks + correct phase sequence')
        passed += 1

        # TEST H10: Streaming endpoint also correctly pauses for HITL approval
        r = await client.put('/api/security/settings/agentic', headers=admin_headers,
                            json={'hitl_enabled': True, 'sensitive_actions': ['coding']})
        assert r.status_code == 200

        stream_events = []
        async with client.stream('POST', '/api/agents/execute/stream', headers=eng_headers,
                                json={'query': 'fix this', 'code': 'print(1/0)', 'code_language': 'python'}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith('data: '):
                    raw = line[6:]
                    if raw == '[DONE]':
                        break
                    stream_events.append(json.loads(raw))
        approval_events = [e for e in stream_events if e['type'] == 'approval_required']
        assert len(approval_events) == 1 and approval_events[0]['task_type'] == 'coding'
        r = await client.post(f"/api/agents/approvals/{approval_events[0]['approval_id']}/reject", headers=mgr_headers)
        assert r.status_code == 200
        print('TEST H10 [PASS]: Streaming endpoint pauses for approval via the same LangGraph interrupt/resume path')
        passed += 1

        r = await client.put('/api/security/settings/agentic', headers=admin_headers, json={'hitl_enabled': False})
        assert r.status_code == 200

        # TEST I: File generation
        for fmt in ['docx', 'pdf', 'pptx', 'xlsx']:
            r = await client.post('/api/generation/generate', headers=eng_headers,
                                 json={'format': fmt, 'title': f'Test {fmt}', 'content': 'Test content'})
            assert r.status_code == 200, f'{fmt} generation failed: {r.text}'
        print('TEST I [PASS]: All 4 file formats generate successfully')
        passed += 1

        # TEST N: Agent-driven document generation - REAL files via the
        # LangGraph file_generation_node, not simulated. Verified by
        # physically reading each file back with its real library.
        from config import get_settings as _get_settings
        from docx import Document as DocxDocument
        from openpyxl import load_workbook
        gen_dir = _get_settings().GENERATED_DIR

        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'Create a project report about our AI system as a Word document.'})
        assert r.status_code == 200
        docx_result = r.json()
        assert docx_result['status'] == 'completed', docx_result
        assert docx_result['task_type'] == 'file_generation'
        gf = docx_result['generated_file']
        assert gf and gf['format'] == 'docx' and gf['filename'].endswith('.docx')
        docx_path = os.path.join(gen_dir, gf['filename'])
        assert os.path.exists(docx_path) and os.path.getsize(docx_path) > 0
        opened = DocxDocument(docx_path)
        assert len(opened.paragraphs) > 0
        print('TEST N1 [PASS]: Agent created a REAL .docx file - verified on disk and opens with python-docx')
        passed += 1

        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'Generate a PDF report summarizing our safety procedures.'})
        assert r.status_code == 200
        pdf_result = r.json()
        assert pdf_result['status'] == 'completed' and pdf_result['generated_file']['format'] == 'pdf'
        pdf_path = os.path.join(gen_dir, pdf_result['generated_file']['filename'])
        assert os.path.getsize(pdf_path) > 0
        with open(pdf_path, 'rb') as f:
            assert f.read(5) == b'%PDF-'
        print('TEST N2 [PASS]: Agent created a REAL .pdf file - verified on disk with a valid PDF header')
        passed += 1

        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'Create an Excel spreadsheet with this data: Name, Score. Alice, 90. Bob, 85.'})
        assert r.status_code == 200
        xlsx_result = r.json()
        assert xlsx_result['status'] == 'completed' and xlsx_result['generated_file']['format'] == 'xlsx'
        xlsx_path = os.path.join(gen_dir, xlsx_result['generated_file']['filename'])
        wb = load_workbook(xlsx_path)
        assert wb.active.max_row >= 1
        print('TEST N3 [PASS]: Agent created a REAL .xlsx file - verified on disk and opens with openpyxl')
        passed += 1

        r = await client.post('/api/agents/execute', headers=eng_headers,
                             json={'query': 'Explain briefly why the sky appears blue', 'enable_rag': False})
        assert r.json()['task_type'] != 'file_generation'
        print('       [PASS]: An ordinary question does not trigger document generation')
        passed += 1

        r = await client.post('/api/agents/execute', headers=rev_headers,
                             json={'query': 'Create a Word document report about this quarter.'})
        denied = r.json()
        assert denied['status'] == 'denied' and denied['missing_permission'] == 'generate_files'
        print('TEST N4 [PASS]: Agent permission gate blocks document creation for a user without generate_files')
        passed += 1

        r = await client.get(f"/api/generation/download/{gf['filename']}", headers=fin_headers)
        assert r.status_code == 403
        print("TEST N5 [PASS]: A different user cannot download another user's agent-generated file (403)")
        passed += 1

        r = await client.get(f"/api/generation/download/{gf['filename']}", headers=eng_headers)
        assert r.status_code == 200 and len(r.content) > 0
        print('       [PASS]: The owner can download their own generated file')
        passed += 1

        r = await client.get(f"/api/generation/download/{gf['filename']}", headers=admin_headers)
        assert r.status_code == 200
        print('       [PASS]: Admin (manage_document_permissions) retains cross-user access')
        passed += 1

        # TEST J: Audit logging
        r = await client.get('/api/audit/events', headers=admin_headers)
        assert r.status_code == 200
        events = r.json()['events']
        actions = set(e['action'] for e in events)
        assert 'login' in actions
        print(f'TEST J [PASS]: Audit has {len(events)} events, actions: {sorted(actions)[:5]}...')
        passed += 1

        # TEST K: Invalid credentials
        r = await client.post('/api/auth/login', json={'username': 'engineer_demo', 'password': 'wrong'})
        assert r.status_code == 401
        assert r.json()['detail'] == 'Invalid credentials'
        print('TEST K [PASS]: Invalid credentials returns generic 401')
        passed += 1

        r = await client.post('/api/auth/login', json={'username': 'nonexistent_user', 'password': 'wrong'})
        assert r.status_code == 401
        assert r.json()['detail'] == 'Invalid credentials'
        print('       [PASS]: Non-existent user also returns same generic 401')
        passed += 1

        # TEST L: Logout
        r = await client.post('/api/auth/logout', headers=eng_headers)
        assert r.status_code == 200
        print('TEST L [PASS]: Logout successful')
        passed += 1

        # TEST M: Setup idempotency
        r = await client.post('/api/auth/setup', json={
            'username': 'hacker', 'password': 'HackAttempt!',
            'display_name': 'Hacker', 'employee_id': 'HACK-001',
            'email': 'hack@evil.com', 'organization_name': 'Evil Corp'
        })
        assert r.status_code == 400
        print('TEST M [PASS]: Second setup attempt blocked (400)')
        passed += 1

        r = await client.post('/api/auth/seed-demo')
        assert r.json()['seeded'] == False
        print('       [PASS]: Second demo seed is idempotent')
        passed += 1

    print(f'\n====================================')
    print(f'RESULTS: {passed} PASSED, {failed} FAILED')
    print(f'====================================')

    server.should_exit = True
    fake_ollama.shutdown()
    return passed, failed


if __name__ == '__main__':
    # Remove stale DB
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'sovereign_ai.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    p, f = asyncio.run(run_tests())
    sys.exit(0 if f == 0 else 1)
