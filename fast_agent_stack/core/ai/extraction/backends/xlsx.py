from __future__ import annotations

import asyncio
import io

try:
    import openpyxl
except ImportError:
    raise ImportError("pip install fast-agent-stack[extract-xlsx]") from None


class XlsxExtractor:
    async def extract(self, data: bytes) -> str:
        def _sync() -> str:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            sheets: list[str] = []
            for ws in wb.worksheets:
                rows = []
                for row in ws.iter_rows(values_only=True):
                    rows.append("\t".join("" if v is None else str(v) for v in row))
                sheets.append("\n".join(rows))
            wb.close()
            return "\n\n".join(sheets)

        return await asyncio.to_thread(_sync)
