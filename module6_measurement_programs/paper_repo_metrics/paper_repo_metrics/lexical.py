"""Physical line metrics and a versioned, explicit Halstead token policy.

Policy lexical-v1: identifiers/literals are operands; keywords and operators
are operators; punctuation delimiters are excluded. This is a reproducible
implementation choice, NOT a claim to reproduce Understand/Multimetric tokens.
"""
from __future__ import annotations
import io
import keyword
import re
import token
import tokenize
from collections import Counter
from dataclasses import dataclass
from .formulas import halstead, ratio


@dataclass
class Lexeme:
    text: str
    kind: str  # operator, operand, delimiter, comment
    start_line: int
    end_line: int


DELIMITERS = set("()[]{};,:.")
JAVA_KEYWORDS = set("""abstract assert boolean break byte case catch char class const
continue default do double else enum exports extends final finally float for goto
if implements import instanceof int interface long module native new non-sealed
open opens package permits private protected provides public record requires
return sealed short static strictfp super switch synchronized this throw throws
transient transitive try uses var void volatile while with yield""".split())
JAVA_NUM = re.compile(r"(?:0[bB][01_]+|0[xX][0-9a-fA-F_]+(?:\.[0-9a-fA-F_]*)?(?:[pP][+-]?[0-9_]+)?|"
                      r"(?:\d[\d_]*(?:\.[\d_]*)?|\.[\d_]+)(?:[eE][+-]?[\d_]+)?)[fFdDlL]?")
JAVA_OP = re.compile(r">>>=|>>=|<<=|>>>|>>|<<|==|!=|<=|>=|&&|\|\||\+\+|--|"
                     r"\+=|-=|\*=|/=|%=|&=|\|=|\^=|->|::|\.\.\.|[^\w\s]", re.UNICODE)


def python_lexemes(text: str) -> list[Lexeme]:
    result = []
    for t in tokenize.generate_tokens(io.StringIO(text).readline):
        if t.type in {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                      tokenize.ENDMARKER, tokenize.ENCODING}:
            continue
        if t.type == tokenize.ERRORTOKEN and t.string.strip():
            raise ValueError(f"Python lexical error on line {t.start[0]}: {t.string!r}")
        if not t.string.strip():
            continue
        if t.type == tokenize.COMMENT:
            kind = "comment"
        elif t.type == tokenize.NAME:
            kind = "operator" if keyword.iskeyword(t.string) and t.string not in {"True", "False", "None"} else "operand"
        elif t.type in {tokenize.STRING, tokenize.NUMBER}:
            kind = "operand"
        elif t.type == tokenize.OP:
            kind = "delimiter" if t.string in DELIMITERS else "operator"
        elif token.tok_name.get(t.type, "").startswith(("FSTRING", "TSTRING")):
            kind = "operand"  # Python-version-specific tokenizer behavior is recorded.
        else:
            kind = "operator"
        last = t.end[0] - (1 if t.end[1] == 0 and t.end[0] > t.start[0] else 0)
        result.append(Lexeme(t.string, kind, t.start[0], last))
    return result


def java_lexemes(text: str) -> list[Lexeme]:
    # Java translates Unicode escapes before tokenization. Refusing avoids
    # interpreting an escaped comment delimiter as ordinary source text.
    if re.search(r"\\u+[0-9a-fA-F]{4}", text):
        raise ValueError("Java Unicode-escape preprocessing not implemented by lexical-v1")
    result, i, line = [], 0, 1
    while i < len(text):
        if text[i].isspace():
            line += text[i] == "\n"
            i += 1
            continue
        start, first = i, line
        if text.startswith("//", i):
            stop = text.find("\n", i)
            i = len(text) if stop < 0 else stop
            kind = "comment"
        elif text.startswith("/*", i):
            stop = text.find("*/", i + 2)
            if stop < 0:
                raise ValueError("Unterminated Java block comment")
            i, kind = stop + 2, "comment"
        elif text.startswith('"""', i):
            i += 3
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text.startswith('"""', i):
                    i += 3
                    break
                else:
                    i += 1
            else:
                raise ValueError("Unterminated Java text block")
            kind = "operand"
        elif text[i] in {'"', "'"}:
            quote = text[i]
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                elif text[i] == quote:
                    i += 1
                    break
                else:
                    i += 1
            else:
                raise ValueError("Unterminated Java string/character literal")
            kind = "operand"
        elif text[i].isalpha() or text[i] in "_$":
            i += 1
            while i < len(text) and (text[i].isalnum() or text[i] in "_$"):
                i += 1
            kind = "operator" if text[start:i] in JAVA_KEYWORDS else "operand"
        elif (match := JAVA_NUM.match(text, i)):
            i = match.end()
            kind = "operand"
        else:
            match = JAVA_OP.match(text, i)
            i = match.end() if match else i + 1
            kind = "delimiter" if text[start:i] in DELIMITERS else "operator"
        value = text[start:i]
        last = first + value.count("\n")
        result.append(Lexeme(value, kind, first, last))
        line = last
    return result


def smali_lexemes(text: str) -> list[Lexeme]:
    """For line occupancy only; no Halstead equivalence is asserted for Smali."""
    result = []
    for lineno, line in enumerate(text.splitlines(), 1):
        quote, escape, comment_at = False, False, len(line)
        for i, char in enumerate(line):
            if escape:
                escape = False
            elif char == "\\" and quote:
                escape = True
            elif char == '"':
                quote = not quote
            elif char == "#" and not quote:
                comment_at = i
                break
        if line[:comment_at].strip():
            result.append(Lexeme(line[:comment_at], "delimiter", lineno, lineno))
        if comment_at < len(line):
            result.append(Lexeme(line[comment_at:], "comment", lineno, lineno))
    return result


def measure_lexical(text: str, language: str) -> tuple[dict, Counter, Counter]:
    lexer = {"python": python_lexemes, "java": java_lexemes, "smali": smali_lexemes}[language]
    tokens = lexer(text)
    lines = text.splitlines()
    code_lines, comment_lines = set(), set()
    operators, operands = Counter(), Counter()
    for t in tokens:
        occupied = set(range(t.start_line, t.end_line + 1))
        if t.kind == "comment":
            comment_lines.update(occupied)
        else:
            code_lines.update(occupied)
        if t.kind == "operator":
            operators[t.text] += 1
        elif t.kind == "operand":
            operands[t.text] += 1
    blanks = {i for i, value in enumerate(lines, 1) if not value.strip()}
    code_lines -= blanks
    mixed = code_lines & comment_lines
    n_code, n_comment = len(code_lines), len(comment_lines)
    metrics = {"total_lines": len(lines), "blank_lines": len(blanks),
               "loc": n_code, "comment_lines": n_comment,
               "comment_only_lines": len(comment_lines - code_lines),
               "mixed_code_comment_lines": len(mixed),
               "lines_without_comment_only": len(lines) - len(comment_lines - code_lines),
               "comment_to_code_ratio": ratio(n_comment, n_code),
               "comment_percentage": 100 * n_comment / n_code if n_code else None}
    if language != "smali":
        metrics.update(halstead(operators, operands))
    return metrics, operators, operands
