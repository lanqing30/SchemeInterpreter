
from scheme_primitives import *

import re


class Buffer:

    def __init__(self, source):
        self.index = 0
        self.lines = []
        self.source = source
        self.current_line = ()
        self.current()

    def pop(self):
        """Remove the next item from self and return it. If self has
        exhausted its source, returns None."""
        current = self.current()
        self.index += 1
        return current

    def current(self):
        """Return the current element, or None if none exists."""
        while not self.more_on_line:
            self.index = 0
            try:
                self.current_line = next(self.source)
                self.lines.append(self.current_line)
            except StopIteration:
                self.current_line = ()
                return None
        return self.current_line[self.index]

    @property
    def more_on_line(self):
        return self.index < len(self.current_line)

###############################################################################

class Pair:

    def __init__(self, first, second):
        self.first = first
        self.second = second

    def __repr__(self):
        return "Pair({0}, {1})".format(repr(self.first), repr(self.second))

    def __str__(self):
        s = "(" + str(self.first)
        second = self.second
        while isinstance(second, Pair):
            s += " " + str(second.first)
            second = second.second
        if second is not nil:
            raise TypeError("PAIR_STR_: the last element of the pair must be NULL")
        return s + ")"

    def __len__(self):
        n, second = 1, self.second
        while isinstance(second, Pair):
            n += 1
            second = second.second
        if second is not nil:
            raise TypeError("PAIR_LEN_: the last element of the pair must be NULL")
        return n

    def __eq__(self, p):
        if not isinstance(p, Pair):
            return False
        return self.first == p.first and self.second == p.second

    def map(self, fn):
        """Return a Scheme list after mapping Python function FN to SELF."""
        mapped = fn(self.first)
        if self.second is nil or isinstance(self.second, Pair):
            return Pair(mapped, self.second.map(fn))
        else:
            raise TypeError("PAIR_MAP_: invalid pair list")

class nil:
    """The empty list"""

    def __repr__(self):
        return "nil"

    def __str__(self):
        return "()"

    def __len__(self):
        return 0

    def map(self, fn):
        return self

nil = nil()
# Assignment hides the nil class; there is only one instance


def scheme_read(src):
    """Read the next expression from SRC, a Buffer of tokens.
    >>> lines = ["(+ 1 ", "(+ 23 4)) ("]
    >>> src = Buffer(tokenize_lines(lines))
    >>> print(scheme_read(src))
    (+ 1 (+ 23 4))
    """
    if src.current() is None:
        raise EOFError('unexpected EOF')
    val = src.pop()
    if val not in DELIMITERS:
        return val
    elif val == "(":
        return read_tail(src)
    else:
        raise SyntaxError("READ: invalid token: {0}".format(val))

def read_tail(src):
    """Return the remainder of a list in SRC, starting before an element or ).
    >>> read_tail(Buffer(tokenize_lines([")"])))
    nil
    >>> read_tail(Buffer(tokenize_lines(["2 (3 4))"])))
    Pair(2, Pair(Pair(3, Pair(4, nil)), nil))
    """

    if src.current() is None:
        raise EOFError('unexpected EOF')
    elif src.current() == ")":
        src.pop()
        return nil
    else:
        first = scheme_read(src)
        rest = read_tail(src)
        return Pair(first, rest)

###############################################################################

class SchemeError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

def check_form(expr, min, max=float('inf')):
    """check the number of the args in range or not"""
    length = len(expr)
    if length < min:
        raise SchemeError("too few args")
    elif length > max:
        raise SchemeError("too many args")

def check_formals(formals):
    """the args must be symbol(identifier), and the args should be unique"""
    paras = formals
    scanned_paras = []
    while paras is not nil:
        if (not isinstance(paras.first, str)) or paras.first in scanned_paras:
            raise SchemeError('the args must be symbol(identifier), and the args should be unique')
        else:
            scanned_paras += [paras.first]
            paras = paras.second
    return

def can_self_evaluating(x):
    if x is True or x is False:
        return True
    elif isinstance(x, (int, float)):
        return True
    elif x is nil or x is None:
        return True
    else:
        return False

def scheme_eval(expr, env):
    # Atoms
    if isinstance(expr, str):
        return env.lookup(expr)
    elif can_self_evaluating(expr):
        return expr
    # Combinations
    first, rest = expr.first, expr.second
    if isinstance(first, str) and first in SPECIAL_FORMS:
        result = SPECIAL_FORMS[first](rest, env)
    else:
        procedure = scheme_eval(first, env)
        if not isinstance(procedure, Procedure):
            raise SchemeError('First arg:{0} not callable'.format(repr(procedure)))
        result = procedure.eval_call(rest, env)
    return result


def eval_all(expressions, env):
    if expressions is nil:
        return
    expr = expressions
    while expr is not nil:
        value = scheme_eval(expr.first, env)
        expr = expr.second
    return value


class Frame:
    def __init__(self, parent):
        self.bindings = {}
        self.parent = parent

    def __repr__(self):
        if self.parent is None:
            return "<Global Frame>"
        else:
            s = sorted(('{0}: {1}'.format(k, v) for k, v in self.bindings.items()))
            return "<{{{0}}} -> {1}>".format(', '.join(s), repr(self.parent))

    def lookup(self, symbol):
        if symbol in self.bindings:
            return self.bindings[symbol]
        elif self.parent is not None:
            return self.parent.lookup(symbol)
        else:
            raise SchemeError('Undefined symbol :{}'.format(repr(symbol)))

    def define(self, symbol, value):
        self.bindings[symbol] = value


class Procedure:
    def eval_call(self, arg_exprs, env):
        args = arg_exprs.map(lambda operand: scheme_eval(operand, env))
        return self.apply(args, env)


class PrimitiveProcedure(Procedure):
    def __init__(self, fn):
        self.fn = fn

    def __repr__(self):
        return '#[{}]'.format('primitive')

    def apply(self, args, env):
        python_args = []
        while args is not nil:
            python_args.append(args.first)
            args = args.second
        return self.fn(*python_args)


class LambdaProcedure(Procedure):
    def __init__(self, formals, body, env):

        self.formals = formals
        self.body = body
        self.env = env

    def make_call_frame(self, args):
        child = Frame(self.env)
        if self.formals is nil:
            return child
        expr = self.formals
        values = args
        if len(expr) != len(values):
            raise SchemeError('Lambda: number of parameters argument should be equal.')
        while expr is not nil:
            child.define(expr.first, values.first)
            expr = expr.second
            values = values.second
        return child

    def __repr__(self):
        return "LambdaProcedure({!r}, {!r}, {!r})".format(
            self.formals, self.body, self.env)

    def apply(self, args, env):
        new_env = self.make_call_frame(args)
        return eval_all(self.body, new_env)

# ###########################-SPECIAL_FORMS-############################


def do_define_form(expressions, env):
    target = expressions.first
    if isinstance(target, str):
        check_form(expressions, 2, 2)
        env.define(expressions.first, scheme_eval(expressions.second.first, env))
        return expressions.first
    elif isinstance(target, Pair) and isinstance(target.first, str):
        lambda_name = LambdaProcedure(target.second, expressions.second, env)
        env.define(target.first, lambda_name)
        return target.first
    else:
        bad = target.first if isinstance(target, Pair) else target
        raise SchemeError("Not a symbol(identifier): {}".format(bad))


def do_lambda_form(expressions, env):
    check_form(expressions, 2)
    check_formals(expressions.first)
    lambda_name = LambdaProcedure(expressions.first, expressions.second, env)
    return lambda_name


def do_if_form(expressions, env):
    check_form(expressions, 2, 3)
    # All values in Scheme are true except False.
    if scheme_eval(expressions.first, env) is not False:
        return scheme_eval(expressions.second.first, env)
    else:
        if expressions.second.second is nil:
            return 
        else:
            return scheme_eval(expressions.second.second.first, env)


def do_and_form(expressions, env):
    if expressions is nil:
        return True
    expr = expressions
    while expr is not nil:
        value = scheme_eval(expr.first, env)
        # Only False is false in Scheme.
        if value is False:
            return False
        expr = expr.second
    return value


def do_or_form(expressions, env):
    expr = expressions
    while expr is not nil:
        value = scheme_eval(expr.first, env)
        if value is not False:

            return value
        expr = expr.second
    return False


def do_cond_form(expressions, env):
    i = 0
    test = False
    while expressions is not nil:
        clause = expressions.first
        check_form(clause, 1)
        if clause.first == "else":
            return True if clause.second is nil else eval_all(clause.second, env)

        clause_cond = scheme_eval(clause.first, env)
        if clause_cond is not False:
            if clause.second is nil:
                return clause_cond
            else:
                return eval_all(clause.second, env)
        expressions = expressions.second
        i += 1
    if not test:
        return
    else:
        return True

SPECIAL_FORMS = {
    "and": do_and_form,
    "define": do_define_form,
    "if": do_if_form,
    "lambda": do_lambda_form,
    "or": do_or_form,
    "cond": do_cond_form,
}

# ###########################-create_global_frame-############################


def add_primitives(frame, funcs_and_names):
    for name, fn in funcs_and_names:
        frame.define(name, PrimitiveProcedure(fn))


def create_global_frame():
    env = Frame(None)
    add_primitives(env, PRIMITIVES)
    return env


# ###############################-MAIN-cases###################################

def load_file(command):
    filename = re.split(r'\s+', command)[1]
    f = open(filename, 'r', encoding='utf-8')
    lines = [line[:-1] for line in f]
    lines = ['('] + lines + [')']
    src = Buffer(tokenize_lines(lines))
    expr = scheme_read(src)
    return eval_all(expr, env)

global_cache = []

def is_done():
    global global_cache
    counter = 0
    for string in global_cache:
        for char in string:
            if char == '(' or char == '[':
                counter += 1
            elif char == ')' or char == ']':
                counter -= 1
            else:
                pass
    if counter == 0:
        return True
    else:
        return False

if __name__ == '__main__':
    print('Tiny Scheme interpreter _Author ZhangLanqing')
    print("Use Command 'load filename' to load a *.scm file")
    env = create_global_frame()

    while True:
        global_cache = []
        line_number = 0
        file_flag = False

        while True:
            if line_number == 0:
                s = input('>>> ')
                if s.strip(' ') == '': continue
                if s.strip(' ').startswith('load'):
                    print(load_file(s.strip()))
                    file_flag = True
                    break
            else:
                s = input('    ')
            line_number += 1

            global_cache.append(s)
            if is_done():
                break

        if file_flag == False:
            src = Buffer(tokenize_lines(global_cache))
            expr = scheme_read(src)
            print(scheme_eval(expr, env))



