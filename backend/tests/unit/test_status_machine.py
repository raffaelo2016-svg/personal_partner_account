"""Unit-тесты: STATUS_TRANSITIONS, STAGE_ORDER, _get_status_index — чистая логика без БД."""

import pytest

from app.models.enums import ClientStatus
from app.services.progress_service import LINEAR_STATUS_ORDER, STAGES, _get_status_index
from app.services.status_machine import STAGE_ORDER, STATUS_TRANSITIONS


class TestStatusTransitionsMap:
    """Проверка таблицы переходов: полнота, непротиворечивость."""

    def test_all_statuses_have_transitions(self):
        """Каждый статус из enum есть в таблице."""
        for status in ClientStatus:
            assert status in STATUS_TRANSITIONS, f"{status} missing from STATUS_TRANSITIONS"

    def test_all_targets_are_valid_statuses(self):
        """Все целевые статусы — валидные enum-значения."""
        for status, targets in STATUS_TRANSITIONS.items():
            for t in targets:
                assert isinstance(t, ClientStatus), f"Invalid target {t} from {status}"

    def test_no_self_transitions(self):
        """Нельзя перейти в текущий статус."""
        for status, targets in STATUS_TRANSITIONS.items():
            assert status not in targets, f"{status} can transition to itself"

    def test_each_status_has_at_least_one_target(self):
        for status, targets in STATUS_TRANSITIONS.items():
            assert len(targets) >= 1, f"{status} has no transitions"

    def test_realization_can_go_back_to_auction(self):
        assert ClientStatus.AUCTION in STATUS_TRANSITIONS[ClientStatus.REALIZATION]

    def test_realization_can_be_completed(self):
        assert ClientStatus.COMPLETED in STATUS_TRANSITIONS[ClientStatus.REALIZATION]

    def test_completed_can_reopen_realization(self):
        assert STATUS_TRANSITIONS[ClientStatus.COMPLETED] == [ClientStatus.REALIZATION]

    def test_documents_collection_only_forward(self):
        targets = STATUS_TRANSITIONS[ClientStatus.DOCUMENTS_COLLECTION]
        assert targets == [ClientStatus.DOCUMENTS_FORMATION]

    @pytest.mark.parametrize(
        "from_s,to_s",
        [
            (ClientStatus.DOCUMENTS_COLLECTION, ClientStatus.DOCUMENTS_FORMATION),
            (ClientStatus.DOCUMENTS_FORMATION, ClientStatus.SENT_TO_COURT),
            (ClientStatus.DOCUMENTS_FORMATION, ClientStatus.DOCUMENTS_COLLECTION),
            (ClientStatus.SENT_TO_COURT, ClientStatus.DOCUMENTS_DECISION),
            (ClientStatus.DOCUMENTS_DECISION, ClientStatus.WAITING_HEARING),
            (ClientStatus.WAITING_HEARING, ClientStatus.RESTRUCTURING),
            (ClientStatus.RESTRUCTURING, ClientStatus.AUCTION),
            (ClientStatus.AUCTION, ClientStatus.REALIZATION),
            (ClientStatus.REALIZATION, ClientStatus.AUCTION),
            (ClientStatus.REALIZATION, ClientStatus.COMPLETED),
            (ClientStatus.COMPLETED, ClientStatus.REALIZATION),
        ],
    )
    def test_valid_transition_exists(self, from_s, to_s):
        assert to_s in STATUS_TRANSITIONS[from_s]

    @pytest.mark.parametrize(
        "from_s,to_s",
        [
            (ClientStatus.DOCUMENTS_COLLECTION, ClientStatus.SENT_TO_COURT),
            (ClientStatus.DOCUMENTS_COLLECTION, ClientStatus.REALIZATION),
            (ClientStatus.DOCUMENTS_FORMATION, ClientStatus.WAITING_HEARING),
            (ClientStatus.SENT_TO_COURT, ClientStatus.AUCTION),
            (ClientStatus.REALIZATION, ClientStatus.DOCUMENTS_COLLECTION),
            (ClientStatus.COMPLETED, ClientStatus.DOCUMENTS_COLLECTION),
            (ClientStatus.COMPLETED, ClientStatus.AUCTION),
        ],
    )
    def test_invalid_transition_not_exists(self, from_s, to_s):
        assert to_s not in STATUS_TRANSITIONS[from_s]

    def test_forward_path_exists(self):
        """Можно пройти от первого до последнего статуса."""
        current = ClientStatus.DOCUMENTS_COLLECTION
        target = ClientStatus.COMPLETED
        visited = set()
        for _ in range(20):
            if current == target:
                break
            visited.add(current)
            forward = [t for t in STATUS_TRANSITIONS[current] if t not in visited]
            assert forward, f"Dead end at {current}"
            current = forward[0]
        assert current == target


class TestStageOrder:
    """Проверка STAGE_ORDER и LINEAR_STATUS_ORDER."""

    def test_stage_order_has_all_statuses(self):
        assert set(STAGE_ORDER) == set(ClientStatus)

    def test_linear_order_has_all_statuses(self):
        assert set(LINEAR_STATUS_ORDER) == set(ClientStatus)

    def test_stage_order_no_duplicates(self):
        assert len(STAGE_ORDER) == len(set(STAGE_ORDER))

    def test_stages_match_linear_order(self):
        stage_keys = [s["status_key"] for s in STAGES]
        # «Завершено» — терминальный статус, а не отдельный этап прогресса.
        assert stage_keys == LINEAR_STATUS_ORDER[:-1]
        assert LINEAR_STATUS_ORDER[-1] == ClientStatus.COMPLETED

    def test_stages_have_sequential_ids(self):
        ids = [s["id"] for s in STAGES]
        assert ids == list(range(1, len(STAGES) + 1))

    def test_stages_all_have_titles(self):
        for s in STAGES:
            assert isinstance(s["title"], str)
            assert len(s["title"]) > 0

    def test_completed_is_after_all_progress_stages(self):
        """Для статуса «Завершено» все этапы считаются пройденными."""
        assert _get_status_index("completed") == len(STAGES)


class TestGetStatusIndex:
    """_get_status_index — pure function."""

    def test_first_status(self):
        assert _get_status_index("documents_collection") == 0

    def test_last_status(self):
        assert _get_status_index("completed") == 8
        assert _get_status_index("realization") == 7

    def test_middle_status(self):
        assert _get_status_index("waiting_hearing") == 4

    def test_invalid_status(self):
        assert _get_status_index("nonexistent") == -1

    def test_empty_string(self):
        assert _get_status_index("") == -1

    def test_monotonic(self):
        indices = [_get_status_index(s.value) for s in LINEAR_STATUS_ORDER]
        assert indices == list(range(9))


class TestClientStatusEnum:
    """Enum corner cases."""

    def test_all_values_lowercase(self):
        for s in ClientStatus:
            assert s.value == s.value.lower()

    def test_from_string(self):
        assert ClientStatus("documents_collection") == ClientStatus.DOCUMENTS_COLLECTION

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            ClientStatus("invalid")

    def test_count(self):
        assert len(ClientStatus) == 9

    def test_client_type_count(self):
        from app.models.enums import ClientType

        assert len(ClientType) == 2
        assert set(ClientType) == {ClientType.BEFORE_COURT, ClientType.IN_COURT}
