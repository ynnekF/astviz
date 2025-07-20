import argparse
import ast
import logging
import os
import sys

from graphviz import Digraph

logger = logging.getLogger(__name__)


class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.calls = set()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.calls.add(node.func.id)
        self.generic_visit(node)


def stop(message: str, code: int = 1):
    logger.error(f"Error: {message}")
    sys.exit(code)


def get_py_files(directory):
    files = []
    for root, _, filenames in os.walk(directory):
        for f in filenames:
            if f.endswith(".py"):
                files.append(os.path.join(root, f))
    return files


def get_fn_defs(tree):
    """Return a mapping of function names to their AST nodes."""
    return {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def call_graph(files, entrypoint):
    logger.info("Generating call graph for entrypoint '%s'", entrypoint)

    all_functions = {}  # func_name -> (AST node, filename)
    graph = {}
    visited = set()

    for filepath in files:
        with open(filepath, "r") as f:
            source = f.read()
        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            logger.error(f"Skipping {filepath} due to syntax error: {e}")
            continue

        functions = get_fn_defs(tree)
        logger.info(f"Found {len(functions)} functions in {filepath}")

        for func_name, node in functions.items():
            logger.info(f"\tf> {func_name}")
            all_functions[func_name] = (node, filepath)

    def visit_func(func_name):
        if func_name not in all_functions or func_name in visited:
            return
        
        visited.add(func_name)
        node, _ = all_functions[func_name]
        
        visitor = FunctionCallVisitor()
        visitor.visit(node)
        
        graph[func_name] = visitor.calls
        for callee in visitor.calls:
            visit_func(callee)

    visit_func(entrypoint)
    return graph


def render_graph(graph, output_file="graph", format="png"):
    logger.info("Rendering graph to %s.%s", output_file, format)

    if not graph:
        logger.warning("No function calls found to render.")
        return

    dot = Digraph()

    for caller, callees in graph.items():
        dot.node(caller)
        for callee in callees:
            dot.node(callee)
            dot.edge(caller, callee)

    dot.render(output_file, format=format, cleanup=True)
    logger.info(f"Graph saved as {output_file}.{format}")


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-s",
        "--source",
        help="Path to the Python source file/folder",
    )

    parser.add_argument(
        "-d",
        "--destination",
        help="Path to the output directory for the graph",
        default="graphs",
    )

    parser.add_argument(
        "-e",
        "--entrypoint",
        help="Name of the entrypoint function to analyze.",
        default="main",
    )

    parser.add_argument(
        "--version",
        dest="version",
        action="store_true",
        help="display version information",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        help="enable verbose output",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Manage command line arguments
    if args.version:
        import meta

        print(f"astviz version: {meta.__version__}")
        return

    # Set up logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    sources = args.source.split(",")
    logger.info("Starting analysis with sources: %s", sources)

    files = []
    for source in sources:
        if not os.path.exists(source):
            continue

        if os.path.isfile(source):
            files.append(source)
        else:
            files.extend(get_py_files(source))

    if not files:
        stop("No Python files found in the given sources.")

    graph = call_graph(files, args.entrypoint)
    render_graph(graph, output_file=os.path.join(args.destination, "call_graph"), format="png")


if __name__ == "__main__":
    main()
