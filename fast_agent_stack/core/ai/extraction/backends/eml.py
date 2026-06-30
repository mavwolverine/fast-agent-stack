from __future__ import annotations

import email
import email.policy


class EmlExtractor:
    async def extract(self, data: bytes) -> str:
        msg = email.message_from_bytes(data, policy=email.policy.default)
        body = msg.get_body(preferencelist=("plain",))
        if body is not None:
            return body.get_content()  # type: ignore[return-value]
        html_body = msg.get_body(preferencelist=("html",))
        if html_body is not None:
            import re
            raw = html_body.get_content()  # type: ignore[union-attr]
            return re.sub(r"<[^>]+>", "", raw)
        return ""
