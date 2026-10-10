"""Tests for election/source.py's challenge test: real challenge and block pages stop a host; ordinary pages that merely
carry a bot vendor's or a form's script do not (the mistake of 2026-10-10 that stopped vote.utah.gov, coloradosos.gov
and 981 campaign sites for 18 hours). Nothing here makes a request: every answer comes from a replay function.

    .venv\\Scripts\\python.exe -m unittest election.tests.test_source_gate
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from election import source  # noqa: E402

HTML = {"Content-Type": "text/html; charset=utf-8"}
WORDS = b"<p>" + b"Find your polling place, see what is on your ballot and learn how to vote by mail. " * 12 + b"</p>"


def page(title, extra=b"", words=WORDS):
    return (b"<!DOCTYPE html><html><head><meta charset='utf-8'><title>" + title + b"</title>" + extra +
            b"</head><body><h1>" + title + b"</h1>" + words + b"</body></html>")


# Ordinary pages, served normally, that the old test took for challenges.
RECAPTCHA = page(b"Regular General Election: November 3, 2026 - Utah Voter Information",
                 b"<script src='https://www.google.com/recaptcha/api.js?render=explicit' async defer></script>"
                 b"<style>.grecaptcha-badge{visibility:hidden}</style>")
CF_BACKGROUND = page(b"Colorado Secretary of State", words=WORDS + (
    b"<script>(function(){function c(){var b=a.contentDocument||a.contentWindow.document;if(b){var d=b.createElement("
    b"'script');d.innerHTML=\"window.__CF$cv$params={r:'8f00aa11bb22cc33',t:'MTcyODU1MDAwMC4wMDAwMDA='};var a=document."
    b"createElement('script');a.nonce='';a.src='/cdn-cgi/challenge-platform/scripts/jsd/main.js';document."
    b"getElementsByTagName('head')[0].appendChild(a);\";b.getElementsByTagName('head')[0].appendChild(d)}}})();</script>"))
CONTACT_FORM = page(b"Tina for the House", words=WORDS + (
    b"<form><div class='h-captcha' data-sitekey='x'></div><div class='g-recaptcha'></div>"
    b"<p>This form is protected by reCAPTCHA and the Google Privacy Policy. We use a CAPTCHA to stop spam.</p></form>"
    b"<script src='https://js.hcaptcha.com/1/api.js'></script>"))
IMPERVA_ON_PAGE = page(b"Department of State: Elections",
                       b"<script src='/_Incapsula_Resource?SWJIYLWA=719d34d31c8e3a6e6fffd425f7e032f3&ns=1'></script>")
SPA_SHELL = (b"<!doctype html><html><head><title>Vote Jess</title><script src='https://www.google.com/recaptcha/api.js'>"
             b"</script><script src='/app.js'></script></head><body><div id='root'></div></body></html>")

# Real challenge and block pages.
CF_CHALLENGE = (b"<!DOCTYPE html><html lang=\"en-US\"><head><title>Just a moment...</title><meta http-equiv=\"refresh\" "
                b"content=\"390\"></head><body><div class=\"main-wrapper\"><h1>www.example.gov</h1><p>Enable JavaScript "
                b"and cookies to continue</p></div><script>(function(){window._cf_chl_opt={cvId: '3',cZone: "
                b"'www.example.gov',cType: 'managed'};var a=document.createElement('script');a.src='/cdn-cgi/"
                b"challenge-platform/h/g/orchestrate/chl_page/v1?ray=8f00';document.head.appendChild(a);}());"
                b"</script></body></html>")
CF_OLD_CAPTCHA = page(b"Attention Required! | Cloudflare", words=b"<p>Please complete the security check to access.</p>")
CF_MARK_ONLY = (b"<html><head><title>example.gov</title></head><body><form id=\"challenge-form\" action=\"/?__cf_chl_f_tk="
                b"x\" method=\"POST\"></form><script>window._cf_chl_opt={cType:'managed'}</script></body></html>")
IMPERVA_STUB = (b"<html>\r\n<head>\r\n<META NAME=\"robots\" CONTENT=\"noindex,nofollow\">\r\n<script src=\"/_Incapsula_Resource"
                b"?SWJIYLWA=5074a744e2e3d891814e9a2dace20bd4,719d34d31c8e3a6e6fffd425f7e032f3\">\r\n</script>\r\n<body>\r\n"
                b"</body></html>\r\n")
IMPERVA_INCIDENT = (b"<html style=\"height:100%\"><head><META NAME=\"ROBOTS\" CONTENT=\"NOINDEX, NOFOLLOW\"></head><body>"
                    b"<iframe id=\"main-iframe\" src=\"/_Incapsula_Resource?CWUDNSAI=9&xinfo=1-2&incident_id=3-4&edet=12"
                    b"\">Request unsuccessful. Incapsula incident ID: 1000-2000</iframe></body></html>")
RADWARE = (b"<html><head><title>Radware Bot Manager Captcha</title></head><body><script>window.location.href="
           b"'https://validate.perfdrive.com/abc/captcha?ssa=1'</script></body></html>")
RADWARE_REDIRECT = (b"<html><head><title>sos.example.gov</title></head><body><script>window.location.href="
                    b"'https://validate.perfdrive.com/abc/captcha?ssa=1'</script></body></html>")
HUMAN_CHECK = page(b"Human Verification", words=b"<p>Please verify that you are a human to continue.</p>")
DATADOME_STUB = (b"<html><head><title>example.com</title><style>#cmsg{animation: A 1.5s;}</style></head><body>"
                 b"<p id=\"cmsg\">Please enable JS and disable any ad blocker</p><script src=\"https://ct.captcha-delivery.com"
                 b"/c.js\"></script></body></html>")


def answer(status, body, headers=None):
    return source.Source(replay=lambda url: (status, body, dict(headers or HTML)), log=lambda *_: None, never_extra=(),
                         stopped_file=None)


class OrdinaryPagesTest(unittest.TestCase):
    """A page served normally is read, whatever scripts it carries, and the host is not stopped."""

    def check_ordinary(self, body, expect_html=True):
        src = answer(200, body)
        r = src.get("https://site.example.gov/", expect_html=expect_html)
        self.assertFalse(r.refused, r.why)
        self.assertTrue(r.ok)
        self.assertIsNone(src.stopped("site.example.gov"))
        src.get("https://site.example.gov/again")          # still allowed: no Refused raised

    def test_recaptcha_script(self):
        self.check_ordinary(RECAPTCHA)

    def test_cloudflare_background_script(self):
        self.check_ordinary(CF_BACKGROUND)

    def test_contact_form_captchas_and_the_word(self):
        self.check_ordinary(CONTACT_FORM)

    def test_imperva_script_on_a_full_page(self):
        self.check_ordinary(IMPERVA_ON_PAGE)

    def test_app_shell_with_recaptcha(self):
        self.check_ordinary(SPA_SHELL)

    def test_json_mentioning_captcha(self):
        src = answer(200, b'{"note": "captcha", "challenge-platform": 1}', {"Content-Type": "application/json"})
        self.assertFalse(src.get("https://data.example.gov/r.json").refused)

    def test_a_500_is_a_failure_not_a_refusal(self):
        src = answer(500, page(b"Server error"))
        r = src.get("https://site.example.gov/")
        self.assertFalse(r.refused)
        self.assertFalse(r.ok)
        self.assertIsNone(src.stopped("site.example.gov"))


class ChallengePagesTest(unittest.TestCase):
    """A real challenge or block page stops the host for the night, and the next request is never sent."""

    def check_refused(self, status, body, headers=None):
        calls = []

        def replay(url):
            calls.append(url)
            return status, body, dict(headers or HTML)
        src = source.Source(replay=replay, log=lambda *_: None, never_extra=(), stopped_file=None)
        r = src.get("https://wall.example.gov/", expect_html=True)
        self.assertTrue(r.refused, f"not refused: {status}")
        self.assertFalse(r.ok)
        self.assertTrue(src.stopped("wall.example.gov"))
        with self.assertRaises(source.Refused):
            src.get("https://wall.example.gov/other")
        self.assertEqual(len(calls), 1)
        return r

    def test_403_and_429(self):
        self.check_refused(403, b"forbidden")
        self.check_refused(429, b"slow down")

    def test_cloudflare_challenge_any_status(self):
        for status in (403, 503, 200):
            self.check_refused(status, CF_CHALLENGE)

    def test_cloudflare_header(self):
        self.check_refused(200, page(b"Results"), {"Content-Type": "text/html", "cf-mitigated": "challenge"})

    def test_aws_waf_header(self):
        self.check_refused(202, b"", {"Content-Type": "text/html", "x-amzn-waf-action": "challenge"})

    def test_cloudflare_old_captcha_title(self):
        self.check_refused(200, CF_OLD_CAPTCHA)

    def test_cloudflare_markers_without_its_title(self):
        self.check_refused(200, CF_MARK_ONLY)

    def test_imperva_stub(self):
        self.check_refused(200, IMPERVA_STUB, {"Content-Type": "text/html"})

    def test_imperva_incident(self):
        self.check_refused(200, IMPERVA_INCIDENT)

    def test_radware(self):
        self.check_refused(200, RADWARE)
        self.check_refused(200, RADWARE_REDIRECT)

    def test_human_verification(self):
        self.check_refused(200, HUMAN_CHECK)

    def test_datadome_stub(self):
        self.check_refused(403, DATADOME_STUB)
        self.check_refused(200, DATADOME_STUB)

    def test_older_test_still_refused(self):
        self.check_refused(200, b"<!DOCTYPE html><title>Just a moment...</title>")


class ReasonTest(unittest.TestCase):
    def test_visible_text(self):
        self.assertEqual(source.visible_text_len(IMPERVA_STUB), 0)
        self.assertGreater(source.visible_text_len(RECAPTCHA), 500)

    def test_reason_words(self):
        self.assertEqual(source.challenge_reason(200, {}, RECAPTCHA), "")
        self.assertEqual(source.challenge_reason(200, {}, CF_BACKGROUND), "")
        self.assertTrue(source.challenge_reason(200, {}, CF_CHALLENGE))


if __name__ == "__main__":
    unittest.main()
