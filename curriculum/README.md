# Source-audited A/L ICT catalogue

The reviewed catalogue covers the **NIE syllabus effective from 2017**, not a claim that a particular later examination year's applicability has been confirmed. The official PDF was fetched again on 2026-11-22 and its SHA-256 matched the supplied copy:

`577659c643467316a84fae39fadc49b4753f8b8f553e8e66cf1655c8951082f8`

Source: [National Institute of Education syllabus](https://nie.lk/pdffiles/tg/eALSyl%20ICT.pdf). All page references below are physical PDF pages, counted from one; printed table pages are 11 lower.

| Unit | Competency levels | Explicit outcomes |
| --- | ---: | ---: |
| 1. Concept of ICT | 7 | 45 |
| 2. Introduction to Computer | 4 | 22 |
| 3. Data Representation | 3 | 15 |
| 4. Fundamental of Digital Circuits | 4 | 17 |
| 5. Computer Operating System | 4 | 38 |
| 6. Data Communication and Networking | 12 | 46 |
| 7. System Analysis and Design | 10 | 41 |
| 8. Database Management | 7 | 43 |
| 9. Programming | 13 | 43 |
| 10. Web Development | 8 | 30 |
| 11. Internet of Things | 2 | 9 |
| 12. ICT in Business | 3 | 12 |
| 13. New trends and Future Directions of ICT | 3 | 7 |
| 14. Project | 2 | 0 |
| Total | **82** | **368** |

The three files in `reviewed/` record exact source wording, competency and subtopic mappings, page spans, reviewer identity, normalization decisions, content topics, period allocations and source defects. Review was performed by Codex through source comparison; it is not teacher approval of questions. The original `extracted-review.json` stays explicitly unverified as an audit input.

All **359 original candidate IDs are retained**. Nine IoT outcomes were missed because their source uses a different bullet glyph and layout. Source Business level 12.2 is printed as 11.2 on PDF page 58: its four existing `NIE2017-11.2-*` IDs stay stable while their unit and level mappings are corrected. The genuine IoT 11.2 outcomes use `NIE2017-11.2-iot-*` IDs. IDs belong to this application, not NIE.

Project has two competency levels but no explicit outcome bullets. Both levels are retained with empty outcome lists. PDF page 62 explicitly assigns the project to Grade 13; other unit-to-grade allocations stay unset because this combined source does not specify them. The overview on PDF page 11 misnumbers the final units and its total differs from the later policy text; detailed competency-table numbering is used, with discrepancies preserved in audit notes.

Source defects such as incomplete outcome sentences are recorded without inventing missing wording. Source verification alone does not provide a complete reviewed question bank, teaching-note corpus or Sinhala translations. Coverage must distinguish these from curriculum inventory completeness.

Validate the complete source catalogue without changing PostgreSQL:

```cmd
cd /d E:\ictrootai\backend
.venv\Scripts\python.exe -m app.curriculum_catalogue
```

After migrations, `python -m app.curriculum_catalogue --apply` backs up existing curriculum metadata privately and upserts the reviewed catalogue transactionally. It preserves questions, account records, supplementary demo outcomes and existing IDs; it does not seed accounts or approve model-generated content.
