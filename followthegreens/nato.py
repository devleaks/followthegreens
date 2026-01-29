"""Convert string to NATO phonetic alphabet

Attributes:
    NATO_CHAR: Character mapping
"""

NATO_CHAR = {
    "A": "alpha",
    "B": "bravo",
    "C": "charlie",
    "D": "delta",
    "E": "echo",
    "F": "foxtrot",
    "G": "golf",
    "H": "hotel",
    "I": "india",
    "J": "juliett",
    "K": "kilo",
    "L": "lima",
    "M": "mike",
    "N": "november",
    "O": "oscar",
    "P": "papa",
    "Q": "quebec",
    "R": "romeo",
    "S": "sierra",
    "T": "tango",
    "U": "uniform",
    "V": "victor",
    "W": "whiskey",
    "X": "x-ray",
    "Y": "yankee",
    "Z": "zulu",
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "tree",
    "4": "fower",
    "5": "fife",
    "6": "six",
    "7": "seven",
    "8": "ate",
    "9": "niner",
    " ": "space",
    "~": "tilde",
    "`": "backtick",
    "!": "exclamation-point",
    "@": "at-sign",
    "#": "octothorpe",
    "$": "dollar-sign",
    "%": "percent",
    "^": "carat",
    "&": "ampersand",
    "*": "asterisk",
    "(": "left-parenthesis",
    ")": "right-parenthesis",
    "-": "dash",
    "_": "underscore",
    "=": "equals",
    "+": "plus-sign",
    "{": "left-curly-brace",
    "}": "right-curly-brace",
    ":": "colon",
    ";": "semicolon",
    "'": "single-quote",
    '"': "double-quote",
    "<": "less-than-sign",
    ">": "greater-than-sign",
    ",": "comma",
    ".": "period",
    "?": "question-mark",
    "/": "forward-slash",
    "\\": "backslash",
    "|": "pipe",
}


def nato_say(source: str) -> str:
    """Convert word to phonetic alphabet words

    Args:
        source (str): String to convert

    Returns:
        str: String to speak
    """
    return " ".join([NATO_CHAR.get(c, c) for c in source.upper()])


def phonetic(instr: str) -> str:
    """Convert entire phrase into phonetic alphabet string

    Args:
        instr (str): Phrase to convert

    Returns:
        str: Phrase to speak
    """
    return " ".join([w if w.isalpha() and len(w) > 1 else nato_say(w) for w in str(instr).split(" ")])


def toml_dumps(toml_dict: dict, table: str = "") -> str:
    # basic but sufficient for FtG
    def _dumps_value(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, list):
            return f"[{', '.join(_dumps_value(v) for v in value)}]"
        else:
            raise TypeError(f"{type(value).__name__} {value!r} is not supported")

    toml = []
    for key, value in toml_dict.items():
        if isinstance(value, dict):
            table_key = f"{table}.{key}" if table else key
            toml.append(f"\n[{table_key}]\n{toml_dumps(value, table_key)}")
        else:
            toml.append(f"{key} = {_dumps_value(value)}")
    return "\n".join(toml)
