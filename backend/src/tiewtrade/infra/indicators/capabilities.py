"""Credential-free compatibility probe for immutable deployment images."""

import sys

from tiewtrade.infra.crypto.indicator_cursor import PreparedCursorClaims
from tiewtrade.infra.indicators.codec import CODEC_VERSION


def main() -> None:
    if CODEC_VERSION != 2 or PreparedCursorClaims.model_fields["format_version"].default != 2:
        raise RuntimeError("INDICATOR_PROTOCOL_UNSUPPORTED")
    sys.stdout.write(
        '{"cursor_formats":[1,2],"codec_version":2,"protocol_version":1,'
        '"source_scope":1,"physical_grace_seconds":22500}\n'
    )


if __name__ == "__main__":
    main()
