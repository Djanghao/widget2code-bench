"""The packaged skill must be the repository's skill.

SKILL.md sits at the repository root so it is the first thing a reader finds,
and a copy ships inside the package so an installed evaluator carries its own
instructions. Two copies drift silently, which is worse than one that is hard to
find - so assert they are the same file.
"""
from importlib.resources import files
from pathlib import Path


def test_packaged_skill_matches_the_repository_root():
    root = Path(__file__).resolve().parents[1] / "SKILL.md"
    packaged = files("widget2code_bench") / "skill" / "SKILL.md"
    assert root.read_text() == packaged.read_text(), (
        "SKILL.md and src/widget2code_bench/skill/SKILL.md have diverged; "
        "copy the root one over the packaged one"
    )


def test_skill_declares_a_name_and_description():
    text = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
    assert text.startswith("---\n"), "skill needs YAML frontmatter"
    front = text.split("---", 2)[1]
    assert "name:" in front and "description:" in front
