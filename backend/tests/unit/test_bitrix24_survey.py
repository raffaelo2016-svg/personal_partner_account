from typing import Any

from app.integrations.bitrix24.survey import REQUIRED_METHODS, Bitrix24Survey


class FakeClient:
    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if method == "method.get":
            return {"isExisting": True, "isAvailable": params["name"] != "sonet_group.create"}
        if method == "scope":
            return ["crm", "disk", "task"]
        return {"method": method}

    async def list_all(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        result_key: str | None = None,
        max_pages: int = 100,
    ) -> list[Any]:
        if method == "user.get":
            return [{"ID": "7", "NAME": "Нина", "EMAIL": "hidden@example.test", "PERSONAL_PHONE": "+7000"}]
        return []


async def test_survey_is_read_only_and_removes_user_contacts():
    survey = Bitrix24Survey(  # type: ignore[arg-type]
        FakeClient(), smart_process_entity_type_id=1070, deal_category_id=3
    )

    result = await survey.run()

    assert result["read_only"] is True
    assert result["oauth_refresh_verified"] is False
    assert set(result["method_availability"]) == set(REQUIRED_METHODS)
    assert result["method_availability"]["sonet_group.create"]["result"]["isAvailable"] is False
    assert result["users"]["result"] == [{"ID": "7", "NAME": "Нина"}]
