from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class AutoGenPlan:
    summary: str
    role_briefs: dict[str, str]
    transcript: list[dict[str, str]]


class AutoGenWebsiteWorkflowAgent:
    """
    基于 AutoGen 的多 Agent 协作规划器。
    - 负责在执行前先让 PM/前端/后端/测试进行简短协作对话
    - 输出每个角色的执行简报，供现有 runtime 落地实现
    """

    ROLE_MAP = {
        "产品经理Agent": "product_manager",
        "前端Agent": "frontend",
        "后端Agent": "backend",
        "测试Agent": "test",
    }

    def __init__(self) -> None:
        self._autogen = self._try_import_autogen()

    @staticmethod
    def _try_import_autogen() -> Any | None:
        try:
            import autogen  # type: ignore

            return autogen
        except Exception:
            return None

    @property
    def available(self) -> bool:
        return self._autogen is not None and bool(os.environ.get("DASHSCOPE_API_KEY"))

    def plan(self, project_id: str, user_goal: str) -> AutoGenPlan | None:
        if not self.available:
            return None

        autogen = self._autogen
        llm_config = {
            "config_list": [
                {
                    "model": "qwen-plus",
                    "api_key": os.environ.get("DASHSCOPE_API_KEY"),
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                }
            ],
            "temperature": 0.2,
            "timeout": 120,
        }

        planner = autogen.AssistantAgent(
            name="Orchestrator",
            llm_config=llm_config,
            system_message=(
                "你是网站一键生成工作流的调度者。你要组织 PM、前端、后端、测试协作，"
                "产出可执行方案，并给出每个角色的独立执行简报。"
                "若用户提供参考网址，需先抽象其信息架构和交互模式，再安排实现。"
                "最终方案必须包含可直接运行的网站交付与启动方式。"
            ),
        )
        pm = autogen.AssistantAgent(
            name="产品经理Agent",
            llm_config=llm_config,
            system_message=(
                "你负责输出结构化需求、页面地图、接口契约草稿和验收标准。"
                "回答应简洁、可执行。"
                "PRD 必须覆盖页面入口、核心流程、API 契约、验收标准与启动说明。"
            ),
        )
        frontend = autogen.AssistantAgent(
            name="前端Agent",
            llm_config=llm_config,
            system_message=(
                "你负责前端页面与交互落地方案。重点说明页面入口、交互流程、数据绑定、风险点。"
                "交付中要包含可访问网址与前端启动命令。"
            ),
        )
        backend = autogen.AssistantAgent(
            name="后端Agent",
            llm_config=llm_config,
            system_message=(
                "你负责后端 API 与数据层落地方案。重点说明接口、校验、错误处理、自测建议。"
                "交付中要包含 API 基础地址与后端启动命令。"
            ),
        )
        tester = autogen.AssistantAgent(
            name="测试Agent",
            llm_config=llm_config,
            system_message=(
                "你负责测试计划与验收策略。重点说明关键测试点、边界条件、回归风险。"
                "必须给出可执行验收结论，并验证启动后关键链路可访问。"
            ),
        )
        user_proxy = autogen.UserProxyAgent(
            name="WorkflowUser",
            human_input_mode="NEVER",
            code_execution_config=False,
        )

        groupchat = autogen.GroupChat(
            agents=[user_proxy, planner, pm, frontend, backend, tester],
            messages=[],
            max_round=10,
            speaker_selection_method="round_robin",
        )
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)
        user_proxy.initiate_chat(
            manager,
            message=(
                f"项目ID：{project_id}\n"
                f"用户目标：{user_goal}\n\n"
                "请先简短讨论再收敛。最后由 Orchestrator 输出 JSON，格式如下：\n"
                '{"summary":"...","role_briefs":{"product_manager":"...","frontend":"...","backend":"...","test":"..."}}'
            ),
        )

        transcript = self._normalize_transcript(groupchat.messages)
        parsed = self._extract_plan(transcript)
        return AutoGenPlan(
            summary=parsed.get("summary", "AutoGen 已完成协作规划。"),
            role_briefs=parsed.get("role_briefs", {}),
            transcript=transcript,
        )

    def _normalize_transcript(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in messages:
            name = str(item.get("name") or item.get("role") or "unknown")
            content = item.get("content")
            if content is None:
                continue
            normalized.append({"name": name, "content": str(content).strip()})
        return normalized

    def _extract_plan(self, transcript: list[dict[str, str]]) -> dict[str, Any]:
        for message in reversed(transcript):
            content = message.get("content", "").strip()
            if not content:
                continue
            payload = self._safe_json(content)
            if payload and isinstance(payload, dict) and "role_briefs" in payload:
                role_briefs = payload.get("role_briefs", {})
                if isinstance(role_briefs, dict):
                    payload["role_briefs"] = self._normalize_role_briefs(role_briefs)
                return payload
        return {"summary": "AutoGen 协作完成，但未返回标准 JSON，已回退到默认角色简报。", "role_briefs": {}}

    def _normalize_role_briefs(self, role_briefs: dict[str, Any]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in role_briefs.items():
            role_key = self.ROLE_MAP.get(str(key), str(key))
            normalized[role_key] = str(value)
        return normalized

    def _safe_json(self, content: str) -> dict[str, Any] | None:
        raw = content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:].strip()
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None


__all__ = ["AutoGenPlan", "AutoGenWebsiteWorkflowAgent"]
