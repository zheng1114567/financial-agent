# Test Plan v0.1 — Qwen Parity Focus

> ✅ Based on PRD v0.2 & QWEN_CSS_TOKENS.json/md
> 🎯 Goal: Validate functional + visual parity with https://www.qianwen.com/

---

## Scope
- Covers all 7 AC-QWEN-* acceptance criteria from PRD v0.2
- Excludes legacy v0.1 features not in Qwen (e.g., dark mode toggle, export as PDF)
- Focus: white-blue theme, message bubbles, SSE fidelity, sidebar, model selector, upload, title editing

## Test Strategy
| AC ID | Validation Method | Tools | Deliverables |
|--------|-------------------|--------|--------------|
| **AC-QWEN-01** | CSS token audit + visual inspection | Cypress (`cy.get('html').should('have.css', 'background-color', 'rgb(255, 255, 255)')`) | `cypress/e2e/ac-qwen-01-theme.cy.ts` |
| **AC-QWEN-02** | DOM snapshot comparison + computed style validation | Cypress + `cypress-plugin-snapshots` | `cypress/e2e/ac-qwen-02-bubbles.cy.ts` |
| **AC-QWEN-03** | SSE event parsing + JSON schema validation | pytest + `sseclient-py` + custom parser | `test/sse-parser.test.ts` |
| **AC-QWEN-04** | Action visibility + interaction flow test | Cypress (hover + click sequence) | `cypress/e2e/ac-qwen-04-actions.cy.ts` |
| **AC-QWEN-05** | Sidebar DOM structure + rename/delete/export UX flow | Cypress + API mocking | `cypress/e2e/ac-qwen-05-sidebar.cy.ts` |
| **AC-QWEN-06** | Model selector rendering + dropdown open/close + value change | Cypress + `cy.get('select').select()` | `cypress/e2e/ac-qwen-06-model-selector.cy.ts` |
| **AC-QWEN-07** | Upload zone drag/drop + file preview + API call verification | Cypress + `cypress-file-upload` plugin | `cypress/e2e/ac-qwen-07-upload.cy.ts` |

## Environment
- Backend: `http://127.0.0.1:8000` (dev server)
- Frontend: `http://127.0.0.1:3000` (Vite dev server)
- Test runner: Cypress v13 (E2E), pytest v8 (unit/SSE)

## Exit Criteria
- ✅ All 7 ACs pass with ≥95% coverage per test case
- ✅ Zero critical defects (UI misalignment >2px, SSE parse failure, missing MVP component)
- ✅ TTFT p95 ≤ 1500ms (measured via `test/ttft_benchmark.py`)

---

## Artifacts to Generate
- `cypress/e2e/ac-qwen-01-theme.cy.ts`
- `cypress/e2e/ac-qwen-02-bubbles.cy.ts`
- `test/sse-parser.test.ts`
- `cypress/e2e/ac-qwen-04-actions.cy.ts`
- `cypress/e2e/ac-qwen-05-sidebar.cy.ts`
- `cypress/e2e/ac-qwen-06-model-selector.cy.ts`
- `cypress/e2e/ac-qwen-07-upload.cy.ts`
- `test/ttft_benchmark.py`

✅ All scripts will be written and committed to `web/minibot-https-www-qianwen-gen-20260319233410/`.
