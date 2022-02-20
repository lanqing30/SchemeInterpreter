"""This module implements the primitives of the Scheme language."""

import math
import operator
import itertools
import string
import sys
import tokenize

########################
# Primitive Operations #
########################

PRIMITIVES = []


def _arith(fn, init, vals):
    """Perform the fn fneration on the number values of VALS, with INIT as
    the value when VALS is empty. Returns the result as a Scheme value."""

    s = init
    for val in vals:
        s = fn(s, val)
    if round(s) == s:
        s = round(s)
    return s


def scheme_add(*vals):
    return _arith(operator.add, 0, vals)


def scheme_sub(val0, *vals):
    if len(vals) == 0:
        return -val0
    return _arith(operator.sub, val0, vals)


def scheme_mul(*vals):
    return _arith(operator.mul, 1, vals)


def scheme_div(val0, *vals):
    if len(vals) == 0:
        return 1 / val0
    return _arith(operator.truediv, val0, vals)


def _numcomp(op, x, y):
    return op(x, y)


def scheme_eq(x, y):
    return _numcomp(operator.eq, x, y)


def scheme_lt(x, y):
    return _numcomp(operator.lt, x, y)


def scheme_gt(x, y):
    return _numcomp(operator.gt, x, y)


def scheme_le(x, y):
    return _numcomp(operator.le, x, y)


def scheme_ge(x, y):
    return _numcomp(operator.ge, x, y)

PRIMITIVES.append(("+", scheme_add))
PRIMITIVES.append(("-", scheme_sub))
PRIMITIVES.append(("*", scheme_mul))
PRIMITIVES.append(("/", scheme_div))
PRIMITIVES.append(("=", scheme_eq))
PRIMITIVES.append(("<", scheme_lt))
PRIMITIVES.append((">", scheme_gt))
PRIMITIVES.append(("<=", scheme_le))
PRIMITIVES.append((">=", scheme_ge))


def number_fn(module, name):
    """A Scheme primitive for the named fn in module, which takes numbers."""
    py_fn = getattr(module, name)
    def scheme_fn(*vals):

        return py_fn(*vals)
    return scheme_fn

# Add number functions in the math module as Scheme primitives
for _name in ["acos", "acosh", "asin", "asinh", "atan", "atan2", "atanh",
              "ceil", "copysign", "cos", "cosh", "degrees", "floor", "log",
              "log10", "log1p", "log2", "radians", "sin", "sinh", "sqrt",
              "tan", "tanh", "trunc"]:
    PRIMITIVES.append((_name, number_fn(math, _name)))

###############################################################################

_NUMERAL_STARTS = set(string.digits) | set('+-.')
_SYMBOL_CHARS = (set('!$%&*/:<=>?@^_~') | set(string.ascii_lowercase) | set(string.ascii_uppercase) | _NUMERAL_STARTS)
_WHITESPACE = set(' \t\n\r')
_SINGLE_CHAR_TOKENS = set("()[]'`")
_TOKEN_END = _WHITESPACE | _SINGLE_CHAR_TOKENS
DELIMITERS = _SINGLE_CHAR_TOKENS

########################
#       Tokenizer      #
########################

def valid_symbol(s):
    """is it a valid symbol (identifier)."""
    if len(s) == 0:
        return False
    for c in s:
        if c not in _SYMBOL_CHARS:
            return False
    return True

def next_candidate_token(line, k):
    """given a string or a cur(pointer)，get the token and the cur(pointer) after moving"""
    while k < len(line):
        c = line[k]
        if c == ';': # lisp comments
            return None, len(line)
        elif c in _WHITESPACE:
            k += 1
        elif c in _SINGLE_CHAR_TOKENS:
            if c == ']': c = ')'
            if c == '[': c = '('
            return c, k+1
        elif c == '#':  # Boolean values #t and #f
            return line[k:k+2], min(k+2, len(line))
        else:
            j = k
            while j < len(line) and line[j] not in _TOKEN_END:
                j += 1
            return line[k:j], j
    return None, len(line)

def tokenize_line(line):
    """given a string，get a token list"""
    result = []
    text, i = next_candidate_token(line, 0)
    while text is not None:
        if text in DELIMITERS:
            result.append(text)
        elif text == '#t' or text.lower() == 'true':
            result.append(True)
        elif text == '#f' or text.lower() == 'false':
            result.append(False)
        elif text[0] in _SYMBOL_CHARS:
            number = False
            if text[0] in _NUMERAL_STARTS:
                try:
                    result.append(int(text))
                    number = True
                except ValueError:
                    try:
                        result.append(float(text))
                        number = True
                    except ValueError:
                        pass
            if not number:
                if valid_symbol(text):
                    result.append(text.lower())
                else:
                    raise ValueError("TOKEN_ERROR: invalid number or digit: {0}".format(text))
        else:
            print("TOKEN_WARNING: invalid token: {0}".format(text), file=sys.stderr)
            print("    ", line, file=sys.stderr)
            print(" " * (i+4), "^", file=sys.stderr)
        text, i = next_candidate_token(line, i)
    return result

def tokenize_lines(input):
    """apply the tokenize line function to each line of the input."""
    return map(tokenize_line, input)


