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


DECLINED = _completed(1, "", "Too few characters. Skipping this page\nError during processing.\n")


def _osd(turn: int):
    return _completed(0, OSD_TURN_90.replace("Rotate: 90", f"Rotate: {turn}"))


def _scripted_run(monkeypatch, *results):
    commands = []
    answers = iter(results)

    def run(command, **kwargs):
        commands.append(command)
        return next(answers)

    monkeypatch.setattr(documents_module.subprocess, "run", run)
    return commands


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_page_turn_is_tesseracts_rotate(monkeypatch, tmp_path, turn):
    commands = _scripted_run(monkeypatch, _osd(turn))
    assert _tesseract_page_turn(tmp_path / "page.png") == turn
    assert commands == [["tesseract", str(tmp_path / "page.png"), "stdout", "--psm", "0"]]


@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_a_declined_page_is_judged_again_from_fewer_characters(monkeypatch, tmp_path, turn):
    commands = _scripted_run(monkeypatch, DECLINED, _osd(turn))
    assert _tesseract_page_turn(tmp_path / "page.png") == turn
    assert commands[1] == [
        "tesseract", str(tmp_path / "page.png"), "stdout", "--psm", "0",
        "-c", "min_characters_to_try=10",
    ]


def test_page_turn_is_zero_when_tesseract_cannot_judge(monkeypatch, tmp_path):
    commands = _scripted_run(monkeypatch, DECLINED, DECLINED)
    assert _tesseract_page_turn(tmp_path / "page.png") == 0
    assert len(commands) == 2


@pytest.mark.parametrize(
    "result",
    [
        _completed(
            1,
            "",
            "Error opening data file /x/osd.traineddata\nFailed loading language 'osd'\n"
            "Tesseract couldn't load any languages!\nCould not initialize tesseract.\n",
        ),
        _osd(45),
        _completed(0, "Page number: 0\n"),
        _completed(1, "", "Error during processing.\n"),
    ],
)
@pytest.mark.parametrize("declined_first", [False, True])
def test_page_turn_fails_closed(monkeypatch, tmp_path, result, declined_first):
    _scripted_run(monkeypatch, *([DECLINED] if declined_first else []), result)
    with pytest.raises(RuntimeError, match="orientation detection"):
        _tesseract_page_turn(tmp_path / "page.png")


# ---------------------------------------------------------------------------
# Which read a page gets (a fake Tesseract records every command and image).


class FakeTesseract:
    """Stands in for the tesseract CLI. OSD answers ``osd`` in turn (None: declines); the
    ``stdout`` read prints ``reads[image name]``'s text; the ``txt tsv`` read writes that
    text and its word confidences."""

    def __init__(self, osd, reads: dict[str, tuple[str, tuple[float, ...]]]):
        self.osd = list(osd) if isinstance(osd, (list, tuple)) else [osd, osd]
        self.reads = reads
        self.commands: list[list[str]] = []
        self.images: dict[str, bytes] = {}

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        image = Path(command[1])
        self.images[image.name] = image.read_bytes()
        if "--psm" in command and command[command.index("--psm") + 1] == "0":
            answer = self.osd.pop(0)
            if answer is None:
                return DECLINED
            return _completed(0, answer)
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

    def read_images(self):
        return [Path(c[1]).name for c in self.commands if c[-2:] == ["txt", "tsv"]]


def _page_pixmap():
    pixmap = fitz.Pixmap(fitz.csRGB, 7, 5, bytes(range(105)), False)
    pixmap.set_dpi(200, 200)
    return pixmap


def _confident(words: int, junk: int = 20) -> tuple[float, ...]:
    """Word confidences: ``words`` read at 95 and ``junk`` at 40."""
    return tuple([95.0] * words + [40.0] * junk)


GOOD = _confident(40)
BAD = _confident(2, junk=30)


def _read(monkeypatch, fake, extraction):
    monkeypatch.setattr(documents_module.subprocess, "run", fake)
    return _ocr_pixmap_text(_page_pixmap(), extraction=extraction)


def test_without_the_setting_the_page_is_read_once_as_rendered(monkeypatch):
    fake = FakeTesseract(OSD_TURN_90, {"page.png": ("as rendered\n", BAD)})
    assert _read(monkeypatch, fake, {"ocr": True, "ocr_orientation": False}) == "as rendered\n"
    assert [command[2:] for command in fake.commands] == [["stdout", "-l", "eng"]]


@pytest.mark.parametrize(
    "osd", [OSD_TURN_90.replace("Rotate: 90", "Rotate: 0"), [None, None], [None, OSD_TURN_90.replace("Rotate: 90", "Rotate: 0")]]
)
def test_an_upright_or_unjudged_page_gets_exactly_the_read_without_the_setting(monkeypatch, osd):
    extraction = {"ocr": True, "ocr_language": "deu", "ocr_psm": 6}
    off = FakeTesseract(osd, {"page.png": ("as rendered\n", BAD)})
    without = _read(monkeypatch, off, {**extraction, "ocr_orientation": False})
    on = FakeTesseract(osd, {"page.png": ("as rendered\n", BAD)})
    assert _read(monkeypatch, on, extraction) == without == "as rendered\n"
    read_without = off.commands[0][2:]
    assert read_without == ["stdout", "-l", "deu", "--psm", "6"]
    assert on.commands[-1][2:] == read_without
    assert all(c[3:5] == ["--psm", "0"] for c in on.commands[:-1])
    assert on.images["page.png"] == off.images["page.png"] == _page_pixmap().tobytes("png")


@pytest.mark.parametrize("turn", [90, 180, 270])
def test_a_turned_page_is_read_upright_when_that_reads_better(monkeypatch, turn):
    fake = FakeTesseract(
        OSD_TURN_90.replace("Rotate: 90", f"Rotate: {turn}"),
        {"page.png": ("upside down\n", BAD), f"turned-{turn}.png": ("upright\n", GOOD)},
    )
    assert _read(monkeypatch, fake, {"ocr": True}) == "upright\n"
    turned = _rotate_pixmap_clockwise(_page_pixmap(), turn).tobytes("png")
    assert fake.images[f"turned-{turn}.png"] == turned
    assert fake.read_images() == ["page.png", f"turned-{turn}.png"]


def test_a_turn_that_does_not_read_better_is_not_kept(monkeypatch):
    fake = FakeTesseract(
        OSD_TURN_90.replace("Rotate: 90", "Rotate: 180"),
        {"page.png": ("as rendered\n", GOOD), "turned-180.png": ("turned\n", BAD)},
    )
    assert _read(monkeypatch, fake, {"ocr": True}) == "as rendered\n"
    assert fake.read_images() == ["page.png", "turned-180.png"]


@pytest.mark.parametrize("turn", [90, 270])
def test_the_other_side_is_tried_when_detection_names_the_wrong_side(monkeypatch, turn):
    # OH-09-027 page 48: detection said 270 (confidence 0.5); the page reads at 90.
    other = 360 - turn
    fake = FakeTesseract(
        OSD_TURN_90.replace("Rotate: 90", f"Rotate: {turn}"),
        {
            "page.png": ("upside down\n", _confident(26)),
            f"turned-{turn}.png": ("still upside down\n", _confident(25)),
            f"turned-{other}.png": ("upright\n", _confident(216)),
        },
    )
    assert _read(monkeypatch, fake, {"ocr": True}) == "upright\n"
    assert fake.read_images() == ["page.png", f"turned-{turn}.png", f"turned-{other}.png"]


@pytest.mark.parametrize(
    ("turn", "kept"),
    [
        # Detection says the page is turned a quarter clockwise, which Tesseract reads about
        # as well as upright: the upright read is kept on a tie.
        (270, "turned\n"),
        # A tie is no evidence for 90 or 180: an upright page turned 90 also reads well.
        (90, "as rendered\n"),
        (180, "as rendered\n"),
    ],
)
def test_only_a_detected_quarter_clockwise_turn_wins_a_tie(monkeypatch, turn, kept):
    reads = {"page.png": ("as rendered\n", _confident(60))}
    for candidate in (90, 180, 270):
        reads[f"turned-{candidate}.png"] = ("turned\n", _confident(60))
    fake = FakeTesseract(OSD_TURN_90.replace("Rotate: 90", f"Rotate: {turn}"), reads)
    assert _read(monkeypatch, fake, {"ocr": True}) == kept


def test_two_upside_down_reads_do_not_tie(monkeypatch):
    # OH-10-006 page 48: detection said 270, but the page is turned the other way. As
    # rendered and turned 270 it reads upside down (18 and 21 read words of 121); the
    # opposite turn reads it.
    fake = FakeTesseract(
        OSD_TURN_90.replace("Rotate: 90", "Rotate: 270"),
        {
            "page.png": ("upside down\n", _confident(18, junk=103)),
            "turned-270.png": ("upside down too\n", _confident(21, junk=100)),
            "turned-90.png": ("upright\n", _confident(88, junk=30)),
        },
    )
    assert _read(monkeypatch, fake, {"ocr": True}) == "upright\n"
    assert fake.read_images() == ["page.png", "turned-270.png", "turned-90.png"]


@pytest.mark.parametrize("value", ["yes", 1, None, "true"])
def test_ocr_orientation_must_be_a_boolean(value):
    with pytest.raises(ValueError, match="ocr_orientation must be true or false"):
        documents_module._pdf_ocr_orientation({"ocr_orientation": value})


confidences = st.lists(st.floats(min_value=0, max_value=100, allow_nan=False), max_size=60)


def _read_words(confidences) -> int:
    return sum(c >= documents_module._OCR_CONFIDENT_WORD for c in confidences)


@settings(max_examples=1000, deadline=None)
@given(confidences, confidences, st.booleans())
def test_the_turn_gate_never_keeps_a_worse_read(turned, rendered, tie):
    t, r = _TesseractRead("", tuple(turned)), _TesseractRead("", tuple(rendered))
    if not _turned_read_is_better(t, r, tie=tie):
        return
    assert _read_words(turned) >= _read_words(rendered)
    if not _turned_read_is_better(t, r, tie=False):
        # Kept only as a tie: the read as rendered was good and the turn holds enough words.
        assert tie
        assert _read_words(rendered) >= documents_module._OCR_GOOD_READ_SHARE * len(rendered)
        assert _read_words(turned) >= documents_module._OCR_TIE_MIN_WORDS
    else:
        assert _read_words(turned) >= _read_words(rendered) + documents_module._OCR_TURN_MIN_GAIN
        assert not _turned_read_is_better(r, t, tie=False)


@settings(max_examples=500, deadline=None)
@given(confidences)
def test_the_strict_gate_is_never_a_tie(turned):
    t = _TesseractRead("", tuple(turned))
    assert not _turned_read_is_better(t, t, tie=False)
    good = _read_words(turned) >= documents_module._OCR_GOOD_READ_SHARE * len(turned)
    enough = _read_words(turned) >= documents_module._OCR_TIE_MIN_WORDS
    assert _turned_read_is_better(t, t, tie=True) == (good and enough)


@settings(max_examples=1000, deadline=None)
@given(confidences, confidences, st.floats(min_value=0, max_value=100, allow_nan=False), st.booleans())
def test_the_turn_gate_is_monotone_in_the_turned_read(turned, rendered, extra, tie):
    t, r = _TesseractRead("", tuple(turned)), _TesseractRead("", tuple(rendered))
    if _turned_read_is_better(t, r, tie=tie):
        assert _turned_read_is_better(_TesseractRead("", (*turned, extra)), r, tie=tie)
    if _turned_read_is_better(t, r, tie=False):
        assert _turned_read_is_better(t, r, tie=True)


@settings(max_examples=1000, deadline=None)
@given(confidences, confidences, st.floats(min_value=0, max_value=100, allow_nan=False))
def test_a_better_read_as_rendered_never_loses_to_a_strict_turn(turned, rendered, extra):
    t, r = _TesseractRead("", tuple(turned)), _TesseractRead("", tuple(rendered))
    if not _turned_read_is_better(t, r, tie=False):
        assert not _turned_read_is_better(t, _TesseractRead("", (*rendered, extra)), tie=False)


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



# Pages of the 2026-09-13 CMS state-plan scopes (docs/ingest-runs/2026-10-13-ocr-page-orientation.md).
CMS_SOURCES = Path(__file__).resolve().parents[1] / "data/corpus/sources"


def _cms_page(state: str, plan: str, name: str, number: int) -> fitz.Pixmap:
    path = (
        CMS_SOURCES / f"us-{state}/policy/2026-09-13-{plan}/official-documents"
        / f"us-{state}-cms-{plan}-spa-{name}.pdf"
    )
    with fitz.open(path) as document:
        return document[number - 1].get_pixmap(dpi=200, alpha=False)


def _reads(pixmap) -> tuple[str, str]:
    on = _ocr_pixmap_text(pixmap, extraction={"ocr": True})
    off = _ocr_pixmap_text(pixmap, extraction={"ocr": True, "ocr_orientation": False})
    return " ".join(on.split()), " ".join(off.split())


@real_tesseract
def test_an_upright_letter_detection_calls_upside_down_reads_as_before():
    # Tesseract 5.5.3 detects this upright CMS letter as "Rotate: 180" at confidence 18.7.
    on, off = _reads(_cms_page("ct", "medicaid-state-plan", "ct-12-009-approval-document", 2))
    assert on == off
    assert "Dear Mr. Bremby" in on


@real_tesseract
def test_a_sideways_organisation_chart_reads_upright():
    on, off = _reads(_cms_page("ut", "medicaid-state-plan", "ut-14-0004-mm-approval-document", 24))
    assert "Executive Director" in on and "David Patton" in on
    assert "Executive Director" not in off


@real_tesseract
def test_a_sideways_slide_never_reads_worse():
    # UT-14-0007-MM page 21 reads "(uas)pjiy usoqun sjuerddy" as rendered. With Tesseract
    # 5.5.3 the turned read wins by 6 confident words to 2 and is kept; a Tesseract that
    # reads it differently may keep the read as rendered, never a worse one.
    on, off = _reads(_cms_page("ut", "medicaid-state-plan", "ut-14-0007-mm-approval-document", 21))
    assert "Spouse of Applicant" not in off
    assert on == off or "Spouse of Applicant" in on
