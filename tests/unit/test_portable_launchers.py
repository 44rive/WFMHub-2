from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_doctor_explains_known_device_guard_exit_without_suggesting_bypass() -> None:
    doctor = (ROOT / "packaging/windows/DOCTOR.cmd").read_text(encoding="utf-8")

    assert "1073751882" in doctor
    assert "0x4000274A" in doctor
    assert "CodeIntegrity" in doctor
    assert "3077" in doctor
    assert "Do not try to bypass company policy" in doctor
