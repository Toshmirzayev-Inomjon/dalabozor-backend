"""AI endpoint va provider adapterlari (faqat mock HTTP bilan)."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.api.v1.ai import get_ai_service
from app.core.config import Settings
from app.core.deps import get_current_user
from app.main import app
from app.schemas.ai import ChatIn, ChatOut
from app.services.ai import AIService
from tests.conftest import API


def ai_settings(**overrides) -> Settings:
    values = {
        "debug": False,
        "scheduler_enabled": False,
        "groq_api_key": "test-groq-key",
        "groq_base_url": "https://api.groq.test/openai/v1",
        "groq_model": "test-model",
        "ai_request_timeout_seconds": 5,
        "ai_chat_max_output_tokens": 300,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


async def test_chat_uses_role_context_and_accepts_allowlisted_action():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.groq.test/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-groq-key"
        body = json.loads(await request.aread())
        assert body["model"] == "test-model"
        system_prompt = body["messages"][0]["content"]
        assert "Faol rol: farmer" in system_prompt
        assert "Joriy bo'lim: offers" in system_prompt
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "reply": "Yangi e'lon bo'limini ochaman.",
                                    "action": {
                                        "type": "navigate",
                                        "value": "new-offer",
                                        "requires_confirmation": False,
                                    },
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = AIService(ai_settings(), client)
        result = await service.chat(
            ChatIn(
                message="E'lon bermoqchiman",
                active_role="farmer",
                active_section="offers",
            ),
            user_roles=["farmer"],
            active_role="farmer",
            active_section="offers",
        )

    assert result.reply == "Yangi e'lon bo'limini ochaman."
    assert result.action is not None
    assert result.action.type == "navigate"
    assert result.action.value == "new-offer"
    assert result.action.requires_confirmation is True


@pytest.mark.parametrize("action_type", ["switch_role", "add_role", "remove_role"])
async def test_chat_filters_role_mutation_actions(action_type):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"reply":"Buni bajara olmayman.",'
                                f'"action":{{"type":"{action_type}","value":"restaurant",'
                                '"requires_confirmation":true}}'
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIService(ai_settings(), client).chat(
            ChatIn(message="Rolimni almashtir"),
            user_roles=["farmer"],
            active_role="farmer",
        )

    assert result.reply == "Buni bajara olmayman."
    assert result.action is None


async def test_chat_plain_text_fallback_and_no_real_http():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Savatingiz katalog bo'limida."}}]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIService(ai_settings(), client).chat(
            ChatIn(message="Savat qayerda?"),
            user_roles=["restaurant"],
            active_role="restaurant",
        )

    assert result == ChatOut(reply="Savatingiz katalog bo'limida.", action=None)


async def test_chat_empty_code_fence_uses_safe_fallback():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "```json\n\n```"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIService(ai_settings(), client).chat(
            ChatIn(message="Yordam bering"),
            user_roles=["farmer"],
            active_role="farmer",
        )

    assert result.action is None
    assert "qayta yozing" in result.reply


async def test_chat_neura_provider_calls_neura_api_and_returns_reply():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://neuraai.up.railway.app/api/chat"
        assert "Authorization" not in request.headers
        body = json.loads(await request.aread())
        assert body == {"message": "Salom"}
        return httpx.Response(
            200,
            json={
                "reply": "Salom, yordam bera olaman.",
                "source": "kb",
                "conversation_id": 1,
            },
        )

    settings = ai_settings(
        ai_provider="neura",
        groq_base_url="https://neuraai.up.railway.app",
        groq_api_key="",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIService(settings, client).chat(
            ChatIn(message="Salom"),
            user_roles=["farmer"],
            active_role="farmer",
        )

    assert result.reply == "Salom, yordam bera olaman."
    assert result.action is None


async def test_chat_neura_provider_plain_text_reply_ok():
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"reply": "Javob: katalog bo'limida topasiz."})

    settings = ai_settings(ai_provider="neura", groq_api_key="")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIService(settings, client).chat(
            ChatIn(message="Savat qayerda?"),
            user_roles=["restaurant"],
            active_role="restaurant",
        )

    assert result.reply == "Javob: katalog bo'limida topasiz."
    assert result.action is None


async def test_ai_status_neura_provider_available_without_key():
    settings = ai_settings(ai_provider="neura", groq_api_key="")
    assert AIService(settings).status() == {"chat_available": True}


class FakeAIService:
    def status(self):
        return {"chat_available": True}

    async def chat(self, payload, **_kwargs):
        return ChatOut(reply=f"Qabul qilindi: {payload.message}")


@pytest.fixture
def ai_dependency_overrides():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role_names=["farmer"]
    )
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_ai_service, None)


async def test_ai_status_requires_auth(client):
    response = await client.get(f"{API}/ai/status")
    # HTTPBearer FastAPI versiyasiga qarab 401 yoki 403 qaytaradi.
    assert response.status_code in {401, 403}


async def test_ai_endpoints_contract(client, ai_dependency_overrides):
    status_response = await client.get(f"{API}/ai/status")
    assert status_response.status_code == 200
    assert status_response.json() == {"chat_available": True}

    chat_response = await client.post(
        f"{API}/ai/chat",
        json={
            "message": "Yordam bering",
            "active_role": "farmer",
            "active_section": "overview",
        },
    )
    assert chat_response.status_code == 200
    assert chat_response.json() == {
        "reply": "Qabul qilindi: Yordam bering",
        "action": None,
    }


async def test_chat_rejects_section_from_another_role(client, ai_dependency_overrides):
    response = await client.post(
        f"{API}/ai/chat",
        json={
            "message": "Katalogni och",
            "active_role": "farmer",
            "active_section": "catalog",
        },
    )
    assert response.status_code == 400
