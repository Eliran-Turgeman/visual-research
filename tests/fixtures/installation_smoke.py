"""Tiny managed render exercising Cairo/Pango without LaTeX or TTS extras."""

from manim import FadeIn, Text

from manim_lib import NarratedScene


class InstallationSmoke(NarratedScene):
    def construct(self):
        with self.narrate("Silent installation check.", beat_id="installation"):
            self.play(FadeIn(Text("Ready to render")), run_time=0.3)
            self.record_visual_event("Text is visible")
