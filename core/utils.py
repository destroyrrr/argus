# core/utils.py
DISCORD_MAX = 1990  # hard limit is 2000 — leave room for code block markers

# ---------------------------
# Chunk Message
# ---------------------------
def chunk_message(text: str, code_block: bool = True) -> list[str]:
    """
    Splits text into Discord-safe chunks under 2000 characters.
    Returns a list of strings — caller sends each one.

    code_block=True  → wraps each chunk in triple backticks
    code_block=False → plain text chunks
    """
    prefix = "```\n" if code_block else ""
    suffix = "\n```" if code_block else ""
    overhead = len(prefix) + len(suffix)
    limit = DISCORD_MAX - overhead

    # Strip existing code block markers if caller already added them
    # so we don't double-wrap
    clean = text
    if code_block:
        clean = text.strip().removeprefix("```").removesuffix("```").strip()

    chunks = []
    while clean:
        chunk = clean[:limit]
        # ---------------------------
        # Truncation indicator
        # ---------------------------
        # If this is not the last chunk, note it was cut
        if len(clean) > limit:
            chunk = chunk + "\n... (truncated)"
        chunks.append(f"{prefix}{chunk}{suffix}")
        clean = clean[limit:]

    return chunks if chunks else [""]


# ---------------------------
# Format Table
# ---------------------------
def format_table(headers: list[str], rows: list[list]) -> str:
    """
    Formats a table into a Discord-safe code block.

    headers : list of column header strings
    rows    : list of rows, each row a list of values

    Example:
        format_table(
            ["Name", "Status", "IP"],
            [["web", "running", "10.0.0.1"],
             ["db",  "stopped", "10.0.0.2"]]
        )

    Output:
        ```
        Name  Status   IP
        ----  -------  ---------
        web   running  10.0.0.1
        db    stopped  10.0.0.2
        ```
    """
    if not rows:
        return "```\nNo results.\n```"

    # Coerce all values to strings
    str_rows = [[str(cell) for cell in row] for row in rows]

    # Column widths — max of header or any cell in that column
    col_widths = [
        max(len(headers[i]), max(len(row[i]) for row in str_rows))
        for i in range(len(headers))
    ]

    def _fmt_row(row):
        return "  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row))

    header_line    = _fmt_row(headers)
    separator_line = "  ".join("-" * col_widths[i] for i in range(len(headers)))
    data_lines     = [_fmt_row(row) for row in str_rows]

    table = "\n".join([header_line, separator_line] + data_lines)
    return f"```\n{table}\n```"


# ---------------------------
# Sanitize Input
# ---------------------------
def sanitize_input(value: str, allow: str = "") -> str:
    """
    Strips characters that have no place in CLI args or SQL identifiers.
    Raises ValueError if the result is empty.

    allow : string of additional characters to permit beyond the default safe set
            e.g. allow="." to permit dots in file paths

    Default safe set: alphanumeric, hyphen, underscore, forward slash, space
    SQL identifiers should use the stricter validate_identifier() below.
    """
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/ ") | set(allow)
    cleaned = "".join(c for c in value if c in safe)
    if not cleaned:
        raise ValueError(f"Input '{value}' contains no safe characters.")
    return cleaned


def validate_identifier(value: str) -> str:
    """
    Strict validation for SQL table names, column names, DB identifiers.
    Permits only alphanumeric and underscores. No spaces, no hyphens.
    Raises ValueError if invalid.
    """
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
    if not all(c in safe for c in value):
        raise ValueError(f"Identifier '{value}' contains invalid characters.")
    if not value:
        raise ValueError("Identifier cannot be empty.")
    return value
