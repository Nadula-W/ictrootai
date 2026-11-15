# Manual question formats

Teachers use Question bank → Manual draft. These examples describe **application schemas**, not official exam questions or verified curriculum content. Set `outcome_id` to a real imported outcome and provide a reviewed explanation before approval. All examples start as drafts. JSON field `sources` contains reviewed resource chunk IDs for that same outcome; conceptual facts require independent teacher review.

Common fields:

```json
{
  "outcome_id": "NIE2017-3.1-conversion-reviewed",
  "kind": "number",
  "difficulty": "medium",
  "prompt": "Convert decimal 59 to hexadecimal. Enter only the hexadecimal digits.",
  "options": [],
  "key": {"answer": "3B", "base": 16},
  "explanation": "59 = 3 × 16 + 11. Hexadecimal 11 is B, so the answer is 3B.",
  "sources": [],
  "rubric": []
}
```

For other formats, replace the relevant fields below. Use a suitable verified outcome; these technical examples must not be mapped to the number-conversion outcome merely for convenience.

| kind | key and additional fields | Marking |
| --- | --- | --- |
| `mcq` | `key: {"answer":"B"}`; four or five unique `{id,text,misconception?}` options | Exact approved option ID |
| `number` | `key: {"answer":"3B","base":16}` | Integer equivalence in declared answer base; allowed bases 2, 8, 10, 16 |
| `boolean` | `key: {"answer":"not (A and B)","variables":["A","B"]}` | Full truth-table equivalence, one to eight unique variables A–H |
| `output` | `key: {"answer":"0\n1\n2"}`; include approved program in prompt | Exact approved output after outer whitespace/line-ending normalization; no code runs |
| `sql` | See below | Disposable read-only SQLite fixture result comparison |
| `short` / `structured` | Teacher-approved `rubric` criteria; expected answer may be in `key.answer` | Pending teacher review; no automatic final descriptive score |

Boolean operators supported: `and`, `or`, `not`, `&`, `|`, `^`, `~`, parentheses, constants 0 and 1. `~` is logical negation here, not Python's integer complement. Calls, attributes and arbitrary Python are rejected. Both the expected expression and variable list are validated before approval.

SQL key example:

```json
{
  "fixtures": [
    "CREATE TABLE learners(id INTEGER, name TEXT)",
    "INSERT INTO learners VALUES (1, 'Amal'), (2, 'Nila')"
  ],
  "expected_rows": [["Amal"], ["Nila"]],
  "ordered": true
}
```

Prompt example: “Write a SELECT query returning learner names ordered alphabetically.” The learner's query should produce the approved expected rows. Only read-only `SELECT`/`WITH` student queries run. Fixtures accept bounded CREATE TABLE and INSERT INTO strings; external DB attachment, pragmas and virtual tables are denied. SQLite semantics apply; this does not mark every PostgreSQL dialect feature. Unordered results preserve duplicate counts and compare integer/float values numerically. Approved expected rows should be verified independently against the fixture.

Rubric example:

```json
[
  {"criterion": "Explains that each position represents a power of two", "weight": 0.5},
  {"criterion": "Provides a correct positional example", "weight": 0.5}
]
```

Rubric weights are teacher guidance in this version. The final teacher score is normalized 0–1 per question; multipart automatic summing is not implemented. Enter a reason when applying a score or override. Invalid legacy technical configurations are sent to teacher review when detected rather than turning configuration errors into student mistakes.

Sinhala translation JSON contains only `prompt` and `options` with unchanged IDs/order. Keep code blocks, SQL, mathematical notation and technical identifiers unchanged. Save as unreviewed, check the saved text and approve with a reason. There is no automatic guarantee of translation accuracy.
