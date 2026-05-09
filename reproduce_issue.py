
import re
import ast

def execute_generated_code_mock(code: str):
    # Fixed logic
    code = re.sub(r"^\s*return\s+.*$", "", code, flags=re.MULTILINE)
    code = re.sub(r"\\\s*$", "", code, flags=re.MULTILINE)

    try:
        tree = ast.parse(code)

        class WithOpenTransformer(ast.NodeTransformer):
            def visit_With(self, node):
                self.generic_visit(node)
                if (
                    len(node.items) == 1
                    and isinstance(node.items[0].context_expr, ast.Call)
                    and isinstance(node.items[0].context_expr.func, ast.Name)
                    and node.items[0].context_expr.func.id == "open"
                    and isinstance(node.items[0].optional_vars, ast.Name)
                ):
                    var_name = node.items[0].optional_vars.id
                    assignment = ast.Assign(
                        targets=[ast.Name(id=var_name, ctx=ast.Store())],
                        value=ast.IfExp(
                            test=ast.Name(id="injected_vars", ctx=ast.Load()),
                            body=ast.Subscript(
                                value=ast.Name(id="injected_vars", ctx=ast.Load()),
                                slice=ast.Constant(value=0),
                                ctx=ast.Load(),
                            ),
                            orelse=ast.List(elts=[], ctx=ast.Load()),
                        ),
                        lineno=node.lineno,
                    )
                    return [assignment] + node.body
                return node

        code = ast.unparse(WithOpenTransformer().visit(tree))
    except Exception as e:
        print(f"AST failed: {e}")
        code = re.sub(
            r"with\s+open\s*\([^)]*\)\s+as\s+(\w+)\s*:",
            r"\1 = injected_vars[0] if injected_vars else []",
            code,
            flags=re.DOTALL,
        )
    
    print("--- Transformed Code ---")
    print(code)
    print("------------------------")
    try:
        ast.parse(code)
        print("ast.parse SUCCESS")
    except Exception as e:
        print(f"ast.parse FAILED: {e}")

code_with_body = """
with open("test.txt") as f:
    content = f.read()
    print(content)
"""

execute_generated_code_mock(code_with_body)

code_with_return = """
with open("test.txt") as f:
    content = f.read()
    return content
"""
print("\nTesting with return:")
execute_generated_code_mock(code_with_return)
