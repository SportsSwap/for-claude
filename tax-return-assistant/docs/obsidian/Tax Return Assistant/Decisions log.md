---
tags: [tax, decisions]
---

# Decisions log

Back to [[Tax Return Assistant]]

## Decided with Claude (14 Oct 2026)
| Question | Decision | Why |
|---|---|---|
| Python or something else? | **Python command-line tool** | Excel/VBA can't redact a PDF before reading it. Hubdoc and Dext receive documents unredacted. |
| How to read PDFs? | **Local only**, with room for an AI reader later | An AI reader would send client data offshore (APP 8) and needs firm approval |
| Tax software | **Xero Tax** | The tool works *around* Xero Tax: pre-fill, lodgment and the official estimate stay there |
| Workpaper layout | **Default layout for now** | All styling is in one file (`layout.py`), so it can be re-skinned to the firm template |
| Scans or digital? | **Mostly digital**, so no OCR yet | Scans get filed and flagged for manual entry |
| Computers | **Windows laptops** | PowerShell setup script |
| First version | **Stages 1–4 working; Xero and FYI built, but tested only with fake data** | No firm credentials available to test against |
| Confirm step | **Yes**: I confirm figures in Excel before the return is built | Catches extraction mistakes before the reviewer sees them |
| Original documents | **Filed unchanged** | FYI is the firm's record system; TASA record-keeping |
| Where the code lives | Its own folder, away from the PLS case study | My request |

## Things Claude decided during the build
- **Unknown hospital cover** is assumed covered, with a note to ask the client.
- **Two calculations** share no code, so a mistake in one shows up as a difference.
- **Rental and other tabs** subtotal each return label separately, and Rental shows net rent.
- **Running the demo twice** doesn't add the documents again.
- **Prior-year comparison** uses the tool's own output from last year automatically.
- **Personal super contributions (D12)** count in the HELP, surcharge and rebate income tests.

The full list, with what each costs if wrong, is in the build session: <https://claude.ai/code/session_01N2pEC5oyPFnAavBcEamEbT>

## Final review (15 Oct 2026)
A second Claude reviewed everything.
- **The tax maths and the Excel formulas were confirmed correct.**
- It found 1 serious bug: figures were lost if `figures.csv` was open in Excel during ingest.
- It found 12 important issues: redaction gaps, encoding, cloud folders, D12, residency, duplicates, Xero token size and others.
- **All of those were fixed**, each with a test.
- The smaller issues are listed in [[Known issues and ideas]].

Related: [[How it works]], [[Privacy rules]]
