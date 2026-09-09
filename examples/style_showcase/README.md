# Visual language showcase

This still scene is the visual regression reference for the shared technical
objects. It deliberately places token states, a probability distribution, a
stable tree, and a labeled matrix in one composition so changes to the design
system can be judged together.

```powershell
.\.venv\Scripts\python.exe -m manim render -ql -s `
  examples\style_showcase\scene.py VisualLanguageShowcase
```

Review the result for hierarchy, contrast, label fit, repeated spacing, and
whether semantic color remains the strongest signal.
