import ast
import importlib.util
import sys
from pathlib import Path


def check_syntax(file_path):
    """Verifies that the file has valid Python syntax."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        compile(content, str(file_path), "exec")
        return True, None
    except Exception as e:
        return False, str(e)


def verify_importable(file_path, project_root):
    """Verifies that the file can be imported without raising errors."""
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    module_name = f"scripts.{file_path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            return False, "Could not create spec"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, None
    except Exception as e:
        return False, str(e)


def get_imported_modules(tree):
    """Extracts imported modules and their aliases from an AST tree."""
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports[n.asname or n.name] = n.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for n in node.names:
                    # For 'from x import y', we map 'y' to 'x.y'
                    imports[n.asname or n.name] = f"{node.module}.{n.name}"
    return imports


def verify_function_calls(file_path, project_root):
    """
    Verifies that function calls to imported 'scripts' modules are correctly mapped
    to existing functions in those modules.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            tree = ast.parse(content)
    except Exception as e:
        return False, f"AST Parse Error: {e}"

    imports = get_imported_modules(tree)

    # We only care about imports that start with 'scripts.'
    script_imports = {alias: name for alias, name in imports.items() if name.startswith("scripts.")}

    # Also handle 'from scripts import xxx'
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "scripts":
            for n in node.names:
                script_imports[n.asname or n.name] = f"scripts.{n.name}"

    errors = []

    # Find all calls like 'module_alias.function_name()'
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                alias = node.func.value.id
                attr = node.func.attr

                if alias in script_imports:
                    full_name = script_imports[alias]
                    # Attempt to verify this attribute exists in the target script
                    # e.g., scripts.obs_controller -> scripts/obs_controller.py
                    module_parts = full_name.split(".")
                    if len(module_parts) >= 2:
                        target_script_name = module_parts[1]
                        target_script_path = project_root / "scripts" / f"{target_script_name}.py"

                        if target_script_path.exists():
                            # Check if the attribute exists in the target script (as a def or assignment)
                            if not check_attribute_in_script(target_script_path, attr):
                                errors.append(
                                    f"Call to '{alias}.{attr}' failed: '{attr}' not found in {target_script_path.name}"
                                )
                        else:
                            # Module not found in scripts/ folder
                            pass

    if errors:
        return False, "; ".join(errors)
    return True, None


def check_attribute_in_script(script_path, attr_name):
    """Statically checks if a script defines a specific attribute (function or variable)."""
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == attr_name:
                return True
            if isinstance(node, ast.AsyncFunctionDef) and node.name == attr_name:
                return True
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return True
        return False
    except Exception:
        return False


def main():
    # Setup paths
    current_file = Path(__file__).resolve()
    project_root = current_file.parents[2]
    scripts_dir = project_root / "scripts"

    if not scripts_dir.exists():
        print(f"Error: Scripts directory not found at {scripts_dir}")
        sys.exit(1)

    scripts = list(scripts_dir.glob("*.py"))
    if not scripts:
        print("No Python scripts found in scripts/ directory.")
        return

    print(f"--- Verifying {len(scripts)} automation scripts ---\n")

    all_ok = True
    for script in scripts:
        print(f"Verifying {script.name}:", end=" ")

        # 1. Syntax check
        syntax_ok, syntax_err = check_syntax(script)
        if not syntax_ok:
            print(f"FAIL\n  [Syntax Error] {syntax_err}")
            all_ok = False
            continue

        # 2. Import check (to catch missing dependencies)
        import_ok, import_err = verify_importable(script, project_root)
        if not import_ok:
            print(f"FAIL\n  [Import Error] {import_err}")
            all_ok = False
            continue

        # 3. Function mapping check
        mapping_ok, mapping_err = verify_function_calls(script, project_root)
        if not mapping_ok:
            print(f"FAIL\n  [Mapping Error] {mapping_err}")
            all_ok = False
            continue

        print("PASS")

    print("\n" + "=" * 40)
    if all_ok:
        print("RESULT: SUCCESS - All scripts verified.")
        sys.exit(0)
    else:
        print("RESULT: FAILURE - Some scripts have issues.")
        sys.exit(1)


if __name__ == "__main__":
    main()
