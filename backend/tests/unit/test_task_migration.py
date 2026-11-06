"""Migration repeatability after a targeted task-only schema rollout."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def setup_db():
    yield


@pytest.fixture
def task_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/a4e8f9c21d73_add_partner_tasks_and_deadlines.py"
    spec = importlib.util.spec_from_file_location("partner_task_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inspector(*, all_columns=False, task_columns=False):
    inspector = Mock()
    columns = [{"name": "client_id", "nullable": all_columns}, {"name": "due_date", "nullable": all_columns}]
    if task_columns or all_columns:
        columns += [{"name": name, "nullable": True} for name in ("partner_id", "due_at")]
    if all_columns:
        columns += [{"name": name, "nullable": False} for name in ("bitrix_imported", "bitrix_published")]
    inspector.get_columns.return_value = columns
    inspector.get_foreign_keys.return_value = (
        [{"constrained_columns": ["partner_id"], "referred_table": "partners", "referred_columns": ["id"]}]
        if task_columns or all_columns else []
    )
    inspector.get_indexes.return_value = (
        [{"column_names": [name], "unique": False} for name in ("partner_id", "due_at")]
        if task_columns or all_columns else []
    )
    return inspector


@pytest.mark.parametrize("existing", ["empty", "partial", "complete"])
def test_online_upgrade_preserves_existing_additive_schema(task_migration, existing):
    operations = Mock()
    inspector = _inspector(all_columns=existing == "complete", task_columns=existing == "partial")
    with (
        patch.object(task_migration, "op", operations),
        patch.object(task_migration.context, "is_offline_mode", return_value=False),
        patch.object(task_migration.sa, "inspect", return_value=inspector),
    ):
        task_migration.upgrade()
    added = {call.args[1].name for call in operations.add_column.call_args_list}
    assert added == {
        "empty": {"partner_id", "due_at", "bitrix_imported", "bitrix_published"},
        "partial": {"bitrix_imported", "bitrix_published"},
        "complete": set(),
    }[existing]
    if existing != "empty":
        operations.create_foreign_key.assert_not_called()
        operations.create_index.assert_not_called()
    if existing == "complete":
        operations.alter_column.assert_not_called()
    queries = [call.args[0] for call in operations.execute.call_args_list]
    assert any("tasks.partner_id IS NULL" in query for query in queries)
    # A future ordinary upgrade must preserve live publication/import decisions.
    assert any("SET bitrix_imported" in query for query in queries) == (existing != "complete")
    assert not any("SET bitrix_published" in query for query in queries)


def test_offline_upgrade_emits_all_schema_without_database_inspection(task_migration):
    operations = Mock()
    with (
        patch.object(task_migration, "op", operations),
        patch.object(task_migration.context, "is_offline_mode", return_value=True),
        patch.object(task_migration.sa, "inspect") as inspect,
    ):
        task_migration.upgrade()
    inspect.assert_not_called()
    operations.get_bind.assert_not_called()
    assert operations.add_column.call_count == 4
    assert operations.create_foreign_key.call_count == 1
    assert operations.create_index.call_count == 2
    assert operations.alter_column.call_count == 2
