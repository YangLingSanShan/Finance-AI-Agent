"""python -m app.storage.migrate [--import-sqlite PATH]. Never prints credentials."""
import argparse
from pathlib import Path
from app.storage.conversations import get_conversation_store, ConversationStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-sqlite', type=Path)
    args = parser.parse_args()
    target = get_conversation_store()
    if args.import_sqlite:
        if not args.import_sqlite.is_file():
            raise SystemExit('源 SQLite 文件不存在')
        # Work on a snapshot so reading an old schema never modifies the source.
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            snapshot = Path(folder) / 'history.sqlite3'
            with sqlite3.connect(f'file:{args.import_sqlite.resolve()}?mode=ro', uri=True) as source:
                with sqlite3.connect(snapshot) as dest:
                    source.backup(dest)
            store = ConversationStore(snapshot)
            count = target.import_history(store)
            store.engine.dispose()
        print(f'导入 {count} 个会话；已存在且完全相同的记录跳过')
    else:
        print('业务数据库 schema v1 已就绪')
    target.engine.dispose()


if __name__ == '__main__':
    main()
