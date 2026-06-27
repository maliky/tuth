#!/usr/bin/env python3
"""Run non-mutating MWE portal smoke checks against a live Tusis instance."""

from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, TypeAlias
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

RouteSetT: TypeAlias = tuple[str, str, tuple[str, ...]]

DEFAULT_BASE_URL: Final[str] = "https://sis.wvstu.online"
DEFAULT_OUTPUT: Final[str] = "/tmp/tusis_arch_browser_smoke.json"
DEFAULT_PASSWORD: Final[str] = "PassW0rd!"
PAGE_TIMEOUT_SECONDS: Final[int] = 15

ROUTE_SETS: Final[tuple[RouteSetT, ...]] = (
    (
        "test_student",
        "student",
        (
            "/student/dashboard/",
            "/student/invoice/statement/",
            "/student/curriculum/",
        ),
    ),
    ("test_finance", "finance", ("/staff/finance/",)),
    (
        "test_finance_officer",
        "finance officer",
        (
            "/staff/finance_officer/",
            "/staff/finance/invoices/",
        ),
    ),
    (
        "test_dean",
        "dean",
        (
            "/staff/dean/",
            "/staff/dean/curricula/",
        ),
    ),
    (
        "test_registrar",
        "registrar",
        (
            "/staff/registrar/",
            "/registrar/grades/",
        ),
    ),
    (
        "test_registrar_officer",
        "registrar officer",
        (
            "/staff/reg_officer/",
            "/registrar/course-windows/",
            "/registrar/grades/",
        ),
    ),
    (
        "test_enrollment",
        "enrollment",
        (
            "/staff/enrollment/",
            "/students/",
            "/students/new/",
        ),
    ),
)

ERROR_MARKERS: Final[tuple[tuple[str, str], ...]] = (
    ("server error", "500"),
    ("page not found", "404"),
    ("not found", "404"),
    ("forbidden", "403"),
    ("permission denied", "403"),
)


@dataclass(frozen=True)
class SmokeResult:
    """One browser-visible route check."""

    username: str
    role_label: str
    path: str
    title: str
    elapsed_ms: int
    ok: bool
    reason: str


def _env(name: str, default: str) -> str:
    """Read a trimmed string environment value."""
    return os.getenv(name, default).strip() or default


def _chrome_binary() -> str | None:
    """Return the first available Chrome-compatible browser binary."""
    candidates = (
        os.getenv("CHROME_BINARY"),
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/brave-browser",
        "/usr/bin/brave",
    )
    return next(
        (candidate for candidate in candidates if candidate and Path(candidate).exists()),
        None,
    )


def _chromedriver_path() -> str:
    """Return the preferred chromedriver path."""
    candidates = (
        os.getenv("CHROMEDRIVER_PATH"),
        shutil.which("chromedriver"),
        "/usr/bin/chromedriver",
    )
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("chromedriver not found; install it or set CHROMEDRIVER_PATH.")


def _driver() -> ChromeDriver:
    """Create a headless Chromium driver using the system chromedriver."""
    options = ChromeOptions()
    binary = _chrome_binary()
    if binary:
        options.binary_location = binary
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1400,900")
    service = ChromeService(executable_path=_chromedriver_path())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(5)
    return driver


def _set_basic_auth(driver: ChromeDriver, user: str, password: str) -> None:
    """Attach Basic Auth headers to all Chrome requests."""
    if not user or not password:
        return
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.setExtraHTTPHeaders",
        {"headers": {"Authorization": f"Basic {token}"}},
    )


def _wait_ready(driver: WebDriver) -> None:
    """Wait until the browser reports a fully loaded document."""
    WebDriverWait(driver, PAGE_TIMEOUT_SECONDS).until(
        lambda browser: browser.execute_script("return document.readyState") == "complete"
    )


def _login(driver: WebDriver, base_url: str, username: str, password: str) -> None:
    """Authenticate a runtime MWE user through the portal login form."""
    driver.get(urljoin(base_url, "/auth/login/"))
    _wait_ready(driver)
    driver.find_element(By.ID, "id_username").clear()
    driver.find_element(By.ID, "id_username").send_keys(username)
    driver.find_element(By.ID, "id_password").clear()
    driver.find_element(By.ID, "id_password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    _wait_ready(driver)


def _classify_page(driver: WebDriver) -> tuple[bool, str]:
    """Return whether the current page looks usable."""
    body = driver.find_element(By.TAG_NAME, "body").text.lower()
    for marker, reason in ERROR_MARKERS:
        if marker in body:
            return False, reason
    return True, "ok"


def _visit(
    driver: WebDriver,
    base_url: str,
    username: str,
    role_label: str,
    path: str,
) -> SmokeResult:
    """Visit one route and record browser-visible status."""
    started = time.perf_counter()
    try:
        driver.get(urljoin(base_url, path))
        _wait_ready(driver)
        ok, reason = _classify_page(driver)
        title = driver.title
    except Exception as exc:  # pragma: no cover - operational script
        ok = False
        reason = f"{type(exc).__name__}: {exc}"
        title = ""
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return SmokeResult(
        username=username,
        role_label=role_label,
        path=path,
        title=title,
        elapsed_ms=elapsed_ms,
        ok=ok,
        reason=reason,
    )


def run() -> int:
    """Execute all configured route checks and persist a JSON artifact."""
    base_url = _env("TUSIS_SMOKE_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/"
    password = _env("TUSIS_TEST_PASSWORD", DEFAULT_PASSWORD)
    basic_auth_user = _env("TUSIS_BASIC_AUTH_USER", "tusis")
    basic_auth_password = _env("TUSIS_BASIC_AUTH_PASSWORD", "tusis")
    output = Path(_env("TUSIS_SMOKE_OUTPUT", DEFAULT_OUTPUT))
    results: list[SmokeResult] = []

    driver = _driver()
    try:
        _set_basic_auth(driver, basic_auth_user, basic_auth_password)
        for username, role_label, paths in ROUTE_SETS:
            _login(driver, base_url, username, password)
            for path in paths:
                results.append(_visit(driver, base_url, username, role_label, path))
    finally:
        driver.quit()

    payload = [asdict(result) for result in results]
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    failed = [result for result in results if not result.ok]
    print(f"wrote {output}")
    print(f"{len(results) - len(failed)}/{len(results)} route checks passed")
    for result in failed:
        print(f"FAIL {result.username} {result.path}: {result.reason}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
