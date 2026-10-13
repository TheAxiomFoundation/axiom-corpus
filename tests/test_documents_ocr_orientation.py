"""OCR of PDF pages scanned sideways or upside down (``ocr_orientation``).

The 2026-09-13 Utah CMS state-plan approval documents include training slides scanned
turned a quarter counter-clockwise. Tesseract read them as upside-down text: page 21 of
UT-14-0007-MM came out "(uas)pjiy usoqun sjuerddy" for "Applicant's Unborn Child(ren)".
With ``ocr_orientation`` (the default) such a page is turned upright before it is read,
and a page Tesseract finds upright is read exactly as before.

Invariants (property tests below, real Tesseract where marked):
- The page turn is an exact pixel permutation: turning by d then by 360-d gives back the
  same pixmap, turns compose, and every pixel lands where the rotation sends it.
- A page orientation detection finds upright, or cannot judge, is read with exactly the
  command and image used without the setting, so its text is unchanged.
- A turned read replaces the read as rendered only when the turn reads better
  (``_turned_read_is_better``), so a detection mistake on an upright page changes nothing.
- An upright text page turned by 90, 180 or 270 degrees is read as the upright page.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.documents as documents_module
from axiom_corpus.corpus.documents import (
    _ocr_pixmap_text,
    _rotate_pixmap_clockwise,
    _tesseract_page_turn,
    _TesseractRead,
    _tsv_word_confidences,
    _turned_read_is_better,
)

# ---------------------------------------------------------------------------
# The page turn is an exact pixel permutation.


@st.composite
def pixmaps(draw):
    colorspace = draw(st.sampled_from([fitz.csGRAY, fitz.csRGB]))
    width = draw(st.integers(min_value=1, max_value=9))
    height = draw(st.integers(min_value=1, max_value=9))
    data = draw(st.binary(min_size=width * height * colorspace.n, max_size=width * height * colorspace.n))
    pixmap = fitz.Pixmap(colorspace, width, height, data, False)
    pixmap.set_dpi(draw(st.integers(72, 400)), draw(st.integers(72, 400)))
    return pixmap


def _pixel(pixmap, x: int, y: int) -> bytes:
    start = y * pixmap.stride + x * pixmap.n
    return pixmap.samples[start : start + pixmap.n]


@settings(max_examples=300, deadline=None)
@given(pixmaps(), st.sampled_from([90, 180, 270]))
def test_turn_moves_every_pixel_where_the_rotation_sends_it(pixmap, degrees):
    turned = _rotate_pixmap_clockwise(pixmap, degrees)
    width, height = pixmap.width, pixmap.height
    if degrees == 180:
        assert (turned.width, turned.height) == (width, height)
        assert (turned.xres, turned.yres) == (pixmap.xres, pixmap.yres)
    else:
        assert (turned.width, turned.height) == (height, width)
        assert (turned.xres, turned.yres) == (pixmap.yres, pixmap.xres)
    assert turned.n == pixmap.n and not turned.alpha
    assert turned.colorspace.name == pixmap.colorspace.name
    for y in range(turned.height):
        for x in range(turned.width):
            if degrees == 90:
                source = (y, height - 1 - x)
            elif degrees == 180:
                source = (width - 1 - x, height - 1 - y)
            else:
                source = (width - 1 - y, x)
            assert _pixel(turned, x, y) == _pixel(pixmap, *source)


@settings(max_examples=300, deadline=None)
@given(pixmaps(), st.sampled_from([90, 180, 270]), st.sampled_from([90, 180, 270]))
def test_turns_undo_and_compose(pixmap, first, second):
    once = _rotate_pixmap_clockwise(pixmap, first)
    back = _rotate_pixmap_clockwise(once, 360 - first)
    assert (back.width, back.height, back.samples) == (pixmap.width, pixmap.height, pixmap.samples)
    assert (back.xres, back.yres) == (pixmap.xres, pixmap.yres)
    total = (first + second) % 360
    twice = _rotate_pixmap_clockwise(once, second)
    expected = pixmap if total == 0 else _rotate_pixmap_clockwise(pixmap, total)
    assert (twice.width, twice.height, twice.samples) == (
        expected.width,
        expected.height,
        expected.samples,
    )


@pytest.mark.parametrize("degrees", [0, 45, 360, -90, "90"])
def test_turn_accepts_only_quarter_turns(degrees):
    pixmap = fitz.Pixmap(fitz.csGRAY, 2, 3, bytes(6), False)
    with pytest.raises(ValueError, match="90, 180 or 270"):
        _rotate_pixmap_clockwise(pixmap, degrees)


def test_turn_refuses_alpha():
    pixmap = fitz.Pixmap(fitz.csRGB, 2, 2, bytes(16), True)
    with pytest.raises(ValueError, match="alpha"):
        _rotate_pixmap_clockwise(pixmap, 90)


# ---------------------------------------------------------------------------
# Tesseract output parsing.

TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def test_tsv_word_confidences_reads_only_words_with_text():
    tsv = "\n".join(
        [
            TSV_HEADER,
            "1\t1\t0\t0\t0\t0\t0\t0\t1700\t2200\t-1\t",
            "4\t1\t1\t1\t1\t0\t10\t10\t300\t40\t-1\t",
            "5\t1\t1\t1\t1\t1\t10\t10\t80\t40\t96.5\tApplicant",
            "5\t1\t1\t1\t1\t2\t95\t10\t80\t40\t12\t ",
            "5\t1\t1\t1\t1\t3\t180\t10\t80\t40\t40.25\tSpouse",
        ]
    )
    assert _tsv_word_confidences(tsv) == (96.5, 40.25)
    assert _tsv_word_confidences(TSV_HEADER) == ()
    assert _tsv_word_confidences("") == ()


def _completed(returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


OSD_TURN_90 = (
    "Page number: 0\nOrientation in degrees: 270\nRotate: 90\n"
    "Orientation confidence: 3.87\nScript: Latin\nScript confidence: 10.37\n"
)


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_page_turn_is_tesseracts_rotate(monkeypatch, tmp_path, turn):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return _completed(0, OSD_TURN_90.replace("Rotate: 90", f"Rotate: {turn}"))

    monkeypatch.setattr(documents_module.subprocess, "run", run)
    assert _tesseract_page_turn(tmp_path / "page.png") == turn
    assert commands == [["tesseract", str(tmp_path / "page.png"), "stdout", "--psm", "0"]]


def test_page_turn_is_zero_when_tesseract_cannot_judge(monkeypatch, tmp_path):
    monkeypatch.setattr(
        documents_module.subprocess,
        "run",
        lambda command, **kwargs: _completed(
            1, "", "Too few characters. Skipping this page\nError during processing.\n"
        ),
    )
    assert _tesseract_page_turn(tmp_path / "page.png") == 0


@pytest.mark.parametrize(
    "result",
    [
        _completed(
            1,
            "",
            "Error opening data file /x/osd.traineddata\nFailed loading language 'osd'\n"
            "Tesseract couldn't load any languages!\nCould not initialize tesseract.\n",
        ),
        _completed(0, OSD_TURN_90.replace("Rotate: 90", "Rotate: 45")),
        _completed(0, "Page number: 0\n"),
        _completed(1, "", "Error during processing.\n"),
    ],
)
def test_page_turn_fails_closed(monkeypatch, tmp_path, result):
    monkeypatch.setattr(documents_module.subprocess, "run", lambda command, **kwargs: result)
    with pytest.raises(RuntimeError, match="orientation detection"):
        _tesseract_page_turn(tmp_path / "page.png")


# ---------------------------------------------------------------------------
# Which read a page gets (a fake Tesseract records every command and image).


class FakeTesseract:
    """Stands in for the tesseract CLI: OSD answers ``osd``; the ``stdout`` read prints
    ``reads[image]`` text; the ``txt tsv`` read writes that text and its confidences."""

    def __init__(self, osd: str | None, reads: dict[str, tuple[str, tuple[float, ...]]]):
        self.osd = osd
        self.reads = reads
        self.commands: list[list[str]] = []
        self.images: dict[str, bytes] = {}

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        image = Path(command[1])
        self.images[image.name] = image.read_bytes()
        if command[-2:] == ["--psm", "0"]:
            if self.osd is None:
                return _completed(1, "", "Too few characters. Skipping this page\nError during processing.\n")
            return _completed(0, self.osd)
        text, confidences = self.reads[image.name]
        if command[2] == "stdout":
            return _completed(0, text)
        assert command[-2:] == ["txt", "tsv"]
        base = Path(command[2])
        base.with_suffix(".txt").write_text(text, encoding="utf-8")
        rows = [TSV_HEADER] + [
            f"5\t1\t1\t1\t1\t{i}\t0\t0\t1\t1\t{c}\tw{i}" for i, c in enumerate(confidences, 1)
        ]
        base.with_suffix(".tsv").write_text("\n".join(rows), encoding="utf-8")
        return _completed(0)


def _page_pixmap():
    pixmap = fitz.Pixmap(fitz.csRGB, 7, 5, bytes(range(105)), False)
    pixmap.set_dpi(200, 200)
    return pixmap


GOOD = tuple([95.0] * 40)
BAD = tuple([20.0] * 30 + [70.0] * 2)


def _read(monkeypatch, fake, extraction):
    monkeypatch.setattr(documents_module.subprocess, "run", fake)
    return _ocr_pixmap_text(_page_pixmap(), extraction=extraction)


def test_without_the_setting_the_page_is_read_once_as_rendered(monkeypatch):
    fake = FakeTesseract(OSD_TURN_90, {"page.png": ("as rendered\n", BAD)})
    assert _read(monkeypatch, fake, {"ocr": True, "ocr_orientation": False}) == "as rendered\n"
    assert [command[2:] for command in fake.commands] == [["stdout", "-l", "eng"]]


@pytest.mark.parametrize("osd", [OSD_TURN_90.replace("Rotate: 90", "Rotate: 0"), None])
def test_an_upright_or_unjudged_page_gets_exactly_the_read_without_the_setting(monkeypatch, osd):
    extraction = {"ocr": True, "ocr_language": "deu", "ocr_psm": 6}
    off = FakeTesseract(osd, {"page.png": ("as rendered\n", BAD)})
    without = _read(monkeypatch, off, {**extraction, "ocr_orientation": False})
    on = FakeTesseract(osd, {"page.png": ("as rendered\n", BAD)})
    assert _read(monkeypatch, on, extraction) == without == "as rendered\n"
    read_without = off.commands[0][2:]
    assert read_without == ["stdout", "-l", "deu", "--psm", "6"]
    assert [c[2:] for c in on.commands] == [["stdout", "--psm", "0"], read_without]
    assert on.images["page.png"] == off.images["page.png"] == _page_pixmap().tobytes("png")


def test_a_turned_page_is_read_upright_when_that_reads_better(monkeypatch):
    fake = FakeTesseract(
        OSD_TURN_90,
        {"page.png": ("upside down\n", BAD), "turned.png": ("upright\n", GOOD)},
    )
    assert _read(monkeypatch, fake, {"ocr": True}) == "upright\n"
    assert fake.images["turned.png"] == _rotate_pixmap_clockwise(_page_pixmap(), 90).tobytes("png")
    assert [c[-2:] for c in fake.commands] == [["--psm", "0"], ["txt", "tsv"], ["txt", "tsv"]]


def test_a_turn_that_does_not_read_better_is_not_kept(monkeypatch):
    fake = FakeTesseract(
        OSD_TURN_90,
        {"page.png": ("as rendered\n", GOOD), "turned.png": ("turned\n", BAD)},
    )
    assert _read(monkeypatch, fake, {"ocr": True}) == "as rendered\n"


@pytest.mark.parametrize("value", ["yes", 1, None, "true"])
def test_ocr_orientation_must_be_a_boolean(value):
    with pytest.raises(ValueError, match="ocr_orientation must be true or false"):
        documents_module._pdf_ocr_orientation({"ocr_orientation": value})


confidences = st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), max_size=60)


@settings(max_examples=500, deadline=None)
@given(confidences, confidences)
def test_the_turn_gate_needs_more_confident_words_and_is_one_sided(turned, upright):
    t, u = _TesseractRead("", tuple(turned)), _TesseractRead("", tuple(upright))
    if _turned_read_is_better(t, u):
        confident = documents_module._OCR_CONFIDENT_WORD
        assert sum(c >= confident for c in turned) > sum(c >= confident for c in upright)
        assert not _turned_read_is_better(u, t)
    assert not _turned_read_is_better(u, u)


@settings(max_examples=500, deadline=None)
@given(confidences, confidences, st.floats(min_value=0, max_value=100, allow_nan=False))
def test_the_turn_gate_is_monotone(turned, upright, extra):
    t, u = _TesseractRead("", tuple(turned)), _TesseractRead("", tuple(upright))
    more_t = _TesseractRead("", (*turned, extra))
    more_u = _TesseractRead("", (*upright, extra))
    if _turned_read_is_better(t, u):
        assert _turned_read_is_better(more_t, u)
    if not _turned_read_is_better(t, u):
        assert not _turned_read_is_better(t, more_u)


# ---------------------------------------------------------------------------
# Real Tesseract (CI installs it; AXIOM_CORPUS_REQUIRE_TESSERACT=1 makes a missing install
# fail these tests instead of skipping them).


def _tesseract_has(*models: str) -> bool:
    if not shutil.which("tesseract"):
        return False
    listed = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
    return set(models) <= set((listed.stdout + listed.stderr).split())


def real_tesseract(test):
    """Run ``test`` against the real tesseract CLI, on one thread so it does not starve the
    other test processes, with room for a slow CI runner."""
    marks = (
        pytest.mark.skipif(
            os.environ.get("AXIOM_CORPUS_REQUIRE_TESSERACT") != "1"
            and not _tesseract_has("eng", "osd"),
            reason="needs the tesseract CLI with the eng and osd models",
        ),
        pytest.mark.timeout(180),
        pytest.mark.usefixtures("one_tesseract_thread"),
    )
    for mark in marks:
        test = mark(test)
    return test


PARAGRAPH = (
    "Each applicant must report household income for the month of application. "
    "The agency counts earned income, unearned income and the value of support "
    "provided by a legally responsible relative. A pregnant woman is counted as "
    "herself plus the number of children she expects to deliver. "
)


@pytest.fixture(scope="module")
def one_tesseract_thread():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("OMP_THREAD_LIMIT", "1")
        yield


@pytest.fixture(scope="module")
def upright_page(one_tesseract_thread):
    """A 6x4 inch page of typed text rendered as OCR renders it (200 dpi, no alpha), and its
    read without ``ocr_orientation``."""
    document = fitz.open()
    page = document.new_page(width=432, height=288)
    page.insert_textbox(fitz.Rect(36, 36, 396, 252), PARAGRAPH * 2, fontsize=11, fontname="tiro")
    pixmap = page.get_pixmap(dpi=200, alpha=False)
    return pixmap, _ocr_pixmap_text(pixmap, extraction={"ocr": True, "ocr_orientation": False})


def _turn_of(pixmap) -> int:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "page.png"
        pixmap.save(str(path))
        return _tesseract_page_turn(path)


@real_tesseract
def test_an_upright_page_reads_exactly_as_without_the_setting(upright_page):
    pixmap, without = upright_page
    assert _turn_of(pixmap) == 0
    assert _ocr_pixmap_text(pixmap, extraction={"ocr": True}) == without
    assert "legally responsible relative" in " ".join(without.split())


@real_tesseract
@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_a_turned_page_reads_as_the_upright_page(upright_page, degrees):
    pixmap, without = upright_page
    turned = _rotate_pixmap_clockwise(pixmap, degrees)
    assert _turn_of(turned) == 360 - degrees
    assert _ocr_pixmap_text(turned, extraction={"ocr": True}) == without

