import json
import sqlite3
from typing import Any, Dict, List, Tuple, Union


def _get_connection(db: Union[str, sqlite3.Connection]):
    if isinstance(db, sqlite3.Connection):
        return db
    return sqlite3.connect(db)


def build_dag(db: Union[str, sqlite3.Connection]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Build a causal DAG from the governance operation log.

    Returns (nodes, edges).
    nodes: mapping event_id -> node attributes
    edges: list of {src: parent_event_id, dst: event_id, attrs: {...}}
    """
    conn = _get_connection(db)
    cur = conn.cursor()

    # Ensure table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='governance_operation_log'")
    if not cur.fetchone():
        return {}, []

    cols = [
        'event_id',
        'parent_event_id',
        'root_event_id',
        'governance_state',
        'operation',
        'operation_type',
        'replay_epoch',
        'operation_hash',
        'timestamp_ns',
        'interception_stage',
        'operation_sequence',
    ]

    # Build a SELECT that tolerates missing columns by using COALESCE
    select_cols = []
    for c in cols:
        select_cols.append(f"COALESCE({c}, '') AS {c}")

    q = f"SELECT {', '.join(select_cols)} FROM governance_operation_log ORDER BY timestamp_ns, operation_sequence"
    cur.execute(q)

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    for row in cur.fetchall():
        rowd = dict(zip([c.split(' AS ')[-1] for c in select_cols], row))
        eid = rowd.get('event_id') or None
        if not eid:
            continue
        node = {
            'event_id': eid,
            'parent_event_id': rowd.get('parent_event_id') or None,
            'root_event_id': rowd.get('root_event_id') or None,
            'governance_state': rowd.get('governance_state') or None,
            'operation': rowd.get('operation') or None,
            'operation_type': rowd.get('operation_type') or None,
            'replay_epoch': int(rowd.get('replay_epoch') or 0) if rowd.get('replay_epoch') != '' else None,
            'operation_hash': rowd.get('operation_hash') or None,
            'timestamp_ns': int(rowd.get('timestamp_ns') or 0) if rowd.get('timestamp_ns') != '' else None,
            'interception_stage': rowd.get('interception_stage') or None,
            'operation_sequence': int(rowd.get('operation_sequence') or 0) if rowd.get('operation_sequence') != '' else None,
        }
        nodes[eid] = node
        parent = node['parent_event_id']
        if parent:
            edges.append({'src': parent, 'dst': eid, 'attrs': {'interception_stage': node['interception_stage'], 'causal_transition': 'parent'}})

    try:
        if isinstance(db, str):
            conn.close()
    except Exception:
        pass

    return nodes, edges


def export_json(nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]], out_path: str):
    payload = {'nodes': list(nodes.values()), 'edges': edges}
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def export_mermaid(nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]], out_path: str):
    lines = ["graph TD"]
    for n in nodes.values():
        label = n.get('operation_type') or n.get('operation') or n['event_id'][:8]
        lines.append(f"    {n['event_id'][:8]}[\"{label}\"]")
    for e in edges:
        src = e['src'][:8]
        dst = e['dst'][:8]
        lines.append(f"    {src} -->|{e['attrs'].get('interception_stage') or ''}| {dst}")

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def export_graphviz(nodes: Dict[str, Dict[str, Any]], edges: List[Dict[str, Any]], out_path: str):
    lines = ["digraph governance_dag {", "  rankdir=LR;"]
    for n in nodes.values():
        label = n.get('operation_type') or n.get('operation') or n['event_id'][:8]
        lines.append(f'  "{n["event_id"]}" [label="{label}"];')
    for e in edges:
        lines.append(f'  "{e["src"]}" -> "{e["dst"]}" [label="{e["attrs"].get("interception_stage") or ""}"];')
    lines.append('}')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
