import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import yaml

import build
import indexnow

NETWORK_FORBIDDEN = "тест IndexNow пытался выйти в сеть"
KEY = "0123456789abcdef0123456789abcdef"
SITE = {"base_url": "https://example.test",
        "indexnow": {"key": KEY, "endpoint": "https://indexnow.example/indexnow"}}
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.test/</loc><lastmod>2026-10-26</lastmod></url>
  <url><loc>https://example.test/en/</loc><lastmod>2026-10-26</lastmod></url>
</urlset>
"""


def refuse_network(*_args, **_kwargs):
    raise AssertionError(NETWORK_FORBIDDEN)


def setUpModule():
    """Любой настоящий запрос из тестов этого файла падает: подмена одного mock не откроет сеть."""
    global _network_guard
    _network_guard = mock.patch("indexnow.urllib.request.urlopen", side_effect=refuse_network)
    _network_guard.start()


def tearDownModule():
    _network_guard.stop()


class NetworkGuardTest(unittest.TestCase):
    def test_real_request_is_refused_in_tests(self):
        with self.assertRaisesRegex(AssertionError, NETWORK_FORBIDDEN):
            indexnow.post_json(SITE["indexnow"]["endpoint"], {})

    def test_real_sitemap_read_is_refused_in_tests(self):
        with self.assertRaisesRegex(AssertionError, NETWORK_FORBIDDEN):
            indexnow.read_sitemap(SITE, [])


class KeyTest(unittest.TestCase):
    def test_key_file_is_named_after_key_and_contains_it(self):
        self.assertEqual(indexnow.key_file_name(SITE["indexnow"]), f"{KEY}.txt")
        self.assertEqual(indexnow.key_file_content(SITE["indexnow"]), KEY)

    def test_malformed_keys_are_rejected(self):
        for key in ("", "abc", KEY.upper(), KEY + "0", "g" * 32, None):
            with self.subTest(key=key), self.assertRaises(ValueError):
                indexnow.check_key({"key": key})

    def test_real_site_key_is_valid(self):
        site = build.load()[0]
        self.assertEqual(indexnow.check_key(site["indexnow"]), site["indexnow"]["key"])


class StaleKeyFilesTest(unittest.TestCase):
    def test_only_files_of_other_keys_are_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (f"{KEY}.txt", "f" * 32 + ".txt", "robots.txt", "llms.txt", "f" * 32 + ".html"):
                (root / name).write_text("x", encoding="utf-8")
            stale = [path.name for path in indexnow.stale_key_files(root, SITE["indexnow"])]
        self.assertEqual(stale, ["f" * 32 + ".txt"])


class KeyFileInBuildTest(unittest.TestCase):
    def write_sitewide_into(self, directory):
        site = build.load()[0]
        written = {}
        with mock.patch("build.OUT", directory), \
                mock.patch("build.write", side_effect=lambda path, text: written.update({path: text})), \
                mock.patch("build.sitewide.previous_lastmods", return_value={}), \
                mock.patch("build.sitewide.build_sitemap", return_value=""), \
                mock.patch("build.sitewide.build_llms_file", return_value=""), \
                mock.patch("build.sitewide.build_manifest", return_value=""), \
                mock.patch("build.localized_site", side_effect=lambda site, locale: site):
            build.write_sitewide(site, {}, {}, [mock.Mock(url_prefix="")], None, {}, [], "")
        return site["indexnow"]["key"], written

    def test_site_build_writes_key_file_with_the_key(self):
        with tempfile.TemporaryDirectory() as directory:
            key, written = self.write_sitewide_into(Path(directory))
            self.assertEqual(written[Path(directory) / f"{key}.txt"], key)

    def test_site_build_removes_key_files_of_old_keys_only_in_its_own_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_key_file = root / ("f" * 32 + ".txt")
            robots = root / "robots.txt"
            for path in (old_key_file, robots):
                path.write_text("x", encoding="utf-8")
            self.write_sitewide_into(root)
            self.assertFalse(old_key_file.exists())
            self.assertTrue(robots.exists())


class SitemapUrlsTest(unittest.TestCase):
    def test_urls_come_in_file_order(self):
        self.assertEqual(indexnow.sitemap_urls(SITEMAP),
                         ["https://example.test/", "https://example.test/en/"])

    def test_alternate_links_are_not_pages(self):
        xml = SITEMAP.replace("</url>", '<xhtml:link href="https://example.test/x/"/></url>', 1) \
                     .replace("<urlset ", '<urlset xmlns:xhtml="http://www.w3.org/1999/xhtml" ', 1)
        self.assertEqual(len(indexnow.sitemap_urls(xml)), 2)


class PayloadTest(unittest.TestCase):
    def test_payload_names_host_key_and_location_of_key_file(self):
        payload = indexnow.build_payload(SITE, ["https://example.test/"])
        self.assertEqual(payload, {"host": "example.test", "key": KEY,
                                   "keyLocation": f"https://example.test/{KEY}.txt",
                                   "urlList": ["https://example.test/"]})

    def test_payload_is_json_serialisable(self):
        json.dumps(indexnow.build_payload(SITE, indexnow.sitemap_urls(SITEMAP)))


class SubmitTest(unittest.TestCase):
    def test_submit_sends_one_request_to_endpoint_from_data(self):
        send = mock.Mock(return_value=200)
        status = indexnow.submit(SITE, indexnow.sitemap_urls(SITEMAP), send)
        self.assertEqual(status, 200)
        send.assert_called_once()
        endpoint, payload = send.call_args.args
        self.assertEqual(endpoint, "https://indexnow.example/indexnow")
        self.assertEqual(payload["urlList"], ["https://example.test/", "https://example.test/en/"])


class ReportSubmissionTest(unittest.TestCase):
    def report(self, send, sitemap=SITEMAP):
        output = StringIO()
        with redirect_stdout(output):
            code = indexnow.report_submission(SITE, sitemap, send)
        return code, output.getvalue()

    def test_success_is_reported_without_warning(self):
        code, output = self.report(mock.Mock(return_value=202))
        self.assertEqual(code, 0)
        self.assertNotIn("::warning::", output)
        self.assertIn("адресов 2", output)

    def test_service_refusal_is_a_warning_and_does_not_fail(self):
        for status in (400, 403, 422, 429, 500):
            with self.subTest(status=status):
                code, output = self.report(mock.Mock(return_value=status))
                self.assertEqual(code, 0)
                self.assertIn(f"::warning::IndexNow: сервис ответил {status}", output)

    def test_network_error_is_a_warning_and_does_not_fail(self):
        code, output = self.report(mock.Mock(side_effect=OSError("нет сети")))
        self.assertEqual(code, 0)
        self.assertIn("::warning::IndexNow: не отправлено: нет сети", output)

    def test_broken_sitemap_is_a_warning_and_does_not_fail(self):
        send = mock.Mock()
        code, output = self.report(send, "не xml")
        self.assertEqual(code, 0)
        self.assertIn("::warning::", output)
        send.assert_not_called()


class MainTest(unittest.TestCase):
    def test_unreachable_sitemap_is_a_warning_and_does_not_fail(self):
        output = StringIO()
        with mock.patch("indexnow.read_sitemap", side_effect=OSError("404")), redirect_stdout(output):
            self.assertEqual(indexnow.main([]), 0)
        self.assertIn("::warning::IndexNow: не удалось прочитать sitemap.xml: 404", output.getvalue())

    def test_sitemap_can_be_read_from_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sitemap.xml"
            path.write_text(SITEMAP, encoding="utf-8")
            self.assertEqual(indexnow.read_sitemap(SITE, [indexnow.SITEMAP_FILE_FLAG, str(path)]), SITEMAP)

    def test_main_sends_sitemap_urls_through_post_json(self):
        with mock.patch("indexnow.read_sitemap", return_value=SITEMAP), \
                mock.patch("indexnow.post_json", return_value=200) as post, redirect_stdout(StringIO()):
            self.assertEqual(indexnow.main([]), 0)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[1]["urlList"],
                         ["https://example.test/", "https://example.test/en/"])


class DeployWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workflow = build.ROOT.parent / ".github" / "workflows" / "deploy.yml"
        cls.jobs = yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"]

    def test_notification_is_a_separate_job_after_deploy_that_cannot_fail_the_run(self):
        job = self.jobs["indexnow"]
        self.assertEqual(job["needs"], "deploy")
        self.assertTrue(job["continue-on-error"])

    def test_deploy_job_has_no_indexnow_steps(self):
        names = [step.get("name") or step.get("uses") for step in self.jobs["deploy"]["steps"]]
        self.assertEqual(names, ["Deploy to GitHub Pages"])

    def test_notification_reads_sitemap_from_checkout(self):
        steps = self.jobs["indexnow"]["steps"]
        self.assertEqual(steps[0]["uses"], "actions/checkout@v4")
        command = steps[-1]["run"]
        self.assertIn("python generator/indexnow.py --sitemap-file vn.neva.beauty/sitemap.xml", command)


if __name__ == "__main__":
    unittest.main()
