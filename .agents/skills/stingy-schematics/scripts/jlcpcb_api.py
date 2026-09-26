#!/usr/bin/env python3
"""
jlcpcb_api.py - Client API agnostique pour interroger en temps réel le catalogue JLCPCB SMT.

Conforme à la Règle 0 (AGENTS.md) :
- Zéro référence en dur à un projet spécifique.
- Requêtes HTTP dynamiques sur l'API publique JLCPCB SMT.
- Extraction des pièces qualifiées Basic Parts, en stock, avec prix et spécifications.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

JLCPCB_SMT_API_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


@dataclass
class JLCPart:
    lcsc_part: str
    mfr_part: str
    manufacturer: str
    package: str
    description: str
    library_type: str  # "base" ou "expand"
    stock: int
    price_usd: float
    raw_attributes: Dict[str, Any]
    first_sort: str = ""
    second_sort: str = ""


class JLCPCBClient:
    """Client de recherche en temps réel sur le catalogue de composants JLCPCB SMT."""

    def __init__(self, timeout_s: float = 8.0):
        self.timeout_s = timeout_s
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://jlcpcb.com/parts",
            "Origin": "https://jlcpcb.com",
        }

    def search_parts(
        self,
        keyword: str,
        only_basic: bool = True,
        only_in_stock: bool = True,
        page_size: int = 25,
        page: int = 1,
        first_sort_name: str = "",
        second_sort_name: str = "",
    ) -> List[JLCPart]:
        """
        Interroge l'API JLCPCB SMT avec pagination et filtres.
        """
        payload = {
            "currentPage": page,
            "pageSize": page_size,
            "searchType": 2,
            "firstSortName": first_sort_name,
            "secondSortName": second_sort_name,
            "componentLibraryType": "base" if only_basic else "",
            "stockFlag": 1 if only_in_stock else 0,
            "keyword": keyword,
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            JLCPCB_SMT_API_URL,
            data=data_bytes,
            headers=self.headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                status_code = resp.getcode()
                if status_code != 200:
                    sys.stderr.write(f"Avertissement : Réponse HTTP {status_code} de JLCPCB.\n")
                    return []
                resp_text = resp.read().decode("utf-8")
                res_json = json.loads(resp_text)
                if "--debug" in sys.argv:
                    print("DEBUG API RESPONSE:", json.dumps(res_json, indent=2)[:500])
        except (urllib.error.URLError, TimeoutError) as e:
            sys.stderr.write(f"Avertissement réseau lors de l'appel JLCPCB API : {e}\n")
            return []
        except Exception as e:
            sys.stderr.write(f"Erreur inattendue : {e}\n")
            return []

        # Extraction des résultats
        data_block = res_json.get("data", {})
        if not isinstance(data_block, dict):
            return []

        component_page = data_block.get("componentPageInfo") or {}
        raw_list = component_page.get("list") or [] if isinstance(component_page, dict) else []

        parts: List[JLCPart] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            
            lib_type = str(item.get("componentLibraryType", "")).lower()
            if only_basic and lib_type != "base":
                continue

            stock = int(item.get("stockCount", 0) or 0)
            if only_in_stock and stock <= 0:
                continue

            # Prix minimum ou unitaire
            prices = item.get("componentPrices", [])
            unit_price = 0.0
            if prices and isinstance(prices, list) and len(prices) > 0:
                unit_price = float(prices[0].get("productPrice", 0.0) or 0.0)

            part = JLCPart(
                lcsc_part=str(item.get("componentCode", "")).strip(),
                mfr_part=str(item.get("componentModelEn", "")).strip(),
                manufacturer=str(item.get("componentBrandEn", "")).strip(),
                package=str(item.get("componentSpecificationEn", "")).strip(),
                description=str(item.get("describe", "")).strip(),
                library_type=lib_type,
                stock=stock,
                price_usd=unit_price,
                raw_attributes=item,
                first_sort=str(item.get("firstSortName", "")).strip(),
                second_sort=str(item.get("secondSortName", "")).strip(),
            )
            parts.append(part)

        return parts


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "100nF 0603"
    print(f"Recherche en direct sur JLCPCB SMT pour : '{kw}' (Basic Parts uniquement)...")
    client = JLCPCBClient()
    results = client.search_parts(keyword=kw, only_basic=True, only_in_stock=True)
    print(f"Trouvé : {len(results)} composants.")
    for p in results[:5]:
        print(f"  - [{p.lcsc_part}] {p.mfr_part} ({p.manufacturer}) | Boîtier: {p.package} | Stock: {p.stock} | Prix: {p.price_usd} $")
