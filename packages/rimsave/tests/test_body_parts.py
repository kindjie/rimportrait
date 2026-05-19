"""Unit tests for body-part index resolution.

Synthetic BodyDef XML covers the pre-order walk independently of the
RimWorld install. Real-data verification lives in
`test_extract_integration.py`.
"""

from __future__ import annotations

from pathlib import Path

from rimsave.body_parts import parse_body_part_index


SYNTHETIC_BODY = """\
<?xml version="1.0" encoding="utf-8" ?>
<Defs>
  <BodyDef>
    <defName>Synth</defName>
    <label>synth body</label>
    <corePart>
      <def>Torso</def>
      <parts>
        <li>
          <def>Head</def>
          <parts>
            <li><def>Eye</def><customLabel>left eye</customLabel></li>
            <li><def>Eye</def><customLabel>right eye</customLabel></li>
          </parts>
        </li>
        <li><def>Arm</def><customLabel>left arm</customLabel></li>
      </parts>
    </corePart>
  </BodyDef>
</Defs>
"""


def test_pre_order_walk_indices(tmp_path: Path) -> None:
  bodies = tmp_path / "Bodies"
  bodies.mkdir()
  (bodies / "Bodies_Synth.xml").write_text(SYNTHETIC_BODY)
  out = parse_body_part_index([bodies])
  assert "Synth" in out
  mapping = out["Synth"]
  assert mapping == {
    0: "Torso",
    1: "Head",
    2: "left eye",
    3: "right eye",
    4: "left arm",
  }


def test_missing_root_directory_is_tolerated() -> None:
  out = parse_body_part_index([Path("/nonexistent/dir")])
  assert out == {}


def test_custom_label_takes_precedence_over_def(tmp_path: Path) -> None:
  bodies = tmp_path / "Bodies"
  bodies.mkdir()
  (bodies / "Bodies_X.xml").write_text("""\
<?xml version="1.0" encoding="utf-8" ?>
<Defs>
  <BodyDef>
    <defName>X</defName>
    <corePart>
      <def>Core</def>
      <parts>
        <li><def>Lung</def><customLabel>left lung</customLabel></li>
        <li><def>Lung</def></li>
      </parts>
    </corePart>
  </BodyDef>
</Defs>
""")
  out = parse_body_part_index([bodies])
  assert out["X"] == {0: "Core", 1: "left lung", 2: "Lung"}
