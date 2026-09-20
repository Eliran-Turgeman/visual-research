# Decision workflow components

This silent still is a visual regression reference for the typed decision
workflow primitives. The upper region follows structured input through Choice,
Score, and NOUL questions into a typed result and an explicit schema boundary.
The lower region deliberately separates that structural check from confidence
policy: the answer is schema-valid, while its 74% confidence routes it to human
review rather than automatic action.

Render the documented scene at 854×480:

```powershell
.\.venv\Scripts\python.exe -m manim render -ql -s `
  examples\decision_workflow_components\scene.py DecisionWorkflowComponents
```

Review label readability, safe margins, arrow clearance, schema emphasis, and
the selected review route. This entrypoint is intentionally silent and does not
produce a narration timeline.
