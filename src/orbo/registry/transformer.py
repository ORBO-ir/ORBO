from __future__ import annotations

from .models import RegistryRecord


def transform_registry(data: list[dict]) -> list[RegistryRecord]:
    """
    Convert MarketMap JSON into RegistryRecord objects.
    """

    records: list[RegistryRecord] = []

    for item in data:

        records.append(
            RegistryRecord(
                ins_code=int(item["insCode"]),
                symbol=item["lVal18AFC"],
                name=item["lVal30"],
                sector=item["lSecVal"],
                label=item["customLabel"].strip() or item["lVal18AFC"],
            )
        )

    return records
