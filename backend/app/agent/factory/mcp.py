# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
import asyncio
import logging
import uuid

from camel.models import ModelFactory
from camel.toolkits import ToolkitMessageIntegration
from camel.types import ModelPlatformType

from app.agent.factory.remote_sub_agent import (
    attach_remote_sub_agent_if_enabled,
    remote_sub_agent_enabled,
)
from app.agent.listen_chat_agent import ListenChatAgent, logger
from app.agent.prompt import MCP_SYS_PROMPT
from app.agent.toolkit.human_toolkit import HumanToolkit
from app.agent.toolkit.mcp_search_toolkit import McpSearchToolkit
from app.agent.tools import get_mcp_tools
from app.model.chat import Chat
from app.model.model_platform import (
    patch_azure_cloud_config,
    patch_bedrock_config,
)
from app.service.mcp_config import merge_installed_mcp
from app.service.task import ActionCreateAgentData, Agents, get_task_lock
from app.utils.file_utils import get_working_directory


async def mcp_agent(options: Chat):
    working_directory = get_working_directory(options)
    # Merge the request's servers with the Brain's local config so the MCP
    # agent sees the same connectors as the single agent (single source of
    # truth lives in ~/.eigent/mcp.json).
    installed_mcp = merge_installed_mcp(options.installed_mcp)
    mcp_servers = installed_mcp["mcpServers"]
    logger.info(
        f"Creating MCP agent for project: {options.project_id} "
        f"with {len(mcp_servers)} MCP servers"
    )
    message_integration = None
    if remote_sub_agent_enabled(options, working_directory):
        message_integration = ToolkitMessageIntegration(
            message_handler=HumanToolkit(
                options.project_id, Agents.mcp_agent
            ).send_message_to_user
        )
    tools = [
        *McpSearchToolkit(options.project_id).get_tools(),
    ]
    tool_names = [McpSearchToolkit.toolkit_name()]
    if len(mcp_servers) > 0:
        try:
            mcp_tools = await get_mcp_tools(installed_mcp)
            logger.info(
                f"Retrieved {len(mcp_tools)} MCP tools "
                f"for task {options.project_id}"
            )
            if mcp_tools:
                mcp_tool_names = [
                    (
                        tool.get_function_name()
                        if hasattr(tool, "get_function_name")
                        else str(tool)
                    )
                    for tool in mcp_tools
                ]
                logger.debug(f"MCP tools: {mcp_tool_names}")
                tool_names.extend(mcp_tool_names)
            tools = [*tools, *mcp_tools]
        except Exception as e:
            logger.debug(repr(e))

    task_lock = get_task_lock(options.project_id)
    agent_id = str(uuid.uuid4())
    logger.info(
        f"Creating MCP agent: {Agents.mcp_agent} with id: "
        f"{agent_id} for task: {options.project_id}"
    )
    asyncio.create_task(
        task_lock.put_queue(
            ActionCreateAgentData(
                data={
                    "agent_name": Agents.mcp_agent,
                    "agent_id": agent_id,
                    "tools": list(mcp_servers.keys()),
                }
            )
        )
    )
    extra_params = {
        k: v
        for k, v in (options.extra_params or {}).items()
        if k not in ["model_platform", "model_type", "api_key", "url"]
    }
    api_url = options.api_url
    if options.model_platform == "aws-bedrock-converse":
        api_url, extra_params = patch_bedrock_config(
            api_url, extra_params, is_cloud=options.is_cloud()
        )
    if options.model_platform == "azure" and options.is_cloud():
        extra_params = patch_azure_cloud_config(extra_params)

    system_message = attach_remote_sub_agent_if_enabled(
        options=options,
        agent_name=Agents.mcp_agent,
        working_directory=working_directory,
        tools=tools,
        tool_names=tool_names,
        system_message=MCP_SYS_PROMPT,
        local_tool_description="local MCP or search tools",
        message_integration=message_integration,
    )

    # Build model_config_dict with prompt caching
    model_config_dict = {}
    if options.is_cloud():
        model_config_dict["user"] = str(options.project_id)
    try:
        platform_enum = ModelPlatformType(options.model_platform.lower())
        if platform_enum in {
            ModelPlatformType.ANTHROPIC,
            ModelPlatformType.AWS_BEDROCK_CONVERSE,
        }:
            model_config_dict.setdefault("cache_control", "5m")
        elif platform_enum == ModelPlatformType.OPENAI:
            model_config_dict.setdefault(
                "prompt_cache_key", str(options.project_id)
            )
    except (ValueError, AttributeError):
        logging.error(
            f"Invalid model platform: {options.model_platform}",
            exc_info=True,
        )

    return ListenChatAgent(
        options.project_id,
        Agents.mcp_agent,
        system_message=system_message,
        model=ModelFactory.create(
            model_platform=options.model_platform,
            model_type=options.model_type,
            api_key=options.api_key,
            url=api_url,
            model_config_dict=model_config_dict or None,
            timeout=600,  # 10 minutes
            **extra_params,
        ),
        # output_language=options.language,
        tools=tools,
        agent_id=agent_id,
    )
