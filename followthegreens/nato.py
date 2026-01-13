nato = {
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


def nato_convert(source: str) -> str:
    return " ".join([nato.get(c, "") for c in source.upper()])

def phonetic(instr: str) -> str:
    if type(instr) is not str:
        instr = str(instr)
    a = instr.split(" ")
    say = []
    for s in a:
        if s.isalpha() and len(s) > 1:
            say.append(s)
        else:
            say.append(nato_convert(s.lower()))
    return " ".join(say)
