#!/usr/bin/env python3
"""
test_dsn_metrics.py - Tests unitaires pour l'analyseur métrologique Specctra SES/DSN
"""

import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from dsn_metrics import SpecctraParser, DsnMetrologyAnalyzer


class TestDsnMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(__file__).parent / ".tmp"
        self.tmp_dir.mkdir(exist_ok=True)
        self.sample_ses_path = self.tmp_dir / "sample.ses"

        # Création d'un SES synthétique
        # 1 unit = 1/1000 mil. 1000 units = 1 mil = 0.0254 mm.
        # Segment de 1000 mil (25.4 mm) : x de 0 à 1000000
        content = """(session "sample"
  (routes 
    (resolution mil 1000)
    (network_out 
      (net "USB_D+"
        (wire
          (path TopLayer 10000
            0 0
            1000000 0
          )
        )
        (via via0 1000000 0)
      )
      (net "USB_D-"
        (wire
          (path TopLayer 10000
            0 50000
            1050000 50000
          )
        )
      )
    )
  )
)
"""
        self.sample_ses_path.write_text(content, encoding="utf-8")

    def tearDown(self):
        if self.sample_ses_path.exists():
            self.sample_ses_path.unlink()
        if self.tmp_dir.exists():
            try:
                self.tmp_dir.rmdir()
            except Exception:
                pass

    def test_parser_net_length_and_vias(self):
        parser = SpecctraParser(self.sample_ses_path)
        self.assertIn("USB_D+", parser.nets_metrics)
        self.assertIn("USB_D-", parser.nets_metrics)

        net_dp = parser.nets_metrics["USB_D+"]
        net_dn = parser.nets_metrics["USB_D-"]

        # 1000 mil = 25.4 mm
        self.assertAlmostEqual(net_dp.total_length_mm, 25.4, places=2)
        self.assertEqual(net_dp.via_count, 1)

        # 1050 mil = 26.67 mm
        self.assertAlmostEqual(net_dn.total_length_mm, 26.67, places=2)
        self.assertEqual(net_dn.via_count, 0)

    def test_analyzer_diff_pair_skew(self):
        manifest = {"placement_constraints": []}
        board = {
            "net_classes": {
                "DIFF_USB": {
                    "nets": ["USB_D+", "USB_D-"],
                    "diff_pair": True,
                    "max_skew_mm": 2.0
                }
            }
        }
        analyzer = DsnMetrologyAnalyzer(self.sample_ses_path, manifest, board)
        rep = analyzer.analyze()

        self.assertEqual(len(rep.diff_pairs), 1)
        dp = rep.diff_pairs[0]
        # Skew = 26.67 - 25.4 = 1.27 mm (< 2.0 mm -> OK)
        self.assertAlmostEqual(dp.skew_mm, 1.27, places=2)
        self.assertTrue(dp.ok)
        self.assertTrue(rep.is_valid)

    def test_analyzer_critical_nets_and_unrouted(self):
        manifest = {"placement_constraints": []}
        board = {
            "net_classes": {
                "SIGNAL_CRITICAL": {
                    "nets": ["K_LINE", "TWAI_RX"],
                    "max_vias": 2
                }
            }
        }
        analyzer = DsnMetrologyAnalyzer(self.sample_ses_path, manifest, board)
        
        # Cas 1 : nets critiques absents du SES (non routés)
        rep1 = analyzer.analyze()
        self.assertEqual(len(rep1.critical_nets), 2)
        self.assertFalse(rep1.critical_nets[0].is_routed)
        self.assertFalse(rep1.is_valid)

        # Cas 2 : forçage de violations ou unrouted items
        rep2 = analyzer.analyze(unrouted_count=1, violation_count=0)
        self.assertFalse(rep2.is_valid)
        self.assertEqual(rep2.unrouted_count, 1)

    def test_analyzer_unrouted_diff_pair(self):
        manifest = {"placement_constraints": []}
        board = {
            "net_classes": {
                "DIFF_CAN": {
                    "nets": ["CANH", "CANL"],
                    "diff_pair": True,
                    "max_skew_mm": 5.0
                }
            }
        }
        analyzer = DsnMetrologyAnalyzer(self.sample_ses_path, manifest, board)
        rep = analyzer.analyze()
        self.assertEqual(len(rep.diff_pairs), 1)
        self.assertFalse(rep.diff_pairs[0].ok)
        self.assertFalse(rep.is_valid)


if __name__ == "__main__":
    unittest.main()

