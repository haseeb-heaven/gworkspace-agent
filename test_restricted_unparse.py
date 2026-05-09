
from RestrictedPython import compile_restricted
import ast

code = """
def foo(x):
    # comment
    return x + 1

print(foo(10))
"""

tree = ast.parse(code)
unparsed = ast.unparse(tree)
print("--- Unparsed ---")
print(unparsed)
print("----------------")

byte_code = compile_restricted(unparsed, filename="<string>", mode="exec")
print("Compile success")
