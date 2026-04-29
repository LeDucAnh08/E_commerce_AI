def main() -> None:
parser = argparse.ArgumentParser(description="Load data_user500.csv into Neo4j graph with Behavior nodes")
parser.add_argument("--data", type=str, default="data_user500.csv", help="Input CSV path") parser.add_argument("--uri", type=str, default="bolt://localhost:7687", help="Neo4j Bolt URI") parser.add_argument("--user", type=str, default="neo4j", help="Neo4j username") parser.add_argument("--password", type=str, default="password", help="Neo4j password") parser.add_argument("--batch-size", type=int, default=500, help="Batch size for insert") parser.add_argument(
"--reset", action="store_true",
help="Delete existing graph data before inserting",
)
