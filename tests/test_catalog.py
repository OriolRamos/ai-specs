"""ASP-050, ASP-051: platform repo, catalog check and impact."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "scripts"))

import ai_specs  # noqa: E402
import catalog  # noqa: E402

PRODUCT = {
    "product": "shop",
    "modules": [{"id": "shop-api", "repo": "owner/shop-api"}, {"id": "shop-web", "repo": "owner/shop-web"}],
    "capabilities": [{"id": "orders", "owner": "shop-api", "modules": ["shop-api", "shop-web"],
                      "specs": ["shop-api:openspec/specs/orders/spec.md"]},
                     {"id": "branding", "owner": "shop-web", "modules": ["shop-web"], "specs": []}],
    "interfaces": [{"id": "orders-api-v1", "contract": "contracts/orders-api/v1", "provider": "shop-api",
                    "consumers": ["shop-web"]}],
    "data": [{"id": "orders-db", "owner": "shop-api", "writers": ["shop-api"], "readers": []}],
}


class PlatformTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.platform = self.root / "shop-platform"
        self.platform.mkdir()
        with redirect_stdout(io.StringIO()):
            done = ai_specs.cmd_init(self.platform, "SHOP", "shop-platform", "English", owner="o1",
                                     kit_repo="o/ai-specs", platform=True)
        self.assertIn("catalog/product.json", done)
        self.assertEqual(json.loads((self.platform / "catalog/product.json").read_text())["product"], "shop")
        (self.platform / "contracts/orders-api/v1").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write(self, data: dict) -> None:
        (self.platform / "catalog/product.json").write_text(json.dumps(data), encoding="utf-8")


class CheckTest(PlatformTest):
    def test_valid_catalog(self) -> None:
        self.write(PRODUCT)
        self.assertEqual(catalog.check(self.platform), [])

    def test_dangling_references_and_duplicates(self) -> None:
        bad = json.loads(json.dumps(PRODUCT))
        bad["interfaces"][0]["provider"] = "ghost"
        bad["data"].append({"id": "orders", "owner": "shop-api"})
        bad["interfaces"][0]["contract"] = "contracts/missing/v1"
        self.write(bad)
        problems = catalog.check(self.platform)
        self.assertIn("interface 'orders-api-v1': unknown module 'ghost'", problems)
        self.assertIn("data: duplicated id 'orders'", problems)
        self.assertTrue(any("'contracts/missing/v1' does not exist" in p for p in problems))

    def test_module_paths_checked_when_the_checkout_is_next_to_the_platform(self) -> None:
        self.write(PRODUCT)
        (self.root / "shop-api").mkdir()  # checkout present but the spec file is not
        self.assertTrue(any("does not exist" in p for p in catalog.check(self.platform)))


class ImpactTest(PlatformTest):
    def test_impact_of_an_interface(self) -> None:
        self.write(PRODUCT)
        found = catalog.impact(self.platform, "orders-api-v1")
        self.assertEqual(found["interfaces"], ["orders-api-v1"])
        self.assertEqual(found["modules"], ["shop-api", "shop-web"])
        self.assertEqual(found["capabilities"], ["branding", "orders"])
        self.assertEqual(found["contracts"], ["contracts/orders-api/v1"])

    def test_cli_reports_unknown_id(self) -> None:
        self.write(PRODUCT)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(ai_specs.main(["impact", str(self.platform), "nothing-here"]), 0)
        self.assertIn("nothing in the catalog references", out.getvalue())


if __name__ == "__main__":
    unittest.main()
