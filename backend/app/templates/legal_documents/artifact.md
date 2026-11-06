# Contract for court document templates

## References

- `application.docx` is copied byte-for-byte from `/Users/anastasia/Downloads/Заявление на банкротство должника 68344.docx`; SHA-256 `a75e5a28ede1d90d2fb85068b2b8c14bc0031d8035059735a707bc6afa34e76f`; four A4 portrait pages.
- `creditors.docx` is copied byte-for-byte from `/Users/anastasia/Downloads/Список кредиторов 68345.docx`; SHA-256 `2980768b077d0e368966ff4c392768a7c364876dc0a53095ddb94a5f9a110432`; five A4 portrait pages.
- `inventory.docx` is copied byte-for-byte from `/Users/anastasia/Downloads/Опись имущества 68346.docx`; SHA-256 `5b95c31c2d70235f2fd18d01d7103568d789b15761697dc8b1bea212a2e80d09`; one A4 portrait section followed by an A4 landscape section, five pages total.

Reference renders are retained for task QA under `/tmp/uritech-docgen/reference`.

## Page and style system

- Application: A4 portrait, 0.79 inch margins on all sides, Times New Roman-style court filing typography, justified body text and a centered bold title.
- Creditors: A4 portrait, left margin 0.79 inch, right and bottom margins 0.39 inch, top margin 0.59 inch. The official form is table-led and includes footnotes.
- Inventory: the identity page is A4 portrait; asset sections are A4 landscape. The official form is table-led and includes footnotes.
- Existing section geometry, paragraph styles, table grids, borders, footnotes, headers, footers and relationships are preserve-only.

## Editable slots

- Identity: full name split into surname, name and patronymic; birth date and place; passport; SNILS; INN; registration and actual addresses; phone; court.
- Application: creditor summary, total and overdue debt, income/employment, family situation, dependants, cash, bank accounts and signature name.
- Creditors: non-business creditors are placed line-by-line inside the available official row; up to three non-business debtors use the existing rows. Business and tax sections remain blank in this release.
- Inventory: records are grouped by the existing real-estate, vehicle and other-asset category rows. Bank accounts are placed line-by-line inside the available official row; up to three company interests and three securities use the existing rows. Unused rows remain blank.
- Document date and signature name are filled in the closing blocks.

## Fidelity gates

- Generation always starts from a fresh in-memory copy of the retained template.
- Only documented paragraphs and table cells are changed.
- Page orientation, margins, table geometry, official headings, footnotes and unchanged package parts must remain recognizable as the source.
- Generated smoke-test documents must render successfully and every page must be visually inspected before the generator is treated as ready.
