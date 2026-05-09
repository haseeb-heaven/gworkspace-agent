
import ast

code_with_body = """
import os

with open("test.txt") as f:
    content = f.read()
    print(content)

print("done")
"""

class WithOpenTransformer(ast.NodeTransformer):
    def visit_With(self, node):
        self.generic_visit(node)
        new_nodes = []
        for item in node.items:
            if (isinstance(item.context_expr, ast.Call) and 
                isinstance(item.context_expr.func, ast.Name) and 
                item.context_expr.func.id == 'open' and 
                isinstance(item.optional_vars, ast.Name)):
                
                var_name = item.optional_vars.id
                # var_name = injected_vars[0] if injected_vars else []
                assignment = ast.Assign(
                    targets=[ast.Name(id=var_name, ctx=ast.Store())],
                    value=ast.IfExp(
                        test=ast.Name(id='injected_vars', ctx=ast.Load()),
                        body=ast.Subscript(
                            value=ast.Name(id='injected_vars', ctx=ast.Load()),
                            slice=ast.Constant(value=0),
                            ctx=ast.Load()
                        ),
                        orelse=ast.List(elts=[], ctx=ast.Load())
                    ),
                    lineno=node.lineno
                )
                new_nodes.append(assignment)
            else:
                # If it's not 'with open(...) as var:', we might want to keep it as a 'with' block
                # but this complicates things if there are multiple items in one 'with'
                pass
        
        if new_nodes:
            # For simplicity, if we matched 'open', we just replace the whole 'with' block
            # with the assignments + the body.
            # If there were other items in the 'with' that were NOT 'open', they are lost here.
            # But the original regex also only handled 'with open(...) as var:'
            return new_nodes + node.body
        
        return node

tree = ast.parse(code_with_body)
transformer = WithOpenTransformer()
new_tree = transformer.visit(tree)
ast.fix_missing_locations(new_tree)
print(ast.unparse(new_tree))
